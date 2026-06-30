from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.api_client import ApiClient

router = Router()

STATUS_EMOJI = {
    "active": "🟢",
    "paused": "🟡",
    "scouted": "🔵",
}


@router.message(Command("cities"))
async def cmd_cities(message: Message, api: ApiClient) -> None:
    cities = await api.get_all_cities()

    if not cities:
        await message.answer("Городов пока нет.")
        return

    buttons = []
    for city in cities:
        emoji = STATUS_EMOJI.get(city["status"], "⚪")
        label = f"{emoji} {city['name']} ({city['status']})"
        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f"city:{city['id']}")]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("<b>Города:</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("city:"))
async def cb_city_detail(callback: CallbackQuery, api: ApiClient) -> None:
    city_id = int(callback.data.split(":")[1])
    city = await api.get_city_detail(city_id)

    if not city:
        await callback.answer("Город не найден", show_alert=True)
        return

    emoji = STATUS_EMOJI.get(city["status"], "⚪")
    metrics = city.get("metrics")
    subscribers = metrics["subscribers"] if metrics else 0
    views_avg = metrics["views_avg"] if metrics else 0

    lines = [
        f"{emoji} <b>{city['name']}</b>\n",
        f"Статус: {city['status']}",
        f"Население: {city['population'] or '—'}",
        f"TG канал: {city['tg_channel_id'] or '—'}",
        f"MAX канал: {city['max_channel_id'] or '—'}",
        f"\nПодписчики: {subscribers}",
        f"Ср. просмотры: {views_avg}",
        f"Источников: {city['sources_count']}",
        f"Постов сегодня: {city['posts_today']}",
        f"Постов за неделю: {city['posts_week']}",
    ]

    actions = []
    if city["status"] != "active":
        actions.append(InlineKeyboardButton(text="▶ Запустить", callback_data=f"run:{city_id}"))
    if city["status"] != "paused":
        actions.append(InlineKeyboardButton(text="⏸ Пауза", callback_data=f"stop:{city_id}"))
    actions.append(InlineKeyboardButton(text="🔍 Скаутинг", callback_data=f"scout:{city_id}"))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        actions,
        [InlineKeyboardButton(text="◀ Назад к списку", callback_data="cities:back")],
    ])

    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "cities:back")
async def cb_cities_back(callback: CallbackQuery, api: ApiClient) -> None:
    cities = await api.get_all_cities()

    if not cities:
        await callback.message.edit_text("Городов пока нет.")
        await callback.answer()
        return

    buttons = []
    for city in cities:
        emoji = STATUS_EMOJI.get(city["status"], "⚪")
        label = f"{emoji} {city['name']} ({city['status']})"
        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f"city:{city['id']}")]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("<b>Города:</b>", reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.message(Command("top"))
async def cmd_top(message: Message, api: ApiClient) -> None:
    scored = await api.get_top_cities(limit=10)

    if not scored:
        await message.answer("Городов пока нет.")
        return

    lines = ["<b>Топ городов (привлекательность)</b>\n"]
    for i, city in enumerate(scored, 1):
        emoji = STATUS_EMOJI.get(city["status"], "⚪")
        pop = city["population"] or 0
        vk_demand = city.get("vk_demand", 0)
        vk_count = city.get("vk_count", 0)
        tg_supply = city.get("tg_supply", 0)
        tg_count = city.get("tg_count", 0)
        ratio = city["ratio"]

        pop_str = f"нас. {pop:,}" if pop else "нас. —"
        tg_part = f"{tg_supply:,} 📢 ({tg_count} кан.)" if tg_count else "0 📢"
        lines.append(
            f"{i}. {emoji} {city['name']} — {pop_str}\n"
            f"   VK: {vk_demand:,} 👥 ({vk_count} групп) | TG: {tg_part}\n"
            f"   Ratio: {ratio:,.1f}"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")
