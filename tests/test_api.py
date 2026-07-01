from pathlib import Path

from fastapi.testclient import TestClient

from tube_explore import config
from tube_explore.api import _create_task, _lock, _sub_lock, _subscribe, _subscribers, _tasks, _unsubscribe, app

client = TestClient(app)


# ── Health ────────────────────────────────────────────────────


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "hasFfmpeg" in data


# ── Profiles ──────────────────────────────────────────────────


def test_list_profiles_empty():
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    assert resp.json() == []


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
    resp = client.put(f"/api/profiles/{create['id']}", json={"label": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["label"] == "Updated"


def test_update_nonexistent_profile():
    resp = client.put("/api/profiles/9999", json={"label": "x"})
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
    resp = client.put("/api/settings", json={"rateLimit": "5M", "socketTimeout": 60})
    assert resp.status_code == 200
    data = resp.json()
    assert data["rateLimit"] == "5M"
    assert data["socketTimeout"] == 60


def test_update_settings_empty():
    resp = client.put("/api/settings", json={})
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
            "profile": "nonexistent",
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


# ── Outbox ────────────────────────────────────────────────────


def test_list_outbox_empty():
    resp = client.get("/api/outbox")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_outbox_with_files(tmp_path):
    outbox = Path(config.get_outbox_dir())
    (outbox / "video.mp4").write_text("dummy")
    (outbox / "audio.webm").write_text("dummy")
    try:
        resp = client.get("/api/outbox")
        assert resp.status_code == 200
        data = resp.json()
        names = {e["name"] for e in data}
        assert names == {"video.mp4", "audio.webm"}
        for e in data:
            assert "size" in e
            assert "modifiedAt" in e
    finally:
        (outbox / "video.mp4").unlink(missing_ok=True)
        (outbox / "audio.webm").unlink(missing_ok=True)


def test_delete_outbox_file():
    outbox = Path(config.get_outbox_dir())
    (outbox / "delete_me.mp4").write_text("to be deleted")
    try:
        resp = client.delete("/api/outbox/delete_me.mp4")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        assert not (outbox / "delete_me.mp4").exists()
    finally:
        (outbox / "delete_me.mp4").unlink(missing_ok=True)


def test_delete_nonexistent_outbox_file():
    resp = client.delete("/api/outbox/nonexistent.mkv")
    assert resp.status_code == 404


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
    resp = client.put(
        "/api/convert-presets/UpdPreset",
        json={"label": "Updated label", "maxHeight": 720},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["label"] == "Updated label"
    assert data["maxHeight"] == 720


def test_update_nonexistent_convert_preset():
    resp = client.put(
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


def test_sse_returns_404_for_nonexistent_task():
    resp = client.get("/api/tasks/nonexistent/stream")
    assert resp.status_code == 404


def test_sse_subscribe_unsubscribe():
    _clear_tasks()
    tid = _create_task("video", "https://x.com/v", {})
    q = _subscribe(tid)
    with _sub_lock:
        assert tid in _subscribers
        assert q in _subscribers[tid]
    _unsubscribe(tid, q)
    with _sub_lock:
        assert not _subscribers.get(tid) or q not in _subscribers[tid]


def test_sse_publish_delivers_to_queue():
    _clear_tasks()
    tid = _create_task("video", "https://x.com/v", {})
    q = _subscribe(tid)
    q.put_nowait({"status": "running"})
    data = q.get_nowait()
    assert data["status"] == "running"
    _unsubscribe(tid, q)
