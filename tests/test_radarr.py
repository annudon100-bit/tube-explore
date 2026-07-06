from datetime import UTC, datetime
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from tube_explore import db
from tube_explore.api import _lock, _tasks, _broadcast, app
from tube_explore.models import RadarrInstanceCreate, RadarrInstanceUpdate, TaskInfo
from tube_explore.radarr_client import RadarrClient, RadarrError

client = TestClient(app)


def _clear_tasks():
    with _lock:
        _tasks.clear()


def _create_radarr_data(**overrides):
    data = dict(
        name="test-radarr",
        baseUrl="http://radarr:7878",
        apiKey="abc123def456",
        tubeWritePath="/downloads/tube",
        radarrImportPath="/downloads/radarr",
        enabled=True,
    )
    data.update(overrides)
    return data


# ── DB layer tests ─────────────────────────────────────────────


class TestRadarrDb:
    def test_create_radarr_instance(self):
        data = RadarrInstanceCreate(
            name="test", base_url="http://radarr:7878", api_key="key123",
            tube_write_path="/tube", radarr_import_path="/radarr",
        )
        inst = db.create_radarr_instance(data)
        assert inst.id is not None
        assert inst.name == "test"
        assert inst.base_url == "http://radarr:7878"
        assert inst.api_key_encrypted == "key123"
        assert inst.tube_write_path == "/tube"
        assert inst.radarr_import_path == "/radarr"
        assert inst.enabled is True
        assert inst.is_default is False

    def test_get_radarr_instance(self):
        data = RadarrInstanceCreate(
            name="gettest", base_url="http://radarr:7878", api_key="k",
            tube_write_path="/t", radarr_import_path="/r",
        )
        created = db.create_radarr_instance(data)
        fetched = db.get_radarr_instance(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "gettest"

    def test_get_nonexistent_radarr_instance(self):
        assert db.get_radarr_instance("nonexistent") is None

    def test_get_radarr_instance_by_name(self):
        data = RadarrInstanceCreate(
            name="byname", base_url="http://r:7878", api_key="k",
            tube_write_path="/t", radarr_import_path="/r",
        )
        db.create_radarr_instance(data)
        fetched = db.get_radarr_instance_by_name("byname")
        assert fetched is not None
        assert fetched.name == "byname"
        assert db.get_radarr_instance_by_name("nope") is None

    def test_list_radarr_instances(self):
        for n in ["aa", "bb", "cc"]:
            db.create_radarr_instance(RadarrInstanceCreate(
                name=n, base_url="http://r:7878", api_key="k",
                tube_write_path="/t", radarr_import_path="/r",
            ))
        instances = db.list_radarr_instances()
        names = {i.name for i in instances}
        assert "aa" in names
        assert "bb" in names
        assert "cc" in names

    def test_update_radarr_instance(self):
        data = RadarrInstanceCreate(
            name="upd", base_url="http://r:7878", api_key="key1",
            tube_write_path="/t", radarr_import_path="/r",
        )
        created = db.create_radarr_instance(data)
        update = RadarrInstanceUpdate(base_url="http://new:7878", enabled=False)
        updated = db.update_radarr_instance(created.id, update)
        assert updated is not None
        assert updated.base_url == "http://new:7878"
        assert updated.enabled is False
        assert updated.name == "upd"

    def test_update_nonexistent_radarr_instance(self):
        result = db.update_radarr_instance("nope", RadarrInstanceUpdate(name="x"))
        assert result is None

    def test_delete_radarr_instance(self):
        data = RadarrInstanceCreate(
            name="del", base_url="http://r:7878", api_key="k",
            tube_write_path="/t", radarr_import_path="/r",
        )
        created = db.create_radarr_instance(data)
        db.delete_radarr_instance(created.id)
        assert db.get_radarr_instance(created.id) is None

    def test_set_radarr_instance_test_result(self):
        data = RadarrInstanceCreate(
            name="tr", base_url="http://r:7878", api_key="k",
            tube_write_path="/t", radarr_import_path="/r",
        )
        inst = db.create_radarr_instance(data)
        db.set_radarr_instance_test_result(inst.id, "ok", None)
        updated = db.get_radarr_instance(inst.id)
        assert updated.last_test_status == "ok"
        assert updated.last_test_message is None

        db.set_radarr_instance_test_result(inst.id, "error", "connection failed", "5.0.0")
        updated = db.get_radarr_instance(inst.id)
        assert updated.last_test_status == "error"
        assert updated.last_test_message == "connection failed"
        assert updated.radarr_version == "5.0.0"

    def test_set_radarr_instance_sync_result(self):
        data = RadarrInstanceCreate(
            name="sr", base_url="http://r:7878", api_key="k",
            tube_write_path="/t", radarr_import_path="/r",
        )
        inst = db.create_radarr_instance(data)
        db.set_radarr_instance_sync_result(inst.id, "ok")
        updated = db.get_radarr_instance(inst.id)
        assert updated.last_sync_status == "ok"
        assert updated.last_sync_at is not None


# ── RadarrClient unit tests ────────────────────────────────────


class TestRadarrClient:
    def test_ping_success(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200

            rc = RadarrClient("http://r:7878", "key")
            assert rc.ping() is True
            mock_instance.get.assert_called_with("/ping")

    def test_ping_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.side_effect = Exception("fail")

            rc = RadarrClient("http://r:7878", "key")
            assert rc.ping() is False

    def test_get_system_status(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"version": "5.0.0"}

            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_system_status()
            assert result["version"] == "5.0.0"
            mock_instance.get.assert_called_with("/api/v3/system/status")

    def test_get_root_folders(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "path": "/movies"}]

            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_root_folders()
            assert result == [{"id": 1, "path": "/movies"}]

    def test_get_quality_profiles(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "name": "HD-1080p"}]

            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_quality_profiles()
            assert result == [{"id": 1, "name": "HD-1080p"}]

    def test_get_missing_movies(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"id": 1, "title": "Test Movie", "hasFile": False, "monitored": True},
            ]

            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_missing_movies()
            assert result[0]["title"] == "Test Movie"

    def test_get_queue(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"records": [{"movieId": 1, "title": "Q"}]}

            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_queue()
            assert result["records"][0]["movieId"] == 1

    def test_create_command(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.post.return_value
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 42, "name": "DownloadMovie"}

            rc = RadarrClient("http://r:7878", "key")
            result = rc.create_command("DownloadMovie", movieId=1)
            assert result["id"] == 42
            mock_instance.post.assert_called_once()
            call_kwargs = mock_instance.post.call_args
            assert call_kwargs[1]["json"]["name"] == "DownloadMovie"

    def test_auth_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 401

            rc = RadarrClient("http://r:7878", "bad_key")
            with pytest.raises(RadarrError) as exc:
                rc.get_system_status()
            assert exc.value.code == "RADARR_AUTH_FAILED"

    def test_connection_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.side_effect = httpx.RequestError("No route")

            rc = RadarrClient("http://r:7878", "key")
            with pytest.raises(RadarrError) as exc:
                rc.get_system_status()
            assert exc.value.code == "RADARR_CONNECTION_FAILED"

    def test_not_found(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 404

            rc = RadarrClient("http://r:7878", "key")
            with pytest.raises(RadarrError) as exc:
                rc.get_system_status()
            assert exc.value.code == "RADARR_NOT_FOUND"

    def test_server_error(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 500

            rc = RadarrClient("http://r:7878", "key")
            with pytest.raises(RadarrError) as exc:
                rc.get_system_status()
            assert exc.value.code == "RADARR_ERROR"


# ── Radarr API endpoint tests ──────────────────────────────────


class TestRadarrApi:
    def _create_instance(self, **overrides):
        data = _create_radarr_data(**overrides)
        return client.post("/api/radarr/instances", json=data)

    def test_create_radarr_instance(self):
        resp = self._create_instance()
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-radarr"
        assert data["baseUrl"] == "http://radarr:7878"
        assert data["apiKeyPreview"] == "abc123de…"
        assert data["tubeWritePath"] == "/downloads/tube"
        assert data["radarrImportPath"] == "/downloads/radarr"
        assert data["enabled"] is True
        assert data["status"] == "unknown"
        assert "id" in data

    def test_create_duplicate_radarr_instance(self):
        self._create_instance()
        resp = self._create_instance()
        assert resp.status_code == 409

    def test_create_missing_api_key(self):
        resp = client.post("/api/radarr/instances", json={
            "name": "nokey", "baseUrl": "http://r:7878",
            "tubeWritePath": "/t", "radarrImportPath": "/r",
        })
        assert resp.status_code == 400

    def test_list_radarr_instances(self):
        self._create_instance(name="first")
        self._create_instance(name="second")
        resp = client.get("/api/radarr/instances")
        assert resp.status_code == 200
        data = resp.json()
        names = {i["name"] for i in data}
        assert "first" in names
        assert "second" in names

    def test_get_radarr_instance(self):
        create = self._create_instance().json()
        resp = client.get(f"/api/radarr/instances/{create['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-radarr"

    def test_get_nonexistent_radarr_instance(self):
        resp = client.get("/api/radarr/instances/nonexistent")
        assert resp.status_code == 404

    def test_update_radarr_instance(self):
        create = self._create_instance().json()
        resp = client.patch(f"/api/radarr/instances/{create['id']}", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_update_nonexistent_radarr_instance(self):
        resp = client.patch("/api/radarr/instances/nonexistent", json={"enabled": False})
        assert resp.status_code == 404

    def test_delete_radarr_instance(self):
        create = self._create_instance().json()
        resp = client.delete(f"/api/radarr/instances/{create['id']}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        resp = client.get(f"/api/radarr/instances/{create['id']}")
        assert resp.status_code == 404

    def test_delete_nonexistent_radarr_instance(self):
        resp = client.delete("/api/radarr/instances/nonexistent")
        assert resp.status_code == 404

    def test_default_radarr_instance(self):
        create = self._create_instance().json()
        resp = client.post(f"/api/radarr/instances/{create['id']}/set-default")
        assert resp.status_code == 200
        updated = client.get(f"/api/radarr/instances/{create['id']}").json()
        assert updated["isDefault"] is True

    def test_set_default_nonexistent(self):
        resp = client.post("/api/radarr/instances/nonexistent/set-default")
        assert resp.status_code == 404

    def test_test_radarr_instance_no_server(self):
        create = self._create_instance().json()
        resp = client.post(f"/api/radarr/instances/{create['id']}/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["canConnect"] is False

    def test_test_radarr_instance_with_body(self):
        resp = client.post(
            "/api/radarr/instances/nonexistent/test",
            json={"baseUrl": "http://invalid:7878", "apiKey": "bad"},
        )
        assert resp.status_code == 200

    def test_summary_empty(self):
        resp = client.get("/api/radarr/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalInstances"] == 0
        assert data["activeConnections"] == 0

    def test_summary_with_instance(self):
        self._create_instance()
        resp = client.get("/api/radarr/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalInstances"] == 1

    def test_sync_history(self):
        create = self._create_instance().json()
        resp = client.get(f"/api/radarr/instances/{create['id']}/sync-history")
        assert resp.status_code == 200
        assert resp.json()["history"] == []

    def test_test_results(self):
        create = self._create_instance().json()
        resp = client.get(f"/api/radarr/instances/{create['id']}/test-results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lastTestStatus"] is None

    def test_root_folders_disabled_instance(self):
        create = self._create_instance(enabled=False).json()
        resp = client.get(f"/api/radarr/instances/{create['id']}/root-folders")
        assert resp.status_code == 400

    def test_root_folders_nonexistent(self):
        resp = client.get("/api/radarr/instances/nonexistent/root-folders")
        assert resp.status_code == 404

    def test_quality_profiles_disabled_instance(self):
        create = self._create_instance(enabled=False).json()
        resp = client.get(f"/api/radarr/instances/{create['id']}/quality-profiles")
        assert resp.status_code == 400

    def test_queue_disabled_instance(self):
        create = self._create_instance(enabled=False).json()
        resp = client.get(f"/api/radarr/instances/{create['id']}/queue")
        assert resp.status_code == 400

    def test_sync_disabled_instance(self):
        create = self._create_instance(enabled=False).json()
        resp = client.post(f"/api/radarr/instances/{create['id']}/sync")
        assert resp.status_code == 400

    def test_missing_movies_disabled_instance(self):
        create = self._create_instance(enabled=False).json()
        resp = client.get(f"/api/radarr/instances/{create['id']}/missing")
        assert resp.status_code == 400


# ── Extended task endpoints ────────────────────────────────────


class TestTaskEndpoints:
    def _seed_task(self, status="completed", **overrides):
        task = TaskInfo(
            id="task-1",
            type="video",
            url="https://youtube.com/watch?v=test",
            params={},
            status=status,
            progress_percent=100,
            created_at=datetime.now(UTC),
            **overrides,
        )
        with _lock:
            _tasks["task-1"] = task
        return task

    def _seed_completed_task_with_files(self):
        return self._seed_task(
            result=[
                {"id": "file-1", "name": "video.mp4", "size": 1024,
                 "path": "/tmp/video.mp4", "fileType": "video", "format": "mp4",
                 "fileExtension": "mp4", "detail": "mp4"},
            ],
            completed_at=datetime.now(UTC),
        )

    def test_list_tasks_empty(self):
        _clear_tasks()
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_tasks_with_status_filter(self):
        _clear_tasks()
        self._seed_task()
        resp = client.get("/api/tasks?status=completed")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = client.get("/api/tasks?status=running")
        assert resp.json()["total"] == 0

    def test_list_tasks_with_search(self):
        _clear_tasks()
        t = self._seed_task()
        # Tasks with search need a title set
        with _lock:
            task = _tasks[t.id]
            task = task.model_copy(update={"title": "My Special Video"})
            _tasks[t.id] = task

        resp = client.get("/api/tasks?search=special")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = client.get("/api/tasks?search=nope")
        assert resp.json()["total"] == 0

    def test_list_tasks_sort_by_title(self):
        _clear_tasks()
        for i, title in enumerate(["Zeta", "Alpha", "Beta"]):
            tid = f"task-s{i}"
            task = TaskInfo(
                id=tid, type="video", url="https://youtube.com/watch?v=test",
                params={}, status="completed", progress_percent=100,
                title=title, created_at=datetime.now(UTC),
            )
            with _lock:
                _tasks[tid] = task

        resp = client.get("/api/tasks?sortBy=title&sortOrder=asc")
        assert resp.status_code == 200
        items = resp.json()["items"]
        titles = [i.get("title") for i in items]
        assert titles == ["Alpha", "Beta", "Zeta"]

    def test_list_tasks_integration_filter(self):
        _clear_tasks()
        self._seed_task()
        resp = client.get("/api/tasks?integration=none")
        assert resp.json()["total"] == 1
        resp = client.get("/api/tasks?integration=radarr")
        assert resp.json()["total"] == 0

    def test_delete_task(self):
        _clear_tasks()
        self._seed_task()
        resp = client.delete("/api/tasks/task-1")
        assert resp.status_code == 200

    def test_delete_nonexistent_task(self):
        resp = client.delete("/api/tasks/nonexistent")
        assert resp.status_code == 404

    def test_delete_running_task_rejected(self):
        _clear_tasks()
        self._seed_task(status="running")
        resp = client.delete("/api/tasks/task-1")
        assert resp.status_code == 409

    def test_get_task_logs(self):
        _clear_tasks()
        self._seed_task()
        resp = client.get("/api/tasks/task-1/logs")
        assert resp.status_code == 200
        assert resp.json()["taskId"] == "task-1"

    def test_get_nonexistent_task_logs(self):
        resp = client.get("/api/tasks/nonexistent/logs")
        assert resp.status_code == 404

    def test_get_task_files(self):
        _clear_tasks()
        self._seed_completed_task_with_files()
        resp = client.get("/api/tasks/task-1/files")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "file-1"
        assert data["items"][0]["name"] == "video.mp4"

    def test_get_nonexistent_task_files(self):
        resp = client.get("/api/tasks/nonexistent/files")
        assert resp.status_code == 404

    def test_get_task_files_no_result(self):
        _clear_tasks()
        self._seed_task()
        resp = client.get("/api/tasks/task-1/files")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_file_detail(self):
        _clear_tasks()
        self._seed_completed_task_with_files()
        resp = client.get("/api/files/file-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "file-1"
        assert data["name"] == "video.mp4"
        assert data["storageState"] == "missing"

    def test_get_nonexistent_file_detail(self):
        resp = client.get("/api/files/nonexistent")
        assert resp.status_code == 404

    def test_delete_file(self):
        _clear_tasks()
        self._seed_completed_task_with_files()
        resp = client.delete("/api/files/file-1")
        assert resp.status_code == 200

    def test_delete_nonexistent_file(self):
        resp = client.delete("/api/files/nonexistent")
        assert resp.status_code == 404

    def test_reveal_file(self):
        resp = client.post("/api/files/file-1/reveal")
        assert resp.status_code == 409
        assert "not available" in resp.json()["detail"]

    def test_list_tasks_pagination(self):
        _clear_tasks()
        for i in range(5):
            tid = f"task-p{i}"
            task = TaskInfo(
                id=tid, type="video", url=f"https://youtube.com/watch?v={i}",
                params={}, status="completed", progress_percent=100,
                created_at=datetime.now(UTC),
            )
            with _lock:
                _tasks[tid] = task

        resp = client.get("/api/tasks?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5


# ── Radarr task integration endpoints ──────────────────────────


class TestRadarrTaskIntegration:
    def _seed_radarr_task(self, **overrides):
        meta = dict(
            instanceId="inst-1", instanceName="My Radarr",
            movieId=42, movieTitle="Test Movie",
            importStatus="none", importMode="move",
        )
        meta.update(overrides)
        task = TaskInfo(
            id="rtask-1", type="video", url="https://youtube.com/watch?v=test",
            params={}, status="completed", progress_percent=100,
            created_at=datetime.now(UTC), completed_at=datetime.now(UTC),
            integration="radarr", integration_meta=meta,
        )
        with _lock:
            _tasks["rtask-1"] = task
        return task

    def test_get_radarr_task(self):
        _clear_tasks()
        self._seed_radarr_task()
        resp = client.get("/api/radarr/tasks/rtask-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["radarrMovieId"] == 42
        assert data["radarrInstanceName"] == "My Radarr"
        assert data["title"] == "Test Movie"
        assert data["importStatus"] == "none"

    def test_get_nonexistent_radarr_task(self):
        resp = client.get("/api/radarr/tasks/nonexistent")
        assert resp.status_code == 404

    def test_get_non_radarr_task(self):
        _clear_tasks()
        task = TaskInfo(
            id="non-radarr", type="video", url="https://youtube.com/watch?v=x",
            params={}, status="completed", progress_percent=100,
            created_at=datetime.now(UTC),
        )
        with _lock:
            _tasks["non-radarr"] = task
        resp = client.get("/api/radarr/tasks/non-radarr")
        assert resp.status_code == 404

    def test_retry_radarr_import(self):
        _clear_tasks()
        self._seed_radarr_task(importStatus="failed")
        resp = client.post("/api/radarr/tasks/rtask-1/import/retry")
        assert resp.status_code == 200
        updated = client.get("/api/radarr/tasks/rtask-1").json()
        assert updated["importStatus"] == "waiting_for_import"

    def test_retry_nonexistent_radarr_import(self):
        resp = client.post("/api/radarr/tasks/nonexistent/import/retry")
        assert resp.status_code == 404

    def test_retry_non_radarr_import(self):
        _clear_tasks()
        task = TaskInfo(
            id="nonr", type="video", url="https://youtube.com/watch?v=x",
            params={}, status="completed", progress_percent=100,
            created_at=datetime.now(UTC),
        )
        with _lock:
            _tasks["nonr"] = task
        resp = client.post("/api/radarr/tasks/nonr/import/retry")
        assert resp.status_code == 404

    def test_cancel_radarr_import(self):
        _clear_tasks()
        self._seed_radarr_task(importStatus="waiting_for_import")
        resp = client.post("/api/radarr/tasks/rtask-1/import/cancel")
        assert resp.status_code == 200
        updated = client.get("/api/radarr/tasks/rtask-1").json()
        assert updated["importStatus"] == "cancelled"

    def test_cancel_nonexistent_radarr_import(self):
        resp = client.post("/api/radarr/tasks/nonexistent/import/cancel")
        assert resp.status_code == 404
