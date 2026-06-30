import logging
import sys
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI

from backend.config import settings
from backend.db import init_db
from backend.routers import cities, reports, sources, status

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    logger.info("БД инициализирована: %s", settings.DB_PATH)
    yield


app = FastAPI(title="News Backend API", lifespan=lifespan)

app.include_router(status.router)
app.include_router(cities.router)
app.include_router(sources.router)
app.include_router(reports.router)


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )
