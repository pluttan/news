"""Load Russian settlements into backend.

Sources (in priority order):
1. Local CSV (tochno.st / Росстат, ~131k населённых пунктов)
2. Wikipedia — 'Список городов России' (актуальные данные, только города)
3. hflabs/city CSV on GitHub (fallback, устаревшие данные ~2014, только города)
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import aiohttp

from scout.api_client import ScoutApiClient
from scout.config import settings
from scout.wiki_parser import fetch_cities_from_wikipedia

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

CITIES_CSV_URL = "https://raw.githubusercontent.com/hflabs/city/master/city.csv"
LOCAL_CSV_PATH = os.getenv(
    "SETTLEMENTS_CSV",
    os.path.join(os.path.dirname(__file__), "data", "settlements.csv"),
)

# Type for progress callback: async fn(stage, detail, current, total)
ProgressCallback = Callable[[str, str, int, int], Awaitable[None]]


@dataclass
class LoadResult:
    total_in_csv: int = 0
    parsed: int = 0
    filtered_out: int = 0
    already_in_db: int = 0
    added: int = 0
    total_in_db: int = 0
    elapsed: float = 0.0
    top_cities: list[dict] = field(default_factory=list)
    source: str = ""


async def _fetch_from_local_csv(
    min_population: int,
    on_progress: ProgressCallback | None = None,
) -> list[dict[str, str | int]]:
    """Primary source: local CSV with ~131k settlements from Росстат."""
    path = os.path.abspath(LOCAL_CSV_PATH)
    if not os.path.exists(path):
        logger.info("Local CSV not found: %s", path)
        return []

    logger.info("[1/3] Loading settlements from local CSV: %s", path)
    if on_progress:
        await on_progress("download", "Загружаю из локальной базы Росстата...", 0, 0)

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)

    total = len(rows)
    logger.info("[1/3] Total rows in local CSV: %d", total)
    if on_progress:
        await on_progress("download", f"Найдено {total:,} населённых пунктов", 0, 0)

    # First pass: collect all valid entries
    all_entries: list[dict[str, str | int]] = []
    below_min = 0

    for row in rows:
        pop_str = row.get("population", "").strip()
        if not pop_str:
            continue
        try:
            population = int(pop_str)
        except ValueError:
            continue

        if population < min_population:
            below_min += 1
            continue

        name = row.get("name", "").strip()
        if not name:
            continue

        all_entries.append({"name": name, "population": population})

    # Sort by population desc so dedup keeps the largest settlement for each name
    all_entries.sort(key=lambda c: c["population"], reverse=True)

    cities: list[dict[str, str | int]] = []
    seen: set[str] = set()
    dupes = 0
    for entry in all_entries:
        if entry["name"] in seen:
            dupes += 1
            continue
        seen.add(entry["name"])
        cities.append(entry)

    logger.info("[2/3] Filter: %d passed, %d below threshold, %d dupes",
                len(cities), below_min, dupes)
    if on_progress:
        await on_progress(
            "parse",
            f"{len(cities):,} н.п. >= {min_population:,} чел. "
            f"(из {total:,}, отброшено {below_min:,})",
            len(cities), len(cities),
        )

    return cities


async def _fetch_from_wikipedia(
    min_population: int,
    on_progress: ProgressCallback | None = None,
) -> list[dict[str, str | int]]:
    """Secondary source: Wikipedia article with current Rosstat data (cities only)."""
    logger.info("[1/3] Fetching cities from Wikipedia...")
    if on_progress:
        await on_progress("download", "Загружаю города с Википедии...", 0, 0)

    t0 = time.monotonic()
    all_cities = await fetch_cities_from_wikipedia()
    elapsed = time.monotonic() - t0

    if not all_cities:
        logger.warning("Wikipedia returned no cities")
        return []

    logger.info("[1/3] Got %d cities from Wikipedia in %.1fs", len(all_cities), elapsed)
    if on_progress:
        await on_progress("download", f"Получено {len(all_cities)} городов за {elapsed:.1f}с", 0, 0)

    cities = [c for c in all_cities if c["population"] >= min_population]
    filtered_out = len(all_cities) - len(cities)

    logger.info("[2/3] After filter (>= %d): %d cities (%d filtered out)",
                min_population, len(cities), filtered_out)
    if on_progress:
        await on_progress(
            "parse",
            f"{len(cities)} городов >= {min_population:,} чел. "
            f"(отброшено {filtered_out})",
            len(cities), len(cities),
        )

    return cities


async def _fetch_from_hflabs_csv(
    min_population: int,
    on_progress: ProgressCallback | None = None,
) -> list[dict[str, str | int]]:
    """Fallback source: hflabs/city CSV from GitHub."""
    logger.info("[1/3] Downloading city database from GitHub (fallback)...")
    if on_progress:
        await on_progress("download", "Загружаю CSV с GitHub (fallback)...", 0, 0)

    t0 = time.monotonic()
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(CITIES_CSV_URL) as resp:
            if resp.status != 200:
                logger.error("GitHub returned %d", resp.status)
                return []
            raw = await resp.read()

    elapsed_dl = time.monotonic() - t0
    logger.info("[1/3] Downloaded %.1f KB in %.1fs", len(raw) / 1024, elapsed_dl)

    text = raw.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    cities: list[dict[str, str | int]] = []
    seen: set[str] = set()

    for row in reader:
        pop_str = row.get("population", "").strip()
        if not pop_str:
            continue
        try:
            population = int(pop_str)
        except ValueError:
            continue
        if population < min_population:
            continue

        name = row.get("city", "").strip()
        if not name:
            if row.get("region_type", "").strip() == "г":
                name = row.get("region", "").strip()
            if not name:
                continue

        if name in seen:
            continue
        seen.add(name)
        cities.append({"name": name, "population": population})

    cities.sort(key=lambda c: c["population"], reverse=True)

    if on_progress:
        await on_progress(
            "parse",
            f"{len(cities)} городов (hflabs CSV fallback)",
            len(cities), len(cities),
        )

    return cities


async def fetch_cities(
    min_population: int,
    on_progress: ProgressCallback | None = None,
) -> list[dict[str, str | int]]:
    """Fetch settlements: local CSV > Wikipedia > hflabs CSV."""
    # 1. Local CSV (131k settlements)
    source = "rosstat"
    cities = await _fetch_from_local_csv(min_population, on_progress)

    # 2. Wikipedia (cities only)
    if not cities:
        source = "wikipedia"
        try:
            cities = await _fetch_from_wikipedia(min_population, on_progress)
        except Exception:
            logger.exception("Wikipedia fetch failed")
            cities = []

    # 3. hflabs CSV (fallback)
    if not cities:
        source = "csv"
        cities = await _fetch_from_hflabs_csv(min_population, on_progress)

    logger.info("Source: %s, settlements: %d", source, len(cities))
    for c in cities:
        c["_source"] = source

    return cities


async def load_cities(
    min_population: int | None = None,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> LoadResult:
    t_start = time.monotonic()
    _min_pop = min_population if min_population is not None else settings.MIN_POPULATION
    result = LoadResult()

    cities = await fetch_cities(_min_pop, on_progress=on_progress)
    result.parsed = len(cities)
    result.source = cities[0].get("_source", "unknown") if cities else "none"

    if not cities:
        logger.warning("No cities found")
        result.elapsed = time.monotonic() - t_start
        return result

    result.top_cities = [
        {"name": c["name"], "population": c["population"]} for c in cities[:5]
    ]

    if dry_run:
        for c in cities:
            print(f"  {c['name']} — {c['population']:,}")
        print(f"\nTotal: {len(cities)} settlements (dry run, nothing saved)")
        result.elapsed = time.monotonic() - t_start
        return result

    logger.info("[3/3] Saving to backend...")
    if on_progress:
        await on_progress("save", f"Сохраняю {len(cities):,} н.п. в базу...", 0, len(cities))

    api = ScoutApiClient()
    await api.start()

    try:
        existing = await api.get_all_cities()
        existing_names: set[str] = {c["name"] for c in existing}
        logger.info("[3/3] Already in DB: %d", len(existing_names))
        result.already_in_db = len(existing_names)

        added = 0
        skipped = 0
        for i, city in enumerate(cities):
            if city["name"] in existing_names:
                skipped += 1
                continue

            await api.add_city(name=city["name"], population=city["population"])
            added += 1

            if added % 100 == 0:
                logger.info("  [3/3] +%d (%d/%d)...", added, i + 1, len(cities))
                if on_progress:
                    await on_progress("save", f"Добавлено {added:,} ({i + 1:,}/{len(cities):,})...", i + 1, len(cities))

        all_cities = await api.get_all_cities()
        result.added = added
        result.total_in_db = len(all_cities)

        logger.info("Done: added=%d, skipped=%d, total=%d", added, skipped, len(all_cities))
    finally:
        await api.close()

    result.elapsed = time.monotonic() - t_start
    logger.info("Total time: %.1fs", result.elapsed)

    if on_progress:
        await on_progress(
            "done",
            f"Готово за {result.elapsed:.1f}с: +{result.added:,} новых, "
            f"{result.total_in_db:,} всего ({result.source})",
            len(cities), len(cities),
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Russian settlements into backend")
    parser.add_argument("--min-population", type=int, default=None,
                        help=f"Minimum population filter (default: {settings.MIN_POPULATION})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only print settlements, don't save to backend")
    args = parser.parse_args()
    asyncio.run(load_cities(min_population=args.min_population, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
