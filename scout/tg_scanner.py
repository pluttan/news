"""TG Scout orchestration: search → dedup → enrich → score → save."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import aiohttp
from aiogram import Bot

from scout.api_client import ScoutApiClient
from scout.config import settings
from scout.queries import build_queries
from scout.relevance import compute_relevance
from scout.tg_catalog import search_tgstat
from scout.tg_client import TgChannel, TgClient
from scout.tg_enricher import TgChannelInfo, enrich_channel, enrich_from_web

logger = logging.getLogger(__name__)

# callback(current_index, total, city_dict, result_or_none)
TgScoutProgressCallback = Callable[
    [int, int, dict, "TgScoutResult | None"], Awaitable[None]
]


@dataclass
class TgScoutResult:
    city_id: int
    city_name: str
    population: int
    searched: int
    found: int
    added: int
    skipped: int
    relevant: int


async def _search_telethon(
    tg: TgClient,
    city_name: str,
) -> dict[str, TgChannel]:
    """Run Telethon search for all query templates, return deduped channels by username."""
    queries = build_queries(city_name)
    seen: dict[str, TgChannel] = {}

    for i, query in enumerate(queries):
        if i > 0:
            await asyncio.sleep(settings.TG_SEARCH_DELAY)
        try:
            channels = await tg.search_channels(query)
        except Exception:
            logger.warning("Telethon search failed for query '%s'", query, exc_info=True)
            continue
        for ch in channels:
            if ch.username and ch.username.lower() not in seen:
                seen[ch.username.lower()] = ch

    return seen


async def _search_catalogs(
    session: aiohttp.ClientSession,
    city_name: str,
) -> dict[str, dict]:
    """Search tgstat.ru for additional channels."""
    seen: dict[str, dict] = {}
    catalog_queries = [f"{city_name} новости", f"{city_name} подслушано"]

    for query in catalog_queries:
        try:
            results = await search_tgstat(session, query)
            for item in results:
                uname = item["username"]
                if isinstance(uname, str) and uname.lower() not in seen:
                    seen[uname.lower()] = item
        except Exception:
            logger.debug("Catalog search failed for '%s'", query, exc_info=True)
        await asyncio.sleep(2.0)

    return seen


async def _enrich(
    bot: Bot | None,
    session: aiohttp.ClientSession,
    username: str,
) -> TgChannelInfo | None:
    """Enrich channel: Bot API first, then web fallback."""
    if bot:
        info = await enrich_channel(bot, username)
        if info and info.subscribers > 0:
            return info
    return await enrich_from_web(session, username)


async def tg_scout_city(
    city_id: int,
    city_name: str,
    tg: TgClient,
    bot: Bot | None,
    api: ScoutApiClient,
    *,
    population: int = 0,
) -> TgScoutResult:
    """Scout TG channels for a single city."""

    # 1. Get existing TG sources for dedup
    existing_sources = await api.get_sources(city_id)
    existing_usernames: set[str] = {
        (s.get("url", "").rstrip("/").rsplit("/", 1)[-1]).lower()
        for s in existing_sources
        if s.get("platform") == "tg" and s.get("url")
    }

    # 2. Telethon search
    telethon_channels = await _search_telethon(tg, city_name)
    searched = len(build_queries(city_name))

    # 3. Catalog search (optional, non-blocking)
    async with aiohttp.ClientSession() as session:
        catalog_channels = await _search_catalogs(session, city_name)

        # 4. Merge: Telethon results take priority
        all_usernames: dict[str, TgChannel | None] = {}
        for uname, ch in telethon_channels.items():
            all_usernames[uname] = ch
        for uname in catalog_channels:
            if uname not in all_usernames:
                all_usernames[uname] = None  # catalog-only, needs enrichment

        found = len(all_usernames)
        added = 0
        skipped = 0
        relevant = 0

        for uname, ch in all_usernames.items():
            if uname in existing_usernames:
                skipped += 1
                continue

            # 5. Enrich
            subscribers = ch.participants_count if ch else 0
            title = ch.title if ch else ""
            description = ch.about if ch else ""

            if not subscribers or not title:
                info = await _enrich(bot, session, uname)
                if info:
                    subscribers = info.subscribers or subscribers
                    title = info.title or title
                    description = info.description or description
                    if not info.is_channel:
                        continue  # skip groups, we want channels only
                await asyncio.sleep(0.5)

            if not title:
                continue

            # 6. Score
            relevance = compute_relevance(title, city_name, subscribers, population)

            # 7. Save
            try:
                await api.add_source(
                    city_id,
                    platform="tg",
                    external_id=uname,
                    name=title,
                    url=f"https://t.me/{uname}",
                    subscribers=subscribers,
                    relevance=relevance,
                )
                existing_usernames.add(uname)
                added += 1
                if relevance > 0:
                    relevant += 1
                logger.info(
                    "Added TG channel: @%s '%s' (%d subscribers, relevance=%d)",
                    uname, title, subscribers, relevance,
                )
            except Exception:
                logger.warning("Failed to save @%s", uname, exc_info=True)

    return TgScoutResult(
        city_id=city_id,
        city_name=city_name,
        population=population,
        searched=searched,
        found=found,
        added=added,
        skipped=skipped,
        relevant=relevant,
    )


async def tg_scout_all(
    clients: list[TgClient],
    bot: Bot | None,
    api: ScoutApiClient,
    *,
    on_progress: TgScoutProgressCallback | None = None,
) -> list[TgScoutResult]:
    """Scout TG channels for all cities, distributed across multiple accounts."""
    cities = await api.get_all_cities()
    total = len(cities)

    # Filter out already scouted cities
    cities_todo: list[tuple[int, dict]] = []
    cities_skip: list[tuple[int, dict]] = []
    for i, city in enumerate(cities):
        existing = await api.get_sources(city["id"])
        tg_sources = [s for s in existing if s.get("platform") == "tg"]
        if tg_sources:
            cities_skip.append((i, city))
        else:
            cities_todo.append((i, city))

    logger.info(
        "TG scout: %d cities total, %d already done, %d to scout with %d account(s)",
        total, len(cities_skip), len(cities_todo), len(clients),
    )

    results: list[TgScoutResult] = []
    progress_lock = asyncio.Lock()
    done_count = 0

    # Report skipped cities
    for orig_idx, city in cities_skip:
        results.append(TgScoutResult(
            city_id=city["id"],
            city_name=city["name"],
            population=city.get("population") or 0,
            searched=0, found=0, added=0, skipped=0, relevant=0,
        ))

    done_count = len(cities_skip)

    if on_progress:
        await on_progress(done_count, total, {}, None)

    # Distribute cities round-robin across clients
    chunks: list[list[tuple[int, dict]]] = [[] for _ in clients]
    for idx, item in enumerate(cities_todo):
        chunks[idx % len(clients)].append(item)

    async def _worker(tg: TgClient, my_cities: list[tuple[int, dict]], worker_id: int) -> None:
        nonlocal done_count
        for j, (orig_idx, city) in enumerate(my_cities):
            if j > 0:
                await asyncio.sleep(settings.DELAY_BETWEEN_CITIES)

            logger.info(
                "[worker %d] TG scouting: %s (id=%d)",
                worker_id, city["name"], city["id"],
            )

            try:
                result = await tg_scout_city(
                    city["id"],
                    city["name"],
                    tg,
                    bot,
                    api,
                    population=city.get("population") or 0,
                )
            except Exception:
                logger.exception("[worker %d] TG scout failed for %s", worker_id, city["name"])
                result = TgScoutResult(
                    city_id=city["id"],
                    city_name=city["name"],
                    population=city.get("population") or 0,
                    searched=0, found=0, added=0, skipped=0, relevant=0,
                )

            async with progress_lock:
                results.append(result)
                done_count += 1
                logger.info(
                    "[worker %d]   searched=%d found=%d added=%d skipped=%d relevant=%d",
                    worker_id, result.searched, result.found, result.added,
                    result.skipped, result.relevant,
                )
                if on_progress:
                    await on_progress(done_count, total, city, result)

    await asyncio.gather(
        *[_worker(tg, chunk, i) for i, (tg, chunk) in enumerate(zip(clients, chunks))]
    )

    return results
