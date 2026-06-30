from __future__ import annotations

from pydantic import BaseModel


class City(BaseModel):
    id: int
    name: str
    population: int | None = None
    status: str = "scouted"
    tg_channel_id: str | None = None
    max_channel_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CityCreate(BaseModel):
    name: str
    population: int | None = None
    status: str = "scouted"
    tg_channel_id: str | None = None
    max_channel_id: str | None = None


class CityUpdate(BaseModel):
    name: str | None = None
    population: int | None = None
    status: str | None = None
    tg_channel_id: str | None = None
    max_channel_id: str | None = None


class MetricsSnapshot(BaseModel):
    subscribers: int = 0
    views_avg: int = 0
    posts_today: int = 0
    recorded_at: str | None = None


class CityDetail(City):
    sources_count: int = 0
    posts_today: int = 0
    posts_week: int = 0
    metrics: MetricsSnapshot | None = None


class CityTop(BaseModel):
    id: int
    name: str
    population: int | None = None
    status: str
    vk_demand: int = 0
    vk_count: int = 0
    tg_supply: int = 0
    tg_count: int = 0
    ratio: float = 0.0


class Source(BaseModel):
    id: int
    city_id: int
    platform: str
    external_id: str | None = None
    name: str | None = None
    url: str | None = None
    subscribers: int = 0
    relevance: int = 0
    is_active: int = 1
    last_parsed_at: str | None = None
    created_at: str | None = None


class SourceCreate(BaseModel):
    platform: str
    external_id: str | None = None
    name: str | None = None
    url: str | None = None
    subscribers: int = 0
    relevance: int = 0


class SystemStatus(BaseModel):
    cities_by_status: dict[str, int] = {}
    total_cities: int = 0
    total_sources: int = 0
    posts_today: int = 0
    last_post_time: str | None = None


class DailyReport(BaseModel):
    posts_today: int = 0
    active_cities: int = 0
    cities_by_status: dict[str, int] = {}


class WeeklyReport(BaseModel):
    posts_week: int = 0
    top_cities: list[dict[str, str | int]] = []
