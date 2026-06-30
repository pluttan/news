from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

HELP_TEXT = (
    "<b>Админ-бот городских каналов</b>\n\n"
    "Доступные команды:\n"
    "/start — приветствие\n"
    "/help — список команд\n"
    "/status — статус системы\n"
    "/cities — список городов\n"
    "/top — топ городов по привлекательности\n"
    "/run &lt;город&gt; — активировать город\n"
    "/stop &lt;город&gt; — поставить город на паузу\n"
    "/post &lt;город&gt; — принудительный постинг\n"
    "/scout &lt;город&gt; [мин_подп] — VK-скаутинг одного города\n"
    "/scout_all [мин_подп] — скаутинг всех городов\n"
    "/scout_stop — остановить массовый скаутинг\n"
    "/tg_scout &lt;город&gt; — TG-скаутинг одного города\n"
    "/tg_scout_all — TG-скаутинг всех городов\n"
    "/tg_scout_stop — остановить TG-скаутинг\n"
    "/load_cities [мин_население] — загрузить н.п. РФ"
)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я админ-бот системы городских ТГ-каналов.\n\n"
        "Используй /help для списка команд.",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")
