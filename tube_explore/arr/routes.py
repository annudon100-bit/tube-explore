from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from tube_explore import config, db, ytdlp
from tube_explore.arr import db as arr_db
from tube_explore.arr.base_client import ArrError
from tube_explore.arr.crypto import decrypt_api_key, encrypt_api_key
from tube_explore.arr.models import ArrInstance, ArrInstanceCreate, ArrInstanceUpdate
from tube_explore.arr.path_mapper import map_tube_path_to_arr_path, to_arr_path
from tube_explore.arr.radarr_client import RadarrClient
from tube_explore.arr.schemas import (
    ArrDownloadRequest,
    ArrInstanceTestRequest,
    ArrInstanceUpsertRequest,
    CreatePlaylistMappingRequest,
    PlaylistInspectRequest,
    UpdatePlaylistMappingRequest,
)
from tube_explore.arr.sonarr_client import SonarrClient
from tube_explore.arr.sonarr_playlist_worker import SonarrPlaylistDownloadWorker
from tube_explore.config import get_config_dir

logger = logging.getLogger(__name__)

# ── Task store access (shared with api.py) ──────────────────────

_tasks: dict = {}
_lock: threading.Lock = threading.Lock()
_broadcast: Any = lambda _e, _d: None
_main_loop: asyncio.AbstractEventLoop | None = None
_worker: SonarrPlaylistDownloadWorker | None = None

ArrKind = Literal["radarr", "sonarr"]


def _wire(task_store: dict, task_lock: threading.Lock, broadcast_fn, loop):
    global _tasks, _lock, _broadcast, _main_loop, _worker
    _tasks = task_store
    _lock = task_lock
    _broadcast = broadcast_fn
    _main_loop = loop
    _worker = SonarrPlaylistDownloadWorker(_tasks, _lock, _broadcast, _main_loop)


# ── Shared helpers ──────────────────────────────────────────────

router = APIRouter(prefix="/api/arr", tags=["Arr"])


def _get_arr_instance(instance_id: str) -> ArrInstance:
    inst = arr_db.get_arr_instance(instance_id)
    if not inst:
        raise HTTPException(404, f"Instance '{instance_id}' not found")
    return inst


def _make_arr_client(instance_id: str) -> RadarrClient | SonarrClient:
    inst = _get_arr_instance(instance_id)
    if not inst.enabled:
        raise HTTPException(400, f"Instance '{inst.name}' is disabled")
    decrypted = decrypt_api_key(inst.api_key_encrypted, get_config_dir())
    if inst.kind == "radarr":
        return RadarrClient(inst.base_url, decrypted)
    return SonarrClient(inst.base_url, decrypted)


def _instance_to_response(inst: ArrInstance) -> dict:
    preview = (inst.api_key_encrypted[:8] + "\u2026") if inst.api_key_encrypted else ""
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
        kind=inst.kind,
        apiKeyPreview=preview,
        tubeWritePath=inst.tube_write_path,
        arrImportPath=inst.arr_import_path,
        hostPathHint=inst.host_path_hint,
        defaultProfileId=inst.default_profile_id,
        defaultQualityProfileId=inst.default_quality_profile_id,
        defaultRootFolderPath=inst.default_root_folder_path,
        importMode=inst.import_mode,
        enabled=inst.enabled,
        isDefault=inst.is_default,
        status=status,
        healthMessage=health_message,
        arrVersion=inst.arr_version,
        lastSyncAt=inst.last_sync_at.isoformat() if inst.last_sync_at else None,
        lastTestAt=inst.last_test_at.isoformat() if inst.last_test_at else None,
        createdAt=inst.created_at.isoformat() if inst.created_at else None,
        updatedAt=inst.updated_at.isoformat() if inst.updated_at else None,
    )


def _camel_to_snake(name: str) -> str:
    import re
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


# ── Instance CRUD ────────────────────────────────────────────────


@router.get("/instances", summary="List Arr instances")
def list_arr_instances(kind: str | None = Query(None, description="Filter by kind: radarr, sonarr")):
    kind_val: ArrKind | None = kind if kind in ("radarr", "sonarr") else None
    instances = arr_db.list_arr_instances(kind_val)
    return [_instance_to_response(i) for i in instances]


@router.get("/instances/{instance_id}", summary="Get Arr instance")
def get_arr_instance(instance_id: str):
    inst = _get_arr_instance(instance_id)
    return _instance_to_response(inst)


@router.post("/instances", status_code=201, summary="Create Arr instance")
def create_arr_instance(body: ArrInstanceUpsertRequest):
    existing = arr_db.get_arr_instance_by_name(body.name)
    if existing:
        raise HTTPException(409, f"Instance '{body.name}' already exists")
    if not body.api_key:
        raise HTTPException(400, "API key is required")

    encrypted = encrypt_api_key(body.api_key, get_config_dir())
    data = ArrInstanceCreate(
        name=body.name,
        base_url=body.base_url,
        api_key=encrypted,
        kind=body.kind,
        tube_write_path=body.tube_write_path,
        arr_import_path=body.arr_import_path,
        host_path_hint=body.host_path_hint,
        default_profile_id=body.default_profile_id,
        default_quality_profile_id=body.default_quality_profile_id,
        default_root_folder_path=body.default_root_folder_path,
        import_mode=body.import_mode,
        enabled=body.enabled,
    )
    inst = arr_db.create_arr_instance(data)
    return _instance_to_response(inst)


@router.patch("/instances/{instance_id}", summary="Update Arr instance")
def update_arr_instance(instance_id: str, body: dict):
    _get_arr_instance(instance_id)
    kwargs: dict[str, Any] = {}
    field_map = {
        "name": "name",
        "baseUrl": "base_url",
        "apiKey": "api_key",
        "tubeWritePath": "tube_write_path",
        "arrImportPath": "arr_import_path",
        "hostPathHint": "host_path_hint",
        "defaultProfileId": "default_profile_id",
        "defaultQualityProfileId": "default_quality_profile_id",
        "defaultRootFolderPath": "default_root_folder_path",
        "importMode": "import_mode",
        "enabled": "enabled",
        "isDefault": "is_default",
    }
    for camel, snake in field_map.items():
        if camel in body:
            kwargs[snake] = body[camel]
    if "api_key" in kwargs and kwargs["api_key"]:
        kwargs["api_key"] = encrypt_api_key(str(kwargs["api_key"]), get_config_dir())
    else:
        kwargs.pop("api_key", None)

    update = ArrInstanceUpdate(**kwargs)
    result = arr_db.update_arr_instance(instance_id, update)
    if not result:
        raise HTTPException(404, "Instance not found after update")
    return _instance_to_response(result)


@router.delete("/instances/{instance_id}", summary="Delete Arr instance")
def delete_arr_instance(instance_id: str):
    _get_arr_instance(instance_id)
    arr_db.delete_arr_instance(instance_id)
    return {"ok": True}


@router.post("/instances/{instance_id}/set-default", summary="Set default Arr instance")
def set_default_arr_instance(instance_id: str):
    _get_arr_instance(instance_id)
    arr_db.update_arr_instance(instance_id, ArrInstanceUpdate(is_default=True))
    return {"ok": True}


# ── Test / Sync ──────────────────────────────────────────────────


@router.post("/instances/{instance_id}/test", summary="Test Arr connection")
def test_arr_instance(instance_id: str, body: ArrInstanceTestRequest | None = None):
    config_dir = get_config_dir()

    test_base_url = body.base_url if (body and body.base_url) else None
    test_api_key = body.api_key if (body and body.api_key) else None
    test_write_path = body.tube_write_path if (body and body.tube_write_path) else None

    client_kind: ArrKind = "radarr"
    if test_base_url and test_api_key:
        pass  # Use provided values, skip instance lookup
        # Try to determine kind from instance if it exists
        existing_inst = arr_db.get_arr_instance(instance_id)
        if existing_inst:
            client_kind = existing_inst.kind
    else:
        inst = _get_arr_instance(instance_id)
        client_kind = inst.kind
        test_base_url = inst.base_url
        test_api_key = decrypt_api_key(inst.api_key_encrypted, config_dir)
        test_write_path = inst.tube_write_path

    warnings_list: list[str] = []
    errors_list: list[str] = []

    try:
        if client_kind == "radarr":
            client = RadarrClient(test_base_url, test_api_key)
        else:
            client = SonarrClient(test_base_url, test_api_key)
        can_ping = client.ping()
        status_data = client.get_system_status()
        version = status_data.get("version", "unknown")
    except ArrError as e:
        version = None
        arr_db.set_arr_instance_test_result(instance_id, "error", str(e))
        return dict(
            ok=False, canConnect=False, apiKeyValid=False,
            tubeWritePathWritable=False, rootFoldersLoaded=False,
            arrVersion=None, warnings=warnings_list, errors=[str(e)],
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

    arr_db.set_arr_instance_test_result(instance_id, status, str(errors_list[0]) if errors_list else None, version)

    return dict(
        ok=ok_flag,
        canConnect=can_connect,
        apiKeyValid=api_key_valid,
        tubeWritePathWritable=tube_writable,
        rootFoldersLoaded=root_folders_loaded,
        arrVersion=version,
        warnings=warnings_list,
        errors=errors_list,
    )


@router.post("/instances/{instance_id}/sync", summary="Sync Arr instance")
def sync_arr_instance(instance_id: str):
    inst = _get_arr_instance(instance_id)
    if not inst.enabled:
        raise HTTPException(400, f"Instance '{inst.name}' is disabled")

    config_dir = get_config_dir()
    decrypted = decrypt_api_key(inst.api_key_encrypted, config_dir)

    try:
        if inst.kind == "radarr":
            client = RadarrClient(inst.base_url, decrypted)
            status_data = client.get_system_status()
            version = status_data.get("version", inst.arr_version)
            root_folders = client.get_root_folders()
            all_movies = client.get_missing_movies()
            movies = all_movies if isinstance(all_movies, list) else all_movies.get("records", [])
            missing = [m for m in movies if not m.get("hasFile", True)]
            monitored = [m for m in movies if m.get("monitored", False)]

            arr_db.upsert_arr_instance_stats(instance_id, {
                "missing_count": len(missing),
                "monitored_count": len(monitored),
                "unmonitored_missing_count": len([m for m in missing if not m.get("monitored", False)]),
                "root_folder_count": len(root_folders),
                "queue_count": 0,
                "imports_24h": 0,
            })
        else:
            client = SonarrClient(inst.base_url, decrypted)
            status_data = client.get_system_status()
            version = status_data.get("version", inst.arr_version)
            root_folders = client.get_root_folders()
            wanted = client.get_wanted_missing()
            episodes = wanted if isinstance(wanted, list) else wanted.get("records", [])
            missing_count = len(episodes)

            arr_db.upsert_arr_instance_stats(instance_id, {
                "missing_count": missing_count,
                "monitored_count": 0,
                "unmonitored_missing_count": 0,
                "root_folder_count": len(root_folders),
                "queue_count": 0,
                "imports_24h": 0,
            })

        arr_db.set_arr_instance_sync_result(instance_id, "ok")
        if inst.arr_version != version:
            arr_db.set_arr_instance_test_result(instance_id, "ok", None, version)

        _broadcast("arr_sync_completed", {"instanceId": instance_id, "instanceName": inst.name, "kind": inst.kind})
        return _instance_to_response(arr_db.get_arr_instance(instance_id))

    except ArrError as e:
        arr_db.set_arr_instance_sync_result(instance_id, "error", str(e))
        _broadcast("arr_sync_failed", {"instanceId": instance_id, "instanceName": inst.name, "error": str(e), "kind": inst.kind})
        raise HTTPException(500, f"Sync failed: {e}")


# ── Summary ──────────────────────────────────────────────────────


@router.get("/summary", summary="Arr summary")
def arr_summary():
    instances = arr_db.list_arr_instances()
    total = len(instances)
    active = sum(1 for i in instances if i.enabled and i.last_test_status == "ok")
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
        missingItems=0,
        monitoredItems=0,
        imports24h=0,
        lastSyncAt=last_sync.isoformat() if last_sync else None,
        instanceStatuses=statuses,
    )


# ── Root folders / Quality profiles / Queue ─────────────────────


@router.get("/instances/{instance_id}/root-folders", summary="List root folders")
def list_root_folders(instance_id: str):
    client = _make_arr_client(instance_id)
    try:
        folders = client.get_root_folders()
        return [dict(id=f["id"], path=f["path"], accessible=True, freeSpace=f.get("freeSpace")) for f in folders]
    except ArrError as e:
        raise HTTPException(500, str(e))


@router.get("/instances/{instance_id}/quality-profiles", summary="List quality profiles")
def list_quality_profiles(instance_id: str):
    client = _make_arr_client(instance_id)
    try:
        profiles = client.get_quality_profiles()
        return [dict(id=p["id"], name=p["name"]) for p in profiles]
    except ArrError as e:
        raise HTTPException(500, str(e))


@router.get("/instances/{instance_id}/queue", summary="Get queue")
def get_arr_queue(instance_id: str):
    client = _make_arr_client(instance_id)
    try:
        queue_data = client.get_queue()
        items = queue_data if isinstance(queue_data, list) else queue_data.get("records", [])
        return [dict(itemId=i.get("movieId") or i.get("seriesId"), itemTitle=i.get("title", ""), status=i.get("status", "")) for i in items]
    except ArrError as e:
        raise HTTPException(500, str(e))


# ── Missing items ────────────────────────────────────────────────


@router.get("/instances/{instance_id}/missing", summary="List missing items")
def list_missing_items(
    instance_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
):
    inst = _get_arr_instance(instance_id)
    if not inst.enabled:
        raise HTTPException(400, f"Instance '{inst.name}' is disabled")

    config_dir = get_config_dir()
    decrypted = decrypt_api_key(inst.api_key_encrypted, config_dir)

    try:
        if inst.kind == "radarr":
            return _list_missing_radarr(inst, decrypted, limit, offset, search)
        else:
            return _list_missing_sonarr(inst, decrypted, limit, offset, search)
    except ArrError as e:
        raise HTTPException(500, str(e))


def _list_missing_radarr(inst: ArrInstance, api_key: str, limit: int, offset: int, search: str | None):
    client = RadarrClient(inst.base_url, api_key)
    # Paginate through ALL pages of monitored movies
    all_movies: list[dict] = []
    page = 1
    total_records = None
    page_size = 200
    while True:
        raw = client.get_missing_movies({"pageSize": page_size, "page": page})
        records = raw if isinstance(raw, list) else raw.get("records", [])
        all_movies.extend(records)
        if total_records is None:
            total_records = raw.get("totalRecords") if isinstance(raw, dict) else len(records)
        if total_records is not None and len(all_movies) >= total_records:
            break
        if not records:
            break
        page += 1
    movies = all_movies

    results = []
    for m in movies:
        if m.get("hasFile", False):
            continue
        results.append(dict(
            instanceId=inst.id,
            itemId=m["id"],
            kind="radarr",
            title=m.get("title", "Unknown"),
            year=m.get("year"),
            tmdbId=m.get("tmdbId"),
            imdbId=m.get("imdbId"),
            monitored=m.get("monitored", False),
            hasFile=m.get("hasFile", False),
            qualityProfileId=m.get("qualityProfileId"),
            qualityProfileName=None,
            rootFolderPath=m.get("rootFolderPath"),
            itemPath=m.get("path"),
            posterUrl=m.get("images", [{}])[0].get("remoteUrl") if m.get("images") else None,
            overview=m.get("overview"),
            arrUrl=f"{inst.base_url.rstrip('/')}/movie/{m.get('id')}",
        ))

    if search:
        term = search.lower()
        results = [r for r in results if term in r["title"].lower() or (r.get("overview") or "").lower().find(term) >= 0]

    results.sort(key=lambda r: r["title"].lower())
    total = len(results)
    return dict(
        items=results[offset:][:limit],
        total=total,
        instance=dict(id=inst.id, name=inst.name, baseUrl=inst.base_url, status=inst.last_test_status, kind="radarr"),
    )


def _list_missing_sonarr(inst: ArrInstance, api_key: str, limit: int, offset: int, search: str | None):
    client = SonarrClient(inst.base_url, api_key)
    # Paginate through ALL pages of wanted/missing
    all_episodes: list[dict] = []
    page = 1
    total_records = None
    page_size = 200

    while True:
        wanted = client.get_wanted_missing({"pageSize": page_size, "page": page})
        records = wanted if isinstance(wanted, list) else wanted.get("records", [])
        all_episodes.extend(records)

        if total_records is None:
            total_records = wanted.get("totalRecords") if isinstance(wanted, dict) else len(records)
        if total_records is not None and len(all_episodes) >= total_records:
            break
        if not records:
            break
        page += 1

    episodes = all_episodes

    # Fetch series titles for context
    series_cache: dict[int, str] = {}
    for ep in episodes:
        sid = ep.get("seriesId")
        if sid and sid not in series_cache:
            try:
                series = client.get_series(sid)
                series_cache[sid] = series.get("title", "Unknown")
            except Exception:
                series_cache[sid] = "Unknown"

    results = []
    for ep in episodes:
        sid = ep.get("seriesId")
        series_title = series_cache.get(sid, "Unknown")
        results.append(dict(
            instanceId=inst.id,
            itemId=ep["id"],
            kind="sonarr",
            title=f"{series_title} S{ep.get('seasonNumber', '?')}E{ep.get('episodeNumber', '?')} - {ep.get('title', 'Unknown')}",
            seriesTitle=series_title,
            seasonNumber=ep.get("seasonNumber"),
            episodeNumber=ep.get("episodeNumber"),
            seriesId=sid,
            monitored=ep.get("monitored", False),
            hasFile=ep.get("hasFile", False),
            airDate=ep.get("airDateUtc"),
            overview=ep.get("overview"),
            arrUrl=f"{inst.base_url.rstrip('/')}/episode/{ep.get('id')}",
        ))

    if search:
        term = search.lower()
        results = [r for r in results if term in r["title"].lower() or term in r.get("seriesTitle", "").lower()]

    results.sort(key=lambda r: r.get("seasonNumber", 0) or 0)
    total = len(results)
    return dict(
        items=results[offset:][:limit],
        total=total,
        instance=dict(id=inst.id, name=inst.name, baseUrl=inst.base_url, status=inst.last_test_status, kind="sonarr"),
    )


# ── Sync history / Test results ─────────────────────────────────


@router.get("/instances/{instance_id}/sync-history", summary="Get sync history")
def get_sync_history(instance_id: str):
    _get_arr_instance(instance_id)
    return {"instanceId": instance_id, "history": []}


@router.get("/instances/{instance_id}/test-results", summary="Get test results")
def get_test_results(instance_id: str):
    inst = _get_arr_instance(instance_id)
    return dict(
        instanceId=inst.id,
        name=inst.name,
        kind=inst.kind,
        lastTestStatus=inst.last_test_status,
        lastTestMessage=inst.last_test_message,
        lastTestAt=inst.last_test_at.isoformat() if inst.last_test_at else None,
        arrVersion=inst.arr_version,
    )


# ── Sonarr-specific series/episode endpoints ────────────────────


@router.get("/instances/{instance_id}/series", summary="List series (Sonarr)")
def list_series(instance_id: str):
    client = _make_arr_client(instance_id)
    if not isinstance(client, SonarrClient):
        raise HTTPException(400, "Instance is not a Sonarr instance")
    try:
        series_list = client.list_series()
        return [dict(
            id=s["id"], title=s.get("title", ""), year=s.get("year"),
            tvdbId=s.get("tvdbId"), imdbId=s.get("imdbId"),
            images=s.get("images"), overview=s.get("overview"),
            monitored=s.get("monitored", False),
            seasonCount=len(s.get("seasons", [])),
            status=s.get("status"), network=s.get("network"),
            path=s.get("path"), qualityProfileId=s.get("qualityProfileId"),
            rootFolderPath=s.get("rootFolderPath"),
        ) for s in series_list]
    except ArrError as e:
        raise HTTPException(500, str(e))


@router.get("/instances/{instance_id}/series/lookup", summary="Lookup series (Sonarr)")
def lookup_series(instance_id: str, term: str = Query(..., min_length=1)):
    client = _make_arr_client(instance_id)
    if not isinstance(client, SonarrClient):
        raise HTTPException(400, "Instance is not a Sonarr instance")
    try:
        results = client.lookup_series(term)
        return [dict(
            id=s["id"], title=s.get("title", ""), year=s.get("year"),
            tvdbId=s.get("tvdbId"), imdbId=s.get("imdbId"),
            images=s.get("images"), overview=s.get("overview"),
            monitored=s.get("monitored", False),
            status=s.get("status"), network=s.get("network"),
        ) for s in results]
    except ArrError as e:
        raise HTTPException(500, str(e))


@router.get("/instances/{instance_id}/series/{series_id}", summary="Get series (Sonarr)")
def get_series(instance_id: str, series_id: int):
    client = _make_arr_client(instance_id)
    if not isinstance(client, SonarrClient):
        raise HTTPException(400, "Instance is not a Sonarr instance")
    try:
        s = client.get_series(series_id)
        return dict(
            id=s["id"], title=s.get("title", ""), year=s.get("year"),
            tvdbId=s.get("tvdbId"), imdbId=s.get("imdbId"),
            images=s.get("images"), overview=s.get("overview"),
            monitored=s.get("monitored", False),
            seasonCount=len(s.get("seasons", [])),
            status=s.get("status"), network=s.get("network"),
            path=s.get("path"), qualityProfileId=s.get("qualityProfileId"),
            rootFolderPath=s.get("rootFolderPath"),
        )
    except ArrError as e:
        raise HTTPException(500, str(e))


@router.get("/instances/{instance_id}/series/{series_id}/episodes", summary="List episodes (Sonarr)")
def list_episodes(
    instance_id: str,
    series_id: int,
    season_number: int | None = Query(None, alias="seasonNumber"),
):
    client = _make_arr_client(instance_id)
    if not isinstance(client, SonarrClient):
        raise HTTPException(400, "Instance is not a Sonarr instance")
    try:
        episodes = client.get_episodes(series_id, season_number)
        series = client.get_series(series_id)
        series_title = series.get("title", "Unknown")
        return [dict(
            id=ep["id"],
            seriesId=ep.get("seriesId"),
            episodeNumber=ep.get("episodeNumber"),
            seasonNumber=ep.get("seasonNumber"),
            title=ep.get("title", ""),
            overview=ep.get("overview"),
            airDate=ep.get("airDateUtc"),
            monitored=ep.get("monitored", False),
            hasFile=ep.get("hasFile", False),
            seriesTitle=series_title,
            images=ep.get("images"),
        ) for ep in episodes]
    except ArrError as e:
        raise HTTPException(500, str(e))


@router.get("/instances/{instance_id}/series/{series_id}/episodes/{episode_id}", summary="Get episode (Sonarr)")
def get_episode(instance_id: str, series_id: int, episode_id: int):
    client = _make_arr_client(instance_id)
    if not isinstance(client, SonarrClient):
        raise HTTPException(400, "Instance is not a Sonarr instance")
    try:
        ep = client.get_episode(episode_id)
        series = client.get_series(series_id)
        ep["seriesTitle"] = series.get("title", "Unknown")
        return ep
    except ArrError as e:
        raise HTTPException(500, str(e))


# ── Sonarr Playlist Mapping ─────────────────────────────────────


@router.post("/sonarr/instances/{instance_id}/playlist/inspect", summary="Inspect playlist for Sonarr mapping")
def sonarr_playlist_inspect(instance_id: str, body: PlaylistInspectRequest):
    client = _make_arr_client(instance_id)
    if not isinstance(client, SonarrClient):
        raise HTTPException(400, "Instance is not a Sonarr instance")
    try:
        series = client.get_series(body.series_id) if body.series_id else {}
        episodes = client.get_episodes(body.series_id, body.season_number) if body.series_id else []
    except ArrError as e:
        raise HTTPException(500, f"Failed to fetch Sonarr data: {e}")

    try:
        playlist_info = ytdlp.get_playlist_info(body.playlist_url)
    except Exception as e:
        raise HTTPException(400, f"Failed to inspect playlist: {e}")

    raw_entries = playlist_info if isinstance(playlist_info, list) else playlist_info.get("entries", [])
    entries = [
        dict(
            index=i,
            title=e.get("title", "Untitled"),
            url=e.get("webpage_url") or e.get("url", ""),
            duration=e.get("duration"),
            thumbnail=e.get("thumbnail") or (e.get("thumbnails") or [{}])[0].get("url") if e.get("thumbnails") else None,
        )
        for i, e in enumerate(raw_entries)
    ]

    ep_list = [
        dict(
            id=ep["id"], seriesId=ep.get("seriesId"),
            episodeNumber=ep.get("episodeNumber"), seasonNumber=ep.get("seasonNumber"),
            title=ep.get("title", ""), hasFile=ep.get("hasFile", False),
            airDate=ep.get("airDateUtc"),
        )
        for ep in episodes
    ]

    return dict(
        entries=entries,
        episodes=ep_list,
        seriesTitle=series.get("title") if series else None,
    )


@router.get("/sonarr/playlist/mappings", summary="List playlist mappings")
def sonarr_list_playlist_mappings(instance_id: str | None = Query(None, alias="instanceId")):
    mappings = arr_db.list_playlist_mappings(instance_id)
    return dict(mappings=[_mapping_to_response(m) for m in mappings], total=len(mappings))


@router.post("/sonarr/instances/{instance_id}/playlist/mappings", status_code=201, summary="Create playlist mapping")
def sonarr_create_playlist_mapping(instance_id: str, body: CreatePlaylistMappingRequest):
    inst = _get_arr_instance(instance_id)
    client = _make_arr_client(instance_id)
    if not isinstance(client, SonarrClient):
        raise HTTPException(400, "Instance is not a Sonarr instance")

    try:
        series = client.get_series(body.series_id)
        series_title = series.get("title", "Unknown")
    except ArrError as e:
        raise HTTPException(500, f"Failed to fetch series: {e}")

    mapping = arr_db.create_playlist_mapping(
        name=body.name,
        arr_instance_id=instance_id,
        series_id=body.series_id,
        series_title=series_title,
        season_number=body.season_number,
        playlist_url=body.playlist_url,
        quality_profile_id=body.quality_profile_id,
        root_folder_path=body.root_folder_path,
        auto_download=body.auto_download,
    )

    if body.items:
        item_dicts = [i.model_dump() for i in body.items]
        arr_db.create_playlist_mapping_items(mapping["id"], item_dicts)
        mapping = arr_db.get_playlist_mapping(mapping["id"])

    return _mapping_to_response(mapping)


@router.get("/sonarr/playlist/mappings/{mapping_id}", summary="Get playlist mapping")
def sonarr_get_playlist_mapping(mapping_id: str):
    mapping = arr_db.get_playlist_mapping(mapping_id)
    if not mapping:
        raise HTTPException(404, "Playlist mapping not found")
    return _mapping_to_response(mapping)


@router.patch("/sonarr/playlist/mappings/{mapping_id}", summary="Update playlist mapping")
def sonarr_update_playlist_mapping(mapping_id: str, body: UpdatePlaylistMappingRequest):
    existing = arr_db.get_playlist_mapping(mapping_id)
    if not existing:
        raise HTTPException(404, "Playlist mapping not found")

    kwargs: dict[str, object] = {}
    for attr in ("name", "quality_profile_id", "root_folder_path", "status"):
        val = getattr(body, attr, None)
        if val is not None:
            kwargs[attr] = val
    if body.auto_download is not None:
        kwargs["auto_download"] = body.auto_download

    if kwargs:
        arr_db.update_playlist_mapping(mapping_id, **kwargs)

    if body.items is not None:
        item_dicts = [i.model_dump() for i in body.items]
        arr_db.update_playlist_mapping_items_for_mapping(mapping_id, item_dicts)

    mapping = arr_db.get_playlist_mapping(mapping_id)
    _broadcast("sonarr_playlist_mapping_updated", {"mappingId": mapping_id})
    return _mapping_to_response(mapping)


@router.post("/sonarr/playlist/mappings/{mapping_id}/auto-map", summary="Auto-map playlist entries to episodes")
def sonarr_auto_map_playlist(mapping_id: str):
    mapping = arr_db.get_playlist_mapping(mapping_id)
    if not mapping:
        raise HTTPException(404, "Playlist mapping not found")

    inst = _get_arr_instance(mapping["arr_instance_id"])
    client = _make_arr_client(mapping["arr_instance_id"])
    if not isinstance(client, SonarrClient):
        raise HTTPException(400, "Instance is not a Sonarr instance")

    try:
        episodes = client.get_episodes(mapping["series_id"], mapping.get("season_number"))
    except ArrError as e:
        raise HTTPException(500, f"Failed to fetch episodes: {e}")

    items = mapping.get("items", [])
    results = []
    mapped_count = 0

    for item in items:
        if item["action"] == "skip":
            results.append(dict(
                itemId=item["id"], playlistIndex=item["playlist_index"],
                episodeId=None, episodeLabel="", confidence="none",
                warning="Skipped",
            ))
            continue

        title = re.sub(r"[^a-z0-9\s]", "", item.get("video_title", "").lower())
        best_match: dict | None = None
        best_score = 0

        for ep in episodes:
            ep_title = re.sub(r"[^a-z0-9\s]", "", (ep.get("title") or "").lower())
            series_match = title in ep_title or ep_title in title
            words = [w for w in title.split() if w]
            match_count = sum(1 for w in words if w in ep_title)
            score = (match_count + 5) if series_match else match_count

            if score > best_score and score >= 2:
                best_score = score
                best_match = ep

        if best_match:
            label = f"S{str(best_match['seasonNumber']).zfill(2)}E{str(best_match['episodeNumber']).zfill(2)} - {best_match.get('title', '')}"
            confidence = "high" if best_score >= 6 else "medium" if best_score >= 4 else "low"
            warning = "Low confidence match — please verify" if confidence == "low" else None
            arr_db.update_playlist_mapping_item(
                item["id"],
                episode_id=best_match["id"],
                season_number=best_match["seasonNumber"],
                episode_number=best_match["episodeNumber"],
                episode_title=best_match.get("title", ""),
                confidence=confidence,
            )
            results.append(dict(
                itemId=item["id"], playlistIndex=item["playlist_index"],
                episodeId=best_match["id"], episodeLabel=label,
                confidence=confidence, warning=warning,
            ))
            mapped_count += 1
        else:
            arr_db.update_playlist_mapping_item(item["id"], confidence="none")
            results.append(dict(
                itemId=item["id"], playlistIndex=item["playlist_index"],
                episodeId=None, episodeLabel="", confidence="none",
                warning="No matching episode found" if item["action"] == "download" else None,
            ))

    _broadcast("sonarr_playlist_mapping_updated", {"mappingId": mapping_id, "action": "auto-map"})
    return dict(results=results, mappedCount=mapped_count, totalCount=len(items))


@router.post("/sonarr/playlist/mappings/{mapping_id}/download", status_code=202, summary="Download playlist mapping items")
def sonarr_download_playlist_mapping(mapping_id: str):
    mapping = arr_db.get_playlist_mapping(mapping_id)
    if not mapping:
        raise HTTPException(404, "Playlist mapping not found")

    if _worker is None:
        raise HTTPException(500, "Worker not initialized")

    items = mapping.get("items", [])
    has_downloadable = any(
        i["action"] == "download" and i.get("episode_id") and i.get("video_url")
        for i in items
    )
    if not has_downloadable:
        raise HTTPException(400, "No downloadable items — all items must be mapped to an episode")

    try:
        arr_db.update_playlist_mapping(mapping_id, status="download_started")
        job = _worker.enqueue_from_mapping(mapping_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    job_id = job["id"]
    task_id = job.get("task_id")
    return {
        "jobId": job_id,
        "taskId": task_id,
        "status": job["status"],
        "statusUrl": f"/api/arr/sonarr/playlist/downloads/{job_id}",
    }


@router.delete("/sonarr/playlist/mappings/{mapping_id}", summary="Delete playlist mapping")
def sonarr_delete_playlist_mapping(mapping_id: str):
    existing = arr_db.get_playlist_mapping(mapping_id)
    if not existing:
        raise HTTPException(404, "Playlist mapping not found")
    arr_db.delete_playlist_mapping(mapping_id)
    return {"ok": True}


# ── Sonarr Playlist Download Job Status Endpoints ────────────────


def _job_to_response(job: dict) -> dict:
    return dict(
        id=job["id"],
        mappingId=job["mapping_id"],
        taskId=job.get("task_id"),
        instanceId=job["arr_instance_id"],
        seriesId=job["series_id"],
        seriesTitle=job["series_title"],
        seasonNumber=job.get("season_number"),
        playlistUrl=job["playlist_url"],
        status=job["status"],
        summary=dict(
            total=job.get("total_items", 0),
            queued=job.get("queued_items", 0),
            skipped=job.get("skipped_items", 0),
            downloaded=job.get("downloaded_items", 0),
            imported=job.get("imported_items", 0),
            failed=job.get("failed_items", 0),
        ),
        currentItemId=job.get("current_item_id"),
        error=job.get("error_message"),
    )


def _item_to_response(item: dict) -> dict:
    return dict(
        id=item["id"],
        jobId=item["job_id"],
        playlistIndex=item["playlist_index"],
        sourceUrl=item["source_url"],
        sourceTitle=item["source_title"],
        episodeId=item["episode_id"],
        seriesId=item["series_id"],
        seasonNumber=item["season_number"],
        episodeNumber=item["episode_number"],
        episodeTitle=item["episode_title"],
        status=item["status"],
        confidence=item["confidence"],
        action=item["action"],
        downloadAttempts=item.get("download_attempts", 0),
        importAttempts=item.get("import_attempts", 0),
        localStageFile=item.get("local_stage_file"),
        arrStagePath=item.get("arr_stage_path"),
        errorCode=item.get("error_code"),
        errorMessage=item.get("error_message"),
    )


@router.get("/sonarr/playlist/downloads/{job_id}", summary="Get playlist download job status")
def get_sonarr_playlist_download_job(job_id: str):
    job = arr_db.get_sonarr_playlist_download_job(job_id)
    if not job:
        raise HTTPException(404, "Download job not found")
    return _job_to_response(job)


@router.get("/sonarr/playlist/downloads/{job_id}/items", summary="List playlist download job items")
def list_sonarr_playlist_download_items(job_id: str):
    job = arr_db.get_sonarr_playlist_download_job(job_id)
    if not job:
        raise HTTPException(404, "Download job not found")
    items = arr_db.get_sonarr_playlist_download_items(job_id)
    return {"items": [_item_to_response(i) for i in items], "total": len(items)}


@router.get("/sonarr/playlist/downloads/{job_id}/items/{item_id}", summary="Get playlist download item")
def get_sonarr_playlist_download_item(job_id: str, item_id: str):
    job = arr_db.get_sonarr_playlist_download_job(job_id)
    if not job:
        raise HTTPException(404, "Download job not found")
    item = arr_db.get_sonarr_playlist_download_item(item_id)
    if not item or item["job_id"] != job_id:
        raise HTTPException(404, "Download item not found")
    return _item_to_response(item)


@router.post("/sonarr/playlist/downloads/{job_id}/pause", summary="Pause playlist download job")
def pause_sonarr_playlist_download_job(job_id: str):
    job = arr_db.get_sonarr_playlist_download_job(job_id)
    if not job:
        raise HTTPException(404, "Download job not found")
    if job["status"] != "running":
        raise HTTPException(409, f"Cannot pause job in status '{job['status']}'")
    if _worker is None:
        raise HTTPException(500, "Worker not initialized")
    _worker.pause_job(job_id)
    return {"ok": True}


@router.post("/sonarr/playlist/downloads/{job_id}/resume", summary="Resume playlist download job")
def resume_sonarr_playlist_download_job(job_id: str):
    job = arr_db.get_sonarr_playlist_download_job(job_id)
    if not job:
        raise HTTPException(404, "Download job not found")
    if job["status"] != "paused":
        raise HTTPException(409, f"Cannot resume job in status '{job['status']}'")
    if _worker is None:
        raise HTTPException(500, "Worker not initialized")
    _worker.resume_job(job_id)
    return {"ok": True}


@router.post("/sonarr/playlist/downloads/{job_id}/cancel", summary="Cancel playlist download job")
def cancel_sonarr_playlist_download_job(job_id: str):
    job = arr_db.get_sonarr_playlist_download_job(job_id)
    if not job:
        raise HTTPException(404, "Download job not found")
    if job["status"] in ("completed", "cancelled"):
        raise HTTPException(409, f"Cannot cancel job in status '{job['status']}'")
    if _worker is None:
        raise HTTPException(500, "Worker not initialized")
    _worker.cancel_job(job_id)
    return {"ok": True}


@router.post("/sonarr/playlist/downloads/{job_id}/retry-failed", summary="Retry all failed items")
def retry_failed_sonarr_playlist_items(job_id: str):
    job = arr_db.get_sonarr_playlist_download_job(job_id)
    if not job:
        raise HTTPException(404, "Download job not found")
    if _worker is None:
        raise HTTPException(500, "Worker not initialized")
    count = _worker.retry_failed_items(job_id)
    return {"retried": count}


@router.post("/sonarr/playlist/downloads/{job_id}/items/{item_id}/retry", summary="Retry a single failed item")
def retry_sonarr_playlist_item(job_id: str, item_id: str):
    job = arr_db.get_sonarr_playlist_download_job(job_id)
    if not job:
        raise HTTPException(404, "Download job not found")
    item = arr_db.get_sonarr_playlist_download_item(item_id)
    if not item or item["job_id"] != job_id:
        raise HTTPException(404, "Download item not found")
    if _worker is None:
        raise HTTPException(500, "Worker not initialized")
    try:
        updated = _worker.retry_item(item_id)
        return _item_to_response(updated) if updated else {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))


def _mapping_to_response(mapping: dict) -> dict:
    items = [
        dict(
            id=i["id"], mappingId=mapping["id"],
            playlistIndex=i["playlist_index"],
            videoTitle=i.get("video_title", ""),
            videoUrl=i.get("video_url", ""),
            videoDuration=i.get("video_duration"),
            episodeId=i.get("episode_id"),
            seasonNumber=i.get("season_number"),
            episodeNumber=i.get("episode_number"),
            episodeTitle=i.get("episode_title", ""),
            action=i.get("action", "download"),
            confidence=i.get("confidence", "none"),
            status=i.get("status", "pending_download"),
            downloadTaskId=i.get("download_task_id"),
            createdAt=i.get("created_at", ""),
            updatedAt=i.get("updated_at", ""),
        )
        for i in (mapping.get("items") or [])
    ]
    return dict(
        id=mapping["id"],
        name=mapping["name"],
        arrInstanceId=mapping["arr_instance_id"],
        seriesId=mapping["series_id"],
        seriesTitle=mapping.get("series_title", ""),
        seasonNumber=mapping.get("season_number"),
        playlistUrl=mapping["playlist_url"],
        status=mapping.get("status", "draft"),
        autoDownload=bool(mapping.get("auto_download", 0)),
        qualityProfileId=mapping.get("quality_profile_id"),
        rootFolderPath=mapping.get("root_folder_path"),
        items=items,
        createdAt=mapping.get("created_at", ""),
        updatedAt=mapping.get("updated_at", ""),
    )


# ── Download ─────────────────────────────────────────────────────


def _arr_import_download(tid: str, files: list[dict], item_id: int | None = None):
    with _lock:
        task = _tasks.get(tid)
        if not task:
            return
        meta = dict(task.integration_meta or {})
        integration_type = task.integration

    if integration_type not in ("radarr", "sonarr"):
        return

    inst_id = meta.get("instanceId") or meta.get("instance_id", "")
    if item_id is None:
        item_id = meta.get("itemId") or meta.get("item_id") or meta.get("movieId") or meta.get("movie_id", 0)
    if not inst_id or not item_id:
        logger.info("arr_import: no instance_id or item_id in meta=%s", meta)
        return

    inst = _get_arr_instance(inst_id)
    if not inst:
        return
    if not files:
        return

    config_dir = get_config_dir()
    decrypted = decrypt_api_key(inst.api_key_encrypted, config_dir)
    meta["importStatus"] = "importing"
    _update_task(tid, integration_meta=meta)

    imported_count = 0
    for file_entry in files:
        local_path = file_entry.get("path", "") if isinstance(file_entry, dict) else str(file_entry)
        if not local_path:
            continue

        try:
            if inst.kind == "radarr":
                client = RadarrClient(inst.base_url, decrypted)
                item = client.get_movie(int(item_id))
                item_path = item.get("path", "")
            else:
                client = SonarrClient(inst.base_url, decrypted)
                ep = client.get_episode(int(item_id))
                series = client.get_series(ep.get("seriesId", 0))
                item_path = series.get("path", "")
                if not item_path:
                    raise RuntimeError("Sonarr series has no path")

            if not item_path:
                raise RuntimeError(f"Arr item {item_id} has no path")

            tube_dest_dir, dest = to_arr_path(
                inst.tube_write_path, inst.arr_import_path, item_path, local_path,
            )

            os.makedirs(tube_dest_dir, exist_ok=True)
            shutil.copy2(local_path, dest)
            logger.info("arr_import: copied %s \u2192 %s", local_path, dest)
            imported_count += 1

            meta["localPath"] = local_path
            meta["importStatus"] = "waiting_for_import"
            _update_task(tid, integration_meta=meta)
        except Exception as e:
            logger.error("arr_import: copy failed for %s: %s", local_path, e)
            meta["importStatus"] = "failed"
            meta["importError"] = f"copy_error: {e}"
            _update_task(tid, integration_meta=meta)
            _broadcast("arr_import_updated", {"taskId": tid, "importStatus": "failed", "kind": inst.kind})

    if imported_count == 0:
        logger.error("arr_import: no files were copied for task %s", tid)
        return

    try:
        if inst.kind == "radarr":
            cmd = client.create_command("RefreshMovie", movieId=int(item_id))
            cmd_id = cmd.get("id", "")
            logger.info("arr_import: RefreshMovie command=%s", cmd_id)
            time.sleep(3)
            updated = client.get_movie(int(item_id))
            if updated.get("hasFile") and updated.get("movieFile"):
                mf_path = updated["movieFile"].get("path") or updated["movieFile"].get("relativePath", "")
                if mf_path:
                    meta["arrPath"] = mf_path
            meta["arrCommandId"] = str(cmd_id)
        else:
            tup = inst.tube_write_path.rstrip("/")
            aip = inst.arr_import_path.rstrip("/")
            sonarr_path = dest.replace(tup, aip, 1)
            cmd = client.create_command("DownloadedEpisodesScan", path=sonarr_path)
            cmd_id = cmd.get("id", "")
            logger.info("arr_import: DownloadedEpisodesScan command=%s path=%s", cmd_id, sonarr_path)
            meta["arrCommandId"] = str(cmd_id)
            time.sleep(3)
            updated_ep = client.get_episode(int(item_id))
            if updated_ep.get("hasFile"):
                meta["arrPath"] = updated_ep.get("episodeFile", {}).get("path", "")

        meta["importStatus"] = "imported"
        _update_task(tid, integration_meta=meta)
        _broadcast("arr_import_updated", {"taskId": tid, "importStatus": "imported", "kind": inst.kind})
    except Exception as e:
        logger.error("arr_import: trigger failed: %s", e)
        meta["importStatus"] = "failed"
        meta["importError"] = f"trigger_error: {e}"
        _update_task(tid, integration_meta=meta)
        _broadcast("arr_import_updated", {"taskId": tid, "importStatus": "failed", "kind": inst.kind})


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


@router.post("/download", status_code=202, summary="Download for Arr")
def arr_download(body: ArrDownloadRequest):
    inst = None
    if body.instance_id:
        inst = _get_arr_instance(body.instance_id)

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
            if body.item_id:
                integration_meta["itemId"] = body.item_id
            if body.item_title:
                integration_meta["itemTitle"] = body.item_title
            if body.item_year:
                integration_meta["itemYear"] = body.item_year
            task = task.model_copy(update={
                "integration": body.kind,
                "integration_meta": integration_meta,
            })
            _tasks[tid] = task

    # import here to avoid circular import
    from tube_explore.api import _resolve_profile, _run_in_background
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
    return {"taskId": tid, "status": "pending", "statusUrl": f"/api/tasks/{tid}"}


def _create_task(task_type: str, url: str, params: dict[str, object]) -> str:
    from tube_explore.models import TaskInfo
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
    _broadcast("task_created", {"id": tid, "status": "pending", "url": url})
    return tid


# ── Arr task integration endpoints ───────────────────────────────


@router.get("/tasks/{task_id}", summary="Get Arr task integration")
def get_arr_task(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")

    if not task.integration or task.integration not in ("radarr", "sonarr"):
        raise HTTPException(404, "Task is not an Arr-linked task")
    meta = task.integration_meta or {}

    return dict(
        taskId=task.id,
        arrInstanceId=meta.get("instanceId", ""),
        arrInstanceName=meta.get("instanceName", ""),
        arrItemId=meta.get("itemId", meta.get("movieId", 0)),
        kind=task.integration,
        title=meta.get("itemTitle", meta.get("movieTitle", task.title or task.url)),
        year=meta.get("itemYear", meta.get("movieYear")),
        downloadStatus=task.status,
        importStatus=meta.get("importStatus", "none"),
        importMode=meta.get("importMode", "move"),
        localFilePath=meta.get("localPath"),
        arrFilePath=meta.get("arrPath"),
        errorCode=meta.get("importError"),
        errorMessage=task.error,
        startedAt=task.created_at.isoformat() if task.created_at else None,
        completedAt=task.completed_at.isoformat() if task.completed_at else None,
    )


@router.post("/tasks/{task_id}/import/retry", summary="Retry Arr import")
def retry_arr_import(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
    if not task.integration or task.integration not in ("radarr", "sonarr"):
        raise HTTPException(404, "Task is not an Arr-linked task")

    meta = task.integration_meta or {}
    meta["importStatus"] = "waiting_for_import"
    meta.pop("importError", None)
    _update_task(task_id, integration_meta=meta)
    _broadcast("arr_import_updated", {"taskId": task_id, "importStatus": "waiting_for_import"})
    return {"ok": True}


@router.post("/tasks/{task_id}/import/cancel", summary="Cancel Arr import")
def cancel_arr_import(task_id: str):
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(404, "Task not found")
    if not task.integration or task.integration not in ("radarr", "sonarr"):
        raise HTTPException(404, "Task is not an Arr-linked task")

    meta = task.integration_meta or {}
    meta["importStatus"] = "cancelled"
    _update_task(task_id, integration_meta=meta)
    _broadcast("arr_import_updated", {"taskId": task_id, "importStatus": "cancelled"})
    return {"ok": True}
