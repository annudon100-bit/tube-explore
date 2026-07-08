from typing import Any
from urllib.parse import urlencode

import httpx

from tube_explore.arr.base_client import ArrError, BaseArrClient


class SonarrClient(BaseArrClient):
    def get_system_status(self) -> dict:
        return self._get("/api/v3/system/status")

    def get_root_folders(self) -> list[dict]:
        return self._get("/api/v3/rootfolder")

    def get_quality_profiles(self) -> list[dict]:
        return self._get("/api/v3/qualityprofile")

    def get_queue(self, params: dict | None = None) -> dict:
        return self._get("/api/v3/queue")

    def lookup_series(self, term: str) -> list[dict]:
        return self._get(f"/api/v3/series/lookup?term={term}")

    def get_series(self, series_id: int) -> dict:
        return self._get(f"/api/v3/series/{series_id}")

    def list_series(self) -> list[dict]:
        return self._get("/api/v3/series")

    def get_episodes(self, series_id: int, season_number: int | None = None) -> list[dict]:
        path = f"/api/v3/episode?seriesId={series_id}"
        if season_number is not None:
            path += f"&seasonNumber={season_number}"
        return self._get(path)

    def get_episode(self, episode_id: int) -> dict:
        return self._get(f"/api/v3/episode/{episode_id}")

    def get_episode_files(self, series_id: int) -> list[dict]:
        return self._get(f"/api/v3/episodefile?seriesId={series_id}")

    def get_wanted_missing(self, params: dict | None = None) -> dict:
        query = params or {}
        query.setdefault("page", 1)
        query.setdefault("pageSize", 50)
        query.setdefault("sortKey", "AirDateUtc")
        query.setdefault("sortDirection", "Descending")
        qs = urlencode(query)
        return self._get(f"/api/v3/wanted/missing?{qs}")

    def get_series_by_id(self, series_id: int) -> dict:
        return self._get(f"/api/v3/series/{series_id}")

    def update_series(self, series_id: int, data: dict) -> dict:
        return self._put(f"/api/v3/series/{series_id}", json=data)

    def manual_import(self, items: list[dict]) -> list[dict]:
        return self._post("/api/v3/manualimport", json=items)

    def get_command(self, command_id: int) -> dict:
        return self._get(f"/api/v3/command/{command_id}")

    def _put(self, path: str, json: dict | None = None) -> Any:
        try:
            resp = self._client.put(path, json=json)
        except httpx.RequestError as e:
            raise ArrError("ARR_CONNECTION_FAILED", f"Connection failed: {e}")
        if resp.status_code == 401:
            raise ArrError("ARR_AUTH_FAILED", "API key rejected", 401)
        if resp.status_code >= 400:
            raise ArrError("ARR_ERROR", f"Arr returned {resp.status_code}", resp.status_code)
        return resp.json()
