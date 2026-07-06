from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tube_explore import config, db
from tube_explore.api import _lock, _global_sub_lock, _global_subscribers, _subscribe_global, _tasks, _unsubscribe_global, _broadcast, app

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
    assert "sseConnected" in data


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


def test_get_nonexistent_task():
    resp = client.get("/api/tasks/nonexistent")
    assert resp.status_code == 404


# ── Files ─────────────────────────────────────────────────────


def test_list_files_empty():
    resp = client.get("/api/files")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_download_nonexistent_file():
    resp = client.get("/api/files/nonexistent/download")
    assert resp.status_code == 404


def test_file_stats_empty():
    resp = client.get("/api/files/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["totalUsed"] == 0
    assert data["totalCapacity"] > 0
    cats = {c["type"]: c for c in data["categories"]}
    for t in ("video", "audio", "playlist", "image", "other"):
        assert t in cats
        assert cats[t]["count"] == 0
        assert cats[t]["size"] == 0


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
