from fastapi import APIRouter, HTTPException, Query

from backend import db
from backend.schemas import City, CityCreate, CityDetail, CityTop, CityUpdate, MetricsSnapshot

router = APIRouter(prefix="/api/cities", tags=["cities"])


@router.get("", response_model=list[City])
async def list_cities() -> list[City]:
    rows = await db.get_all_cities()
    return [City(**r) for r in rows]


@router.get("/search", response_model=list[City])
async def search_cities(name: str = Query(..., min_length=1)) -> list[City]:
    rows = await db.find_city_by_name(name)
    return [City(**r) for r in rows]


@router.get("/top", response_model=list[CityTop])
async def top_cities(limit: int = Query(10, ge=1, le=100)) -> list[CityTop]:
    rows = await db.get_top_cities(limit)
    return [CityTop(**r) for r in rows]


@router.get("/{city_id}", response_model=CityDetail)
async def get_city_detail(city_id: int) -> CityDetail:
    city = await db.get_city(city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    sources_count = await db.get_sources_count(city_id)
    posts_today = await db.get_posts_today(city_id)
    posts_week = await db.get_posts_week(city_id)
    raw_metrics = await db.get_latest_metrics(city_id)

    metrics = None
    if raw_metrics:
        metrics = MetricsSnapshot(
            subscribers=raw_metrics["subscribers"],
            views_avg=raw_metrics["views_avg"],
            posts_today=raw_metrics["posts_today"],
            recorded_at=raw_metrics["recorded_at"],
        )

    return CityDetail(
        **city,
        sources_count=sources_count,
        posts_today=posts_today,
        posts_week=posts_week,
        metrics=metrics,
    )


@router.post("", response_model=City, status_code=201)
async def create_city(body: CityCreate) -> City:
    city = await db.create_city(
        name=body.name,
        population=body.population,
        status=body.status,
        tg_channel_id=body.tg_channel_id,
        max_channel_id=body.max_channel_id,
    )
    return City(**city)


@router.patch("/{city_id}", response_model=City)
async def update_city(city_id: int, body: CityUpdate) -> City:
    existing = await db.get_city(city_id)
    if not existing:
        raise HTTPException(status_code=404, detail="City not found")

    fields = body.model_dump(exclude_unset=True)
    updated = await db.update_city(city_id, **fields)
    return City(**updated)  # type: ignore[arg-type]
