import asyncio
import json
import os
import shutil
import tempfile
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from tube_explore import config, db, ytdlp
from tube_explore.models import (
    ConversionPreset,
    ConversionPresetCreate,
    ConversionPresetUpdate,
    OutboxFileCreate,
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
    DownloadedFile,
    DownloadPlaylistRequest,
    DownloadTaskCreatedResponse,
    DownloadVideoRequest,
    ErrorResponse,
    FileInfo,
    HealthResponse,
    MetadataResponse,
    OkResponse,
    OutboxEntry,
    OutboxProcessRequest,
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
    TaskResultResponse,
)

_404: dict[int | str, dict[str, Any]] = {404: {"model": ErrorResponse, "description": "Resource not found"}}
_409: dict[int | str, dict[str, Any]] = {409: {"model": ErrorResponse, "description": "Conflict"}}
_404_409: dict[int | str, dict[str, Any]] = {**_404, **_409}
_400: dict[int | str, dict[str, Any]] = {400: {"model": ErrorResponse, "description": "Bad request"}}
_422: dict[int | str, dict[str, Any]] = {422: {"model": ErrorResponse, "description": "Validation error"}}
_500: dict[int | str, dict[str, Any]] = {500: {"model": ErrorResponse, "description": "Operation failed — invalid media URL, unsupported URL, extractor failure, or network failure"}}
_503: dict[int | str, dict[str, Any]] = {503: {"model": ErrorResponse, "description": "Service unavailable — ffmpeg missing, temp directory not writable, or download directory not writable"}}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    db.init_db()
    _sync_outbox_db()
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


# ── CORS ─────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Task store ───────────────────────────────────────────────
_tasks: dict[str, TaskInfo] = {}
_lock = threading.Lock()


# ── Global SSE event bus ─────────────────────────────────────
_main_loop: asyncio.AbstractEventLoop | None = None
_global_subscribers: set[asyncio.Queue] = set()
_global_sub_lock = threading.Lock()


def _subscribe_global() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    with _global_sub_lock:
        _global_subscribers.add(q)
    return q


def _unsubscribe_global(q: asyncio.Queue) -> None:
    with _global_sub_lock:
        _global_subscribers.discard(q)


def _active_sse_connections() -> int:
    with _global_sub_lock:
        return len(_global_subscribers)


def _broadcast(event: str, data: dict) -> None:
    with _global_sub_lock:
        queues = list(_global_subscribers)
    if not queues:
        return
    payload = json.dumps(data)
    for q in queues:
        if _main_loop and _main_loop.is_running():
            _main_loop.call_soon_threadsafe(q.put_nowait, (event, payload))
        else:
            q.put_nowait((event, payload))


def _create_task(task_type: str, url: str, params: dict[str, object]) -> str:
    tid = str(uuid.uuid4())
    task = TaskInfo(
        id=tid,
        type=task_type,
        url=url,
        params=params,
        status="pending",
        progress_percent=0,
        created_at=datetime.now(UTC),
        error=None,
        completed_at=None,
        result=None,
    )
    with _lock:
        _tasks[tid] = task
    _broadcast("task_created", task.model_dump(mode="json"))
    return tid


def _update_task(tid: str, **kwargs):
    with _lock:
        task = _tasks.get(tid)
        if task is None:
            return
        extra: dict[str, object] = {"updated_at": datetime.now(UTC)}
        if kwargs.get("status") in ("completed", "failed"):
            extra["completed_at"] = datetime.now(UTC)
        task = task.model_copy(update=kwargs | extra)
        _tasks[tid] = task
        data = task.model_dump(mode="json")
    _broadcast("task_updated", data)


def _run_in_background(tid: str, fn, *args, **kwargs):
    def wrapper():
        _update_task(tid, status="running", progress_percent=50)

        def _progress(percent: int, file_progress_list: list[dict] | None = None):
            extra: dict[str, object] = {"progress_percent": percent}
            if file_progress_list is not None:
                extra["file_progress"] = file_progress_list
            _update_task(tid, **extra)

        kwargs["progress_callback"] = _progress
        try:
            result = fn(*args, **kwargs)
            if not result:
                _update_task(tid, status="completed", progress_percent=100)
                return
            outbox = result.get("outbox")
            files = result.get("files")
            if outbox and files:
                _update_task(tid, status="completed", error=f"Some files routed to outbox: {outbox}", result=files, progress_percent=100)
            elif outbox:
                _update_task(tid, status="completed", error=f"Files routed to outbox: {outbox}", progress_percent=100)
            elif files:
                _update_task(tid, status="completed", result=files, progress_percent=100)
            else:
                _update_task(tid, status="completed", progress_percent=100)
        except Exception as e:
            _update_task(tid, status="failed", error=str(e), progress_percent=100)

    t = threading.Thread(target=wrapper, daemon=True, name="download-worker")
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


def _resolve_output_path(body, profile: Profile) -> str:
    base = profile.download_directory or os.getcwd()
    sub = getattr(body, "download_path_override", None) or getattr(body, "output_dir", None)
    if sub:
        return os.path.join(base, sub)
    return base


# ── Search / Metadata / Playlist ─────────────────────────────


def _sync_outbox_db() -> None:
    outbox_dir = Path(config.get_outbox_dir())
    if not outbox_dir.is_dir():
        return
    known: set[str] = {r.file_name for r in db.list_outbox_files()}
    for p in sorted(outbox_dir.rglob("*")):
        if not p.is_file() or p.name in known:
            continue
        rel = str(p.relative_to(outbox_dir))
        if rel in known:
            continue
        stat = p.stat()
        record = OutboxFileCreate(
            id=str(uuid.uuid4()),
            file_name=rel,
            file_size=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )
        db.insert_outbox_file(record)


@app.get("/api/search", response_model=SearchResponse, responses=_500, summary="Search media", description="Search for media content by query string. Returns a ranked list of matching results with ID, title, duration, and channel info.", tags=["Search"])
def search(q: str = Query(..., min_length=1, description="Search query string"), limit: int = Query(10, ge=1, le=50, description="Maximum number of results (1–50)")):
    try:
        results = ytdlp.search_videos(q, limit)
        return SearchResponse(query=q, count=len(results), results=[SearchResult(**r) for r in results])
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/metadata", response_model=MetadataResponse, responses=_500, summary="Get media metadata", description="Fetch full metadata for a given media URL, including available formats, duration, resolution, and thumbnails.", tags=["Metadata"])
def metadata(url: str = Query(..., pattern=r"^https?://\S+", description="Media URL to inspect")):
    try:
        return ytdlp.get_metadata(url)
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/playlist", response_model=PlaylistResponse, responses=_500, summary="Get playlist info", description="Fetch all entries in a playlist URL, including per-video duration, position, title, and thumbnails.", tags=["Playlists"])
def playlist(url: str = Query(..., pattern=r"^https?://\S+", description="Playlist URL")):
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


@app.post("/api/download/video", response_model=DownloadTaskCreatedResponse, status_code=202, responses={**_404, **_500, **_503}, summary="Download video", description="Start a background task to download a single video. Accepts profile name or per-request overrides for quality, format, directory, audio-only mode, and a conversion preset. Returns a task ID for status polling.", tags=["Downloads"])
def download_video(body: DownloadVideoRequest):
    gs = _make_settings(db.get_all_settings())
    profile = _resolve_profile(body.profile_id, body)
    conversion_preset = _resolve_convert_preset(body)
    out = _resolve_output_path(body, profile)

    tid = _create_task("video", body.url, body.model_dump(by_alias=True))
    _run_in_background(
        tid, ytdlp.download_video, body.url, output_dir=out, profile=profile, settings=gs, audio_only=body.audio_only, conversion_preset=conversion_preset, task_id=tid
    )
    return DownloadTaskCreatedResponse(task_id=tid, status="pending", status_url=f"/api/tasks/{tid}")


@app.post("/api/download/playlist", response_model=DownloadTaskCreatedResponse, status_code=202, responses={**_404, **_500, **_503}, summary="Download playlist", description="Start a background task to download all videos in a playlist. Supports optional index range filtering, audio-only mode, and a conversion preset. Returns a task ID for status polling.", tags=["Downloads"])
def download_playlist(body: DownloadPlaylistRequest):
    gs = _make_settings(db.get_all_settings())
    profile = _resolve_profile(body.profile_id, body)
    conversion_preset = _resolve_convert_preset(body)
    out = _resolve_output_path(body, profile)

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
        task_id=tid,
    )
    return DownloadTaskCreatedResponse(task_id=tid, status="pending", status_url=f"/api/tasks/{tid}")


# ── Tasks ────────────────────────────────────────────────────


@app.get("/api/tasks/{task_id}", response_model=TaskResponse, responses=_404, summary="Get task status", description="Poll the status of a background download task by its ID. Returns the current status (pending/running/completed/failed), type, URL, timestamps, and error if any.", tags=["Tasks"])
def get_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@app.get("/api/tasks", response_model=list[TaskResponse], summary="List tasks", description="List all background download tasks. Sorted by creation time (newest first). Includes status, type, URL, and error info for each task.", tags=["Tasks"])
def list_tasks(limit: int = Query(50, ge=1, le=200, description="Maximum number of results"), offset: int = Query(0, ge=0, description="Number of results to skip")):
    with _lock:
        items = list(_tasks.values())
    return items[offset:][:limit]


@app.get("/api/events", summary="Global event stream", description="Persistent SSE connection that streams all task lifecycle events: snapshot, task_created, task_updated, task_deleted. Sends keepalive every 30s.", tags=["Tasks"])
async def event_stream():
    q = _subscribe_global()

    async def event_gen():
        try:
            # initial snapshot
            with _lock:
                tasks_data = [t.model_dump(mode="json") for t in _tasks.values()]
            yield f"event: snapshot\ndata: {json.dumps({'tasks': tasks_data})}\n\n"
            while True:
                try:
                    event, payload = await asyncio.wait_for(q.get(), timeout=30)
                except TimeoutError:
                    yield "event: keepalive\ndata: {}\n\n"
                    continue
                yield f"event: {event}\ndata: {payload}\n\n"
        finally:
            _unsubscribe_global(q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@app.get("/api/tasks/{task_id}/result", response_model=TaskResultResponse, responses=_404, summary="Get task result", description="Retrieve the files produced by a completed download task. Returns file names, sizes, and absolute paths.", tags=["Tasks"])
def get_task_result(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    files = [DownloadedFile(**f) for f in (task.result or [])]
    return TaskResultResponse(task_id=task.id, status=cast("Literal['pending', 'running', 'completed', 'failed', 'cancelled']", task.status), files=files)


@app.post("/api/tasks/{task_id}/cancel", responses=_404_409, summary="Cancel task", description="Cancel a pending or running task. Sets status to `cancelled` so the result is discarded.", tags=["Tasks"])
def cancel_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        if task.status not in ("pending", "running"):
            raise HTTPException(409, f"Cannot cancel task in status '{task.status}'")
        _update_task(task_id, status="cancelled")
    return OkResponse(ok=True)


def _re_run_task(task: TaskInfo) -> str:
    gs = _make_settings(db.get_all_settings())
    params = task.params
    if task.type == "video":
        body = DownloadVideoRequest.model_validate(params)
        profile = _resolve_profile(body.profile_id, body)
        conversion_preset = _resolve_convert_preset(body)
        out = _resolve_output_path(body, profile)
        tid = _create_task("video", body.url, body.model_dump(by_alias=True))
        _run_in_background(
            tid, ytdlp.download_video, body.url, output_dir=out, profile=profile,
            settings=gs, audio_only=body.audio_only, conversion_preset=conversion_preset, task_id=tid,
        )
        return tid
    # playlist
    pl_body = DownloadPlaylistRequest.model_validate(params)
    profile = _resolve_profile(pl_body.profile_id, pl_body)
    conversion_preset = _resolve_convert_preset(pl_body)
    out = _resolve_output_path(pl_body, profile)
    tid = _create_task("playlist", pl_body.url, pl_body.model_dump(by_alias=True))
    _run_in_background(
        tid, ytdlp.download_playlist, pl_body.url, output_dir=out, profile=profile,
        settings=gs, video_range=pl_body.range, audio_only=pl_body.audio_only,
        conversion_preset=conversion_preset, task_id=tid,
    )
    return tid


@app.post("/api/tasks/{task_id}/retry", response_model=DownloadTaskCreatedResponse, responses=_404_409, summary="Retry task", description="Retry a failed or partially-failed download task. Creates a new task with the same parameters and returns the new task ID and status URLs.", tags=["Tasks"])
def retry_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status not in ("failed", "completed"):
        raise HTTPException(409, f"Cannot retry task in status '{task.status}'")
    if task.status == "completed" and not task.error:
        raise HTTPException(409, "Task completed successfully with no errors; nothing to retry")
    tid = _re_run_task(task)
    return DownloadTaskCreatedResponse(task_id=tid, status="pending", status_url=f"/api/tasks/{tid}")


@app.delete("/api/tasks/{task_id}", response_model=OkResponse, responses=_404_409, summary="Delete task", description="Remove a completed, failed, or cancelled task from memory.", tags=["Tasks"])
def delete_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        if task.status in ("pending", "running"):
            raise HTTPException(409, f"Cannot delete task in status '{task.status}'")
        del _tasks[task_id]
    _broadcast("task_deleted", {"id": task_id})
    return OkResponse(ok=True)


# ── Profiles ─────────────────────────────────────────────────


@app.get("/api/profiles", response_model=list[ProfileResponse], summary="List profiles", description="List all saved download profiles. Each profile bundles quality mode, format string, download directory, and audio-only flag.", tags=["Profiles"])
def list_profiles(limit: int = Query(50, ge=1, le=200, description="Maximum number of results"), offset: int = Query(0, ge=0, description="Number of results to skip")):
    return db.list_profiles()[offset:][:limit]


@app.post("/api/profiles", response_model=ProfileResponse, status_code=201, responses=_409, summary="Create profile", description="Create a new download profile. Name must be unique. Quality mode can be `best`, `least`, `at_most`, or `at_least` (latter two require a pixel height value).", tags=["Profiles"])
def create_profile(body: ProfileCreateRequest):
    existing = db.get_profile_by_name(body.name)
    if existing:
        raise HTTPException(409, f"Profile '{body.name}' already exists")
    p = db.create_profile(ProfileCreate(**body.model_dump()))
    return p


@app.get("/api/profiles/{profile_id}", response_model=ProfileResponse, responses=_404, summary="Get profile", description="Retrieve a single download profile by its ID.", tags=["Profiles"])
def get_profile(profile_id: int):
    p = db.get_profile(profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    return p


@app.patch("/api/profiles/{profile_id}", response_model=ProfileResponse, responses=_404, summary="Update profile", description="Patch an existing download profile. Only provided fields are changed; omitted fields keep their current values.", tags=["Profiles"])
def update_profile(profile_id: int, body: ProfileUpdateRequest):
    existing = db.get_profile(profile_id)
    if not existing:
        raise HTTPException(404, "Profile not found")
    data = body.model_dump(exclude_none=True)
    if not data:
        return existing
    p = db.update_profile(profile_id, ProfileUpdate(**data))
    return p


@app.delete("/api/profiles/{profile_id}", response_model=OkResponse, responses=_404, summary="Delete profile", description="Delete a download profile by its ID.", tags=["Profiles"])
def delete_profile(profile_id: int):
    existing = db.get_profile(profile_id)
    if not existing:
        raise HTTPException(404, "Profile not found")
    db.delete_profile(profile_id)
    return OkResponse()


# ── Global settings ──────────────────────────────────────────


@app.get("/api/settings", response_model=SettingsResponse, summary="Get settings", description="Retrieve all global download settings: rate limit, temp directory, retry count, and socket timeout.", tags=["Settings"])
def get_settings():
    raw = db.get_all_settings()
    return SettingsResponse(**raw)


@app.patch("/api/settings", response_model=SettingsResponse, summary="Update settings", description="Patch global download settings. Only provided fields are changed; omitted fields keep their current values.", tags=["Settings"])
def update_settings(body: SettingsUpdateRequest):
    data = {k: str(v) for k, v in body.model_dump(exclude_none=True).items()}
    if data:
        db.set_settings(data)
    return get_settings()


# ── Health ───────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse, summary="Health check", description="Returns service health status, ffmpeg/yt-dlp availability with versions, directory writability, and worker status.", tags=["Health"])
def health():
    settings = db.get_all_settings()
    ffmpeg_ver = ytdlp.get_ffmpeg_version()
    ytdlp_ver = ytdlp.get_ytdlp_version()
    temp_dir = settings.get("temp_directory", "").strip() or tempfile.gettempdir()
    os.makedirs(temp_dir, exist_ok=True)
    worker_running = any(
        t.name == "download-worker" for t in threading.enumerate()
    )
    # Check writability of config dir (where DB lives) and temp dir
    config_dir = config.get_config_dir()
    return HealthResponse(
        status="ok",
        has_ffmpeg=ytdlp.HAS_FFMPEG,
        ffmpeg_version=ffmpeg_ver,
        has_ytdlp=ytdlp.HAS_YTDLP,
        ytdlp_version=ytdlp_ver,
        download_directory_writable=os.access(config_dir, os.W_OK),
        temp_directory_writable=os.access(temp_dir, os.W_OK),
        worker_running=worker_running,
        active_sse_connections=_active_sse_connections(),
    )


@app.get("/api/ready", response_model=HealthResponse, summary="Readiness check", description="Returns 200 when the service is ready to accept requests (always ready in current implementation).", tags=["Health"])
def ready():
    return health()


# ── Files ─────────────────────────────────────────────────────


@app.get("/api/files", response_model=list[FileInfo], summary="List downloaded files", description="List all completed download files across all tasks. Returns metadata including source URL, task ID, and creation time.", tags=["Files"])
def list_files(limit: int = Query(50, ge=1, le=200, description="Maximum number of results"), offset: int = Query(0, ge=0, description="Number of results to skip")):
    results: list[FileInfo] = []
    with _lock:
        tasks = list(_tasks.values())
    for task in tasks:
        if task.status not in ("completed",):
            continue
        for f in (task.result or []):
            results.append(FileInfo(
                id=f.get("id", str(uuid.uuid4())),
                name=f["name"],
                size=f["size"],
                path=f["path"],
                task_id=task.id,
                source_url=task.url,
                created_at=task.completed_at or task.created_at,
            ))
    return results[offset:][:limit]


@app.get("/api/files/{file_id}/download", summary="Download a file", description="Download a completed file by its file ID. Returns the file as a binary stream.", tags=["Files"])
def download_file(file_id: str):
    with _lock:
        tasks = list(_tasks.values())
    for task in tasks:
        if task.status != "completed":
            continue
        for f in (task.result or []):
            if f.get("id") == file_id:
                path = f["path"]
                if not os.path.isfile(path):
                    raise HTTPException(404, "File not found on disk")
                return StreamingResponse(
                    open(path, "rb"),
                    media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{f["name"]}"'},
                )
    raise HTTPException(404, "File not found")


@app.exception_handler(RequestValidationError)
async def _validation_exc(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorResponse(detail=str(exc)).model_dump(by_alias=True))


@app.exception_handler(HTTPException)
async def _http_exc(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=ErrorResponse(detail=exc.detail).model_dump(by_alias=True))


# ── Outbox ────────────────────────────────────────────────────


def _list_outbox() -> list[OutboxEntry]:
    records = db.list_outbox_files()
    outbox_dir = Path(config.get_outbox_dir())
    entries: list[OutboxEntry] = []
    for r in records:
        file_path = outbox_dir / r.file_name
        if not file_path.is_file():
            continue
        entries.append(
            OutboxEntry(
                id=r.id,
                name=r.file_name,
                size=r.file_size,
                media_url=r.media_url,
                task_id=r.task_id,
                quality_mode=r.quality_mode,
                quality_value=r.quality_value,
                convert_preset=r.convert_preset,
                status=cast("Literal['pending', 'processing', 'completed', 'failed']", r.status),
                error=r.error,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return entries


@app.get("/api/outbox", response_model=list[OutboxEntry], summary="List outbox files", description="List all files in the outbox directory — downloads that completed but failed post-processing (e.g. missing ffmpeg).", tags=["Outbox"])
def list_outbox(limit: int = Query(50, ge=1, le=200, description="Maximum number of results"), offset: int = Query(0, ge=0, description="Number of results to skip")):
    return _list_outbox()[offset:][:limit]


@app.delete("/api/outbox/{file_id}", response_model=OkResponse, responses=_404, summary="Delete outbox file", description="Remove a file from the outbox by its file ID. Also deletes the file from disk.", tags=["Outbox"])
def delete_outbox_file(file_id: str):
    record = db.get_outbox_file(file_id)
    if not record:
        raise HTTPException(404, f"Outbox file '{file_id}' not found")
    file_path = Path(config.get_outbox_dir()) / record.file_name
    if file_path.is_file():
        file_path.unlink()
    db.delete_outbox_file(file_id)
    return OkResponse()


@app.post("/api/outbox/{file_id}/process", response_model=OkResponse, responses={**_404, **_400, **_422}, summary="Retry conversion on outbox file", description="Attempt to convert an outbox file using the specified conversion preset. Requires ffmpeg. On success the converted file is moved out of the outbox to the specified download directory (or current working directory) and the outbox entry is removed.", tags=["Outbox"])
def process_outbox_file(file_id: str, body: OutboxProcessRequest):
    record = db.get_outbox_file(file_id)
    if not record:
        raise HTTPException(404, f"Outbox file '{file_id}' not found")

    outbox_dir = Path(config.get_outbox_dir())
    file_path = outbox_dir / record.file_name
    if not file_path.is_file():
        db.update_outbox_file_status(file_id, "failed", error="File not found on disk")
        raise HTTPException(404, f"File '{record.file_name}' not found on disk")

    db.update_outbox_file_status(file_id, "processing")

    cp = db.get_preset_by_name(body.preset)
    if not cp:
        db.update_outbox_file_status(file_id, "failed", error=f"Conversion preset '{body.preset}' not found")
        raise HTTPException(404, f"Conversion preset '{body.preset}' not found")

    if not ytdlp.HAS_FFMPEG:
        db.update_outbox_file_status(file_id, "failed", error="ffmpeg is not available")
        raise HTTPException(400, "ffmpeg is not available; cannot retry conversion")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpfile = shutil.copy2(str(file_path), tmpdir)
        try:
            converted = ytdlp._run_conversion_on_file(tmpfile, cp)
        except RuntimeError as e:
            db.update_outbox_file_status(file_id, "failed", error=str(e))
            raise HTTPException(422, str(e)) from e

    if not converted:
        err = "Conversion produced no output file"
        db.update_outbox_file_status(file_id, "failed", error=err)
        raise HTTPException(422, err)

    target_dir = Path(body.download_directory) if body.download_directory else Path.cwd()
    target_dir.mkdir(parents=True, exist_ok=True)
    output_name = f"{file_path.stem}.{cp.output_ext}"
    output_path = target_dir / output_name
    shutil.move(converted, str(output_path))
    file_path.unlink()

    db.delete_outbox_file(file_id)

    return OkResponse()


# ── Conversion Presets ───────────────────────────────────────


@app.get("/api/convert-presets", response_model=list[ConversionPresetResponse], summary="List conversion presets", description="List all predefined and custom output format presets.", tags=["Conversion Presets"])
def list_convert_presets(limit: int = Query(50, ge=1, le=200, description="Maximum number of results"), offset: int = Query(0, ge=0, description="Number of results to skip")):
    return db.list_presets()[offset:][:limit]


@app.post("/api/convert-presets", response_model=ConversionPresetResponse, status_code=201, responses=_409, summary="Create conversion preset", description="Create a custom output format preset with container, codecs, bitrate, resolution, and other encoding parameters.", tags=["Conversion Presets"])
def create_convert_preset(body: ConversionPresetCreateRequest):
    existing = db.get_preset_by_name(body.name)
    if existing:
        raise HTTPException(409, f"Conversion preset '{body.name}' already exists")
    p = db.create_preset(ConversionPresetCreate(**body.model_dump()))
    return p


@app.get("/api/convert-presets/{preset_name}", response_model=ConversionPresetResponse, responses=_404, summary="Get conversion preset", description="Retrieve a single conversion preset by name.", tags=["Conversion Presets"])
def get_convert_preset(preset_name: str):
    p = db.get_preset_by_name(preset_name)
    if not p:
        raise HTTPException(404, f"Conversion preset '{preset_name}' not found")
    return p


@app.patch("/api/convert-presets/{preset_name}", response_model=ConversionPresetResponse, responses=_404, summary="Update conversion preset", description="Patch an existing conversion preset. Only provided fields are changed.", tags=["Conversion Presets"])
def update_convert_preset(preset_name: str, body: ConversionPresetUpdateRequest):
    existing = db.get_preset_by_name(preset_name)
    if not existing:
        raise HTTPException(404, f"Conversion preset '{preset_name}' not found")
    data = body.model_dump(exclude_none=True)
    if not data:
        return existing
    p = db.update_preset(existing.id, ConversionPresetUpdate(**data))
    return p


@app.delete("/api/convert-presets/{preset_name}", response_model=OkResponse, responses=_404, summary="Delete conversion preset", description="Remove a conversion preset by name.", tags=["Conversion Presets"])
def delete_convert_preset(preset_name: str):
    existing = db.get_preset_by_name(preset_name)
    if not existing:
        raise HTTPException(404, f"Conversion preset '{preset_name}' not found")
    db.delete_preset(existing.id)
    return OkResponse()


# ── UI static file serving ────────────────────────────────────


UI_BUILD_DIR = Path(__file__).resolve().parent.parent / "web-ui" / "build"
_HAS_UI = UI_BUILD_DIR.is_dir()


if _HAS_UI:
    from fastapi.staticfiles import StaticFiles

    app.mount("/_app", StaticFiles(directory=str(UI_BUILD_DIR / "_app")), name="ui_assets")

    @app.get("/favicon.svg")
    async def _ui_favicon():
        return FileResponse(str(UI_BUILD_DIR / "favicon.svg"))

    @app.get("/{full:path}")
    async def _ui_index(full: str):
        if full.startswith("api/") or full == "openapi.json" or full.startswith("docs"):
            raise HTTPException(404, "Not found")
        return FileResponse(str(UI_BUILD_DIR / "index.html"))
