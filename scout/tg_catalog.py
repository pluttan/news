"""Parse TG channel catalogs (tgstat.ru, telemetr.me) for additional discovery."""
from __future__ import annotations

import logging
import re

import aiohttp

logger = logging.getLogger(__name__)

_TGSTAT_RE = re.compile(
    r'href="https?://t\.me/([A-Za-z]\w{3,})"[^>]*>.*?'
    r'class="[^"]*channel-card[^"]*"',
    re.DOTALL,
)
_TGSTAT_TITLE_RE = re.compile(
    r'class="[^"]*channel-card__title[^"]*"[^>]*>([^<]+)',
)
_TGSTAT_SUBS_RE = re.compile(
    r'class="[^"]*channel-card__subscribers[^"]*"[^>]*>(\d[\d\s]*)',
)

_TELEMETR_USERNAME_RE = re.compile(
    r'href="https?://t\.me/([A-Za-z]\w{3,})"',
)


async def search_tgstat(
    session: aiohttp.ClientSession,
    query: str,
) -> list[dict[str, str | int]]:
    """Search tgstat.ru and return list of {username, title, subscribers}."""
    url = "https://tgstat.ru/channels/search"
    params = {"q": query}
    try:
        async with session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "Mozilla/5.0"},
        ) as resp:
            if resp.status != 200:
                logger.debug("tgstat.ru returned %d for query '%s'", resp.status, query)
                return []
            html = await resp.text()
    except Exception:
        logger.debug("tgstat.ru: request failed for '%s'", query, exc_info=True)
        return []

    results: list[dict[str, str | int]] = []
    # Simple extraction: find all t.me/username links
    usernames_seen: set[str] = set()
    for m in re.finditer(r'href="https?://t\.me/([A-Za-z]\w{3,})"', html):
        username = m.group(1).lower()
        if username in usernames_seen:
            continue
        if username in ("proxy", "socks", "share", "joinchat", "addstickers"):
            continue
        usernames_seen.add(username)
        results.append({"username": username, "title": "", "subscribers": 0})

    return results


async def search_telemetr(
    session: aiohttp.ClientSession,
    query: str,
) -> list[dict[str, str | int]]:
    """Search telemetr.me and return list of {username, title, subscribers}."""
    url = "https://telemetr.me/channels/"
    params = {"search": query}
    try:
        async with session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "Mozilla/5.0"},
        ) as resp:
            if resp.status != 200:
                logger.debug("telemetr.me returned %d for query '%s'", resp.status, query)
                return []
            html = await resp.text()
    except Exception:
        logger.debug("telemetr.me: request failed for '%s'", query, exc_info=True)
        return []

    results: list[dict[str, str | int]] = []
    usernames_seen: set[str] = set()
    for m in _TELEMETR_USERNAME_RE.finditer(html):
        username = m.group(1).lower()
        if username in usernames_seen:
            continue
        if username in ("proxy", "socks", "share", "joinchat", "addstickers"):
            continue
        usernames_seen.add(username)
        results.append({"username": username, "title": "", "subscribers": 0})

    return results
