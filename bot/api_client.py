from __future__ import annotations

from typing import Any

import aiohttp

from bot.config import settings


class ApiClient:
    def __init__(self) -> None:
        self._base_url = settings.API_BASE_URL.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        assert self._session is not None, "ApiClient not started"
        url = f"{self._base_url}{path}"
        async with self._session.request(method, url, params=params, json=json) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            return await resp.json()

    # --- status ---

    async def get_system_status(self) -> dict[str, Any]:
        return await self._request("GET", "/api/status")

    # --- cities ---

    async def get_all_cities(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/cities")

    async def get_city_detail(self, city_id: int) -> dict[str, Any] | None:
        return await self._request("GET", f"/api/cities/{city_id}")

    async def search_city(self, name: str) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/cities/search", params={"name": name})

    async def update_city(self, city_id: int, **fields: Any) -> dict[str, Any] | None:
        return await self._request("PATCH", f"/api/cities/{city_id}", json=fields)

    async def get_top_cities(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/cities/top", params={"limit": limit})

    async def create_city(self, **fields: Any) -> dict[str, Any]:
        return await self._request("POST", "/api/cities", json=fields)

    # --- sources ---

    async def add_source(self, city_id: int, **fields: Any) -> dict[str, Any]:
        return await self._request("POST", f"/api/cities/{city_id}/sources", json=fields)

    # --- reports ---

    async def get_daily_report(self) -> dict[str, Any]:
        return await self._request("GET", "/api/reports/daily")

    async def get_weekly_report(self) -> dict[str, Any]:
        return await self._request("GET", "/api/reports/weekly")
