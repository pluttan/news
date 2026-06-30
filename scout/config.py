import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    VK_TOKEN: str = os.getenv("VK_TOKEN", "")
    VK_API_VERSION: str = "5.199"
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    MIN_SUBSCRIBERS: int = int(os.getenv("SCOUT_MIN_SUBSCRIBERS", "500"))
    MAX_RESULTS_PER_QUERY: int = 50
    DELAY_BETWEEN_REQUESTS: float = float(os.getenv("SCOUT_DELAY_REQUESTS", "1.0"))
    DELAY_BETWEEN_CITIES: float = float(os.getenv("SCOUT_DELAY_CITIES", "30.0"))
    MIN_POPULATION: int = int(os.getenv("SCOUT_MIN_POPULATION", "10000"))
    HTTP_PROXY: str = os.getenv("HTTP_PROXY", "")

    # Telegram (Telethon)
    TG_API_ID: int = int(os.getenv("TG_API_ID", "0"))
    TG_API_HASH: str = os.getenv("TG_API_HASH", "")
    TG_PHONE: str = os.getenv("TG_PHONE", "")
    TG_SESSION_PATH: str = os.getenv("TG_SESSION_PATH", "data/tg_session")
    TG_SESSION_PATHS: list[str] = [
        p.strip()
        for p in os.getenv("TG_SESSION_PATHS", "").split(",")
        if p.strip()
    ]
    TG_SEARCH_DELAY: float = float(os.getenv("TG_SEARCH_DELAY", "10.0"))


settings = Settings()
