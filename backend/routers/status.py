from fastapi import APIRouter

from backend import db
from backend.schemas import SystemStatus

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status", response_model=SystemStatus)
async def get_system_status() -> SystemStatus:
    summary = await db.get_cities_summary()
    total_sources = await db.get_total_sources_count()
    posts_today = await db.get_posts_today()
    last_post = await db.get_last_post_time()

    return SystemStatus(
        cities_by_status=summary,
        total_cities=sum(summary.values()),
        total_sources=total_sources,
        posts_today=posts_today,
        last_post_time=last_post,
    )
