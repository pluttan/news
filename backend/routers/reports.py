from fastapi import APIRouter

from backend import db
from backend.schemas import DailyReport, WeeklyReport

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/daily", response_model=DailyReport)
async def daily_report() -> DailyReport:
    data = await db.get_daily_report_data()
    summary = await db.get_cities_summary()

    return DailyReport(
        posts_today=data["posts_today"],
        active_cities=data["active_cities"],
        cities_by_status=summary,
    )


@router.get("/weekly", response_model=WeeklyReport)
async def weekly_report() -> WeeklyReport:
    data = await db.get_weekly_report_data()

    return WeeklyReport(
        posts_week=data["posts_week"],
        top_cities=data["top_cities"],
    )
