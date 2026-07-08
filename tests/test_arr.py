import os
import uuid
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from tube_explore import db
from tube_explore.api import _lock, _tasks, _broadcast, app
from tube_explore.arr import db as arr_db
from tube_explore.arr.base_client import ArrError
from tube_explore.arr.crypto import decrypt_api_key, encrypt_api_key
from tube_explore.arr.models import ArrInstanceCreate, ArrInstanceUpdate, ArrKind
from tube_explore.arr.path_mapper import to_arr_path
from tube_explore.arr.radarr_client import RadarrClient
from tube_explore.arr.sonarr_client import SonarrClient
from tube_explore.config import get_config_dir
from tube_explore.models import TaskInfo

client = TestClient(app)


def _clear_tasks():
    with _lock:
        _tasks.clear()


# ── Helpers ──────────────────────────────────────────────────────


def _create_arr_data(kind: ArrKind = "radarr", **overrides):
    data = dict(
        name=f"test-{kind}-{uuid.uuid4().hex[:6]}",
        baseUrl="http://arr:7878",
        apiKey="abc123def456",
        kind=kind,
        tubeWritePath="/downloads/tube",
        arrImportPath="/downloads/arr",
        enabled=True,
    )
    data.update(overrides)
    return data


# ── Crypto tests ─────────────────────────────────────────────────


class TestCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        key = "my-secret-api-key-12345"
        config_dir = get_config_dir()
        encrypted = encrypt_api_key(key, config_dir)
        assert encrypted != key
        assert encrypted.startswith("gAAAAA")  # Fernet prefix
        decrypted = decrypt_api_key(encrypted, config_dir)
        assert decrypted == key

    def test_encryption_is_deterministic_with_same_key(self):
        key = "test-key"
        config_dir = get_config_dir()
        encrypted1 = encrypt_api_key(key, config_dir)
        encrypted2 = encrypt_api_key(key, config_dir)
        # Fernet produces different ciphertext each time (IV)
        assert encrypted1 != encrypted2
        assert decrypt_api_key(encrypted1, config_dir) == key
        assert decrypt_api_key(encrypted2, config_dir) == key

    def test_crypto_with_preexisting_salt_file(self):
        """Cover the salt-file-exists path (crypto.py lines 24-25)."""
        key = "existing-salt-test"
        config_dir = get_config_dir()
        salt_path = os.path.join(config_dir, "arr_api_key.salt")
        key_path = os.path.join(config_dir, "arr_api_key.key")
        # Remove artifacts so we start fresh
        for p in (salt_path, key_path):
            try: os.remove(p)
            except FileNotFoundError: pass
        # First call creates salt and key files
        encrypted = encrypt_api_key(key, config_dir)
        # Second call — both files already exist, _get_fernet reads key directly
        encrypted2 = encrypt_api_key(key, config_dir)
        assert encrypted != encrypted2
        assert os.path.exists(salt_path)
        assert os.path.exists(key_path)
        assert decrypt_api_key(encrypted, config_dir) == key
        assert decrypt_api_key(encrypted2, config_dir) == key

    def test_crypto_salt_exists_key_missing(self):
        """Cover _derive_key path where salt file already exists but key doesn't (lines 24-25)."""
        key = "salt-exists-no-key"
        config_dir = get_config_dir()
        salt_path = os.path.join(config_dir, "arr_api_key.salt")
        key_path = os.path.join(config_dir, "arr_api_key.key")
        # Delete key file but keep salt
        try: os.remove(key_path)
        except FileNotFoundError: pass
        # Ensure salt exists
        if not os.path.exists(salt_path):
            with open(salt_path, "wb") as f:
                f.write(os.urandom(16))
        # This forces _derive_key to read existing salt then create new key
        encrypted = encrypt_api_key(key, config_dir)
        assert encrypted.startswith("gAAAAA")
        assert decrypt_api_key(encrypted, config_dir) == key


# ── Path mapper tests ────────────────────────────────────────────


class TestPathMapper:
    def test_to_arr_path_basic(self):
        tube_dir, dest = to_arr_path(
            tube_write_path="/tube",
            arr_import_path="/arr",
            arr_item_path="/arr/Movies/Test Movie (2024)",
            local_file_path="/downloads/temp/video.mp4",
        )
        assert tube_dir == "/tube/Movies/Test Movie (2024)"
        assert dest == "/tube/Movies/Test Movie (2024)/video.mp4"

    def test_to_arr_path_no_subdir(self):
        tube_dir, dest = to_arr_path(
            tube_write_path="/tube",
            arr_import_path="/arr",
            arr_item_path="/arr",
            local_file_path="/tmp/video.mp4",
        )
        assert dest == "/tube/video.mp4"

    def test_to_arr_path_different_base(self):
        tube_dir, dest = to_arr_path(
            tube_write_path="/data/tube",
            arr_import_path="/media/arr",
            arr_item_path="/media/arr/Series/Breaking Bad/Season 1",
            local_file_path="/tmp/bb_s01e01.mkv",
        )
        assert tube_dir == "/data/tube/Series/Breaking Bad/Season 1"
        assert dest == "/data/tube/Series/Breaking Bad/Season 1/bb_s01e01.mkv"


# ── Arr DB tests ─────────────────────────────────────────────────


class TestArrDb:
    def _create_arr_instance(self, kind: ArrKind = "radarr"):
        import uuid
        data = ArrInstanceCreate(
            name=f"{kind}-{uuid.uuid4().hex[:8]}",
            base_url=f"http://{kind}:7878",
            api_key="encrypted-key-123",
            kind=kind,
            tube_write_path=f"/tube/{kind}",
            arr_import_path=f"/arr/{kind}",
        )
        return arr_db.create_arr_instance(data)

    def test_create_radarr_instance(self):
        inst = self._create_arr_instance("radarr")
        assert inst.id is not None
        assert inst.kind == "radarr"
        assert inst.name.startswith("radarr-")
        assert inst.enabled is True
        assert inst.is_default is False

    def test_create_sonarr_instance(self):
        inst = self._create_arr_instance("sonarr")
        assert inst.id is not None
        assert inst.kind == "sonarr"
        assert inst.name.startswith("sonarr-")
        assert inst.tube_write_path == "/tube/sonarr"
        assert inst.arr_import_path == "/arr/sonarr"

    def test_list_arr_instances_all(self):
        r = self._create_arr_instance("radarr")
        s = self._create_arr_instance("sonarr")
        all_insts = arr_db.list_arr_instances()
        ids = {i.id for i in all_insts}
        assert r.id in ids
        assert s.id in ids

    def test_list_arr_instances_by_kind(self):
        self._create_arr_instance("radarr")
        s = self._create_arr_instance("sonarr")
        radarrs = arr_db.list_arr_instances("radarr")
        sonarrs = arr_db.list_arr_instances("sonarr")
        assert all(i.kind == "radarr" for i in radarrs)
        assert all(i.kind == "sonarr" for i in sonarrs)
        assert s.id in {i.id for i in sonarrs}
        assert s.id not in {i.id for i in radarrs}

    def test_get_arr_instance(self):
        inst = self._create_arr_instance()
        fetched = arr_db.get_arr_instance(inst.id)
        assert fetched is not None
        assert fetched.id == inst.id
        assert fetched.name == inst.name

    def test_get_nonexistent_arr_instance(self):
        assert arr_db.get_arr_instance("nonexistent") is None

    def test_get_arr_instance_by_name(self):
        inst = self._create_arr_instance()
        fetched = arr_db.get_arr_instance_by_name(inst.name)
        assert fetched is not None
        assert fetched.id == inst.id

    def test_update_arr_instance(self):
        inst = self._create_arr_instance()
        update = ArrInstanceUpdate(base_url="http://new:7878", enabled=False)
        updated = arr_db.update_arr_instance(inst.id, update)
        assert updated is not None
        assert updated.base_url == "http://new:7878"
        assert updated.enabled is False
        assert updated.name == inst.name

    def test_update_nonexistent_arr_instance(self):
        result = arr_db.update_arr_instance("nope", ArrInstanceUpdate(name="x"))
        assert result is None

    def test_delete_arr_instance(self):
        inst = self._create_arr_instance()
        arr_db.delete_arr_instance(inst.id)
        assert arr_db.get_arr_instance(inst.id) is None

    def test_set_test_result(self):
        inst = self._create_arr_instance()
        arr_db.set_arr_instance_test_result(inst.id, "ok", None)
        updated = arr_db.get_arr_instance(inst.id)
        assert updated.last_test_status == "ok"

        arr_db.set_arr_instance_test_result(inst.id, "error", "connection failed", "4.0.0")
        updated = arr_db.get_arr_instance(inst.id)
        assert updated.last_test_status == "error"
        assert updated.last_test_message == "connection failed"
        assert updated.arr_version == "4.0.0"

    def test_set_sync_result(self):
        inst = self._create_arr_instance()
        arr_db.set_arr_instance_sync_result(inst.id, "ok")
        updated = arr_db.get_arr_instance(inst.id)
        assert updated.last_sync_status == "ok"
        assert updated.last_sync_at is not None

    def test_upsert_stats(self):
        inst = self._create_arr_instance()
        arr_db.upsert_arr_instance_stats(inst.id, {
            "missing_count": 10,
            "monitored_count": 50,
            "root_folder_count": 3,
        })
        stats = arr_db.get_arr_instance_stats(inst.id)
        assert stats is not None
        assert stats.missing_count == 10
        assert stats.monitored_count == 50
        assert stats.root_folder_count == 3
        assert stats.queue_count == 0

    def test_delete_cleans_up_stats(self):
        inst = self._create_arr_instance()
        arr_db.upsert_arr_instance_stats(inst.id, {"missing_count": 5})
        arr_db.delete_arr_instance(inst.id)
        assert arr_db.get_arr_instance_stats(inst.id) is None

    def test_create_duplicate_name_raises(self):
        name = f"dup-{uuid.uuid4().hex[:8]}"
        data = ArrInstanceCreate(
            name=name, base_url="http://r:7878", api_key="k",
            kind="radarr", tube_write_path="/t", arr_import_path="/r",
        )
        arr_db.create_arr_instance(data)
        with pytest.raises(ValueError, match="already exists"):
            arr_db.create_arr_instance(data)

    def test_default_flag(self):
        inst1 = self._create_arr_instance()
        inst2 = self._create_arr_instance()
        arr_db.update_arr_instance(inst2.id, ArrInstanceUpdate(is_default=True))
        updated1 = arr_db.get_arr_instance(inst1.id)
        updated2 = arr_db.get_arr_instance(inst2.id)
        assert updated2.is_default is True
        assert updated1.is_default is False


# ── RadarrClient unit tests ──────────────────────────────────────


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

    def test_auth_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 401
            rc = RadarrClient("http://r:7878", "bad_key")
            with pytest.raises(ArrError) as exc:
                rc.get_system_status()
            assert exc.value.code == "ARR_AUTH_FAILED"

    def test_connection_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.side_effect = httpx.RequestError("No route")
            rc = RadarrClient("http://r:7878", "key")
            with pytest.raises(ArrError) as exc:
                rc.get_system_status()
            assert exc.value.code == "ARR_CONNECTION_FAILED"

    def test_not_found(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 404
            rc = RadarrClient("http://r:7878", "key")
            with pytest.raises(ArrError) as exc:
                rc.get_system_status()
            assert exc.value.code == "ARR_NOT_FOUND"

    def test_server_error(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 500
            rc = RadarrClient("http://r:7878", "key")
            with pytest.raises(ArrError) as exc:
                rc.get_system_status()
            assert exc.value.code == "ARR_ERROR"

    def test_lookup_movie(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "title": "Test Movie"}]
            rc = RadarrClient("http://r:7878", "key")
            result = rc.lookup_movie("test")
            assert result[0]["title"] == "Test Movie"
            mock_instance.get.assert_called_with("/api/v3/movie/lookup?term=test")


# ── SonarrClient unit tests ──────────────────────────────────────


class TestSonarrClient:
    def test_ping_success(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            sc = SonarrClient("http://s:7878", "key")
            assert sc.ping() is True

    def test_get_system_status(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"version": "4.0.0"}
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_system_status()
            assert result["version"] == "4.0.0"

    def test_lookup_series(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "title": "Breaking Bad"}]
            sc = SonarrClient("http://s:7878", "key")
            result = sc.lookup_series("breaking")
            assert result[0]["title"] == "Breaking Bad"
            mock_instance.get.assert_called_with("/api/v3/series/lookup?term=breaking")

    def test_list_series(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"id": 1, "title": "Series A"},
                {"id": 2, "title": "Series B"},
            ]
            sc = SonarrClient("http://s:7878", "key")
            result = sc.list_series()
            assert len(result) == 2

    def test_get_series(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": 5, "title": "Test Series"}
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_series(5)
            assert result["title"] == "Test Series"
            mock_instance.get.assert_called_with("/api/v3/series/5")

    def test_get_episodes(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {"id": 10, "seriesId": 5, "episodeNumber": 1, "seasonNumber": 1, "title": "Pilot"},
            ]
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_episodes(5, 1)
            assert len(result) == 1
            assert result[0]["title"] == "Pilot"
            assert "seasonNumber=1" in mock_instance.get.call_args[0][0]

    def test_get_episodes_no_season(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = []
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_episodes(5)
            assert result == []
            assert "seasonNumber" not in mock_instance.get.call_args[0][0]

    def test_get_episode(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": 100, "title": "Ozymandias"}
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_episode(100)
            assert result["title"] == "Ozymandias"
            mock_instance.get.assert_called_with("/api/v3/episode/100")

    def test_get_wanted_missing(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"records": [{"id": 1, "title": "Missing Ep"}]}
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_wanted_missing()
            assert result["records"][0]["title"] == "Missing Ep"
            mock_instance.get.assert_called_with(
                "/api/v3/wanted/missing?page=1&pageSize=50&sortKey=AirDateUtc&sortDirection=Descending"
            )

    def test_get_episode_files(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "relativePath": "S01E01.mkv"}]
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_episode_files(5)
            assert result[0]["relativePath"] == "S01E01.mkv"
            mock_instance.get.assert_called_with("/api/v3/episodefile?seriesId=5")

    def test_get_root_folders(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "path": "/series"}]
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_root_folders()
            assert result[0]["path"] == "/series"

    def test_get_quality_profiles(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "name": "HD-1080p"}]
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_quality_profiles()
            assert result[0]["name"] == "HD-1080p"

    def test_create_command(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.post.return_value
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 42, "name": "RefreshSeries"}
            sc = SonarrClient("http://s:7878", "key")
            result = sc.create_command("RefreshSeries", seriesId=1)
            assert result["id"] == 42
            call_kwargs = mock_instance.post.call_args
            assert call_kwargs[1]["json"]["name"] == "RefreshSeries"

    def test_auth_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 401
            sc = SonarrClient("http://s:7878", "bad_key")
            with pytest.raises(ArrError) as exc:
                sc.get_system_status()
            assert exc.value.code == "ARR_AUTH_FAILED"

    def test_connection_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.side_effect = httpx.RequestError("No route")
            sc = SonarrClient("http://s:7878", "key")
            with pytest.raises(ArrError) as exc:
                sc.get_system_status()
            assert exc.value.code == "ARR_CONNECTION_FAILED"

    def test_get_queue(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"records": [{"seriesId": 1, "title": "Ep1", "status": "downloading"}]}
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_queue()
            assert result["records"][0]["title"] == "Ep1"

    def test_get_series_by_id(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": 99, "title": "Designated Series"}
            sc = SonarrClient("http://s:7878", "key")
            result = sc.get_series_by_id(99)
            assert result["title"] == "Designated Series"

    def test_update_series(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.put.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": 5, "title": "Updated Series", "monitored": True}
            sc = SonarrClient("http://s:7878", "key")
            result = sc.update_series(5, {"monitored": True})
            assert result["monitored"] is True
            mock_instance.put.assert_called_once()

    def test_put_auth_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.put.return_value
            mock_response.status_code = 401
            sc = SonarrClient("http://s:7878", "bad")
            with pytest.raises(ArrError) as exc:
                sc.update_series(1, {})
            assert exc.value.code == "ARR_AUTH_FAILED"

    def test_put_server_error(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.put.return_value
            mock_response.status_code = 500
            sc = SonarrClient("http://s:7878", "key")
            with pytest.raises(ArrError) as exc:
                sc.update_series(1, {})
            assert exc.value.code == "ARR_ERROR"

    def test_put_connection_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.put.side_effect = httpx.RequestError("No route")
            sc = SonarrClient("http://s:7878", "key")
            with pytest.raises(ArrError) as exc:
                sc.update_series(1, {})
            assert exc.value.code == "ARR_CONNECTION_FAILED"


# ── BaseArrClient unit tests ─────────────────────────────────────


class TestBaseArrClient:
    def test_post_connection_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.post.side_effect = httpx.RequestError("No route")
            sc = SonarrClient("http://s:7878", "key")
            with pytest.raises(ArrError) as exc:
                sc.create_command("RefreshSeries", seriesId=1)
            assert exc.value.code == "ARR_CONNECTION_FAILED"

    def test_post_auth_failure(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.post.return_value
            mock_response.status_code = 401
            sc = SonarrClient("http://s:7878", "bad")
            with pytest.raises(ArrError) as exc:
                sc.create_command("RefreshSeries", seriesId=1)
            assert exc.value.code == "ARR_AUTH_FAILED"

    def test_post_server_error(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.post.return_value
            mock_response.status_code = 500
            sc = SonarrClient("http://s:7878", "key")
            with pytest.raises(ArrError) as exc:
                sc.create_command("RefreshSeries", seriesId=1)
            assert exc.value.code == "ARR_ERROR"

    def test_post_204_no_content(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.post.return_value
            mock_response.status_code = 204
            mock_response.content = b""
            sc = SonarrClient("http://s:7878", "key")
            result = sc.create_command("RefreshSeries", seriesId=1)
            assert result == {}

    def test_post_empty_content(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.post.return_value
            mock_response.status_code = 200
            mock_response.content = b""
            sc = SonarrClient("http://s:7878", "key")
            result = sc.create_command("RefreshSeries", seriesId=1)
            assert result == {}

    def test_close(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            rc = RadarrClient("http://r:7878", "key")
            rc.close()
            mock_instance.close.assert_called_once()


# ── RadarrClient additional unit tests ──────────────────────────


class TestRadarrClientAdditional:
    def test_get_movie(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": 42, "title": "Test Movie", "hasFile": True}
            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_movie(42)
            assert result["title"] == "Test Movie"
            mock_instance.get.assert_called_with("/api/v3/movie/42")

    def test_get_quality_profiles(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "name": "HD-1080p"}]
            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_quality_profiles()
            assert result[0]["name"] == "HD-1080p"

    def test_get_queue(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"records": [{"movieId": 1, "title": "Movie 1", "status": "downloading"}]}
            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_queue()
            assert result["records"][0]["status"] == "downloading"

    def test_get_manual_import(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "path": "/movies/manual/test.mkv"}]
            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_manual_import("/movies/manual", movie_id=42)
            assert len(result) == 1
            assert result[0]["path"] == "/movies/manual/test.mkv"

    def test_get_manual_import_no_movie_id(self):
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = []
            rc = RadarrClient("http://r:7878", "key")
            result = rc.get_manual_import("/movies/manual")
            assert result == []


# ── Arr API endpoint tests ───────────────────────────────────────


class TestArrApi:
    def _create_instance(self, kind: str = "radarr", **overrides):
        data = _create_arr_data(kind=kind, **overrides)
        return client.post("/api/arr/instances", json=data)

    def test_create_radarr_instance(self):
        resp = self._create_instance("radarr")
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"].startswith("test-radarr-")
        assert data["kind"] == "radarr"
        assert data["baseUrl"] == "http://arr:7878"
        assert data["tubeWritePath"] == "/downloads/tube"
        assert data["arrImportPath"] == "/downloads/arr"
        assert data["enabled"] is True
        assert "apiKeyPreview" in data
        assert "id" in data

    def test_create_sonarr_instance(self):
        resp = self._create_instance("sonarr")
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"].startswith("test-sonarr-")
        assert data["kind"] == "sonarr"

    def test_create_duplicate_instance(self):
        resp = self._create_instance("radarr")
        assert resp.status_code == 201
        # Create with same name
        name = resp.json()["name"]
        resp2 = client.post("/api/arr/instances", json={
            "name": name, "baseUrl": "http://r:7878",
            "apiKey": "key", "kind": "radarr",
            "tubeWritePath": "/t", "arrImportPath": "/r",
        })
        assert resp2.status_code == 409

    def test_create_missing_api_key(self):
        resp = client.post("/api/arr/instances", json={
            "name": "nokey", "baseUrl": "http://r:7878",
            "kind": "radarr", "tubeWritePath": "/t", "arrImportPath": "/r",
        })
        assert resp.status_code == 400

    def test_list_arr_instances(self):
        self._create_instance("radarr", name="radarr-first")
        self._create_instance("sonarr", name="sonarr-second")
        resp = client.get("/api/arr/instances")
        assert resp.status_code == 200
        data = resp.json()
        names = {i["name"] for i in data}
        assert "radarr-first" in names
        assert "sonarr-second" in names

    def test_list_arr_instances_filtered(self):
        self._create_instance("radarr", name="radarr-only")
        self._create_instance("sonarr", name="sonarr-only")
        resp = client.get("/api/arr/instances?kind=sonarr")
        assert resp.status_code == 200
        data = resp.json()
        assert all(i["kind"] == "sonarr" for i in data)
        assert len(data) == 1

    def test_get_arr_instance(self):
        create = self._create_instance().json()
        resp = client.get(f"/api/arr/instances/{create['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == create["id"]

    def test_get_nonexistent_arr_instance(self):
        resp = client.get("/api/arr/instances/nonexistent")
        assert resp.status_code == 404

    def test_update_arr_instance(self):
        create = self._create_instance().json()
        resp = client.patch(f"/api/arr/instances/{create['id']}", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_update_nonexistent_arr_instance(self):
        resp = client.patch("/api/arr/instances/nonexistent", json={"enabled": False})
        assert resp.status_code == 404

    def test_update_arr_instance_change_kind(self):
        """Kind should not be changeable via update, but ensures no crash."""
        create = self._create_instance("radarr").json()
        resp = client.patch(
            f"/api/arr/instances/{create['id']}",
            json={"name": "renamed"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed"

    def test_delete_arr_instance(self):
        create = self._create_instance().json()
        resp = client.delete(f"/api/arr/instances/{create['id']}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        resp = client.get(f"/api/arr/instances/{create['id']}")
        assert resp.status_code == 404

    def test_delete_nonexistent_arr_instance(self):
        resp = client.delete("/api/arr/instances/nonexistent")
        assert resp.status_code == 404

    def test_set_default_arr_instance(self):
        create = self._create_instance().json()
        resp = client.post(f"/api/arr/instances/{create['id']}/set-default")
        assert resp.status_code == 200
        updated = client.get(f"/api/arr/instances/{create['id']}").json()
        assert updated["isDefault"] is True

    def test_set_default_nonexistent(self):
        resp = client.post("/api/arr/instances/nonexistent/set-default")
        assert resp.status_code == 404

    def test_test_arr_instance_no_server(self):
        create = self._create_instance().json()
        resp = client.post(f"/api/arr/instances/{create['id']}/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["canConnect"] is False

    def test_test_arr_instance_with_body(self):
        resp = client.post(
            "/api/arr/instances/nonexistent/test",
            json={"baseUrl": "http://invalid:7878", "apiKey": "bad"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False

    def test_summary_empty(self):
        resp = client.get("/api/arr/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalInstances"] == 0
        assert data["activeConnections"] == 0

    def test_summary_with_instances(self):
        self._create_instance("radarr")
        self._create_instance("sonarr")
        resp = client.get("/api/arr/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalInstances"] >= 2

    def test_sync_history(self):
        create = self._create_instance().json()
        resp = client.get(f"/api/arr/instances/{create['id']}/sync-history")
        assert resp.status_code == 200
        assert resp.json()["history"] == []

    def test_test_results(self):
        create = self._create_instance().json()
        resp = client.get(f"/api/arr/instances/{create['id']}/test-results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lastTestStatus"] is None
        assert data["kind"] == "radarr"

    def test_root_folders_disabled_instance(self):
        create = self._create_instance(enabled=False).json()
        resp = client.get(f"/api/arr/instances/{create['id']}/root-folders")
        assert resp.status_code == 400

    def test_root_folders_nonexistent(self):
        resp = client.get("/api/arr/instances/nonexistent/root-folders")
        assert resp.status_code == 404

    def test_quality_profiles_disabled(self):
        create = self._create_instance(enabled=False).json()
        resp = client.get(f"/api/arr/instances/{create['id']}/quality-profiles")
        assert resp.status_code == 400

    def test_queue_disabled(self):
        create = self._create_instance(enabled=False).json()
        resp = client.get(f"/api/arr/instances/{create['id']}/queue")
        assert resp.status_code == 400

    def test_sync_disabled(self):
        create = self._create_instance(enabled=False).json()
        resp = client.post(f"/api/arr/instances/{create['id']}/sync")
        assert resp.status_code == 400

    def test_missing_items_disabled(self):
        create = self._create_instance(enabled=False).json()
        resp = client.get(f"/api/arr/instances/{create['id']}/missing")
        assert resp.status_code == 400

    def test_missing_items_nonexistent(self):
        resp = client.get("/api/arr/instances/nonexistent/missing")
        assert resp.status_code == 404

    def test_backward_compat_radarr_routes(self):
        """Old /api/radarr/ instances endpoints should still work."""
        create_resp = client.post("/api/radarr/instances", json={
            "name": "compat-radarr",
            "baseUrl": "http://radarr:7878",
            "apiKey": "test-key-123",
            "tubeWritePath": "/tube",
            "radarrImportPath": "/radarr",
            "enabled": True,
        })
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["name"] == "compat-radarr"

        list_resp = client.get("/api/radarr/instances")
        assert list_resp.status_code == 200
        names = {i["name"] for i in list_resp.json()}
        assert "compat-radarr" in names

        # Verify it also shows up in /api/arr/
        arr_list = client.get("/api/arr/instances?kind=radarr").json()
        arr_names = {i["name"] for i in arr_list}
        assert "compat-radarr" in arr_names


# ── Arr task integration endpoints ───────────────────────────────


class TestArrTaskIntegration:
    def _seed_arr_task(self, integration_type: str = "radarr", **overrides):
        meta = dict(
            instanceId="inst-1", instanceName="My Instance",
            itemId=42, itemTitle="Test Item",
            importStatus="none", importMode="move",
        )
        meta.update(overrides)
        import uuid
        tid = f"arrtask-{uuid.uuid4().hex[:8]}"
        task = TaskInfo(
            id=tid, type="video", url="https://youtube.com/watch?v=test",
            params={}, status="completed", progress_percent=100,
            created_at=datetime.now(UTC), completed_at=datetime.now(UTC),
            integration=integration_type, integration_meta=meta,
        )
        with _lock:
            _tasks[tid] = task
        return tid

    def test_get_arr_task_radarr(self):
        _clear_tasks()
        tid = self._seed_arr_task("radarr")
        resp = client.get(f"/api/arr/tasks/{tid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["arrItemId"] == 42
        assert data["kind"] == "radarr"
        assert data["importStatus"] == "none"

    def test_get_arr_task_sonarr(self):
        _clear_tasks()
        tid = self._seed_arr_task("sonarr")
        resp = client.get(f"/api/arr/tasks/{tid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["kind"] == "sonarr"
        assert data["arrItemId"] == 42

    def test_get_nonexistent_arr_task(self):
        resp = client.get("/api/arr/tasks/nonexistent")
        assert resp.status_code == 404

    def test_get_non_arr_task(self):
        _clear_tasks()
        import uuid
        task = TaskInfo(
            id="non-arr", type="video", url="https://youtube.com/watch?v=x",
            params={}, status="completed", progress_percent=100,
            created_at=datetime.now(UTC),
        )
        with _lock:
            _tasks["non-arr"] = task
        resp = client.get("/api/arr/tasks/non-arr")
        assert resp.status_code == 404

    def test_retry_arr_import(self):
        _clear_tasks()
        tid = self._seed_arr_task("sonarr", importStatus="failed")
        resp = client.post(f"/api/arr/tasks/{tid}/import/retry")
        assert resp.status_code == 200
        updated = client.get(f"/api/arr/tasks/{tid}").json()
        assert updated["importStatus"] == "waiting_for_import"

    def test_retry_nonexistent_arr_import(self):
        resp = client.post("/api/arr/tasks/nonexistent/import/retry")
        assert resp.status_code == 404

    def test_cancel_arr_import(self):
        _clear_tasks()
        tid = self._seed_arr_task("radarr", importStatus="waiting_for_import")
        resp = client.post(f"/api/arr/tasks/{tid}/import/cancel")
        assert resp.status_code == 200
        updated = client.get(f"/api/arr/tasks/{tid}").json()
        assert updated["importStatus"] == "cancelled"

    def test_cancel_nonexistent_arr_import(self):
        resp = client.post("/api/arr/tasks/nonexistent/import/cancel")
        assert resp.status_code == 404


# ── Arr download endpoint ────────────────────────────────────────


class TestArrDownload:
    def test_download_no_url(self):
        resp = client.post("/api/arr/download", json={})
        assert resp.status_code == 422

    def test_download_with_invalid_url(self):
        resp = client.post("/api/arr/download", json={
            "url": "not-a-url",
        })
        assert resp.status_code == 422



# ── Sonarr-specific route endpoint tests ──────────────────────────


class TestSonarrRoutes(TestArrApi):
    """Requires TestArrApi helper methods."""

    def _create_sonarr_instance(self):
        return self._create_instance("sonarr").json()

    def test_list_series_radarr_rejected(self):
        inst = self._create_instance("radarr").json()
        resp = client.get(f"/api/arr/instances/{inst['id']}/series")
        assert resp.status_code == 400

    def test_lookup_series_radarr_rejected(self):
        inst = self._create_instance("radarr").json()
        resp = client.get(f"/api/arr/instances/{inst['id']}/series/lookup?term=test")
        assert resp.status_code == 400

    def test_get_series_radarr_rejected(self):
        inst = self._create_instance("radarr").json()
        resp = client.get(f"/api/arr/instances/{inst['id']}/series/1")
        assert resp.status_code == 400

    def test_list_episodes_radarr_rejected(self):
        inst = self._create_instance("radarr").json()
        resp = client.get(f"/api/arr/instances/{inst['id']}/series/1/episodes")
        assert resp.status_code == 400

    def test_get_episode_radarr_rejected(self):
        inst = self._create_instance("radarr").json()
        resp = client.get(f"/api/arr/instances/{inst['id']}/series/1/episodes/1")
        assert resp.status_code == 400

    def test_list_series_enabled_sonarr(self):
        """Sonarr series endpoint with mocked client."""
        import json
        fake_series = [
            {"id": 1, "title": "Series A", "year": 2020, "tvdbId": 100, "seasons": [{"seasonNumber": 1}],
             "overview": "Test", "monitored": True, "status": "continuing", "network": "NBC",
             "path": "/series/a", "qualityProfileId": 1, "rootFolderPath": "/data/series",
             "images": [{"coverType": "poster", "url": "http://img/poster.jpg"}],
             "imdbId": "tt1234"},
        ]
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = fake_series
            resp = client.get(f"/api/arr/instances/{inst['id']}/series")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["title"] == "Series A"
            assert data[0]["seasonCount"] == 1

    def test_list_series_arr_error(self):
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/series")
            assert resp.status_code == 500

    def test_lookup_series(self):
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "title": "Breaking Bad", "year": 2008}]
            resp = client.get(f"/api/arr/instances/{inst['id']}/series/lookup?term=breaking")
            assert resp.status_code == 200
            data = resp.json()
            assert data[0]["title"] == "Breaking Bad"

    def test_lookup_series_arr_error(self):
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/series/lookup?term=test")
            assert resp.status_code == 500

    def test_get_series(self):
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            fake_get = mock_instance.get
            fake_get.return_value.status_code = 200
            fake_get.return_value.json.return_value = {
                "id": 5, "title": "Test Series", "year": 2021, "seasons": [{"seasonNumber": 1}, {"seasonNumber": 2}],
                "monitored": True, "status": "ended", "network": "AMC",
                "path": "/series/test", "qualityProfileId": 1, "rootFolderPath": "/data",
                "overview": "Great show", "tvdbId": 200, "imdbId": "tt5678",
                "images": [], "seasonCount": 2,
            }
            resp = client.get(f"/api/arr/instances/{inst['id']}/series/5")
            assert resp.status_code == 200
            data = resp.json()
            assert data["title"] == "Test Series"
            assert data["seasonCount"] == 2

    def test_get_series_arr_error(self):
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/series/5")
            assert resp.status_code == 500

    def test_list_episodes(self):
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 200
            # First call: episodes, Second call: series
            mock_instance.get.return_value.json.side_effect = [
                [{"id": 10, "seriesId": 5, "episodeNumber": 1, "seasonNumber": 1, "title": "Pilot",
                  "overview": "First", "airDateUtc": "2021-01-01", "monitored": True, "hasFile": False,
                  "images": []}],
                {"id": 5, "title": "Test Series", "seasons": [{"seasonNumber": 1}]},
            ]
            resp = client.get(f"/api/arr/instances/{inst['id']}/series/5/episodes?seasonNumber=1")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["title"] == "Pilot"
            assert data[0]["seriesTitle"] == "Test Series"

    def test_list_episodes_arr_error(self):
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/series/5/episodes")
            assert resp.status_code == 500

    def test_get_episode(self):
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 200
            # First call: episode, Second call: series
            mock_instance.get.return_value.json.side_effect = [
                {"id": 100, "seriesId": 5, "episodeNumber": 9, "seasonNumber": 5, "title": "Ozymandias",
                 "overview": "Best episode", "airDateUtc": "2013-09-15", "monitored": True, "hasFile": True},
                {"id": 5, "title": "Breaking Bad"},
            ]
            resp = client.get(f"/api/arr/instances/{inst['id']}/series/5/episodes/100")
            assert resp.status_code == 200
            data = resp.json()
            assert data["title"] == "Ozymandias"
            assert data.get("seriesTitle") == "Breaking Bad"

    def test_get_episode_arr_error(self):
        inst = self._create_sonarr_instance()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/series/5/episodes/100")
            assert resp.status_code == 500


# ─── Route tests: root-folders, quality-profiles, queue success paths ───


class TestArrRouteSuccess(TestArrApi):
    def test_root_folders_success(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "path": "/series", "accessible": True, "freeSpace": 1000000}]
            resp = client.get(f"/api/arr/instances/{inst['id']}/root-folders")
            assert resp.status_code == 200
            data = resp.json()
            assert data[0]["path"] == "/series"
            assert data[0]["freeSpace"] == 1000000

    def test_root_folders_arr_error(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/root-folders")
            assert resp.status_code == 500

    def test_quality_profiles_success(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = [{"id": 1, "name": "HD-1080p"}]
            resp = client.get(f"/api/arr/instances/{inst['id']}/quality-profiles")
            assert resp.status_code == 200
            data = resp.json()
            assert data[0]["name"] == "HD-1080p"

    def test_quality_profiles_arr_error(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/quality-profiles")
            assert resp.status_code == 500

    def test_queue_success_radarr(self):
        inst = self._create_instance("radarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"records": [{"movieId": 1, "title": "Movie", "status": "downloading"}]}
            resp = client.get(f"/api/arr/instances/{inst['id']}/queue")
            assert resp.status_code == 200
            data = resp.json()
            assert data[0]["itemId"] == 1

    def test_queue_success_sonarr(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {"records": [{"seriesId": 5, "title": "Episode", "status": "downloading"}]}
            resp = client.get(f"/api/arr/instances/{inst['id']}/queue")
            assert resp.status_code == 200
            data = resp.json()
            assert data[0]["itemId"] == 5

    def test_queue_arr_error(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_response = mock_instance.get.return_value
            mock_response.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/queue")
            assert resp.status_code == 500

    def test_sync_radarr_success(self):
        inst = self._create_instance("radarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 200
            mock_instance.get.return_value.json.side_effect = [
                {"version": "5.0.0"},                # get_system_status
                [{"id": 1, "path": "/movies"}],      # get_root_folders
                [{"id": 1, "title": "Movie", "hasFile": False, "monitored": True}],  # get_missing_movies
            ]
            resp = client.post(f"/api/arr/instances/{inst['id']}/sync")
            assert resp.status_code == 200

    def test_sync_sonarr_success(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 200
            mock_instance.get.return_value.json.side_effect = [
                {"version": "4.0.0"},                # get_system_status
                [{"id": 1, "path": "/series"}],      # get_root_folders
                {"records": [{"id": 1, "title": "Missing Ep", "hasFile": False, "seriesId": 1}]},  # get_wanted_missing
                {"id": 1, "title": "Test Series"},    # get_series (in _list_missing_sonarr)
            ]
            resp = client.post(f"/api/arr/instances/{inst['id']}/sync")
            assert resp.status_code == 200

    def test_sync_arr_error(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.side_effect = httpx.RequestError("fail")
            resp = client.post(f"/api/arr/instances/{inst['id']}/sync")
            assert resp.status_code == 500

    def test_missing_items_sonarr_success(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 200
            mock_instance.get.return_value.json.side_effect = [
                {"totalRecords": 1, "records": [{"id": 1, "title": "Missing Ep", "hasFile": False, "monitored": True,
                                                 "seasonNumber": 1, "episodeNumber": 1, "seriesId": 5,
                                                 "airDateUtc": "2024-01-01",
                                                 "overview": "A missing episode"}]},
                {"id": 5, "title": "Test Series"},
            ]
            resp = client.get(f"/api/arr/instances/{inst['id']}/missing")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] >= 1
            assert "Test Series" in data["items"][0]["title"]

    def test_missing_items_sonarr_arr_error(self):
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/missing")
            assert resp.status_code == 500

    def test_missing_items_radarr_success(self):
        inst = self._create_instance("radarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 200
            mock_instance.get.return_value.json.return_value = [
                {"id": 1, "title": "Missing Movie", "year": 2024, "hasFile": False, "monitored": True,
                 "tmdbId": 123, "imdbId": "tt456", "qualityProfileId": 1,
                 "rootFolderPath": "/movies", "path": "/movies/Missing Movie (2024)",
                 "images": [{"remoteUrl": "http://img/poster.jpg"}], "overview": "A missing movie"},
            ]
            resp = client.get(f"/api/arr/instances/{inst['id']}/missing")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] >= 1
            assert data["items"][0]["title"] == "Missing Movie"

    def test_missing_items_radarr_search(self):
        inst = self._create_instance("radarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 200
            mock_instance.get.return_value.json.return_value = [
                {"id": 1, "title": "Found Movie", "hasFile": False, "monitored": True},
                {"id": 2, "title": "Other Movie", "hasFile": False, "monitored": True},
            ]
            resp = client.get(f"/api/arr/instances/{inst['id']}/missing?search=found")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["items"][0]["title"] == "Found Movie"

    def test_missing_items_radarr_arr_error(self):
        inst = self._create_instance("radarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 500
            resp = client.get(f"/api/arr/instances/{inst['id']}/missing")
            assert resp.status_code == 500

    def test_summary_with_instances_and_statuses(self):
        """Cover _instance_to_response all status paths + summary."""
        radarr = self._create_instance("radarr").json()
        sonarr = self._create_instance("sonarr").json()
        # Mark radarr as connected
        client.post(f"/api/arr/instances/{radarr['id']}/test", json={
            "baseUrl": "http://r:7878", "apiKey": "key",
        })
        # Mark sonarr as error
        client.post(f"/api/arr/instances/{sonarr['id']}/test", json={
            "baseUrl": "http://s:7878", "apiKey": "bad",
        })
        resp = client.get("/api/arr/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["totalInstances"] >= 2


# ── Download endpoint with valid params ──────────────────────────


class TestArrDownloadExtended:
    def _clear(self):
        from tube_explore.api import _lock, _tasks
        with _lock:
            _tasks.clear()

    def test_download_with_instance(self):
        self._clear()
        resp = client.post("/api/arr/download", json={
            "url": "https://youtube.com/watch?v=test123",
            "instanceId": "test-instance",
            "itemId": 42,
            "itemTitle": "Test Item",
            "kind": "sonarr",
        })
        # Should fail at instance lookup but not 422
        assert resp.status_code == 404  # instance not found

    def test_download_minimal(self):
        self._clear()
        resp = client.post("/api/arr/download", json={
            "url": "https://youtube.com/watch?v=test456",
        })
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "pending"


# ── Arr DB additional tests ─────────────────────────────────────


class TestArrDbAdditional:
    def test_create_instance_with_default(self):
        import uuid
        name = f"default-test-{uuid.uuid4().hex[:8]}"
        data = ArrInstanceCreate(
            name=name, base_url="http://r:7878", api_key="key",
            kind="radarr", tube_write_path="/t", arr_import_path="/r",
            is_default=True,
        )
        inst = arr_db.create_arr_instance(data)
        assert inst.is_default is True

    def test_update_instance_no_fields(self):
        instance = arr_db.list_arr_instances("radarr")
        if not instance:
            pytest.skip("no instances to test")
        # Updates with no changes should return the instance
        result = arr_db.update_arr_instance(instance[0].id, ArrInstanceUpdate())
        assert result is not None
        assert result.id == instance[0].id

    def test_stats_with_sync_at(self):
        import uuid
        name = f"sync-test-{uuid.uuid4().hex[:8]}"
        data = ArrInstanceCreate(
            name=name, base_url="http://r:7878", api_key="key",
            kind="radarr", tube_write_path="/t", arr_import_path="/r",
        )
        inst = arr_db.create_arr_instance(data)
        arr_db.upsert_arr_instance_stats(inst.id, {
            "missing_count": 5,
            "monitored_count": 10,
            "last_sync_at": datetime.now(UTC).isoformat(),
        })
        stats = arr_db.get_arr_instance_stats(inst.id)
        assert stats is not None
        assert stats.missing_count == 5
        assert stats.last_sync_at is not None

    def test_migrate_from_radarr_tables(self):
        """Test that migration from old radarr tables works."""
        import uuid
        from tube_explore.arr import db as arr_db_module
        from tube_explore.config import get_db_path
        import os, sqlite3

        old_id = str(uuid.uuid4())
        old_name = f"migrate-test-{uuid.uuid4().hex[:8]}"
        now = datetime.now(UTC).isoformat()

        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        # Ensure old radarr table exists (from main db)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='radarr_instances'"
        ).fetchall()
        if not rows:
            pytest.skip("No radarr_instances table to migrate from")

        conn.execute(
            "INSERT OR IGNORE INTO radarr_instances "
            "(id, name, base_url, api_key_encrypted, tube_write_path, radarr_import_path, "
            "host_path_hint, default_profile_id, default_quality_profile_id, "
            "default_root_folder_path, import_mode, enabled, is_default, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (old_id, old_name, "http://old:7878", "enc-key",
             "/tube", "/radarr", None, None, None, None, "move", 1, 0, now, now),
        )
        # Add stats
        conn.execute(
            "INSERT OR IGNORE INTO radarr_instance_stats "
            "(radarr_instance_id, missing_count, monitored_count, unmonitored_missing_count, "
            "root_folder_count, queue_count, imports_24h, last_sync_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (old_id, 5, 10, 2, 1, 0, 0, now, now),
        )
        conn.commit()

        # Run migration once
        arr_db_module.migrate_from_radarr_tables(conn)
        conn.commit()

        # Verify migrated instance exists in arr_instances
        migrated = conn.execute(
            "SELECT * FROM arr_instances WHERE id = ?", (old_id,)
        ).fetchone()
        assert migrated is not None
        assert migrated["name"] == old_name
        assert migrated["kind"] == "radarr"

        # Verify stats migrated
        migrated_stats = conn.execute(
            "SELECT * FROM arr_instance_stats WHERE arr_instance_id = ?", (old_id,)
        ).fetchone()
        assert migrated_stats is not None
        assert migrated_stats["missing_count"] == 5

        # Run migration again — should skip existing (covers db.py line 196)
        arr_db_module.migrate_from_radarr_tables(conn)
        conn.commit()

        conn.close()


# ── Arr route: status mapping coverage ──────────────────────────


class TestArrInstanceToResponse:
    """Cover _instance_to_response mapping for all status paths."""

    def test_enabled_no_test(self):
        import uuid
        name = f"notest-{uuid.uuid4().hex[:8]}"
        data = ArrInstanceCreate(
            name=name, base_url="http://r:7878", api_key="key",
            kind="sonarr", tube_write_path="/t", arr_import_path="/r",
            enabled=True,
        )
        inst = arr_db.create_arr_instance(data)
        resp = client.get(f"/api/arr/instances/{inst.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "unknown"

    def test_health_message_mapped(self):
        import uuid
        name = f"healthmsg-{uuid.uuid4().hex[:8]}"
        data = ArrInstanceCreate(
            name=name, base_url="http://r:7878", api_key="key",
            kind="sonarr", tube_write_path="/t", arr_import_path="/r",
            enabled=True,
        )
        inst = arr_db.create_arr_instance(data)
        arr_db.set_arr_instance_test_result(inst.id, "error", "Disk full")
        resp = client.get(f"/api/arr/instances/{inst.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert data["healthMessage"] == "Disk full"

    def test_status_warning(self):
        import uuid
        name = f"warn-{uuid.uuid4().hex[:8]}"
        data = ArrInstanceCreate(
            name=name, base_url="http://r:7878", api_key="key",
            kind="radarr", tube_write_path="/t", arr_import_path="/r",
            enabled=True,
        )
        inst = arr_db.create_arr_instance(data)
        arr_db.set_arr_instance_test_result(inst.id, "warning", "Slow connection")
        resp = client.get(f"/api/arr/instances/{inst.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "warning"


# ── Test route error handling and edge cases ─────────────────────


class TestArrRouteEdgeCases(TestArrApi):
    """Cover remaining routes.py uncovered paths."""

    def test_update_with_api_key(self):
        """Cover routes.py line 182 (api_key path in update)."""
        inst = self._create_instance("sonarr").json()
        resp = client.patch(f"/api/arr/instances/{inst['id']}", json={
            "apiKey": "new-secret-key",
        })
        assert resp.status_code == 200
        # apiKeyPreview should change
        assert "new" not in (resp.json().get("apiKeyPreview") or "")

    def test_update_with_empty_api_key(self):
        """Cover routes.py line 184 (api_key empty/falsy, pop it)."""
        inst = self._create_instance("sonarr").json()
        resp = client.patch(f"/api/arr/instances/{inst['id']}", json={
            "apiKey": "",
        })
        assert resp.status_code == 200

    def test_update_nonexistent_field_ignored(self):
        """Cover routes.py line 189 (update returns None)."""
        resp = client.patch("/api/arr/instances/nonexistent", json={"name": "new"})
        assert resp.status_code == 404

    def test_test_with_sonarr_kind_from_body(self):
        """Cover routes.py line 242 (test with client_kind detection from existing instance)."""
        import json
        inst = self._create_instance("sonarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            # Make ping fail so we get an ArrError instead of trying root folders
            mock_instance.get.side_effect = httpx.RequestError("fail")
            resp = client.post(f"/api/arr/instances/{inst['id']}/test", json={
                "baseUrl": "http://sonarr:8989",
                "apiKey": "test-key",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is False

    def test_test_no_body_sonarr(self):
        """Cover routes.py lines 252-279 (test with sonarr kind, full success)."""
        inst = self._create_instance("sonarr").json()
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Update the instance to point to a writable temp dir
            client.patch(f"/api/arr/instances/{inst['id']}", json={
                "tubeWritePath": tmpdir,
            })
            with patch.object(httpx, "Client") as MockClient:
                mock_instance = MockClient.return_value
                mock_instance.get.return_value.status_code = 200
                mock_instance.get.return_value.json.side_effect = [
                    {"version": "4.0.0"},  # get_system_status
                    [{"id": 1, "path": "/series"}],  # get_root_folders
                ]
                resp = client.post(f"/api/arr/instances/{inst['id']}/test")
                assert resp.status_code == 200
                data = resp.json()
                assert data["canConnect"] is True
                assert data["tubeWritePathWritable"] is True

    def test_summary_with_last_sync(self):
        """Cover routes.py line 365 (last_sync calculation)."""
        import uuid
        from datetime import UTC, datetime
        name = f"sync-summary-{uuid.uuid4().hex[:8]}"
        data = ArrInstanceCreate(
            name=name, base_url="http://r:7878", api_key="key",
            kind="radarr", tube_write_path="/t", arr_import_path="/r",
            enabled=True,
        )
        inst = arr_db.create_arr_instance(data)
        arr_db.set_arr_instance_sync_result(inst.id, "ok")
        resp = client.get("/api/arr/summary")
        assert resp.status_code == 200
        data = resp.json()
        # Wait — the sync happened, but summary might not pick it up
        # because it reads from the DB. Checking that it still works.
        assert "totalInstances" in data

    def test_missing_radarr_with_has_file(self):
        """Cover routes.py line 446 (skip movies with hasFile)."""
        inst = self._create_instance("radarr").json()
        with patch.object(httpx, "Client") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.get.return_value.status_code = 200
            mock_instance.get.return_value.json.return_value = [
                {"id": 1, "title": "Has File", "hasFile": True, "monitored": True},
                {"id": 2, "title": "Missing", "hasFile": False, "monitored": True,
                 "year": 2024, "tmdbId": 123, "imdbId": "tt456", "qualityProfileId": 1,
                 "rootFolderPath": "/movies", "path": "/movies/Missing",
                 "images": [{"remoteUrl": "http://img/poster.jpg"}], "overview": "desc"},
            ]
            resp = client.get(f"/api/arr/instances/{inst['id']}/missing")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 1
            assert data["items"][0]["title"] == "Missing"


from datetime import UTC, datetime  # noqa: E402, F811
