from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from scout.config import settings

logger = logging.getLogger(__name__)


class VKApiError(Exception):
    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"VK API error {code}: {message}")


@dataclass
class VKGroup:
    id: int
    name: str
    screen_name: str
    is_closed: int
    members_count: int
    activity: str
    description: str


class VKClient:
    def __init__(self, token: str | None = None) -> None:
        self._token = token or settings.VK_TOKEN
        self._version = settings.VK_API_VERSION
        self._proxy = settings.HTTP_PROXY or None
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def search_groups(
        self,
        query: str,
        *,
        group_type: str = "group",
        count: int = 50,
        sort: int = 6,
    ) -> list[VKGroup]:
        assert self._session is not None, "VKClient not started"
        url = "https://api.vk.com/method/groups.search"
        params: dict[str, Any] = {
            "q": query,
            "type": group_type,
            "count": count,
            "sort": sort,
            "fields": "members_count,activity,description",
            "access_token": self._token,
            "v": self._version,
        }
        async with self._session.get(url, params=params, proxy=self._proxy) as resp:
            data = await resp.json()

        if "error" in data:
            err = data["error"]
            raise VKApiError(err.get("error_code", 0), err.get("error_msg", "unknown"))

        items = data.get("response", {}).get("items", [])
        return [
            VKGroup(
                id=item["id"],
                name=item.get("name", ""),
                screen_name=item.get("screen_name", ""),
                is_closed=item.get("is_closed", 0),
                members_count=item.get("members_count", 0),
                activity=item.get("activity", ""),
                description=item.get("description", ""),
            )
            for item in items
        ]
