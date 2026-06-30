from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.api_client import ApiClient

router = Router()


@router.message(Command("status"))
async def cmd_status(message: Message, api: ApiClient) -> None:
    data = await api.get_system_status()

    summary = data["cities_by_status"]
    total_cities = data["total_cities"]
    total_sources = data["total_sources"]
    posts_today = data["posts_today"]
    last_post = data["last_post_time"]

    active = summary.get("active", 0)
    paused = summary.get("paused", 0)
    scouted = summary.get("scouted", 0)

    lines = [
        "<b>Статус системы</b>\n",
        f"Городов: {total_cities}",
        f"  ├ active: {active}",
        f"  ├ paused: {paused}",
        f"  └ scouted: {scouted}",
        f"\nИсточников: {total_sources}",
        f"Постов сегодня: {posts_today}",
        f"Последний пост: {last_post or '—'}",
    ]

    await message.answer("\n".join(lines), parse_mode="HTML")
