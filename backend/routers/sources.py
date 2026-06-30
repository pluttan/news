from fastapi import APIRouter, HTTPException

from backend import db
from backend.schemas import Source, SourceCreate

router = APIRouter(prefix="/api/cities/{city_id}/sources", tags=["sources"])


@router.get("", response_model=list[Source])
async def list_sources(city_id: int) -> list[Source]:
    city = await db.get_city(city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    rows = await db.get_sources_by_city(city_id)
    return [Source(**r) for r in rows]


@router.post("", response_model=Source, status_code=201)
async def create_source(city_id: int, body: SourceCreate) -> Source:
    city = await db.get_city(city_id)
    if not city:
        raise HTTPException(status_code=404, detail="City not found")

    source = await db.create_source(
        city_id=city_id,
        platform=body.platform,
        external_id=body.external_id,
        name=body.name,
        url=body.url,
        subscribers=body.subscribers,
        relevance=body.relevance,
    )
    return Source(**source)
