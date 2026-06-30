"""Score VK groups by relevance to local news/community content (0-100).

Formula: pattern (0-40) + subscribers (0-40) + city_name (0-20)
Subscribers carry equal weight to content pattern — a huge local group
with a generic name is more valuable than a tiny group with perfect keywords.
"""
from __future__ import annotations

import math
import re

_NEWS: list[str] = [
    "новост", "подслушано", "типичн", "инцидент",
    "дтп", "жесть", "вести ", " чп ", " чп|",
]
_COMMUNITY: list[str] = [
    "интересн", "наш ", "наша ", "наше ",
    "мой ", "моя ", "моё ",
    "городск", "паблик", "онлайн", "сегодня",
]
_MEDIA: list[str] = [
    "портал", "газет", "медиа", "информ",
    "блокнот", "лента", " сми",
]
_EVENTS: list[str] = [
    "афиш", "событ", "фестивал", "концерт",
    "куда пойти", "flash", "выставк",
]
_CLASSIFIEDS: list[str] = [
    "объявлен", "барахолк",
]
_LOCAL: list[str] = [
    "район", " life", "лайф", "это ",
]

_SPAM: list[str] = [
    "black russia", " gta", "gta ", "вирт", "radmir", "majestic",
    "hassle", "namalsk", "sa:mp", "самп", "crmp", "minecraft",
    "майнкрафт", "roblox", "brawl", "standoff", "fortnite",
    "фортнайт", "valorant", "pubg", "csgo", "counter-strike",
    "roleplay", "ролевая", "ролевой",
    "аниме", "anime", "k-pop", "кпоп", "манга", "manga",
    "крипто", "crypto", "forex", "форекс", "казино", "casino",
    "букмекер", "ставки на спорт",
    "discord", "дискорд", "взаимные лайки", "накрутк",
    "займ онлайн", "микрозайм",
]

_COMMERCIAL: list[str] = [
    "работа ", " работа", "вакансии", "вакансия",
    "распродажа", "оптовый", "поставщик", "закупк",
    "магазин", "доставка еды", "доставка цвет",
    "фитнес", "тренажер", "спортзал",
    "ресторан", "пиццер", "суши", "бургер", "шаурм",
    "салон красот", "маникюр", "парикмахер", "стрижк",
    "тату ", "татуаж",
    "фотограф", "видеограф", "видеосъем",
    "свадеб", "ведущий на ",
    "ищу модель", "ищу мастер",
    "автосервис", "шиномонтаж", "автомойк",
    "эвакуатор", "прокат ",
    "недвижимост", "ипотек", "аренда квартир",
    "детский сад ", "мбоу ", "мбдоу ",
    "диссертац", "диплом", "курсов",
]


def _sub_score(subscribers: int, population: int) -> int:
    """Subscribers score 0-40 based on coverage ratio (subs / population).

    ratio 0.1% → 0,  1% → 13,  5% → 23,  10% → 27,  20% → 31,  50% → 36
    Falls back to absolute log scale when population is unknown.
    """
    if subscribers <= 0:
        return 0
    if population and population > 0:
        ratio = subscribers / population
        if ratio <= 0:
            return 0
        # log10(0.001)=-3, log10(0.5)=-0.3 → range ~2.7, map to 0-40
        raw = (math.log10(ratio) + 3) * 14.8
        return max(0, min(40, int(raw)))
    # Fallback: absolute scale (no population data)
    raw = math.log10(subscribers) * 8.5 - 18
    return max(0, min(40, int(raw)))


_VOWELS_AND_SOFT = set("аеёиоуыэюяь")


def _city_stem(city: str) -> str:
    """Naive stem: drop the last char if the city ends with a vowel or ь.

    Абаза → абаз, Москва → москв, Казань → казан, Краснодар → краснодар
    """
    if city and city[-1] in _VOWELS_AND_SOFT:
        return city[:-1]
    return city


def _city_in_name(name: str, city: str) -> bool:
    """Check that city (or its stem + inflection suffix) appears in name.

    Handles Russian case forms by matching stem + up to 3 suffix chars.
    Rejects adjective forms (stem + ск/цк).

    'абаза'     in 'администрация города абазы' → True  (stem абаз + ы)
    'краснодар' in 'новости краснодара'         → True  (stem краснодар + а)
    'краснодар' in 'краснодарский край'         → False (adjective: ск after stem)
    'москва'    in 'московский проспект'        → False (suffix > 3 chars)
    """
    stem = _city_stem(city)
    # stem + optional 0-3 letter suffix, NOT followed by a letter
    # but reject adjective patterns: stem + ...ск / ...цк
    pattern = re.compile(
        re.escape(stem) + r"([а-яёА-ЯЁ]{0,3})(?![а-яёА-ЯЁ])"
    )
    for m in pattern.finditer(name):
        suffix = m.group(1)
        # Reject adjective forms: suffix ends with ск or цк
        if suffix.endswith("ск") or suffix.endswith("цк"):
            continue
        return True
    return False


def compute_relevance(group_name: str, city_name: str, subscribers: int = 0, population: int = 0) -> int:
    """Compute relevance score 0-100 for a VK group."""
    name = group_name.lower()
    city = city_name.lower()

    # No city name in group = very low relevance
    if not _city_in_name(name, city):
        return 0

    # Spam = 0
    for kw in _SPAM:
        if kw in name:
            return 0

    # Pattern score (0-40)
    pattern = 0
    for kw in _NEWS:
        if kw in name:
            pattern = 40
            break
    if not pattern:
        for kw in _COMMUNITY:
            if kw in name:
                pattern = 35
                break
    if not pattern:
        for kw in _MEDIA:
            if kw in name:
                pattern = 32
                break
    if not pattern:
        for kw in _EVENTS:
            if kw in name:
                pattern = 28
                break
    if not pattern:
        for kw in _CLASSIFIEDS:
            if kw in name:
                pattern = 22
                break
    if not pattern:
        for kw in _LOCAL:
            if kw in name:
                pattern = 18
                break
    if not pattern:
        pattern = 5  # city name only, no pattern

    # Commercial penalty
    for kw in _COMMERCIAL:
        if kw in name:
            pattern = max(pattern - 15, 2)
            break

    # City name bonus (always 20 since we checked above)
    city_score = 20

    # Subscribers (0-40)
    subs = _sub_score(subscribers, population)

    return min(100, pattern + city_score + subs)
