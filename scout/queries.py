TEMPLATES: list[str] = [
    "{city}",
    "новости {city}",
    "подслушано {city}",
    "типичный {city}",
    "{city} сегодня",
]


def build_queries(city_name: str) -> list[str]:
    return [t.format(city=city_name) for t in TEMPLATES]
