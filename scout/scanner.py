from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from scout.api_client import ScoutApiClient
from scout.config import settings
from scout.queries import build_queries
from scout.relevance import compute_relevance
from scout.vk_client import VKApiError, VKClient, VKGroup

logger = logging.getLogger(__name__)

# callback(current_index, total, city_name, result_or_none)
ScoutProgressCallback = Callable[[int, int, str, "ScoutResult | None"], Awaitable[None]]


@dataclass
class ScoutResult:
    city_id: int
    city_name: str
    found: int
    filtered: int
    added: int
    skipped: int


def _passes_filter(group: VKGroup, *, min_subscribers: int) -> bool:
    if group.is_closed != 0:
        return False
    if group.members_count < min_subscribers:
        return False
    return True


async def scout_city(
    city_id: int,
    city_name: str,
    vk: VKClient,
    api: ScoutApiClient,
    *,
    population: int = 0,
    min_subscribers: int | None = None,
    max_results: int | None = None,
) -> ScoutResult:
    _min_subs = min_subscribers if min_subscribers is not None else settings.MIN_SUBSCRIBERS
    _max_res = max_results if max_results is not None else settings.MAX_RESULTS_PER_QUERY

    existing_sources = await api.get_sources(city_id)
    existing_ids: set[str] = {
        s["external_id"]
        for s in existing_sources
        if s.get("platform") == "vk" and s.get("external_id")
    }

    seen: dict[int, VKGroup] = {}
    queries = build_queries(city_name)

    for i, query in enumerate(queries):
        if i > 0:
            await asyncio.sleep(settings.DELAY_BETWEEN_REQUESTS)
        groups = await vk.search_groups(query, count=_max_res)
        for g in groups:
            if g.id not in seen:
                seen[g.id] = g

    found = len(seen)

    passed = {gid: g for gid, g in seen.items() if _passes_filter(g, min_subscribers=_min_subs)}
    filtered = found - len(passed)

    added = 0
    skipped = 0

    for gid, group in passed.items():
        ext_id = str(gid)
        if ext_id in existing_ids:
            skipped += 1
            continue

        relevance = compute_relevance(group.name, city_name, group.members_count, population)

        await api.add_source(
            city_id,
            platform="vk",
            external_id=ext_id,
            name=group.name,
            url=f"https://vk.com/{group.screen_name}",
            subscribers=group.members_count,
            relevance=relevance,
        )
        existing_ids.add(ext_id)
        added += 1
        logger.info(
            "Added VK group: %s (%d subscribers, relevance=%d)",
            group.name, group.members_count, relevance,
        )

    return ScoutResult(
        city_id=city_id,
        city_name=city_name,
        found=found,
        filtered=filtered,
        added=added,
        skipped=skipped,
    )


async def scout_all_cities(
    vk: VKClient,
    api: ScoutApiClient,
    *,
    on_progress: ScoutProgressCallback | None = None,
    **kwargs: int,
) -> list[ScoutResult]:
    cities = await api.get_all_cities()
    results: list[ScoutResult] = []

    if on_progress:
        await on_progress(0, len(cities), "", None)

    for i, city in enumerate(cities):
        if i > 0:
            logger.info("Waiting %.1fs before next city...", settings.DELAY_BETWEEN_CITIES)
            await asyncio.sleep(settings.DELAY_BETWEEN_CITIES)
        logger.info("Scouting city %d/%d: %s (id=%d)", i + 1, len(cities), city["name"], city["id"])
        try:
            result = await scout_city(
                city["id"], city["name"], vk, api,
                population=city.get("population") or 0, **kwargs,
            )
        except VKApiError:
            raise
        except Exception:
            logger.exception("Scout failed for city %s", city["name"])
            result = ScoutResult(
                city_id=city["id"], city_name=city["name"],
                found=0, filtered=0, added=0, skipped=0,
            )
        results.append(result)
        logger.info(
            "  found=%d filtered=%d added=%d skipped=%d",
            result.found, result.filtered, result.added, result.skipped,
        )
        if on_progress:
            await on_progress(i + 1, len(cities), city["name"], result)

    return results
