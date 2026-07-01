import os
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query

from tube_explore import db, ytdlp
from tube_explore.models import Profile, ProfileCreate, ProfileUpdate, SettingsDict, TaskInfo
from tube_explore.schemas import (
    DownloadPlaylistRequest,
    DownloadVideoRequest,
    HealthResponse,
    MetadataResponse,
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


app = FastAPI(title="Tube Explore API", version="1.0.0", lifespan=lifespan)


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
            fn(*args, **kwargs)
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


# ── Search / Metadata / Playlist ─────────────────────────────


@app.get("/api/search", response_model=SearchResponse)
def search(q: str = Query(...), limit: int = Query(10, ge=1, le=50)):
    try:
        results = ytdlp.search_videos(q, limit)
        return SearchResponse(query=q, count=len(results), results=[SearchResult(**r) for r in results])
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/metadata", response_model=MetadataResponse)
def metadata(url: str = Query(...)):
    try:
        return ytdlp.get_metadata(url)
    except RuntimeError as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/playlist", response_model=PlaylistResponse)
def playlist(url: str = Query(...)):
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


@app.post("/api/download/video", status_code=202)
def download_video(body: DownloadVideoRequest):
    gs = _make_settings(db.get_all_settings())
    profile = _resolve_profile(body.profile, body)

    out = body.output_dir or profile.download_directory or gs.temp_directory or os.getcwd()

    tid = _create_task("video", body.url, body.model_dump(by_alias=True))
    _run_in_background(
        tid, ytdlp.download_video, body.url, output_dir=out, profile=profile, settings=gs, audio_only=body.audio_only
    )
    return {"taskId": tid, "status": "pending"}


@app.post("/api/download/playlist", status_code=202)
def download_playlist(body: DownloadPlaylistRequest):
    gs = _make_settings(db.get_all_settings())
    profile = _resolve_profile(body.profile, body)

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
    )
    return {"taskId": tid, "status": "pending"}


# ── Tasks ────────────────────────────────────────────────────


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@app.get("/api/tasks", response_model=list[TaskResponse])
def list_tasks():
    with _lock:
        return list(_tasks.values())


# ── Profiles ─────────────────────────────────────────────────


@app.get("/api/profiles", response_model=list[ProfileResponse])
def list_profiles():
    return db.list_profiles()


@app.post("/api/profiles", response_model=ProfileResponse, status_code=201)
def create_profile(body: ProfileCreateRequest):
    existing = db.get_profile_by_name(body.name)
    if existing:
        raise HTTPException(409, f"Profile '{body.name}' already exists")
    p = db.create_profile(ProfileCreate(**body.model_dump()))
    return p


@app.get("/api/profiles/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: int):
    p = db.get_profile(profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    return p


@app.put("/api/profiles/{profile_id}", response_model=ProfileResponse)
def update_profile(profile_id: int, body: ProfileUpdateRequest):
    existing = db.get_profile(profile_id)
    if not existing:
        raise HTTPException(404, "Profile not found")
    data = body.model_dump(exclude_none=True)
    if not data:
        return existing
    p = db.update_profile(profile_id, ProfileUpdate(**data))
    return p


@app.delete("/api/profiles/{profile_id}")
def delete_profile(profile_id: int):
    existing = db.get_profile(profile_id)
    if not existing:
        raise HTTPException(404, "Profile not found")
    db.delete_profile(profile_id)
    return {"ok": True}


# ── Global settings ──────────────────────────────────────────


@app.get("/api/settings", response_model=SettingsResponse)
def get_settings():
    raw = db.get_all_settings()
    return SettingsResponse(**raw)


@app.put("/api/settings", response_model=SettingsResponse)
def update_settings(body: SettingsUpdateRequest):
    data = {k: str(v) for k, v in body.model_dump(exclude_none=True).items()}
    if data:
        db.set_settings(data)
    return get_settings()


# ── Health ───────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", has_ffmpeg=ytdlp.HAS_FFMPEG)
