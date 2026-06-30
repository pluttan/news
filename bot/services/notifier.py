from aiogram import Bot

from bot.api_client import ApiClient
from bot.config import settings


async def notify(bot: Bot, text: str) -> None:
    await bot.send_message(chat_id=settings.ADMIN_ID, text=text, parse_mode="HTML")


async def send_daily_report(bot: Bot, api: ApiClient) -> None:
    data = await api.get_daily_report()

    summary = data.get("cities_by_status", {})

    lines = [
        "<b>Отчёт за день</b>\n",
        f"Активных городов: {summary.get('active', 0)}",
        f"Постов сегодня: {data['posts_today']}",
    ]

    await notify(bot, "\n".join(lines))


async def send_weekly_report(bot: Bot, api: ApiClient) -> None:
    data = await api.get_weekly_report()

    lines = [
        "<b>Отчёт за неделю</b>\n",
        f"Всего постов: {data['posts_week']}",
    ]

    if data["top_cities"]:
        lines.append("\nТоп городов:")
        for i, city in enumerate(data["top_cities"][:5], 1):
            lines.append(f"  {i}. {city['name']} — {city['cnt']} постов")
    else:
        lines.append("\nПостов за неделю не было.")

    await notify(bot, "\n".join(lines))


async def alert_free_city(bot: Bot, city_name: str, population: int) -> None:
    await notify(
        bot,
        f"🔍 <b>Найден свободный город!</b>\n\n"
        f"Город: {city_name}\n"
        f"Население: {population:,}",
    )
