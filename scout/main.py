from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from scout.api_client import ScoutApiClient
from scout.config import settings
from scout.scanner import ScoutResult, scout_all_cities, scout_city
from scout.tg_client import TgClient
from scout.tg_scanner import TgScoutResult, tg_scout_all, tg_scout_city
from scout.vk_client import VKClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def print_result(result: ScoutResult) -> None:
    print(
        f"[{result.city_name}] "
        f"found={result.found} filtered={result.filtered} "
        f"added={result.added} skipped={result.skipped}"
    )


def print_tg_result(result: TgScoutResult) -> None:
    print(
        f"[{result.city_name}] "
        f"searched={result.searched} found={result.found} "
        f"added={result.added} skipped={result.skipped}"
    )


async def run(
    city_name: str | None,
    *,
    min_subscribers: int | None = None,
    max_results: int | None = None,
    delay_requests: float | None = None,
    delay_cities: float | None = None,
) -> None:
    if not settings.VK_TOKEN:
        logger.error("VK_TOKEN not set. Add it to .env file.")
        sys.exit(1)

    vk = VKClient()
    api = ScoutApiClient()
    await vk.start()
    await api.start()

    if delay_requests is not None:
        settings.DELAY_BETWEEN_REQUESTS = delay_requests
    if delay_cities is not None:
        settings.DELAY_BETWEEN_CITIES = delay_cities

    scout_kwargs: dict[str, int] = {}
    if min_subscribers is not None:
        scout_kwargs["min_subscribers"] = min_subscribers
    if max_results is not None:
        scout_kwargs["max_results"] = max_results

    try:
        if city_name:
            cities = await api.search_city(city_name)
            if not cities:
                logger.error("City '%s' not found in backend.", city_name)
                sys.exit(1)

            city = cities[0]
            result = await scout_city(city["id"], city["name"], vk, api, **scout_kwargs)
            print_result(result)
        else:
            results = await scout_all_cities(vk, api, **scout_kwargs)
            if not results:
                print("No cities found in backend.")
            for result in results:
                print_result(result)
    finally:
        await vk.close()
        await api.close()


async def run_tg(
    city_name: str | None,
    *,
    delay_cities: float | None = None,
) -> None:
    if not settings.TG_API_ID or not settings.TG_API_HASH:
        logger.error("TG_API_ID / TG_API_HASH not set. Add them to .env file.")
        sys.exit(1)

    tg = TgClient()
    api = ScoutApiClient()
    await api.start()
    await tg.start()

    if delay_cities is not None:
        settings.DELAY_BETWEEN_CITIES = delay_cities

    try:
        if city_name:
            cities = await api.search_city(city_name)
            if not cities:
                logger.error("City '%s' not found in backend.", city_name)
                sys.exit(1)

            city = cities[0]
            result = await tg_scout_city(
                city["id"], city["name"], tg, None, api,
                population=city.get("population") or 0,
            )
            print_tg_result(result)
        else:
            results = await tg_scout_all(tg, None, api)
            if not results:
                print("No cities found in backend.")
            for result in results:
                print_tg_result(result)
    finally:
        await tg.close()
        await api.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scout - search groups/channels for cities")
    parser.add_argument("city", nargs="?", default=None, help="City name to scout (all cities if omitted)")
    parser.add_argument("--tg", action="store_true", help="Use Telegram (Telethon) instead of VK")
    parser.add_argument("--min-subscribers", type=int, default=None, help=f"Minimum subscribers filter (default: {settings.MIN_SUBSCRIBERS})")
    parser.add_argument("--max-results", type=int, default=None, help=f"Max results per query (default: {settings.MAX_RESULTS_PER_QUERY})")
    parser.add_argument("--delay-requests", type=float, default=None, help=f"Delay between API requests in seconds (default: {settings.DELAY_BETWEEN_REQUESTS})")
    parser.add_argument("--delay-cities", type=float, default=None, help=f"Delay between cities in seconds (default: {settings.DELAY_BETWEEN_CITIES})")
    args = parser.parse_args()

    if args.tg:
        asyncio.run(run_tg(
            args.city,
            delay_cities=args.delay_cities,
        ))
    else:
        asyncio.run(run(
            args.city,
            min_subscribers=args.min_subscribers,
            max_results=args.max_results,
            delay_requests=args.delay_requests,
            delay_cities=args.delay_cities,
        ))


if __name__ == "__main__":
    main()
