import asyncio
import logging
import time

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.api_client import ApiClient
from scout.api_client import ScoutApiClient
from scout.city_loader import LoadResult, load_cities
from scout.config import settings as scout_settings
from scout.scanner import ScoutResult, scout_all_cities, scout_city
from scout.tg_client import TgClient
from scout.tg_scanner import TgScoutResult, tg_scout_all, tg_scout_city
from scout.vk_client import VKApiError, VKClient

logger = logging.getLogger(__name__)

router = Router()

# Фоновые задачи скаутинга
_scout_all_task: asyncio.Task | None = None
_tg_scout_all_task: asyncio.Task | None = None


@router.message(Command("run"))
async def cmd_run(message: Message, command: CommandObject, api: ApiClient) -> None:
    if not command.args:
        await message.answer("Использование: /run &lt;название города&gt;", parse_mode="HTML")
        return

    city_name = command.args.strip()
    results = await api.search_city(city_name)

    if not results:
        await message.answer(f"Город «{city_name}» не найден.")
        return

    city = results[0]

    if city["status"] == "active":
        await message.answer(f"Город «{city['name']}» уже активен.")
        return

    await api.update_city(city["id"], status="active")
    await message.answer(f"Город «{city['name']}» активирован. ✅")


@router.message(Command("stop"))
async def cmd_stop(message: Message, command: CommandObject, api: ApiClient) -> None:
    if not command.args:
        await message.answer("Использование: /stop &lt;название города&gt;", parse_mode="HTML")
        return

    city_name = command.args.strip()
    results = await api.search_city(city_name)

    if not results:
        await message.answer(f"Город «{city_name}» не найден.")
        return

    city = results[0]

    if city["status"] == "paused":
        await message.answer(f"Город «{city['name']}» уже на паузе.")
        return

    await api.update_city(city["id"], status="paused")
    await message.answer(f"Город «{city['name']}» поставлен на паузу. ⏸")


@router.message(Command("post"))
async def cmd_post(message: Message, command: CommandObject, api: ApiClient) -> None:
    if not command.args:
        await message.answer("Использование: /post &lt;название города&gt;", parse_mode="HTML")
        return

    city_name = command.args.strip()
    results = await api.search_city(city_name)

    if not results:
        await message.answer(f"Город «{city_name}» не найден.")
        return

    city = results[0]

    # Заглушка — будет реализовано с пайплайном постинга
    await message.answer(
        f"Принудительный постинг для «{city['name']}» пока не реализован.\n"
        "Будет доступно после подключения пайплайна."
    )


@router.message(Command("scout"))
async def cmd_scout(message: Message, command: CommandObject, api: ApiClient) -> None:
    if not command.args:
        await message.answer(
            "Использование: /scout &lt;город&gt; [мин_подписчики]\n"
            "Пример: /scout Воронеж 1000",
            parse_mode="HTML",
        )
        return

    parts = command.args.strip().rsplit(maxsplit=1)
    min_subscribers: int | None = None
    if len(parts) == 2 and parts[1].isdigit():
        city_name = parts[0]
        min_subscribers = int(parts[1])
    else:
        city_name = command.args.strip()

    results = await api.search_city(city_name)

    if not results:
        await message.answer(f"Город «{city_name}» не найден.")
        return

    city = results[0]
    await message.answer(f"Запускаю VK-скаутинг для «{city['name']}»...")

    vk = VKClient()
    scout_api = ScoutApiClient()
    await vk.start()
    await scout_api.start()

    try:
        scout_kwargs: dict[str, int] = {}
        if min_subscribers is not None:
            scout_kwargs["min_subscribers"] = min_subscribers
        result = await scout_city(
            city["id"], city["name"], vk, scout_api,
            population=city.get("population") or 0, **scout_kwargs,
        )
        await message.answer(
            f"Скаутинг «{result.city_name}» завершён.\n\n"
            f"Найдено групп: {result.found}\n"
            f"Отфильтровано: {result.filtered}\n"
            f"Добавлено: {result.added}\n"
            f"Пропущено (дубли): {result.skipped}",
        )
    except VKApiError as e:
        logger.error("VK API error for city %s: %s", city["name"], e)
        await message.answer(f"Ошибка VK API: {e.message}")
    except Exception:
        logger.exception("Scout failed for city %s", city["name"])
        await message.answer(f"Ошибка при скаутинге «{city['name']}». Проверьте логи.")
    finally:
        await vk.close()
        await scout_api.close()


@router.message(Command("scout_all"))
async def cmd_scout_all(message: Message, command: CommandObject, api: ApiClient) -> None:
    global _scout_all_task

    if _scout_all_task and not _scout_all_task.done():
        await message.answer("Скаутинг уже запущен. /scout_stop — отменить.")
        return

    if not scout_settings.VK_TOKEN:
        await message.answer("VK_TOKEN не настроен. Добавьте его в .env и перезапустите.")
        return

    min_subscribers: int | None = None
    if command.args and command.args.strip().isdigit():
        min_subscribers = int(command.args.strip())

    status_msg = await message.answer("🔍 Запускаю скаутинг всех городов...")

    last_edit: dict[str, float] = {"t": 0.0}
    totals: dict[str, int] = {"found": 0, "added": 0, "skipped": 0, "errors": 0}

    async def on_progress(current: int, total: int, city_name: str, result: ScoutResult | None) -> None:
        if result:
            totals["found"] += result.found
            totals["added"] += result.added
            totals["skipped"] += result.skipped
            if result.found == 0 and result.added == 0:
                totals["errors"] += 0  # just no results

        now = time.monotonic()
        if now - last_edit["t"] < 5.0 and current != total and current != 0:
            return
        last_edit["t"] = now

        if current == 0:
            text = f"🔍 Скаутинг: 0/{total} городов..."
        else:
            pct = int(current / total * 100)
            filled = pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            text = (
                f"🔍 Скаутинг: {current}/{total} ({pct}%)\n"
                f"[{bar}]\n\n"
                f"Последний: {city_name}\n"
                f"Найдено групп: {totals['found']:,}\n"
                f"Добавлено: {totals['added']:,}\n"
                f"Дубли: {totals['skipped']:,}"
            )

        try:
            await status_msg.edit_text(text)
        except Exception:
            pass

    async def _run_scout_all() -> None:
        vk = VKClient()
        scout_api = ScoutApiClient()
        await vk.start()
        await scout_api.start()

        try:
            scout_kwargs: dict[str, int] = {}
            if min_subscribers is not None:
                scout_kwargs["min_subscribers"] = min_subscribers

            results = await scout_all_cities(
                vk, scout_api, on_progress=on_progress, **scout_kwargs,
            )

            total_found = sum(r.found for r in results)
            total_added = sum(r.added for r in results)
            total_skipped = sum(r.skipped for r in results)

            await status_msg.edit_text(
                f"✅ Скаутинг завершён!\n\n"
                f"Городов: {len(results):,}\n"
                f"Найдено групп: {total_found:,}\n"
                f"Добавлено: {total_added:,}\n"
                f"Дубли: {total_skipped:,}",
            )
        except asyncio.CancelledError:
            await status_msg.edit_text("⏹ Скаутинг отменён.")
        except VKApiError as e:
            logger.error("scout_all VK error: %s", e)
            await status_msg.edit_text(f"Ошибка VK API: {e.message}")
        except Exception:
            logger.exception("scout_all failed")
            await status_msg.edit_text("Ошибка при массовом скаутинге. Проверьте логи.")
        finally:
            await vk.close()
            await scout_api.close()

    _scout_all_task = asyncio.create_task(_run_scout_all())


@router.message(Command("scout_stop"))
async def cmd_scout_stop(message: Message) -> None:
    global _scout_all_task

    if not _scout_all_task or _scout_all_task.done():
        await message.answer("Нет активного скаутинга.")
        return

    _scout_all_task.cancel()
    await message.answer("Останавливаю скаутинг...")


@router.message(Command("load_cities"))
async def cmd_load_cities(message: Message, command: CommandObject, api: ApiClient) -> None:
    min_pop = 10000
    if command.args and command.args.strip().isdigit():
        min_pop = int(command.args.strip())

    status_msg = await message.answer(f"Загружаю н.п. РФ (>= {min_pop:,} чел.)...\n\n[          ] 0%")

    STAGE_ICONS = {"download": "1/3 🌐", "parse": "2/3 🔍", "save": "3/3 💾", "done": "✅"}
    last_edit: dict[str, float] = {"t": 0.0}

    async def on_progress(stage: str, detail: str, current: int, total: int) -> None:
        now = time.monotonic()
        if now - last_edit["t"] < 2.0 and stage != "done":
            return
        last_edit["t"] = now

        icon = STAGE_ICONS.get(stage, "")
        if total > 0:
            pct = int(current / total * 100)
            filled = pct // 10
            bar = "█" * filled + "░" * (10 - filled)
            text = f"[{icon}] {detail}\n\n[{bar}] {pct}%"
        else:
            text = f"[{icon}] {detail}"

        try:
            await status_msg.edit_text(text)
        except Exception:
            pass

    try:
        result: LoadResult = await load_cities(min_population=min_pop, on_progress=on_progress)

        top_lines = ""
        if result.top_cities:
            top_lines = "\nТоп-5 по населению:\n"
            for c in result.top_cities:
                top_lines += f"  {c['name']} — {c['population']:,}\n"

        source_label = {
            "rosstat": "Росстат (tochno.st)",
            "wikipedia": "Wikipedia",
            "csv": "hflabs CSV",
        }.get(result.source, result.source)
        await status_msg.edit_text(
            f"Загрузка завершена за {result.elapsed:.1f}с\n\n"
            f"Источник: {source_label}\n"
            f"Найдено н.п.: {result.parsed:,}\n"
            f"Было в базе: {result.already_in_db:,}\n"
            f"Добавлено новых: {result.added:,}\n"
            f"Всего в базе: {result.total_in_db:,}"
            f"{top_lines}",
        )
    except Exception:
        logger.exception("load_cities failed")
        await status_msg.edit_text("Ошибка при загрузке городов. Проверьте логи.")


@router.message(Command("tg_scout"))
async def cmd_tg_scout(message: Message, command: CommandObject, api: ApiClient) -> None:
    if not command.args:
        await message.answer(
            "Использование: /tg_scout &lt;город&gt;\n"
            "Пример: /tg_scout Воронеж",
            parse_mode="HTML",
        )
        return

    city_name = command.args.strip()
    results = await api.search_city(city_name)

    if not results:
        await message.answer(f"Город «{city_name}» не найден.")
        return

    if not scout_settings.TG_API_ID or not scout_settings.TG_API_HASH:
        await message.answer("TG_API_ID / TG_API_HASH не настроены. Добавьте в .env.")
        return

    city = results[0]
    await message.answer(f"Запускаю TG-скаутинг для «{city['name']}»...")

    async def _notify_flood(seconds: int) -> None:
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        wait_str = f"{h}ч {m}м" if h else f"{m}м {s}с"
        try:
            await message.answer(f"⏳ FloodWait от Telegram: ждём {wait_str}")
        except Exception:
            pass

    tg = TgClient(on_flood_wait=_notify_flood)
    scout_api = ScoutApiClient()
    await scout_api.start()

    try:
        await tg.start()
    except RuntimeError as e:
        await message.answer(str(e))
        await scout_api.close()
        return

    try:
        result = await tg_scout_city(
            city["id"], city["name"], tg, message.bot, scout_api,
            population=city.get("population") or 0,
        )
        await message.answer(
            f"TG-скаутинг «{result.city_name}» завершён.\n\n"
            f"Запросов: {result.searched}\n"
            f"Найдено каналов: {result.found}\n"
            f"Добавлено: {result.added}\n"
            f"Пропущено (дубли): {result.skipped}",
        )
    except Exception:
        logger.exception("TG scout failed for city %s", city["name"])
        await message.answer(f"Ошибка при TG-скаутинге «{city['name']}». Проверьте логи.")
    finally:
        await tg.close()
        await scout_api.close()


@router.message(Command("tg_scout_all"))
async def cmd_tg_scout_all(message: Message, command: CommandObject, api: ApiClient) -> None:
    global _tg_scout_all_task

    if _tg_scout_all_task and not _tg_scout_all_task.done():
        await message.answer("TG-скаутинг уже запущен. /tg_scout_stop — отменить.")
        return

    if not scout_settings.TG_API_ID or not scout_settings.TG_API_HASH:
        await message.answer("TG_API_ID / TG_API_HASH не настроены. Добавьте в .env.")
        return

    status_msg = await message.answer("🔍 Запускаю TG-скаутинг всех городов...")

    last_edit: dict[str, float] = {"t": 0.0}
    start_time: dict[str, float] = {"t": 0.0}
    totals: dict[str, int] = {"found": 0, "added": 0, "skipped": 0, "relevant": 0}

    async def on_progress(
        current: int, total: int, city: dict, result: TgScoutResult | None,
    ) -> None:
        if result:
            totals["found"] += result.found
            totals["added"] += result.added
            totals["skipped"] += result.skipped
            totals["relevant"] += result.relevant

        now = time.monotonic()
        if now - last_edit["t"] < 5.0 and current != total and current != 0:
            return
        last_edit["t"] = now

        if current == 0:
            start_time["t"] = now
            text = f"🔍 TG-скаутинг: 0/{total} городов..."
        else:
            pct = int(current / total * 100)
            filled = pct // 5
            bar = "▓" * filled + "░" * (20 - filled)
            elapsed = now - start_time["t"]
            elapsed_m, elapsed_s = divmod(int(elapsed), 60)
            elapsed_h, elapsed_m = divmod(elapsed_m, 60)

            eta_str = ""
            if current > 0:
                avg = elapsed / current
                remaining = avg * (total - current)
                eta_m, eta_s = divmod(int(remaining), 60)
                eta_h, eta_m = divmod(eta_m, 60)
                if eta_h:
                    eta_str = f"{eta_h}ч {eta_m}м"
                else:
                    eta_str = f"{eta_m}м {eta_s}с"

            city_name = city.get("name", "")
            population = city.get("population") or 0
            city_line = city_name
            if population:
                city_line += f" ({population:,} чел.)"

            if result and result.relevant > 0:
                city_line += f" +{result.relevant} рел."

            time_line = ""
            if elapsed_h:
                time_line = f"⏱ {elapsed_h}ч {elapsed_m}м"
            else:
                time_line = f"⏱ {elapsed_m}м {elapsed_s}с"
            if eta_str:
                time_line += f"  ⏳ ~{eta_str}"

            text = (
                f"🔍 TG-скаутинг: {current}/{total} ({pct}%)\n"
                f"[{bar}]\n"
                f"{time_line}\n\n"
                f"Город: {city_line}\n\n"
                f"📊 Найдено: {totals['found']:,}\n"
                f"💾 Добавлено: {totals['added']:,}\n"
                f"✅ Релевантных: {totals['relevant']:,}\n"
                f"🔄 Дубли: {totals['skipped']:,}"
            )

        try:
            await status_msg.edit_text(text)
        except Exception:
            pass

    async def _run_tg_scout_all() -> None:
        async def _make_flood_cb(idx: int):
            async def _notify_flood(seconds: int) -> None:
                m, s = divmod(seconds, 60)
                h, m = divmod(m, 60)
                wait_str = f"{h}ч {m}м" if h else f"{m}м {s}с"
                try:
                    await status_msg.reply(f"⏳ Акк #{idx + 1} FloodWait: ждём {wait_str}")
                except Exception:
                    pass
            return _notify_flood

        # Build list of TG session paths
        session_paths = list(scout_settings.TG_SESSION_PATHS)
        if not session_paths:
            session_paths = [scout_settings.TG_SESSION_PATH]

        clients: list[TgClient] = []
        for i, path in enumerate(session_paths):
            tg = TgClient(session_path=path, on_flood_wait=await _make_flood_cb(i))
            try:
                await tg.start()
                clients.append(tg)
                logger.info("TG account #%d connected: %s", i + 1, path)
            except RuntimeError as e:
                logger.warning("TG account #%d (%s) failed: %s", i + 1, path, e)

        if not clients:
            await status_msg.edit_text("Не удалось подключить ни один TG-аккаунт.")
            return

        await status_msg.edit_text(
            f"🔍 TG-скаутинг: подключено {len(clients)} акк(ов), загружаю города..."
        )

        scout_api = ScoutApiClient()
        await scout_api.start()

        try:
            results = await tg_scout_all(
                clients, message.bot, scout_api, on_progress=on_progress,
            )

            total_found = sum(r.found for r in results)
            total_added = sum(r.added for r in results)
            total_skipped = sum(r.skipped for r in results)
            total_relevant = sum(r.relevant for r in results)

            elapsed = time.monotonic() - start_time["t"]
            elapsed_m, elapsed_s = divmod(int(elapsed), 60)
            elapsed_h, elapsed_m = divmod(elapsed_m, 60)
            if elapsed_h:
                time_str = f"{elapsed_h}ч {elapsed_m}м"
            else:
                time_str = f"{elapsed_m}м {elapsed_s}с"

            await status_msg.edit_text(
                f"✅ TG-скаутинг завершён за {time_str}!\n\n"
                f"🏙 Городов: {len(results):,}\n"
                f"📊 Найдено каналов: {total_found:,}\n"
                f"💾 Добавлено: {total_added:,}\n"
                f"✅ Релевантных: {total_relevant:,}\n"
                f"🔄 Дубли: {total_skipped:,}",
            )
        except asyncio.CancelledError:
            await status_msg.edit_text("⏹ TG-скаутинг отменён.")
        except Exception:
            logger.exception("tg_scout_all failed")
            await status_msg.edit_text("Ошибка при массовом TG-скаутинге. Проверьте логи.")
        finally:
            for c in clients:
                await c.close()
            await scout_api.close()

    _tg_scout_all_task = asyncio.create_task(_run_tg_scout_all())


@router.message(Command("tg_scout_stop"))
async def cmd_tg_scout_stop(message: Message) -> None:
    global _tg_scout_all_task

    if not _tg_scout_all_task or _tg_scout_all_task.done():
        await message.answer("Нет активного TG-скаутинга.")
        return

    _tg_scout_all_task.cancel()
    await message.answer("Останавливаю TG-скаутинг...")


# --- Inline-кнопки ---

STATUS_EMOJI = {
    "active": "🟢",
    "paused": "🟡",
    "scouted": "🔵",
}


def _city_actions_kb(city: dict) -> InlineKeyboardMarkup:
    actions: list[InlineKeyboardButton] = []
    if city["status"] != "active":
        actions.append(InlineKeyboardButton(text="▶ Запустить", callback_data=f"run:{city['id']}"))
    if city["status"] != "paused":
        actions.append(InlineKeyboardButton(text="⏸ Пауза", callback_data=f"stop:{city['id']}"))
    actions.append(InlineKeyboardButton(text="🔍 Скаутинг", callback_data=f"scout:{city['id']}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        actions,
        [InlineKeyboardButton(text="◀ Назад к списку", callback_data="cities:back")],
    ])


@router.callback_query(F.data.startswith("run:"))
async def cb_run(callback: CallbackQuery, api: ApiClient) -> None:
    city_id = int(callback.data.split(":")[1])
    city = await api.get_city_detail(city_id)

    if not city:
        await callback.answer("Город не найден", show_alert=True)
        return

    if city["status"] == "active":
        await callback.answer(f"«{city['name']}» уже активен", show_alert=True)
        return

    await api.update_city(city_id, status="active")
    city["status"] = "active"

    emoji = STATUS_EMOJI.get("active", "⚪")
    await callback.message.edit_text(
        f"{emoji} <b>{city['name']}</b> — активирован ✅",
        reply_markup=_city_actions_kb(city),
        parse_mode="HTML",
    )
    await callback.answer("Активирован")


@router.callback_query(F.data.startswith("stop:"))
async def cb_stop(callback: CallbackQuery, api: ApiClient) -> None:
    city_id = int(callback.data.split(":")[1])
    city = await api.get_city_detail(city_id)

    if not city:
        await callback.answer("Город не найден", show_alert=True)
        return

    if city["status"] == "paused":
        await callback.answer(f"«{city['name']}» уже на паузе", show_alert=True)
        return

    await api.update_city(city_id, status="paused")
    city["status"] = "paused"

    emoji = STATUS_EMOJI.get("paused", "⚪")
    await callback.message.edit_text(
        f"{emoji} <b>{city['name']}</b> — на паузе ⏸",
        reply_markup=_city_actions_kb(city),
        parse_mode="HTML",
    )
    await callback.answer("На паузе")


@router.callback_query(F.data.startswith("scout:"))
async def cb_scout(callback: CallbackQuery, api: ApiClient) -> None:
    city_id = int(callback.data.split(":")[1])
    city = await api.get_city_detail(city_id)

    if not city:
        await callback.answer("Город не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"🔍 Запускаю VK-скаутинг для «{city['name']}»...",
        parse_mode="HTML",
    )
    await callback.answer()

    vk = VKClient()
    scout_api = ScoutApiClient()
    await vk.start()
    await scout_api.start()

    try:
        result = await scout_city(
            city_id, city["name"], vk, scout_api,
            population=city.get("population") or 0,
        )
        await callback.message.edit_text(
            f"🔍 Скаутинг «{result.city_name}» завершён\n\n"
            f"Найдено групп: {result.found}\n"
            f"Отфильтровано: {result.filtered}\n"
            f"Добавлено: {result.added}\n"
            f"Пропущено (дубли): {result.skipped}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀ К городу", callback_data=f"city:{city_id}")],
            ]),
        )
    except Exception:
        logger.exception("Scout failed for city %s", city["name"])
        await callback.message.edit_text(
            f"Ошибка при скаутинге «{city['name']}». Проверьте логи.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀ К городу", callback_data=f"city:{city_id}")],
            ]),
        )
    finally:
        await vk.close()
        await scout_api.close()
