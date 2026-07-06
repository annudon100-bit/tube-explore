import asyncio
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from fastapi.staticfiles import StaticFiles

from tube_explore import config, db, ytdlp
from tube_explore.ytdlp import PauseError
from tube_explore.models import (
    Profile,
    ProfileCreate,
    ProfileUpdate,
    TaskInfo,
    RadarrInstanceCreate,
    RadarrInstanceUpdate,
)
from tube_explore.schemas import (
    DownloadedFile,
    DownloadPlaylistRequest,
    DownloadTaskCreatedResponse,
    DownloadVideoRequest,
    ErrorResponse,
    FileCategory,
    FileInfo,
    FilesListResponse,
    FileStatsResponse,
    HealthResponse,
    MetadataResponse,
    OkResponse,
    PlaylistEntry,
    PlaylistResponse,
    ProfileCreateRequest,
    ProfileResponse,
    ProfileUpdateRequest,
    RadarrInstanceTestRequest,
    RadarrInstanceUpsertRequest,
    RadarrMovieDownloadRequest,
    SearchResponse,
    SearchResult,
    SettingsResponse,
    SettingsUpdateRequest,
    TaskIntegration,
    TaskResponse,
    classify_file_extension,
    classify_file_format,
    classify_file_type,
)
from tube_explore.radarr_client import RadarrClient, RadarrError

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
            "name": "Radarr",
            "description": "Radarr integration: manage instances, missing movies, imports, and linked downloads.",
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
    _broadcast("task_created", _task_to_response(task))
    return tid


def _camel_to_snake(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def _task_to_response(task: TaskInfo) -> dict[str, object]:
    dump = task.model_dump()
    integration_val = dump.pop("integration", None)
    meta = dump.pop("integration_meta", None)
    if integration_val and meta and isinstance(meta, dict):
        normalized: dict[str, object] = {}
        for k, v in meta.items():
            normalized[_camel_to_snake(k)] = v
        normalized.setdefault("movie_title", "Unknown")
        dump["integration"] = TaskIntegration(type=integration_val, **normalized)
    return TaskResponse(**dump).model_dump(mode="json", by_alias=True)


def _update_task(tid: str, **kwargs):
    with _lock:
        task = _tasks.get(tid)
        if task is None:
            return
        extra: dict[str, object] = {"updated_at": datetime.now(UTC)}
        terminal_states = ("completed", "failed", "cancelled")
        if kwargs.get("status") in terminal_states:
            extra["completed_at"] = datetime.now(UTC)
        new_kwargs = kwargs | extra
        task = task.model_copy(update=new_kwargs)
        _tasks[tid] = task
        data = _task_to_response(task)
    logger.info("_update_task: kwargs=%s data_speed=%s data_eta=%s data_totalBytes=%s", new_kwargs, data.get("speed"), data.get("eta"), data.get("totalBytes"))
    _broadcast("task_updated", data)


def _run_in_background(tid: str, fn, *args, url: str | None = None, metadata_fetched: dict | None = None, **kwargs):
    """Run fn in a background thread with progress tracking.

    If url is provided, metadata is pre-fetched (title, thumbnail, etc.)
    and populated on the task before the download begins.
    """

    def wrapper():
        _update_task(tid, status="running", progress_percent=0)

        # ── Pre-fetch metadata and cache thumbnail ─────────────
        if url and not metadata_fetched:
            try:
                meta = ytdlp.get_metadata(url)
                thumb_rel = ytdlp.cache_thumbnail(meta["id"], meta.get("thumbnail"))
                meta_fields: dict[str, object] = {
                    "title": meta.get("title"),
                    "channel": meta.get("channel"),
                    "duration": meta.get("duration"),
                    "thumbnail_path": f"/api/{thumb_rel}" if thumb_rel else None,
                }
                if meta.get("formats"):
                    meta_fields["format_info"] = meta["formats"]
                _update_task(tid, **meta_fields)
            except Exception as e:
                logger.warning("Metadata pre-fetch failed for task %s: %s", tid, e)

        # ── Pre-fetch playlist video titles and thumbnails ────
        _playlist_titles: dict[int, str] = {}
        _playlist_thumbnails: dict[int, str] = {}
        if url and ("playlist" in url or "list=" in url):
            try:
                entries = ytdlp.get_playlist_info(url)
                for i, e in enumerate(entries):
                    _playlist_titles[i] = e.get("title") or f"Video {i+1}"
                    thumb = e.get("thumbnail_url")
                    if thumb:
                        _playlist_thumbnails[i] = thumb
                fp = [
                    {"index": i, "title": _playlist_titles[i], "thumbnailUrl": _playlist_thumbnails.get(i)}
                    for i in range(len(entries))
                ]
                _update_task(tid, file_progress=fp, total_items=len(fp))
            except Exception as e:
                logger.warning("Failed to pre-fetch playlist entries for task %s: %s", tid, e)

        # ── Progress callback ────────────────────────────────
        _start_time = datetime.now(UTC)

        def _progress(percent: int, file_progress_list: list[dict] | None = None, extra: dict | None = None):
            nonlocal _start_time
            elapsed = int((datetime.now(UTC) - _start_time).total_seconds())
            update: dict[str, object] = {"progress_percent": percent, "elapsed": elapsed}
            if file_progress_list is not None:
                if _playlist_titles:
                    for fp in file_progress_list:
                        idx = fp.get("index")
                        if idx is not None:
                            if not fp.get("title") and idx in _playlist_titles:
                                fp["title"] = _playlist_titles[idx]
                            if not fp.get("thumbnailUrl") and idx in _playlist_thumbnails:
                                fp["thumbnailUrl"] = _playlist_thumbnails[idx]
                update["file_progress"] = file_progress_list
            if extra:
                step = extra.get("step")
                if step:
                    update["progress_step"] = step
                db_bytes = extra.get("downloaded_bytes")
                if db_bytes is not None:
                    update["downloaded_bytes"] = db_bytes
                tb = extra.get("total_bytes")
                if tb is not None:
                    update["total_bytes"] = tb
                spd = extra.get("speed")
                if spd:
                    update["speed"] = spd
                eta_val = extra.get("eta")
                if eta_val:
                    update["eta"] = eta_val
                ci = extra.get("current_index")
                if ci is not None:
                    update["current_index"] = ci
                ti = extra.get("total_items")
                if ti is not None:
                    update["total_items"] = ti
            logger.info("_progress: extra=%s update=%s", extra, update)
            _update_task(tid, **update)

        kwargs["progress_callback"] = _progress
        try:
            result = fn(*args, **kwargs)
            with _lock:
                task = _tasks.get(tid)
                if task and task.status == "cancelled":
                    return
            if not result:
                _update_task(tid, status="completed", progress_percent=100)
                return
            files = result.get("files")
            if files:
                _update_task(tid, status="completed", result=files, progress_percent=100)
                _radarr_import_download(tid, files)
            else:
                _update_task(tid, status="completed", progress_percent=100)
        except PauseError:
            return
        except Exception as e:
            with _lock:
                task = _tasks.get(tid)
                if task and task.status == "cancelled":
                    return
            _update_task(tid, status="failed", error=str(e), progress_percent=100)

    t = threading.Thread(target=wrapper, daemon=True, name="download-worker")
    t.start()


# ── Helpers ──────────────────────────────────────────────────


def _radarr_import_download(tid: str, files: list[dict]):
    """After a Radarr-linked download completes, copy the file into the
    movie's subdirectory under tube_write_path, trigger a refresh+rescan,
    then query Radarr for the final movie file path."""
    with _lock:
        task = _tasks.get(tid)
        if not task or task.integration != "radarr":
            return
        meta = dict(task.integration_meta or {})
    inst_id = meta.get("instanceId") or meta.get("instance_id", "")
    movie_id = meta.get("movieId") or meta.get("movie_id", 0)
    if not inst_id or not movie_id:
        logger.info("radarr_import: no instance_id or movie_id in meta=%s", meta)
        return

    inst = _get_radarr_instance(inst_id)
    if not inst:
        return
    if not files:
        return

    local_path = files[0].get("path", "") if isinstance(files[0], dict) else str(files[0])
    if not local_path:
        logger.info("radarr_import: no file path in result files=%s", files)
        return

    meta["importStatus"] = "importing"
    _update_task(tid, integration_meta=meta)

    try:
        client = RadarrClient(inst.base_url, inst.api_key_encrypted)
        movie = client.get_movie(int(movie_id))
        movie_path = movie.get("path", "")
        if not movie_path:
            raise RuntimeError(f"Radarr movie {movie_id} has no path")

        # Derive relative subdirectory from movie's Radarr-side path
        radarr_base = inst.radarr_import_path.rstrip("/")
        subdir = movie_path
        if radarr_base and movie_path.startswith(radarr_base):
            subdir = movie_path[len(radarr_base):].lstrip("/")
        tube_dest_dir = os.path.join(inst.tube_write_path, subdir)
        dest = os.path.join(tube_dest_dir, os.path.basename(local_path))

        os.makedirs(tube_dest_dir, exist_ok=True)
        shutil.copy2(local_path, dest)
        logger.info("radarr_import: copied %s → %s", local_path, dest)

        meta["localPath"] = local_path
        meta["importStatus"] = "waiting_for_import"
        _update_task(tid, integration_meta=meta)
    except Exception as e:
        logger.error("radarr_import: copy failed: %s", e)
        meta["importStatus"] = "failed"
        meta["importError"] = f"copy_error: {e}"
        _update_task(tid, integration_meta=meta)
        _broadcast("radarr_import_updated", {"taskId": tid, "importStatus": "failed"})
        return

    try:
        cmd = client.create_command("RefreshMovie", movieId=int(movie_id))
        cmd_id = cmd.get("id", "")
        logger.info("radarr_import: RefreshMovie command=%s", cmd_id)

        # Query Radarr for the actual movie file path after import
        time.sleep(3)
        updated = client.get_movie(int(movie_id))
        if updated.get("hasFile") and updated.get("movieFile"):
            mf_path = updated["movieFile"].get("path") or updated["movieFile"].get("relativePath", "")
            if mf_path:
                meta["radarrPath"] = mf_path

        meta["importStatus"] = "imported"
        meta["radarrCommandId"] = str(cmd_id)
        _update_task(tid, integration_meta=meta)
        _broadcast("radarr_import_updated", {"taskId": tid, "importStatus": "imported"})
    except Exception as e:
        logger.error("radarr_import: trigger failed: %s", e)
        meta["importStatus"] = "failed"
        meta["importError"] = f"trigger_error: {e}"
        _update_task(tid, integration_meta=meta)
        _broadcast("radarr_import_updated", {"taskId": tid, "importStatus": "failed"})


def _normalize_rel_path(path: str) -> str:
    """Strip leading slash, resolve dots, ensure no absolute traversal."""
    cleaned = path.lstrip("/").lstrip("\\")
    return os.path.normpath(cleaned) if cleaned else ""


def _safe_join(base: str, *parts: str) -> str:
    """Join path segments and verify the result is within base."""
    cleaned = [p for p in parts if p]
    if not cleaned:
        return base
    joined = os.path.join(base, *cleaned)
    real = os.path.realpath(joined)
    real_base = os.path.realpath(base)
    if not real.startswith(real_base + os.sep) and real != real_base:
        raise HTTPException(400, f"Path traversal detected: '{joined}' escapes download base directory")
    return real


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
    return Profile(id=0, created_at=now, updated_at=now, **merged.model_dump(exclude_none=True))


def _resolve_output_path(body, profile: Profile) -> str:
    download_base = config.get_download_dir()

    override = getattr(body, "download_path_override", None)
    if override:
        rel = _normalize_rel_path(override)
        if not rel:
            return download_base
        return _safe_join(download_base, rel)

    segments: list[str] = []
    profile_dir = profile.download_directory or ""
    if profile_dir:
        segments.append(_normalize_rel_path(profile_dir))

    output_dir = getattr(body, "output_dir", None)
    if output_dir:
        segments.append(_normalize_rel_path(output_dir))

    playlist_dir = getattr(body, "playlist_directory", None)
    if playlist_dir:
        segments.append(_normalize_rel_path(playlist_dir))

    if not segments:
        return download_base
    return _safe_join(download_base, *segments)


# ── Search / Metadata / Playlist ─────────────────────────────


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


@app.post("/api/download/video", response_model=DownloadTaskCreatedResponse, status_code=202, responses={**_404, **_500, **_503}, summary="Download video", description="Start a background task to download a single video. Accepts profile name or per-request overrides for quality, format, directory, audio-only mode, audio format/quality, and remux target. Returns a task ID for status polling.", tags=["Downloads"])
def download_video(body: DownloadVideoRequest):
    settings = db.get_all_settings()
    profile = _resolve_profile(body.profile_id, body)
    out = _resolve_output_path(body, profile)
    download_base = config.get_download_dir()
    temp_dir = settings.get("temp_directory", "").strip() or "/temp"

    tid = _create_task("video", body.url, body.model_dump(by_alias=True))
    _run_in_background(
        tid, ytdlp.download_video, body.url,
        url=body.url,
        output_dir=out, profile=profile, settings=settings,
        audio_only=body.audio_only,
        audio_format=body.audio_format.value if body.audio_format else None,
        audio_quality=body.audio_quality,
        remux_to=body.remux_to,
        task_id=tid,
        download_base=download_base,
        temp_dir=temp_dir,
    )
    return DownloadTaskCreatedResponse(task_id=tid, status="pending", status_url=f"/api/tasks/{tid}")


@app.post("/api/download/playlist", response_model=DownloadTaskCreatedResponse, status_code=202, responses={**_404, **_500, **_503}, summary="Download playlist", description="Start a background task to download all videos in a playlist. Supports optional index range filtering, audio-only mode, audio format/quality, and remux target. Returns a task ID for status polling.", tags=["Downloads"])
def download_playlist(body: DownloadPlaylistRequest):
    settings = db.get_all_settings()
    profile = _resolve_profile(body.profile_id, body)
    out = _resolve_output_path(body, profile)
    download_base = config.get_download_dir()
    temp_dir = settings.get("temp_directory", "").strip() or "/temp"

    tid = _create_task("playlist", body.url, body.model_dump(by_alias=True))
    _run_in_background(
        tid, ytdlp.download_playlist, body.url,
        url=body.url,
        output_dir=out, profile=profile, settings=settings,
        video_range=body.range,
        audio_only=body.audio_only,
        audio_format=body.audio_format.value if body.audio_format else None,
        audio_quality=body.audio_quality,
        remux_to=body.remux_to,
        task_id=tid,
        include_playlist_dir=body.include_playlist_dir,
        download_base=download_base,
        temp_dir=temp_dir,
    )
    return DownloadTaskCreatedResponse(task_id=tid, status="pending", status_url=f"/api/tasks/{tid}")


# ── Tasks ────────────────────────────────────────────────────


@app.get("/api/tasks/{task_id}", responses=_404, summary="Get task status", description="Poll the status of a background download task by its ID. Returns the current status (pending/running/completed/failed), type, URL, timestamps, and error if any.", tags=["Tasks"])
def get_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return _task_to_response(task)


@app.get("/api/events", summary="Global event stream", description="Persistent SSE connection that streams all task lifecycle events: snapshot, task_created, task_updated. Sends keepalive every 30s.", tags=["Tasks"])
async def event_stream():
    q = _subscribe_global()

    async def event_gen():
        try:
            with _lock:
                tasks_data = [_task_to_response(t) for t in _tasks.values()]
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


@app.post("/api/tasks/{task_id}/cancel", responses=_404_409, summary="Cancel task", description="Cancel a pending, running, or paused task. Terminates the yt-dlp process, removes partial download files, and sets status to `cancelled`.", tags=["Tasks"])
def cancel_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        if task.status not in ("pending", "running", "paused"):
            raise HTTPException(409, f"Cancel task in status '{task.status}'")
    # Lock released before _update_task (which acquires _lock internally)
    _update_task(task_id, status="cancelled")
    ytdlp.cancel_download(task_id)
    return OkResponse(ok=True)


@app.post("/api/tasks/{task_id}/pause", responses=_404_409, summary="Pause task", description="Pause a running download task. The yt-dlp process is terminated but partial files are preserved for resume.", tags=["Tasks"])
def pause_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        if task.status != "running":
            raise HTTPException(409, f"Cannot pause task in status '{task.status}'")
    # Lock released before _update_task (which acquires _lock internally)
    paused = ytdlp.pause_download(task_id)
    if paused:
        _update_task(task_id, status="paused")
    else:
        raise HTTPException(409, "Process not found or already completed")
    return OkResponse(ok=True)


@app.post("/api/tasks/{task_id}/resume", responses=_404_409, summary="Resume task", description="Resume a paused download task. Restarts yt-dlp with --continue to pick up partial files.", tags=["Tasks"])
def resume_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        if task.status != "paused":
            raise HTTPException(409, f"Cannot resume task in status '{task.status}'")
    try:
        _resume_task_download(task)
    except Exception as e:
        with _lock:
            _update_task(task_id, status="failed", error=f"Resume failed: {e}")
        raise HTTPException(500, f"Resume failed: {e}") from e
    return OkResponse(ok=True)


def _resume_task_download(task: TaskInfo) -> None:
    """Re-spawn a download with the same task_id (for resume). Uses --continue."""
    settings = db.get_all_settings()
    download_base = config.get_download_dir()
    temp_dir = settings.get("temp_directory", "").strip() or "/temp"
    params = task.params
    if task.type == "video":
        body = DownloadVideoRequest.model_validate(params)
        profile = _resolve_profile(body.profile_id, body)
        out = _resolve_output_path(body, profile)
        _run_in_background(
            task.id, ytdlp.download_video, body.url,
            url=body.url,
            output_dir=out, profile=profile, settings=settings,
            audio_only=body.audio_only,
            audio_format=body.audio_format.value if body.audio_format else None,
            audio_quality=body.audio_quality,
            remux_to=body.remux_to,
            task_id=task.id,
            download_base=download_base,
            temp_dir=temp_dir,
            continue_download=True,
        )
    else:
        pl_body = DownloadPlaylistRequest.model_validate(params)
        profile = _resolve_profile(pl_body.profile_id, pl_body)
        out = _resolve_output_path(pl_body, profile)
        _run_in_background(
            task.id, ytdlp.download_playlist, pl_body.url,
            url=pl_body.url,
            output_dir=out, profile=profile, settings=settings,
            video_range=pl_body.range,
            audio_only=pl_body.audio_only,
            audio_format=pl_body.audio_format.value if pl_body.audio_format else None,
            audio_quality=pl_body.audio_quality,
            remux_to=pl_body.remux_to,
            task_id=task.id,
            include_playlist_dir=pl_body.include_playlist_dir,
            download_base=download_base,
            temp_dir=temp_dir,
            continue_download=True,
        )


def _re_run_task(task: TaskInfo) -> str:
    settings = db.get_all_settings()
    download_base = config.get_download_dir()
    temp_dir = settings.get("temp_directory", "").strip() or "/temp"
    params = task.params
    if task.type == "video":
        body = DownloadVideoRequest.model_validate(params)
        profile = _resolve_profile(body.profile_id, body)
        out = _resolve_output_path(body, profile)
        tid = _create_task("video", body.url, body.model_dump(by_alias=True))
        _run_in_background(
            tid, ytdlp.download_video, body.url,
            url=body.url,
            output_dir=out, profile=profile, settings=settings,
            audio_only=body.audio_only,
            audio_format=body.audio_format.value if body.audio_format else None,
            audio_quality=body.audio_quality,
            remux_to=body.remux_to,
            task_id=tid,
            download_base=download_base,
            temp_dir=temp_dir,
            continue_download=True,
        )
        return tid
    pl_body = DownloadPlaylistRequest.model_validate(params)
    profile = _resolve_profile(pl_body.profile_id, pl_body)
    out = _resolve_output_path(pl_body, profile)
    tid = _create_task("playlist", pl_body.url, pl_body.model_dump(by_alias=True))
    _run_in_background(
        tid, ytdlp.download_playlist, pl_body.url,
        url=pl_body.url,
        output_dir=out, profile=profile, settings=settings,
        video_range=pl_body.range,
        audio_only=pl_body.audio_only,
        audio_format=pl_body.audio_format.value if pl_body.audio_format else None,
        audio_quality=pl_body.audio_quality,
        remux_to=pl_body.remux_to,
        task_id=tid,
        include_playlist_dir=pl_body.include_playlist_dir,
        download_base=download_base,
        temp_dir=temp_dir,
        continue_download=True,
    )
    return tid


@app.post("/api/tasks/{task_id}/retry", response_model=DownloadTaskCreatedResponse, responses=_404_409, summary="Retry task", description="Retry a failed, paused, or partially-failed download task. Resumes a paused task or creates a new task with the same parameters for failed tasks. Returns the task ID and status URL.", tags=["Tasks"])
def retry_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status not in ("failed", "paused", "cancelled", "completed"):
        raise HTTPException(409, f"Cannot retry task in status '{task.status}'")
    if task.status == "completed" and not task.error:
        raise HTTPException(409, "Task completed successfully with no errors; nothing to retry")

    if task.status == "paused":
        _resume_task_download(task)
        return DownloadTaskCreatedResponse(task_id=task_id, status="pending", status_url=f"/api/tasks/{task_id}")

    tid = _re_run_task(task)
    return DownloadTaskCreatedResponse(task_id=tid, status="pending", status_url=f"/api/tasks/{tid}")


# ── Profiles ─────────────────────────────────────────────────


@app.get("/api/profiles", response_model=list[ProfileResponse], summary="List profiles", description="List all saved download profiles. Each profile bundles quality mode, format string, download directory, and audio/remux settings.", tags=["Profiles"])
def list_profiles(limit: int = Query(50, ge=1, le=200, description="Maximum number of results"), offset: int = Query(0, ge=0, description="Number of results to skip")):
    return db.list_profiles()[offset:][:limit]


@app.post("/api/profiles", response_model=ProfileResponse, status_code=201, responses=_409, summary="Create profile", description="Create a new download profile. Name must be unique. Quality mode can be `best`, `least`, `at_most`, or `at_least` (latter two require a pixel height value).", tags=["Profiles"])
def create_profile(body: ProfileCreateRequest):
    existing = db.get_profile_by_name(body.name)
    if existing:
        raise HTTPException(409, f"Profile '{body.name}' already exists")
    data = body.model_dump()
    dd = data.get("download_directory")
    if dd:
        data["download_directory"] = _normalize_rel_path(dd)
    p = db.create_profile(ProfileCreate(**data))
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
    dd = data.get("download_directory")
    if dd:
        data["download_directory"] = _normalize_rel_path(dd)
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
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except OSError:
        temp_dir = tempfile.gettempdir()
        os.makedirs(temp_dir, exist_ok=True)
    worker_running = any(
        t.name == "download-worker" for t in threading.enumerate()
    )
    download_dir = config.get_download_dir()
    try:
        os.makedirs(download_dir, exist_ok=True)
    except OSError:
        download_dir = tempfile.gettempdir()
    return HealthResponse(
        status="ok",
        has_ffmpeg=ytdlp.HAS_FFMPEG,
        ffmpeg_version=ffmpeg_ver,
        has_ytdlp=ytdlp.HAS_YTDLP,
        ytdlp_version=ytdlp_ver,
        download_directory_writable=os.access(download_dir, os.W_OK),
        temp_directory_writable=os.access(temp_dir, os.W_OK),
        worker_running=worker_running,
        sse_connected=_active_sse_connections() > 0,
    )


@app.get("/api/ready", response_model=HealthResponse, summary="Readiness check", description="Returns 200 when the service is ready to accept requests (always ready in current implementation).", tags=["Health"])
def ready():
    return health()


# ── Files ─────────────────────────────────────────────────────


@app.get("/api/files", response_model=FilesListResponse, summary="List downloaded files", description="List all completed download files across all tasks. Supports search, type filter, and sorting. Returns paginated results with total count.", tags=["Files"])
def list_files(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    search: str | None = Query(None, description="Filter by name or path (case-insensitive)"),
    file_type: str | None = Query(None, alias="fileType", description="Filter by file type (video, audio, playlist, image, other)"),
    sort_by: str | None = Query(None, alias="sortBy", description="Sort field: name, size, created_at (default: newest first)"),
    sort_order: str | None = Query("desc", alias="sortOrder", description="Sort direction: asc or desc"),
):
    download_base = config.get_download_dir().rstrip("/")
    seen: dict[tuple, FileInfo] = {}
    with _lock:
        tasks = list(_tasks.values())
    for task in tasks:
        if task.status not in ("completed",):
            continue
        thumbnail_base = None
        if task.thumbnail_path:
            thumbnail_base = task.thumbnail_path
        for f in (task.result or []):
            fp = f.get("path", "")
            # Skip internal Radarr import copies (files written under a radarr/ subdirectory)
            rel = fp[len(download_base):].lstrip("/") if fp.startswith(download_base) else fp
            if rel.startswith("radarr/"):
                continue
            file_type_val = f.get("fileType") or classify_file_type(fp)
            fmt = f.get("format") or classify_file_format(fp)
            ext = f.get("fileExtension") or classify_file_extension(fp)
            detail = f.get("detail") or fmt
            fi = FileInfo(
                id=f.get("id", str(uuid.uuid4())),
                name=f["name"],
                size=f["size"],
                path=fp,
                file_type=file_type_val,
                format=fmt,
                detail=detail,
                file_extension=ext,
                task_id=task.id,
                source_url=task.url,
                created_at=task.completed_at or task.created_at,
                thumbnail_url=thumbnail_base,
            )
            # Dedup by (name, size) — same content produces same tuple
            key = (f["name"], f["size"])
            if key not in seen:
                seen[key] = fi
    results = list(seen.values())
    # Apply search filter
    if search:
        term = search.lower()
        results = [r for r in results if term in r.name.lower() or term in r.path.lower() or term in r.format.lower()]
    # Apply type filter
    if file_type:
        results = [r for r in results if r.file_type == file_type]
    # Apply sort
    if sort_by == "name":
        results.sort(key=lambda r: r.name.lower(), reverse=(sort_order == "desc"))
    elif sort_by == "size":
        results.sort(key=lambda r: r.size, reverse=(sort_order == "desc"))
    else:
        results.sort(key=lambda r: r.created_at, reverse=(sort_order == "desc"))
    total = len(results)
    return FilesListResponse(items=results[offset:][:limit], total=total)


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


@app.get("/api/files/stats", response_model=FileStatsResponse, summary="File storage statistics", description="Returns aggregate storage statistics: total used, total capacity, and breakdown by file type category.", tags=["Files"])
def file_stats():
    total_used = 0
    categories: dict[str, dict[str, int]] = {
        "video": {"size": 0, "count": 0},
        "audio": {"size": 0, "count": 0},
        "playlist": {"size": 0, "count": 0},
        "image": {"size": 0, "count": 0},
        "other": {"size": 0, "count": 0},
    }
    category_labels = {
        "video": "Videos", "audio": "Audio", "playlist": "Playlists",
        "image": "Images", "other": "Others",
    }
    with _lock:
        tasks = list(_tasks.values())
    for task in tasks:
        if task.status not in ("completed",):
            continue
        for f in (task.result or []):
            size = f.get("size", 0)
            total_used += size
            ft = f.get("fileType") or classify_file_type(f.get("path", ""))
            if ft not in categories:
                ft = "other"
            categories[ft]["size"] += size
            categories[ft]["count"] += 1
    return FileStatsResponse(
        total_used=total_used,
        total_capacity=274877906944,
        categories=[
            FileCategory(type=ft, label=category_labels.get(ft, ft.capitalize()), **stats)
            for ft, stats in categories.items()
        ],
    )


# ── Task list / extended task endpoints ────────────────────────


@app.get("/api/tasks", summary="List all tasks", description="List all download tasks with optional filtering. Supports pagination, status filter, integration filter, and sorting.", tags=["Tasks"])
def list_tasks(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, description="Filter by status: pending, running, completed, failed, cancelled, paused"),
    search: str | None = Query(None, description="Search in title or URL"),
    integration: str | None = Query(None, description="Integration: all, none, radarr"),
    sort_by: str | None = Query(None, alias="sortBy", description="Sort field: created_at, title, status, progress"),
    sort_order: str | None = Query("desc", alias="sortOrder"),
):
    with _lock:
        tasks = list(_tasks.values())

    results = [_task_to_response(t) for t in tasks]

    if status:
        results = [t for t in results if t["status"] == status]
    if search:
        term = search.lower()
        results = [t for t in results if (t.get("title") or "").lower().find(term) >= 0 or t.get("url", "").lower().find(term) >= 0]
    if integration == "radarr":
        results = [t for t in results if t.get("integration") and t["integration"].get("type") == "radarr"]
    elif integration == "none":
        results = [t for t in results if not t.get("integration")]

    if sort_by == "title":
        results.sort(key=lambda t: (t.get("title") or "").lower(), reverse=(sort_order == "desc"))
    elif sort_by == "status":
        results.sort(key=lambda t: t.get("status", ""), reverse=(sort_order == "desc"))
    elif sort_by == "progress":
        results.sort(key=lambda t: t.get("progressPercent", 0), reverse=(sort_order == "desc"))
    else:
        results.sort(key=lambda t: t.get("createdAt", ""), reverse=(sort_order == "desc"))

    total = len(results)
    return {"items": results[offset:][:limit], "total": total}


@app.delete("/api/tasks/{task_id}", responses=_404, summary="Delete task", description="Remove a completed task from the task list.", tags=["Tasks"])
def delete_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
        if task.status not in ("completed", "failed", "cancelled"):
            raise HTTPException(409, f"Cannot delete task in status '{task.status}'")
        del _tasks[task_id]
    return OkResponse(ok=True)


@app.get("/api/tasks/{task_id}/logs", responses=_404, summary="Task logs", description="Get log entries for a specific task.", tags=["Tasks"])
def get_task_logs(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
    return {"taskId": task_id, "logs": []}


@app.get("/api/tasks/{task_id}/files", response_model=FilesListResponse, responses=_404, summary="Task files", description="Get files associated with a specific task.", tags=["Tasks"])
def get_task_files(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
    files = []
    if task.result:
        for f in task.result:
            files.append(FileInfo(
                id=f.get("id", str(uuid.uuid4())),
                name=f["name"],
                size=f["size"],
                path=f["path"],
                file_type=f.get("fileType", classify_file_type(f.get("path", ""))),
                format=f.get("format", classify_file_format(f.get("path", ""))),
                detail=f.get("detail", classify_file_format(f.get("path", ""))),
                file_extension=f.get("fileExtension", classify_file_extension(f.get("path", ""))),
                task_id=task.id,
                source_url=task.url,
                created_at=task.completed_at or task.created_at,
                thumbnail_url=task.thumbnail_path,
            ))
    return FilesListResponse(items=files, total=len(files))


# ── Extended file endpoints ────────────────────────────────────


@app.get("/api/files/{file_id}", summary="Get file detail", description="Get detailed information about a specific file including Radarr import state.", tags=["Files"])
def get_file_detail(file_id: str):
    with _lock:
        tasks_data = list(_tasks.values())
    for task in tasks_data:
        if task.status != "completed":
            continue
        for f in (task.result or []):
            if f.get("id") == file_id:
                return FileInfo(
                    id=file_id,
                    name=f["name"],
                    size=f["size"],
                    path=f["path"],
                    file_type=f.get("fileType", classify_file_type(f.get("path", ""))),
                    format=f.get("format", classify_file_format(f.get("path", ""))),
                    detail=f.get("detail", classify_file_format(f.get("path", ""))),
                    file_extension=f.get("fileExtension", classify_file_extension(f.get("path", ""))),
                    task_id=task.id,
                    source_url=task.url,
                    created_at=task.completed_at or task.created_at,
                    thumbnail_url=task.thumbnail_path,
                    storage_state="local" if os.path.isfile(f["path"]) else "missing",
                    downloadable=os.path.isfile(f["path"]),
                )
    raise HTTPException(404, "File not found")


@app.delete("/api/files/{file_id}", responses=_404, summary="Delete file", description="Delete a downloaded file from disk and remove it from the file list.", tags=["Files"])
def delete_file(file_id: str):
    with _lock:
        tasks_data = list(_tasks.values())
    for task in tasks_data:
        if task.status != "completed":
            continue
        if task.result:
            for i, f in enumerate(task.result):
                if f.get("id") == file_id:
                    path = f["path"]
                    if os.path.isfile(path):
                        os.remove(path)
                    task.result.pop(i)
                    _update_task(task.id, result=task.result)
                    return OkResponse(ok=True)
    raise HTTPException(404, "File not found")


@app.post("/api/files/{file_id}/reveal", responses={**_404, 409: {"model": ErrorResponse}}, summary="Reveal file in folder", description="Open the containing folder in the file manager. Only available in local desktop deployments.", tags=["Files"])
def reveal_file(file_id: str):
    raise HTTPException(409, "Reveal in folder is not available in this deployment")


# ── Radarr API ─────────────────────────────────────────────────


def _get_radarr_instance(instance_id: str):
    inst = db.get_radarr_instance(instance_id)
    if not inst:
        raise HTTPException(404, f"Radarr instance '{instance_id}' not found")
    return inst


def _instance_to_response(inst) -> dict:
    preview = (inst.api_key_encrypted[:8] + "…") if inst.api_key_encrypted else ""
    status = "disabled"
    health_message = None
    if inst.enabled:
        if inst.last_test_status == "ok":
            status = "connected"
        elif inst.last_test_status == "warning":
            status = "warning"
        elif inst.last_test_status == "error":
            status = "error"
            health_message = inst.last_test_message
        else:
            status = "unknown"
    return dict(
        id=inst.id,
        name=inst.name,
        baseUrl=inst.base_url,
        apiKeyPreview=preview,
        tubeWritePath=inst.tube_write_path,
        radarrImportPath=inst.radarr_import_path,
        hostPathHint=inst.host_path_hint,
        defaultProfileId=inst.default_profile_id,
        defaultQualityProfileId=inst.default_quality_profile_id,
        defaultRootFolderPath=inst.default_root_folder_path,
        importMode=inst.import_mode,
        enabled=inst.enabled,
        isDefault=inst.is_default,
        status=status,
        healthMessage=health_message,
        radarrVersion=inst.radarr_version,
        lastSyncAt=inst.last_sync_at.isoformat() if inst.last_sync_at else None,
        lastTestAt=inst.last_test_at.isoformat() if inst.last_test_at else None,
        createdAt=inst.created_at.isoformat() if inst.created_at else None,
        updatedAt=inst.updated_at.isoformat() if inst.updated_at else None,
    )


def _make_radarr_client(instance_id: str) -> RadarrClient:
    inst = _get_radarr_instance(instance_id)
    if not inst.enabled:
        raise HTTPException(400, f"Radarr instance '{inst.name}' is disabled")
    return RadarrClient(inst.base_url, inst.api_key_encrypted)


@app.get("/api/radarr/instances", summary="List Radarr instances", description="Get all configured Radarr instances with status and stats.", tags=["Radarr"])
def list_radarr_instances():
    instances = db.list_radarr_instances()
    return [_instance_to_response(i) for i in instances]


@app.get("/api/radarr/instances/{instance_id}", summary="Get Radarr instance", description="Get a single Radarr instance by ID.", tags=["Radarr"])
def get_radarr_instance(instance_id: str):
    inst = _get_radarr_instance(instance_id)
    return _instance_to_response(inst)


@app.post("/api/radarr/instances", response_model=dict, status_code=201, responses={409: {"model": ErrorResponse}}, summary="Create Radarr instance", description="Add a new Radarr instance connection.", tags=["Radarr"])
def create_radarr_instance(body: RadarrInstanceUpsertRequest):
    existing = db.get_radarr_instance_by_name(body.name)
    if existing:
        raise HTTPException(409, f"Radarr instance '{body.name}' already exists")
    if not body.api_key:
        raise HTTPException(400, "API key is required")
    data = RadarrInstanceCreate(
        name=body.name,
        base_url=body.base_url,
        api_key=body.api_key,
        tube_write_path=body.tube_write_path,
        radarr_import_path=body.radarr_import_path,
        host_path_hint=body.host_path_hint,
        default_profile_id=body.default_profile_id,
        default_quality_profile_id=body.default_quality_profile_id,
        default_root_folder_path=body.default_root_folder_path,
        import_mode=body.import_mode,
        enabled=body.enabled,
    )
    inst = db.create_radarr_instance(data)
    return _instance_to_response(inst)


@app.patch("/api/radarr/instances/{instance_id}", responses=_404, summary="Update Radarr instance", description="Update an existing Radarr instance.", tags=["Radarr"])
def update_radarr_instance(instance_id: str, body: dict):
    _get_radarr_instance(instance_id)
    update = RadarrInstanceUpdate(
        name=body.get("name"),
        base_url=body.get("baseUrl"),
        api_key=body.get("apiKey"),
        tube_write_path=body.get("tubeWritePath"),
        radarr_import_path=body.get("radarrImportPath"),
        host_path_hint=body.get("hostPathHint"),
        default_profile_id=body.get("defaultProfileId"),
        default_quality_profile_id=body.get("defaultQualityProfileId"),
        default_root_folder_path=body.get("defaultRootFolderPath"),
        import_mode=body.get("importMode"),
        enabled=body.get("enabled"),
        is_default=body.get("isDefault"),
    )
    result = db.update_radarr_instance(instance_id, update)
    if not result:
        raise HTTPException(404, "Instance not found after update")
    return _instance_to_response(result)


@app.delete("/api/radarr/instances/{instance_id}", responses=_404, summary="Delete Radarr instance", description="Remove a Radarr instance configuration.", tags=["Radarr"])
def delete_radarr_instance(instance_id: str):
    _get_radarr_instance(instance_id)
    db.delete_radarr_instance(instance_id)
    return OkResponse(ok=True)


@app.post("/api/radarr/instances/{instance_id}/test", summary="Test Radarr connection", description="Test connection, API key, path writability, and root folder access for a Radarr instance.", tags=["Radarr"])
def test_radarr_instance(instance_id: str, body: RadarrInstanceTestRequest | None = None):
    base_url = body.base_url if body else None
    api_key = body.api_key if body else None
    write_path = body.tube_write_path if body else None

    test_base_url = None
    test_api_key = None
    test_write_path = None

    if base_url and api_key:
        test_base_url = base_url
        test_api_key = api_key
        test_write_path = write_path
    else:
        inst = _get_radarr_instance(instance_id)
        test_base_url = inst.base_url
        test_api_key = inst.api_key_encrypted
        test_write_path = inst.tube_write_path

    warnings_list = []
    errors_list = []

    try:
        client = RadarrClient(test_base_url, test_api_key)
        can_ping = client.ping()
        status_data = client.get_system_status()
        version = status_data.get("version", "unknown")
    except RadarrError as e:
        version = None
        db.set_radarr_instance_test_result(instance_id, "error", str(e))
        return dict(
            ok=False, canConnect=False, apiKeyValid=False,
            tubeWritePathWritable=False, radarrRootFoldersLoaded=False,
            radarrVersion=None, warnings=warnings_list, errors=[str(e)],
        )

    can_connect = can_ping
    api_key_valid = can_connect

    tube_writable = False
    if test_write_path:
        try:
            test_file = os.path.join(test_write_path, f".tube_test_{uuid.uuid4().hex[:8]}")
            os.makedirs(test_write_path, exist_ok=True)
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            tube_writable = True
        except OSError as e:
            errors_list.append(f"Tube Explore write path not writable: {e}")

    root_folders_loaded = False
    try:
        root_folders = client.get_root_folders()
        root_folders_loaded = True
    except Exception as e:
        warnings_list.append(f"Could not load root folders: {e}")

    ok_flag = can_connect and api_key_valid and tube_writable
    status = "ok" if ok_flag else "warning" if can_connect else "error"

    db.set_radarr_instance_test_result(instance_id, status, str(errors_list[0]) if errors_list else None, version)

    return dict(
        ok=ok_flag,
        canConnect=can_connect,
        apiKeyValid=api_key_valid,
        tubeWritePathWritable=tube_writable,
        radarrRootFoldersLoaded=root_folders_loaded,
        radarrVersion=version,
        warnings=warnings_list,
        errors=errors_list,
    )


@app.post("/api/radarr/instances/{instance_id}/sync", summary="Sync Radarr instance", description="Trigger a sync for a Radarr instance. Updates stats, missing movie cache, and instance health.", tags=["Radarr"])
def sync_radarr_instance(instance_id: str):
    inst = _get_radarr_instance(instance_id)
    if not inst.enabled:
        raise HTTPException(400, f"Instance '{inst.name}' is disabled")
    try:
        client = RadarrClient(inst.base_url, inst.api_key_encrypted)
        status_data = client.get_system_status()
        version = status_data.get("version", inst.radarr_version)

        root_folders = client.get_root_folders()
        quality_profiles = client.get_quality_profiles()

        all_movies = client.get_missing_movies()
        movies = all_movies if isinstance(all_movies, list) else all_movies.get("records", [])

        missing = [m for m in movies if not m.get("hasFile", True)]
        monitored = [m for m in movies if m.get("monitored", False)]

        db.upsert_radarr_instance_stats(instance_id, {
            "missing_count": len(missing),
            "monitored_count": len(monitored),
            "unmonitored_missing_count": len([m for m in missing if not m.get("monitored", False)]),
            "root_folder_count": len(root_folders),
            "queue_count": 0,
            "imports_24h": 0,
        })

        db.set_radarr_instance_sync_result(instance_id, "ok")
        if inst.radarr_version != version:
            db.set_radarr_instance_test_result(instance_id, "ok", None, version)

        _broadcast("radarr_sync_completed", {"instanceId": instance_id, "instanceName": inst.name})

        return _instance_to_response(db.get_radarr_instance(instance_id))
    except RadarrError as e:
        db.set_radarr_instance_sync_result(instance_id, "error", str(e))
        _broadcast("radarr_sync_failed", {"instanceId": instance_id, "instanceName": inst.name, "error": str(e)})
        raise HTTPException(500, f"Sync failed: {e}")


@app.post("/api/radarr/download", response_model=DownloadTaskCreatedResponse, status_code=202, responses=_500, summary="Download for Radarr", description="Download a video and link it to a Radarr movie for import.", tags=["Radarr"])
def radarr_download(body: RadarrMovieDownloadRequest):
    inst = None
    if body.instance_id:
        inst = _get_radarr_instance(body.instance_id)
    settings = db.get_all_settings()
    download_base = config.get_download_dir()
    temp_dir = settings.get("temp_directory", "").strip() or "/temp"

    params = body.model_dump(by_alias=True)
    tid = _create_task("video", body.url, params)
    with _lock:
        task = _tasks.get(tid)
        if task:
            integration_meta: dict[str, object] = {}
            if inst:
                integration_meta = {
                    "instanceId": inst.id,
                    "instanceName": inst.name,
                }
            if body.movie_id:
                integration_meta["movieId"] = body.movie_id
            if body.movie_title:
                integration_meta["movieTitle"] = body.movie_title
            if body.movie_year:
                integration_meta["movieYear"] = body.movie_year
            task = task.model_copy(update={
                "integration": "radarr",
                "integration_meta": integration_meta,
            })
            _tasks[tid] = task
    _run_in_background(
        tid, ytdlp.download_video, body.url,
        url=body.url,
        output_dir=download_base,
        profile=_resolve_profile(body.profile_id, body),
        settings=settings,
        task_id=tid,
        download_base=download_base,
        temp_dir=temp_dir,
    )
    return DownloadTaskCreatedResponse(task_id=tid, status="pending", status_url=f"/api/tasks/{tid}")


@app.post("/api/radarr/instances/{instance_id}/set-default", responses=_404, summary="Set default Radarr instance", description="Set a Radarr instance as the default.", tags=["Radarr"])
def set_default_radarr_instance(instance_id: str):
    _get_radarr_instance(instance_id)
    db.update_radarr_instance(instance_id, RadarrInstanceUpdate(is_default=True))
    return OkResponse(ok=True)


@app.get("/api/radarr/summary", summary="Radarr summary", description="Aggregate Radarr summary for the overview page.", tags=["Radarr"])
def radarr_summary():
    instances = db.list_radarr_instances()
    total = len(instances)
    active = sum(1 for i in instances if i.enabled and i.last_test_status == "ok")
    missing = 0
    monitored = 0
    imports_24h = 0
    statuses: dict[str, int] = {}
    last_sync = None

    for inst in instances:
        stats_key = inst.last_test_status or "unknown"
        statuses[stats_key] = statuses.get(stats_key, 0) + 1
        if inst.last_sync_at and (last_sync is None or inst.last_sync_at > last_sync):
            last_sync = inst.last_sync_at

    return dict(
        totalInstances=total,
        activeConnections=active,
        missingMovies=missing,
        monitoredMovies=monitored,
        imports24h=imports_24h,
        lastSyncAt=last_sync.isoformat() if last_sync else None,
        instanceStatuses=statuses,
    )


@app.get("/api/radarr/instances/{instance_id}/missing", summary="List missing movies", description="Get missing movies for a Radarr instance.", tags=["Radarr"])
def list_missing_movies(
    instance_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
    monitored: str | None = Query(None, description="all, monitored, unmonitored"),
    sort_by: str | None = Query(None, alias="sortBy"),
    sort_order: str | None = Query("asc", alias="sortOrder"),
):
    inst = _get_radarr_instance(instance_id)
    if not inst.enabled:
        raise HTTPException(400, f"Radarr instance '{inst.name}' is disabled")
    try:
        client = RadarrClient(inst.base_url, inst.api_key_encrypted)
        all_movies = client.get_missing_movies()
        movies = all_movies if isinstance(all_movies, list) else all_movies.get("records", [])

        results = []
        for m in movies:
            if m.get("hasFile", False):
                continue
            results.append(dict(
                instanceId=instance_id,
                movieId=m["id"],
                title=m.get("title", "Unknown"),
                year=m.get("year"),
                tmdbId=m.get("tmdbId"),
                imdbId=m.get("imdbId"),
                monitored=m.get("monitored", False),
                hasFile=m.get("hasFile", False),
                qualityProfileId=m.get("qualityProfileId"),
                qualityProfileName=None,
                rootFolderPath=m.get("rootFolderPath"),
                moviePath=m.get("path"),
                posterUrl=m.get("images", [{}])[0].get("remoteUrl") if m.get("images") else None,
                overview=m.get("overview"),
                radarrUrl=f"{inst.base_url.rstrip('/')}/movie/{m.get('id')}",
            ))

        if search:
            term = search.lower()
            results = [r for r in results if term in r["title"].lower() or (r.get("overview") or "").lower().find(term) >= 0]
        if monitored == "monitored":
            results = [r for r in results if r.get("monitored")]
        elif monitored == "unmonitored":
            results = [r for r in results if not r.get("monitored")]

        if sort_by == "year":
            results.sort(key=lambda r: r.get("year") or 0, reverse=(sort_order == "desc"))
        elif sort_by == "qualityProfile":
            results.sort(key=lambda r: r.get("qualityProfileName") or "", reverse=(sort_order == "desc"))
        else:
            results.sort(key=lambda r: r["title"].lower(), reverse=(sort_order == "desc"))

        total = len(results)
        return dict(
            items=results[offset:][:limit],
            total=total,
            instance=dict(id=inst.id, name=inst.name, baseUrl=inst.base_url, status=inst.last_test_status),
        )
    except RadarrError as e:
        raise HTTPException(500, str(e))


@app.get("/api/radarr/instances/{instance_id}/root-folders", summary="List root folders", description="Get Radarr root folders for an instance.", tags=["Radarr"])
def list_root_folders(instance_id: str):
    client = _make_radarr_client(instance_id)
    try:
        folders = client.get_root_folders()
        return [dict(id=f["id"], path=f["path"], accessible=True, freeSpace=f.get("freeSpace")) for f in folders]
    except RadarrError as e:
        raise HTTPException(500, str(e))


@app.get("/api/radarr/instances/{instance_id}/quality-profiles", summary="List quality profiles", description="Get Radarr quality profiles for an instance.", tags=["Radarr"])
def list_quality_profiles(instance_id: str):
    client = _make_radarr_client(instance_id)
    try:
        profiles = client.get_quality_profiles()
        return [dict(id=p["id"], name=p["name"]) for p in profiles]
    except RadarrError as e:
        raise HTTPException(500, str(e))


@app.get("/api/radarr/instances/{instance_id}/queue", summary="Get queue", description="Get the Radarr queue for an instance.", tags=["Radarr"])
def get_radarr_queue(instance_id: str):
    client = _make_radarr_client(instance_id)
    try:
        queue = client.get_queue()
        items = queue if isinstance(queue, list) else queue.get("records", [])
        return [dict(movieId=i.get("movieId"), movieTitle=i.get("title", ""), status=i.get("status", "")) for i in items]
    except RadarrError as e:
        raise HTTPException(500, str(e))


@app.get("/api/radarr/instances/{instance_id}/sync-history", summary="Get sync history", description="Get sync history for a Radarr instance.", tags=["Radarr"])
def get_sync_history(instance_id: str):
    _get_radarr_instance(instance_id)
    return {"instanceId": instance_id, "history": []}


@app.get("/api/radarr/instances/{instance_id}/test-results", summary="Get test results", description="Get the last test result for a Radarr instance.", tags=["Radarr"])
def get_test_results(instance_id: str):
    inst = _get_radarr_instance(instance_id)
    return dict(
        instanceId=inst.id,
        name=inst.name,
        lastTestStatus=inst.last_test_status,
        lastTestMessage=inst.last_test_message,
        lastTestAt=inst.last_test_at.isoformat() if inst.last_test_at else None,
        radarrVersion=inst.radarr_version,
    )


@app.get("/api/radarr/tasks/{task_id}", summary="Get Radarr task integration", description="Get Radarr integration details for a specific task.", tags=["Radarr"])
def get_radarr_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
    if not task.integration or task.integration != "radarr":
        raise HTTPException(404, "Task is not a Radarr-linked task")
    meta = task.integration_meta or {}

    link = None
    for lid in [meta.get("downloadLinkId")]:
        if lid:
            link = lid
            break

    return dict(
        taskId=task.id,
        radarrInstanceId=meta.get("instanceId", ""),
        radarrInstanceName=meta.get("instanceName", ""),
        radarrMovieId=meta.get("movieId", 0),
        title=meta.get("movieTitle", task.title or task.url),
        year=meta.get("movieYear"),
        downloadStatus=task.status,
        importStatus=meta.get("importStatus", "none"),
        importMode=meta.get("importMode", "move"),
        localFilePath=meta.get("localPath"),
        radarrFilePath=meta.get("radarrPath"),
        errorCode=meta.get("importError"),
        errorMessage=task.error,
        startedAt=task.created_at.isoformat() if task.created_at else None,
        completedAt=task.completed_at.isoformat() if task.completed_at else None,
    )


@app.post("/api/radarr/tasks/{task_id}/import/retry", responses=_404, summary="Retry Radarr import", description="Retry a failed Radarr import for a task.", tags=["Radarr"])
def retry_radarr_import(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
    if not task.integration or task.integration != "radarr":
        raise HTTPException(404, "Task is not a Radarr-linked task")

    meta = task.integration_meta or {}
    meta["importStatus"] = "waiting_for_import"
    meta.pop("importError", None)
    _update_task(task_id, integration_meta=meta)
    _broadcast("radarr_import_updated", {"taskId": task_id, "importStatus": "waiting_for_import"})
    return OkResponse(ok=True)


@app.post("/api/radarr/tasks/{task_id}/import/cancel", responses=_404, summary="Cancel Radarr import", description="Cancel a pending or in-progress Radarr import.", tags=["Radarr"])
def cancel_radarr_import(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
    if not task.integration or task.integration != "radarr":
        raise HTTPException(404, "Task is not a Radarr-linked task")

    meta = task.integration_meta or {}
    meta["importStatus"] = "cancelled"
    _update_task(task_id, integration_meta=meta)
    _broadcast("radarr_import_updated", {"taskId": task_id, "importStatus": "cancelled"})
    return OkResponse(ok=True)


@app.exception_handler(RequestValidationError)
async def _validation_exc(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content=ErrorResponse(detail=str(exc)).model_dump(by_alias=True))


@app.exception_handler(HTTPException)
async def _http_exc(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=ErrorResponse(detail=exc.detail).model_dump(by_alias=True))


# ── Thumbnail serving ─────────────────────────────────────────
_THUMBNAIL_DIR = os.path.join(config.get_metadata_dir(), "thumbnails")
os.makedirs(_THUMBNAIL_DIR, exist_ok=True)
app.mount("/api/thumbnails", StaticFiles(directory=_THUMBNAIL_DIR), name="thumbnails")


# ── UI static file serving ────────────────────────────────────


UI_BUILD_DIR = Path(__file__).resolve().parent.parent / "web-ui" / "build"
_HAS_UI = UI_BUILD_DIR.is_dir()


if _HAS_UI:
    app.mount("/_app", StaticFiles(directory=str(UI_BUILD_DIR / "_app")), name="ui_assets")

    @app.get("/favicon.svg")
    async def _ui_favicon():
        return FileResponse(str(UI_BUILD_DIR / "favicon.svg"))

    @app.get("/{full:path}")
    async def _ui_index(full: str):
        if full.startswith("api/") or full == "openapi.json" or full.startswith("docs"):
            raise HTTPException(404, "Not found")
        return FileResponse(str(UI_BUILD_DIR / "index.html"))
