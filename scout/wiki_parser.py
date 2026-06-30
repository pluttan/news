"""Parse Russian cities from Wikipedia article 'Список городов России'."""
from __future__ import annotations

import logging
import re

import aiohttp

logger = logging.getLogger(__name__)

WIKI_API = "https://ru.wikipedia.org/w/api.php"
WIKI_PAGE = "Список_городов_России"


def _parse_wikitext_table(wikitext: str) -> list[dict[str, str | int]]:
    """Parse cities from Wikipedia wikitext table.

    Handles both formats:
    - Cities table: | |[[Файл:...]] | [[City]] | [[Region]] | District |Population| ...
    - ПГТ table:    || [[Name]] | [[Region]] | [[District]] | Population
    """
    cities: list[dict[str, str | int]] = []

    for line in wikitext.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue

        # Find all [[...]] links in the line
        links = re.findall(r"\[\[([^\]]+)\]\]", line)
        if not links:
            continue

        # First non-image link is the city name
        city_link = None
        for link in links:
            if link.startswith("Файл:") or link.startswith("File:"):
                continue
            city_link = link
            break

        if not city_link:
            continue

        # Extract display name: [[Page|Display]] -> Display
        name = city_link.split("|")[-1].strip()
        if not name:
            continue

        # Remove wikilinks, <ref> tags, HTML to isolate raw values
        clean_line = re.sub(r"\[\[[^\]]+\]\]", "LINK", line)
        clean_line = re.sub(r"<ref[^>]*>.*?</ref>", "", clean_line, flags=re.DOTALL)
        clean_line = re.sub(r"<ref[^>]*/?>", "", clean_line)
        clean_line = re.sub(r"<[^>]+>", "", clean_line)

        # Split by | and look for population (first large number)
        parts = clean_line.split("|")
        population = None
        for part in parts:
            p = part.strip().replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
            p = re.sub(r"'{2,}", "", p)
            if p.isdigit() and len(p) >= 3:
                val = int(p)
                if val >= 100:
                    population = val
                    break

        if population is not None:
            cities.append({"name": name, "population": population})

    return cities


async def fetch_cities_from_wikipedia(
    session: aiohttp.ClientSession | None = None,
) -> list[dict[str, str | int]]:
    """Fetch and parse all Russian cities from Wikipedia.

    Parses both sections:
    - Section 1: regular cities (~1105)
    - Section 2: cities within federal cities (Зеленоград, Колпино, etc.)

    Returns list of {"name": str, "population": int} sorted by population desc.
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "CityBot/1.0 (city loader)"},
        )

    all_cities: list[dict[str, str | int]] = []

    try:
        for section_idx in ("1", "2"):
            params = {
                "action": "parse",
                "page": WIKI_PAGE,
                "prop": "wikitext",
                "format": "json",
                "section": section_idx,
            }
            async with session.get(WIKI_API, params=params) as resp:
                if resp.status != 200:
                    logger.error("Wikipedia API returned %d for section %s", resp.status, section_idx)
                    continue
                data = await resp.json()

            wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
            if not wikitext:
                continue

            cities = _parse_wikitext_table(wikitext)
            logger.info("Wikipedia section %s: %d cities", section_idx, len(cities))
            all_cities.extend(cities)

        # Deduplicate by name
        seen: set[str] = set()
        unique: list[dict[str, str | int]] = []
        for city in all_cities:
            if city["name"] not in seen:
                seen.add(city["name"])
                unique.append(city)

        unique.sort(key=lambda c: c["population"], reverse=True)
        logger.info("Wikipedia total: %d unique cities", len(unique))
        return unique

    finally:
        if own_session:
            await session.close()
