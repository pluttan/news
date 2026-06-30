from __future__ import annotations

from typing import Any

import aiohttp

from scout.config import settings


class ScoutApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.API_BASE_URL).rstrip("/")
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
        assert self._session is not None, "ScoutApiClient not started"
        url = f"{self._base_url}{path}"
        async with self._session.request(method, url, params=params, json=json) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            return await resp.json()

    async def get_all_cities(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/cities")

    async def search_city(self, name: str) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/cities/search", params={"name": name})

    async def get_sources(self, city_id: int) -> list[dict[str, Any]]:
        result = await self._request("GET", f"/api/cities/{city_id}/sources")
        return result or []

    async def add_city(self, **fields: Any) -> dict[str, Any]:
        return await self._request("POST", "/api/cities", json=fields)

    async def add_source(self, city_id: int, **fields: Any) -> dict[str, Any]:
        return await self._request("POST", f"/api/cities/{city_id}/sources", json=fields)
