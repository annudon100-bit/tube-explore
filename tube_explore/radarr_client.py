import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RADARR_TIMEOUT = 15.0


class RadarrError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 0):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class RadarrClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Api-Key": api_key, "Accept": "application/json"},
            timeout=RADARR_TIMEOUT,
            follow_redirects=False,
        )

    def _get(self, path: str) -> Any:
        try:
            resp = self._client.get(path)
        except httpx.RequestError as e:
            raise RadarrError("RADARR_CONNECTION_FAILED", f"Connection failed: {e}")
        if resp.status_code == 401:
            raise RadarrError("RADARR_AUTH_FAILED", "API key rejected by Radarr", 401)
        if resp.status_code == 404:
            raise RadarrError("RADARR_NOT_FOUND", f"Resource not found: {path}", 404)
        if resp.status_code >= 400:
            raise RadarrError("RADARR_ERROR", f"Radarr returned {resp.status_code}", resp.status_code)
        return resp.json()

    def _post(self, path: str, json: dict | None = None) -> Any:
        try:
            resp = self._client.post(path, json=json)
        except httpx.RequestError as e:
            raise RadarrError("RADARR_CONNECTION_FAILED", f"Connection failed: {e}")
        if resp.status_code == 401:
            raise RadarrError("RADARR_AUTH_FAILED", "API key rejected by Radarr", 401)
        if resp.status_code >= 400:
            raise RadarrError("RADARR_ERROR", f"Radarr returned {resp.status_code}", resp.status_code)
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def ping(self) -> bool:
        try:
            resp = self._client.get("/ping")
            return resp.status_code == 200
        except Exception:
            return False

    def get_system_status(self) -> dict:
        return self._get("/api/v3/system/status")

    def get_root_folders(self) -> list[dict]:
        return self._get("/api/v3/rootfolder")

    def get_quality_profiles(self) -> list[dict]:
        return self._get("/api/v3/qualityprofile")

    def get_missing_movies(self, params: dict | None = None) -> dict:
        query = params or {}
        query.setdefault("page", 1)
        query.setdefault("pageSize", 50)
        query.setdefault("sortKey", "title")
        query.setdefault("sortDirection", "asc")
        query["filterKey"] = "monitored"
        query["filterValue"] = "true"
        return self._get("/api/v3/movie")

    def get_movie(self, movie_id: int) -> dict:
        return self._get(f"/api/v3/movie/{movie_id}")

    def get_queue(self, params: dict | None = None) -> dict:
        query = params or {}
        return self._get("/api/v3/queue")

    def get_manual_import(self, folder: str, movie_id: int | None = None) -> list[dict]:
        params = {"folder": folder}
        if movie_id is not None:
            params["movieId"] = movie_id
        return self._get(f"/api/v3/manualimport")

    def create_command(self, name: str, **kwargs) -> dict:
        body = {"name": name, **kwargs}
        return self._post("/api/v3/command", json=body)

    def close(self):
        self._client.close()
