from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx


@dataclass(slots=True)
class ConcienciaClient:
    base_url: str
    api_key: str
    timeout: float = 10.0

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        url = urljoin(self.base_url.rstrip("/") + "/", path.lstrip("/"))
        with httpx.Client(
            timeout=self.timeout,
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
        ) as client:
            response = client.request(method, url, params=params)
            response.raise_for_status()
            return response.json()

    def get_me(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/me")

    def list_departments(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/departments")

    def list_work_items(self, **params: Any) -> dict[str, Any]:
        return self._request("GET", "/api/v1/work-items", params=params)

    def get_work_item(self, work_item_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/work-items/{work_item_id}")

    def get_overdue_work(self) -> dict[str, Any]:
        return self.list_work_items(overdue=True)

    def get_department_work(self, department_id: str) -> dict[str, Any]:
        return self.list_work_items(department=department_id)


def from_env() -> ConcienciaClient:
    base_url = os.environ.get("LINTEAM_BASE_URL")
    api_key = os.environ.get("LINTEAM_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError("LINTEAM_BASE_URL and LINTEAM_API_KEY must be set")
    return ConcienciaClient(base_url=base_url, api_key=api_key)
