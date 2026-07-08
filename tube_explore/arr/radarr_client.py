from typing import Any
from urllib.parse import urlencode

from tube_explore.arr.base_client import BaseArrClient


class RadarrClient(BaseArrClient):
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
        qs = urlencode(query)
        return self._get(f"/api/v3/movie?{qs}")

    def get_movie(self, movie_id: int) -> dict:
        return self._get(f"/api/v3/movie/{movie_id}")

    def get_queue(self, params: dict | None = None) -> dict:
        return self._get("/api/v3/queue")

    def get_manual_import(self, folder: str, movie_id: int | None = None) -> list[dict]:
        params = {"folder": folder}
        if movie_id is not None:
            params["movieId"] = movie_id
        return self._get("/api/v3/manualimport")

    def lookup_movie(self, term: str) -> list[dict]:
        return self._get(f"/api/v3/movie/lookup?term={term}")
