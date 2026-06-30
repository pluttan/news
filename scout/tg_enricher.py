"""Enrich TG channel data via Bot API (primary) and t.me/s/ HTML (fallback)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import aiohttp
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger(__name__)


@dataclass
class TgChannelInfo:
    username: str
    title: str
    description: str
    subscribers: int
    is_channel: bool


async def enrich_channel(bot: Bot, username: str) -> TgChannelInfo | None:
    """Get channel info via Bot API (works for public channels without joining)."""
    try:
        chat = await bot.get_chat(f"@{username}")
    except (TelegramBadRequest, TelegramForbiddenError):
        logger.debug("Bot API: cannot get chat @%s", username)
        return None
    except Exception:
        logger.debug("Bot API: unexpected error for @%s", username, exc_info=True)
        return None

    is_channel = chat.type in ("channel",)
    try:
        count = await bot.get_chat_member_count(chat.id)
    except Exception:
        count = 0

    return TgChannelInfo(
        username=username,
        title=chat.title or "",
        description=chat.description or "",
        subscribers=count,
        is_channel=is_channel,
    )


_RE_SUBSCRIBERS = re.compile(r'class="tgme_page_extra"[^>]*>(\d[\d\s]*)\s*(subscribers|members)', re.I)
_RE_TITLE = re.compile(r'class="tgme_page_title"[^>]*><span[^>]*>([^<]+)</span>')
_RE_DESCRIPTION = re.compile(r'class="tgme_page_description"[^>]*>([^<]+)')


async def enrich_from_web(
    session: aiohttp.ClientSession,
    username: str,
) -> TgChannelInfo | None:
    """Fallback: parse t.me/s/{username} public page for channel info."""
    url = f"https://t.me/s/{username}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()
    except Exception:
        logger.debug("Web fallback: cannot fetch @%s", username, exc_info=True)
        return None

    title = ""
    m = _RE_TITLE.search(html)
    if m:
        title = m.group(1).strip()

    description = ""
    m = _RE_DESCRIPTION.search(html)
    if m:
        description = m.group(1).strip()

    subscribers = 0
    m = _RE_SUBSCRIBERS.search(html)
    if m:
        subscribers = int(m.group(1).replace(" ", "").replace("\xa0", ""))

    if not title:
        return None

    return TgChannelInfo(
        username=username,
        title=title,
        description=description,
        subscribers=subscribers,
        is_channel=True,
    )
