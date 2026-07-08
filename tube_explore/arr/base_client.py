import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ARR_TIMEOUT = 15.0


class ArrError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 0):
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class BaseArrClient(ABC):
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Api-Key": api_key, "Accept": "application/json"},
            timeout=ARR_TIMEOUT,
            follow_redirects=False,
        )

    def _get(self, path: str) -> Any:
        try:
            resp = self._client.get(path)
        except httpx.RequestError as e:
            raise ArrError("ARR_CONNECTION_FAILED", f"Connection failed: {e}")
        if resp.status_code == 401:
            raise ArrError("ARR_AUTH_FAILED", "API key rejected", 401)
        if resp.status_code == 404:
            raise ArrError("ARR_NOT_FOUND", f"Resource not found: {path}", 404)
        if resp.status_code >= 400:
            body = resp.text[:500] if resp.text else ""
            raise ArrError("ARR_ERROR", f"Arr returned {resp.status_code}: {body}", resp.status_code)
        return resp.json()

    def _post(self, path: str, json: dict | None = None) -> Any:
        try:
            resp = self._client.post(path, json=json)
        except httpx.RequestError as e:
            raise ArrError("ARR_CONNECTION_FAILED", f"Connection failed: {e}")
        if resp.status_code == 401:
            raise ArrError("ARR_AUTH_FAILED", "API key rejected", 401)
        if resp.status_code >= 400:
            body = resp.text[:500] if resp.text else ""
            raise ArrError("ARR_ERROR", f"Arr returned {resp.status_code}: {body}", resp.status_code)
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    def ping(self) -> bool:
        try:
            resp = self._client.get("/ping")
            return resp.status_code == 200
        except Exception:
            return False

    @abstractmethod
    def get_system_status(self) -> dict:
        ...

    @abstractmethod
    def get_root_folders(self) -> list[dict]:
        ...

    @abstractmethod
    def get_quality_profiles(self) -> list[dict]:
        ...

    @abstractmethod
    def get_queue(self, params: dict | None = None) -> dict:
        ...

    def create_command(self, name: str, **kwargs) -> dict:
        body = {"name": name, **kwargs}
        return self._post("/api/v3/command", json=body)

    def close(self):
        self._client.close()
