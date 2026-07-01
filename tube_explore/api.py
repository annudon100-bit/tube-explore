import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from tube_explore import config, db, ytdlp
from tube_explore.models import (
    ConversionPreset,
    ConversionPresetCreate,
    ConversionPresetUpdate,
    Profile,
    ProfileCreate,
    ProfileUpdate,
    SettingsDict,
    TaskInfo,
)
from tube_explore.schemas import (
    ConversionPresetCreateRequest,
    ConversionPresetResponse,
    ConversionPresetUpdateRequest,
    DownloadPlaylistRequest,
    DownloadVideoRequest,
    HealthResponse,
    MetadataResponse,
    OkResponse,
    OutboxEntry,
    PlaylistEntry,
    PlaylistResponse,
    ProfileCreateRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    SearchResponse,
    SearchResult,
    SettingsResponse,
    SettingsUpdateRequest,
    TaskResponse,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Tube Explore API",
    description="Media download and search backend. Download videos, fetch metadata, browse playlists, and manage download profiles via a clean REST API.",
    summary="Media downloader REST API",
    version="1.0.0",
    terms_of_service="https://github.com/anomalyco/tube-explore",
    contact={
        "name": "Tube Explore",
        "url": "https://github.com/anomalyco/tube-explore",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {"url": "http://localhost:8000", "description": "Local development"},
    ],
    lifespan=lifespan,
    docs_url=None,
    redoc_url="/docs",
    openapi_tags=[
        {
            "name": "Search",
            "description": "Search for media content by query string.",
        },
        {
            "name": "Metadata",
            "description": "Retrieve detailed metadata for a specific media URL.",
        },
        {
            "name": "Playlists",
            "description": "Browse and list entries in a playlist.",
        },
        {
            "name": "Downloads",
            "description": "Start background download tasks for videos or playlists.",
        },
        {
            "name": "Tasks",
            "description": "Monitor and list background download task status.",
        },
        {
            "name": "Profiles",
            "description": "CRUD management of download profiles (quality, format, directory settings).",
        },
        {
            "name": "Settings",
            "description": "Global download settings (rate limit, temp directory, retries, timeout).",
        },
        {
            "name": "Health",
            "description": "Service health check.",
        },
        {
            "name": "Outbox",
            "description": "List and manage files in the outbox — completed downloads that failed post-processing (e.g. missing ffmpeg).",
        },
        {
            "name": "Conversion Presets",
            "description": "Manage conversion presets — predefined output format configurations (codec, container, resolution, bitrate).",
        },
    ],
)


# ── Task store ───────────────────────────────────────────────
_tasks: dict[str, TaskInfo] = {}
_lock = threading.Lock()


def _create_task(task_type: str, url: str, params: dict[str, object]) -> str:
    tid = str(uuid.uuid4())
    task = TaskInfo(
        id=tid,
        type=task_type,
        url=url,
        params=params,
        status="pending",
        created_at=datetime.now(UTC),
        error=None,
    )
    with _lock:
        _tasks[tid] = task
    return tid


def _update_task(tid: str, **kwargs):
    with _lock:
        if tid in _tasks:
            _tasks[tid] = _tasks[tid].model_copy(update=kwargs)


def _run_in_background(tid: str, fn, *args, **kwargs):
    def wrapper():
        _update_task(tid, status="running")
        try:
            result = fn(*args, **kwargs)
            if not result:
                _update_task(tid, status="completed")
                return
            outbox = result.get("outbox")
            converted = result.get("converted")
            if outbox:
                _update_task(tid, status="completed", error=f"Files routed to outbox: {outbox}")
            elif converted:
                _update_task(tid, status="completed", error=f"Converted to: {converted}")
            else:
                _update_task(tid, status="completed")
        except Exception as e:
            _update_task(tid, status="failed", error=str(e))

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()


# ── Helpers ──────────────────────────────────────────────────


def _resolve_profile(profile_name: str | None, body_overrides) -> Profile:
    if profile_name:
        p = db.get_profile_by_name(profile_name)
        if not p:
            raise HTTPException(404, f"Profile '{profile_name}' not found")
        merged = ProfileCreate(**p.model_dump())
    else:
        merged = ProfileCreate(name="_adhoc")

    for attr in ProfileCreate.model_fields:
        val = getattr(body_overrides, attr, None)
        if val is not None:
            setattr(merged, attr, val)

    now = datetime.now(UTC)
    return Profile(id=0, created_at=now, updated_at=now, **merged.model_dump())


def _resolve_convert_preset(body) -> ConversionPreset | None:
    preset_name = getattr(body, "convert_preset", None)
    if not preset_name:
        return None
    preset = db.get_preset_by_name(preset_name)
    if not preset:
        raise HTTPException(404, f"Conversion preset '{preset_name}' not found")
    return preset


# ── Search / Metadata / Playlist ─────────────────────────────


@app.get("/api/search", response_model=SearchResponse, summary="Search media", description="Search for media content by query string. Returns a ranked list of matching results with ID, title, duration, and channel info.", tags=["Search"])
def search(q: str = Query(..., description="Search query string"), limit: int = Query(10, ge=1, le=50, description="Maximum number of results (1–50)")):
    try:
        results = ytdlp.search_videos(q, limit)
        return SearchResponse(query=q, count=len(results), results=[SearchResult(**r) for r in results])
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/metadata", response_model=MetadataResponse, summary="Get media metadata", description="Fetch full metadata for a given media URL, including available formats, duration, resolution, and thumbnails.", tags=["Metadata"])
def metadata(url: str = Query(..., description="Media URL to inspect")):
    try:
        return ytdlp.get_metadata(url)
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/playlist", response_model=PlaylistResponse, summary="Get playlist info", description="Fetch all entries in a playlist URL, including per-video duration, position, title, and thumbnails.", tags=["Playlists"])
def playlist(url: str = Query(..., description="Playlist URL")):
    try:
        entries = ytdlp.get_playlist_info(url)
        total_dur = sum(e["duration"] or 0 for e in entries)
        return PlaylistResponse(url=url, count=len(entries), total_duration=total_dur, entries=[PlaylistEntry(**e) for e in entries])
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e


# ── Download ─────────────────────────────────────────────────


def _make_settings(raw: dict[str, str]) -> SettingsDict:
    return SettingsDict(
        rate_limit=raw.get("rate_limit", ""),
        temp_directory=raw.get("temp_directory", ""),
        retry_count=int(raw.get("retry_count", "3")),
        socket_timeout=int(raw.get("socket_timeout", "30")),
    )


@app.post("/api/download/video", status_code=202, summary="Download video", description="Start a background task to download a single video. Accepts profile name or per-request overrides for quality, format, directory, audio-only mode, and a conversion preset. Returns a task ID for status polling.", tags=["Downloads"])
def download_video(body: DownloadVideoRequest):
    gs = _make_settings(db.get_all_settings())
    profile = _resolve_profile(body.profile, body)
    conversion_preset = _resolve_convert_preset(body)

    out = body.output_dir or profile.download_directory or gs.temp_directory or os.getcwd()

    tid = _create_task("video", body.url, body.model_dump(by_alias=True))
    _run_in_background(
        tid, ytdlp.download_video, body.url, output_dir=out, profile=profile, settings=gs, audio_only=body.audio_only, conversion_preset=conversion_preset
    )
    return {"taskId": tid, "status": "pending"}


@app.post("/api/download/playlist", status_code=202, summary="Download playlist", description="Start a background task to download all videos in a playlist. Supports optional index range filtering, audio-only mode, and a conversion preset. Returns a task ID for status polling.", tags=["Downloads"])
def download_playlist(body: DownloadPlaylistRequest):
    gs = _make_settings(db.get_all_settings())
    profile = _resolve_profile(body.profile, body)
    conversion_preset = _resolve_convert_preset(body)

    out = body.output_dir or profile.download_directory or gs.temp_directory or os.getcwd()

    tid = _create_task("playlist", body.url, body.model_dump(by_alias=True))
    _run_in_background(
        tid,
        ytdlp.download_playlist,
        body.url,
        output_dir=out,
        profile=profile,
        settings=gs,
        video_range=body.range,
        audio_only=body.audio_only,
        conversion_preset=conversion_preset,
    )
    return {"taskId": tid, "status": "pending"}


# ── Tasks ────────────────────────────────────────────────────


@app.get("/api/tasks/{task_id}", response_model=TaskResponse, summary="Get task status", description="Poll the status of a background download task by its ID. Returns the current status (pending/running/completed/failed), type, URL, timestamps, and error if any.", tags=["Tasks"])
def get_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@app.get("/api/tasks", response_model=list[TaskResponse], summary="List tasks", description="List all background download tasks. Sorted by creation time (newest first). Includes status, type, URL, and error info for each task.", tags=["Tasks"])
def list_tasks():
    with _lock:
        return list(_tasks.values())


# ── Profiles ─────────────────────────────────────────────────


@app.get("/api/profiles", response_model=list[ProfileResponse], summary="List profiles", description="List all saved download profiles. Each profile bundles quality mode, format string, download directory, and audio-only flag.", tags=["Profiles"])
def list_profiles():
    return db.list_profiles()


@app.post("/api/profiles", response_model=ProfileResponse, status_code=201, summary="Create profile", description="Create a new download profile. Name must be unique. Quality mode can be `best`, `least`, `at_most`, or `at_least` (latter two require a pixel height value).", tags=["Profiles"])
def create_profile(body: ProfileCreateRequest):
    existing = db.get_profile_by_name(body.name)
    if existing:
        raise HTTPException(409, f"Profile '{body.name}' already exists")
    p = db.create_profile(ProfileCreate(**body.model_dump()))
    return p


@app.get("/api/profiles/{profile_id}", response_model=ProfileResponse, summary="Get profile", description="Retrieve a single download profile by its ID.", tags=["Profiles"])
def get_profile(profile_id: int):
    p = db.get_profile(profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    return p


@app.put("/api/profiles/{profile_id}", response_model=ProfileResponse, summary="Update profile", description="Update an existing download profile. Only provided fields are changed; omitted fields keep their current values.", tags=["Profiles"])
def update_profile(profile_id: int, body: ProfileUpdateRequest):
    existing = db.get_profile(profile_id)
    if not existing:
        raise HTTPException(404, "Profile not found")
    data = body.model_dump(exclude_none=True)
    if not data:
        return existing
    p = db.update_profile(profile_id, ProfileUpdate(**data))
    return p


@app.delete("/api/profiles/{profile_id}", summary="Delete profile", description="Delete a download profile by its ID. Returns `{\"ok\": true}` on success.", tags=["Profiles"])
def delete_profile(profile_id: int):
    existing = db.get_profile(profile_id)
    if not existing:
        raise HTTPException(404, "Profile not found")
    db.delete_profile(profile_id)
    return {"ok": True}


# ── Global settings ──────────────────────────────────────────


@app.get("/api/settings", response_model=SettingsResponse, summary="Get settings", description="Retrieve all global download settings: rate limit, temp directory, retry count, and socket timeout.", tags=["Settings"])
def get_settings():
    raw = db.get_all_settings()
    return SettingsResponse(**raw)


@app.put("/api/settings", response_model=SettingsResponse, summary="Update settings", description="Update global download settings. Only provided fields are changed; omitted fields keep their current values.", tags=["Settings"])
def update_settings(body: SettingsUpdateRequest):
    data = {k: str(v) for k, v in body.model_dump(exclude_none=True).items()}
    if data:
        db.set_settings(data)
    return get_settings()


# ── Health ───────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse, summary="Health check", description="Returns service health status and whether ffmpeg is available for audio/video merging.", tags=["Health"])
def health():
    return HealthResponse(status="ok", has_ffmpeg=ytdlp.HAS_FFMPEG)


# ── Outbox ────────────────────────────────────────────────────


def _list_outbox() -> list[OutboxEntry]:
    outbox_dir = Path(config.get_outbox_dir())
    if not outbox_dir.is_dir():
        return []
    entries: list[OutboxEntry] = []
    for p in sorted(outbox_dir.iterdir()):
        if p.is_file():
            stat = p.stat()
            entries.append(
                OutboxEntry(
                    name=p.name,
                    size=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                )
            )
    return entries


@app.get("/api/outbox", response_model=list[OutboxEntry], summary="List outbox files", description="List all files in the outbox directory — downloads that completed but failed post-processing (e.g. missing ffmpeg).", tags=["Outbox"])
def list_outbox():
    return _list_outbox()


@app.delete("/api/outbox/{file_name}", response_model=OkResponse, summary="Delete outbox file", description="Remove a file from the outbox by name.", tags=["Outbox"])
def delete_outbox_file(file_name: str):
    file_path = Path(config.get_outbox_dir()) / file_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, f"File '{file_name}' not found in outbox")
    file_path.unlink()
    return OkResponse()


# ── Conversion Presets ───────────────────────────────────────


@app.get("/api/convert-presets", response_model=list[ConversionPresetResponse], summary="List conversion presets", description="List all predefined and custom output format presets.", tags=["Conversion Presets"])
def list_convert_presets():
    return db.list_presets()


@app.post("/api/convert-presets", response_model=ConversionPresetResponse, status_code=201, summary="Create conversion preset", description="Create a custom output format preset with container, codecs, bitrate, resolution, and other encoding parameters.", tags=["Conversion Presets"])
def create_convert_preset(body: ConversionPresetCreateRequest):
    existing = db.get_preset_by_name(body.name)
    if existing:
        raise HTTPException(409, f"Conversion preset '{body.name}' already exists")
    p = db.create_preset(ConversionPresetCreate(**body.model_dump()))
    return p


@app.get("/api/convert-presets/{preset_name}", response_model=ConversionPresetResponse, summary="Get conversion preset", description="Retrieve a single conversion preset by name.", tags=["Conversion Presets"])
def get_convert_preset(preset_name: str):
    p = db.get_preset_by_name(preset_name)
    if not p:
        raise HTTPException(404, f"Conversion preset '{preset_name}' not found")
    return p


@app.put("/api/convert-presets/{preset_name}", response_model=ConversionPresetResponse, summary="Update conversion preset", description="Update an existing conversion preset. Only provided fields are changed.", tags=["Conversion Presets"])
def update_convert_preset(preset_name: str, body: ConversionPresetUpdateRequest):
    existing = db.get_preset_by_name(preset_name)
    if not existing:
        raise HTTPException(404, f"Conversion preset '{preset_name}' not found")
    data = body.model_dump(exclude_none=True)
    if not data:
        return existing
    p = db.update_preset(existing.id, ConversionPresetUpdate(**data))
    return p


@app.delete("/api/convert-presets/{preset_name}", response_model=OkResponse, summary="Delete conversion preset", description="Remove a conversion preset by name.", tags=["Conversion Presets"])
def delete_convert_preset(preset_name: str):
    existing = db.get_preset_by_name(preset_name)
    if not existing:
        raise HTTPException(404, f"Conversion preset '{preset_name}' not found")
    db.delete_preset(existing.id)
    return OkResponse()
