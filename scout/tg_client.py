from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel

from scout.config import settings

logger = logging.getLogger(__name__)

OnFloodWait = Callable[[int], Awaitable[None]]


@dataclass
class TgChannel:
    id: int
    title: str
    username: str | None
    participants_count: int
    about: str


class TgClient:
    def __init__(
        self,
        api_id: int | None = None,
        api_hash: str | None = None,
        session_path: str | None = None,
        proxy: str | None = None,
        on_flood_wait: OnFloodWait | None = None,
    ) -> None:
        self._api_id = api_id or settings.TG_API_ID
        self._api_hash = api_hash or settings.TG_API_HASH
        self._session_path = session_path or settings.TG_SESSION_PATH
        self._proxy = proxy or settings.HTTP_PROXY or None
        self._client: TelegramClient | None = None
        self._on_flood_wait = on_flood_wait

    async def start(self) -> None:
        proxy_args: dict = {}
        if self._proxy:
            # Parse http://host:port or socks5://host:port
            from urllib.parse import urlparse

            parsed = urlparse(self._proxy)
            if parsed.scheme in ("socks5", "socks4"):
                proxy_args["proxy"] = (
                    parsed.scheme,
                    parsed.hostname,
                    parsed.port,
                )
            elif parsed.scheme in ("http", "https"):
                proxy_args["proxy"] = (
                    "http",
                    parsed.hostname,
                    parsed.port,
                )

        self._client = TelegramClient(
            self._session_path,
            self._api_id,
            self._api_hash,
            **proxy_args,
        )
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError(
                "Telethon session not authorized. Run 'make tg-auth' first."
            )
        logger.info("Telethon client connected")

    async def close(self) -> None:
        if self._client:
            await self._client.disconnect()
            self._client = None

    async def search_channels(self, query: str, *, limit: int = 20) -> list[TgChannel]:
        assert self._client is not None, "TgClient not started"
        try:
            result = await self._client(SearchRequest(q=query, limit=limit))
        except FloodWaitError as e:
            logger.warning("FloodWait: sleeping %d seconds", e.seconds)
            if self._on_flood_wait:
                await self._on_flood_wait(e.seconds)
            await asyncio.sleep(e.seconds)
            result = await self._client(SearchRequest(q=query, limit=limit))

        channels: list[TgChannel] = []
        for chat in result.chats:
            if not isinstance(chat, Channel):
                continue
            if not chat.broadcast:
                continue
            channels.append(
                TgChannel(
                    id=chat.id,
                    title=chat.title or "",
                    username=chat.username,
                    participants_count=chat.participants_count or 0,
                    about="",
                )
            )
        return channels
