import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "news.db"))
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    HTTP_PROXY: str = os.getenv("HTTP_PROXY", "")


settings = Settings()
