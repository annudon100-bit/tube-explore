from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tube_explore import config, db
from tube_explore.api import _create_task, _lock, _global_sub_lock, _global_subscribers, _subscribe_global, _tasks, _unsubscribe_global, _broadcast, app
from tube_explore.models import OutboxFileCreate

client = TestClient(app)


# ── Health ────────────────────────────────────────────────────


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "hasFfmpeg" in data
    assert "hasYtdlp" in data
    assert "downloadDirectoryWritable" in data
    assert "tempDirectoryWritable" in data
    assert "workerRunning" in data


def test_ready():
    resp = client.get("/api/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


# ── Profiles ──────────────────────────────────────────────────


SEED_PROFILE_NAMES = {"best-video", "1080p", "720p", "4k", "audio-best", "audio-mp3", "smallest"}


def test_list_profiles_seeded():
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    data = resp.json()
    names = {p["name"] for p in data}
    assert names == SEED_PROFILE_NAMES


def test_create_profile():
    resp = client.post("/api/profiles", json={"name": "test_profile"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test_profile"
    assert data["id"] > 0
    assert "createdAt" in data


def test_create_profile_with_camel_case():
    resp = client.post(
        "/api/profiles",
        json={
            "name": "hd720",
            "label": "HD 720p",
            "downloadQualityMode": "at_most",
            "downloadQualityValue": 720,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["downloadQualityMode"] == "at_most"
    assert data["downloadQualityValue"] == 720


def test_create_duplicate_profile():
    client.post("/api/profiles", json={"name": "dup"})
    resp = client.post("/api/profiles", json={"name": "dup"})
    assert resp.status_code == 409


def test_get_profile():
    create = client.post("/api/profiles", json={"name": "get_test"}).json()
    resp = client.get(f"/api/profiles/{create['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "get_test"


def test_get_nonexistent_profile():
    resp = client.get("/api/profiles/9999")
    assert resp.status_code == 404


def test_update_profile():
    create = client.post("/api/profiles", json={"name": "upd"}).json()
    resp = client.patch(f"/api/profiles/{create['id']}", json={"label": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "Updated"


def test_update_nonexistent_profile():
    resp = client.patch("/api/profiles/9999", json={"label": "x"})
    assert resp.status_code == 404


def test_delete_profile():
    create = client.post("/api/profiles", json={"name": "del"}).json()
    resp = client.delete(f"/api/profiles/{create['id']}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp = client.get(f"/api/profiles/{create['id']}")
    assert resp.status_code == 404


def test_delete_nonexistent_profile():
    resp = client.delete("/api/profiles/9999")
    assert resp.status_code == 404


# ── Settings ──────────────────────────────────────────────────


def test_get_settings():
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "rateLimit" in data
    assert "tempDirectory" in data
    assert "retryCount" in data
    assert "socketTimeout" in data


def test_update_settings():
    resp = client.patch("/api/settings", json={"rateLimit": "5M", "socketTimeout": 60})
    assert resp.status_code == 200
    data = resp.json()
    assert data["rateLimit"] == "5M"
    assert data["socketTimeout"] == 60


def test_update_settings_empty():
    resp = client.patch("/api/settings", json={})
    assert resp.status_code == 200


# ── Search / Metadata (mock or skip — needs yt-dlp) ──────────


def test_search_no_query():
    resp = client.get("/api/search")
    assert resp.status_code == 422


def test_metadata_no_url():
    resp = client.get("/api/metadata")
    assert resp.status_code == 422


def test_playlist_no_url():
    resp = client.get("/api/playlist")
    assert resp.status_code == 422


# ── Download ──────────────────────────────────────────────────


def test_download_video_no_url():
    resp = client.post("/api/download/video", json={})
    assert resp.status_code == 422


def test_download_playlist_no_url():
    resp = client.post("/api/download/playlist", json={})
    assert resp.status_code == 422


def test_download_video_unknown_profile():
    resp = client.post(
        "/api/download/video",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "profileId": "nonexistent",
        },
    )
    assert resp.status_code == 404


# ── Tasks ─────────────────────────────────────────────────────


def test_list_tasks_empty():
    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_nonexistent_task():
    resp = client.get("/api/tasks/nonexistent")
    assert resp.status_code == 404


# ── Files ─────────────────────────────────────────────────────


def test_list_files_empty():
    resp = client.get("/api/files")
    assert resp.status_code == 200
    assert resp.json() == []


def test_download_nonexistent_file():
    resp = client.get("/api/files/nonexistent/download")
    assert resp.status_code == 404


# ── Outbox ────────────────────────────────────────────────────


def test_list_outbox_empty():
    resp = client.get("/api/outbox")
    assert resp.status_code == 200
    assert resp.json() == []


def _make_outbox_record(tmp_path, name: str, status: str = "pending") -> str:
    from datetime import UTC, datetime
    outbox = Path(config.get_outbox_dir())
    (outbox / name).write_text("dummy")
    rec = db.insert_outbox_file(
        OutboxFileCreate(
            id=str(uuid4()),
            file_name=name,
            file_size=(outbox / name).stat().st_size,
            status=status,
            created_at=datetime.now(UTC),
        )
    )
    return rec.id


def test_list_outbox_with_files(tmp_path):
    fid1 = _make_outbox_record(tmp_path, "video.mp4")
    fid2 = _make_outbox_record(tmp_path, "audio.webm")
    try:
        resp = client.get("/api/outbox")
        assert resp.status_code == 200
        data = resp.json()
        names = {e["name"] for e in data}
        assert names == {"video.mp4", "audio.webm"}
        for e in data:
            assert "size" in e
            assert "id" in e
    finally:
        outbox = Path(config.get_outbox_dir())
        (outbox / "video.mp4").unlink(missing_ok=True)
        (outbox / "audio.webm").unlink(missing_ok=True)
        db.delete_outbox_file(fid1)
        db.delete_outbox_file(fid2)


def test_delete_outbox_file():
    from datetime import UTC, datetime
    outbox = Path(config.get_outbox_dir())
    (outbox / "delete_me.mp4").write_text("to be deleted")
    rec = db.insert_outbox_file(
        OutboxFileCreate(
            id=str(uuid4()),
            file_name="delete_me.mp4",
            file_size=(outbox / "delete_me.mp4").stat().st_size,
            created_at=datetime.now(UTC),
        )
    )
    try:
        resp = client.delete(f"/api/outbox/{rec.id}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert not (outbox / "delete_me.mp4").exists()
    finally:
        (outbox / "delete_me.mp4").unlink(missing_ok=True)
        db.delete_outbox_file(rec.id)


def test_delete_nonexistent_outbox_file():
    resp = client.delete("/api/outbox/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_process_outbox_file_nonexistent():
    resp = client.post("/api/outbox/00000000-0000-0000-0000-000000000000/process", json={"preset": "MP4 1080p"})
    assert resp.status_code == 404


def test_process_outbox_file_no_ffmpeg():
    from tube_explore.ytdlp import HAS_FFMPEG
    if HAS_FFMPEG:
        pytest.skip("ffmpeg is available, cannot test no-ffmpeg branch")
    from datetime import UTC, datetime
    outbox = Path(config.get_outbox_dir())
    (outbox / "noffmpeg.mp4").write_text("dummy")
    rec = db.insert_outbox_file(
        OutboxFileCreate(
            id=str(uuid4()),
            file_name="noffmpeg.mp4",
            file_size=(outbox / "noffmpeg.mp4").stat().st_size,
            created_at=datetime.now(UTC),
        )
    )
    try:
        resp = client.post(f"/api/outbox/{rec.id}/process", json={"preset": "MP4 1080p"})
        assert resp.status_code == 400
    finally:
        (outbox / "noffmpeg.mp4").unlink(missing_ok=True)
        db.delete_outbox_file(rec.id)


def test_process_outbox_file_nonexistent_preset():
    from datetime import UTC, datetime
    outbox = Path(config.get_outbox_dir())
    (outbox / "some_file.mp4").write_text("dummy")
    rec = db.insert_outbox_file(
        OutboxFileCreate(
            id=str(uuid4()),
            file_name="some_file.mp4",
            file_size=(outbox / "some_file.mp4").stat().st_size,
            created_at=datetime.now(UTC),
        )
    )
    try:
        resp = client.post(f"/api/outbox/{rec.id}/process", json={"preset": "NONEXISTENT"})
        assert resp.status_code == 404
    finally:
        (outbox / "some_file.mp4").unlink(missing_ok=True)
        db.delete_outbox_file(rec.id)


# ── Conversion Presets ────────────────────────────────────────


def test_list_convert_presets():
    resp = client.get("/api/convert-presets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 12
    names = {p["name"] for p in data}
    assert "MP4 1080p" in names
    assert "MP3 320kbps" in names


def test_get_convert_preset():
    resp = client.get("/api/convert-presets/MP4%201080p")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "MP4 1080p"
    assert data["container"] == "mp4"
    assert data["videoCodec"] == "h264"
    assert data["audioCodec"] == "aac"


def test_get_nonexistent_convert_preset():
    resp = client.get("/api/convert-presets/nonexistent")
    assert resp.status_code == 404


def test_create_convert_preset():
    resp = client.post(
        "/api/convert-presets",
        json={
            "name": "TestPreset",
            "container": "mkv",
            "videoCodec": "hevc",
            "audioCodec": "flac",
            "maxHeight": 2160,
            "outputExt": "mkv",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "TestPreset"
    assert data["container"] == "mkv"
    assert data["videoCodec"] == "hevc"


def test_create_duplicate_convert_preset():
    resp = client.post(
        "/api/convert-presets",
        json={"name": "MP4 1080p", "container": "mp4", "outputExt": "mp4"},
    )
    assert resp.status_code == 409


def test_update_convert_preset():
    client.post(
        "/api/convert-presets",
        json={"name": "UpdPreset", "container": "mp4", "outputExt": "mp4"},
    )
    resp = client.patch(
        "/api/convert-presets/UpdPreset",
        json={"label": "Updated label", "maxHeight": 720},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "Updated label"
    assert data["maxHeight"] == 720


def test_update_nonexistent_convert_preset():
    resp = client.patch(
        "/api/convert-presets/nonexistent",
        json={"label": "x"},
    )
    assert resp.status_code == 404


def test_delete_convert_preset():
    client.post(
        "/api/convert-presets",
        json={"name": "DelPreset", "container": "mp4", "outputExt": "mp4"},
    )
    resp = client.delete("/api/convert-presets/DelPreset")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp = client.get("/api/convert-presets/DelPreset")
    assert resp.status_code == 404


def test_delete_nonexistent_convert_preset():
    resp = client.delete("/api/convert-presets/nonexistent")
    assert resp.status_code == 404


# ── SSE ────────────────────────────────────────────────────────


def _clear_tasks():
    with _lock:
        _tasks.clear()


def test_global_sse_subscribe_unsubscribe():
    q = _subscribe_global()
    with _global_sub_lock:
        assert q in _global_subscribers
    _unsubscribe_global(q)
    with _global_sub_lock:
        assert q not in _global_subscribers


def test_global_sse_broadcast_delivers_to_queue():
    import json
    q = _subscribe_global()
    _broadcast("test_event", {"msg": "hello"})
    event, payload = q.get_nowait()
    assert event == "test_event"
    assert json.loads(payload)["msg"] == "hello"
    _unsubscribe_global(q)


def test_global_sse_multiple_subscribers():
    import json
    q1 = _subscribe_global()
    q2 = _subscribe_global()
    _broadcast("multi", {"n": 42})
    ev1, payload1 = q1.get_nowait()
    ev2, payload2 = q2.get_nowait()
    assert ev1 == "multi"
    assert ev2 == "multi"
    assert json.loads(payload1) == {"n": 42}
    assert json.loads(payload2) == {"n": 42}
    _unsubscribe_global(q1)
    _unsubscribe_global(q2)


def test_global_sse_unsubscribed_receives_no_events():
    q = _subscribe_global()
    _unsubscribe_global(q)
    _broadcast("lost", {"x": 1})
    assert q.qsize() == 0
