import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from bot.api_client import ApiClient
from bot.config import settings
from bot.handlers import cities, manage, start, status
from bot.middlewares.admin_only import AdminOnlyMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не задан. Создайте .env файл (см. .env.example)")
        sys.exit(1)

    if not settings.ADMIN_ID:
        logger.error("ADMIN_ID не задан. Укажите свой Telegram ID в .env")
        sys.exit(1)

    api = ApiClient()
    await api.start()
    logger.info("API клиент подключён: %s", settings.API_BASE_URL)

    session = AiohttpSession(proxy=settings.HTTP_PROXY) if settings.HTTP_PROXY else None
    bot = Bot(token=settings.BOT_TOKEN, session=session)
    dp = Dispatcher()

    dp.update.outer_middleware(AdminOnlyMiddleware())

    dp.include_router(start.router)
    dp.include_router(status.router)
    dp.include_router(cities.router)
    dp.include_router(manage.router)

    try:
        logger.info("Бот запускается...")
        await dp.start_polling(bot, api=api)
    finally:
        await api.close()
        logger.info("API клиент закрыт")


if __name__ == "__main__":
    asyncio.run(main())
