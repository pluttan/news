![Header](header.png)

<div align="center">

# news

**Automated news Telegram channels for Russian cities**

[![License](https://img.shields.io/badge/license-MIT-2C2C2C?style=for-the-badge&labelColor=1E1E1E)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-2C2C2C?style=for-the-badge&logo=python&labelColor=1E1E1E)]()
[![FastAPI](https://img.shields.io/badge/fastapi-backend-2C2C2C?style=for-the-badge&logo=fastapi&labelColor=1E1E1E)]()
[![Telegram](https://img.shields.io/badge/telegram-bot-2C2C2C?style=for-the-badge&logo=telegram&labelColor=1E1E1E)]()
[![Docker](https://img.shields.io/badge/docker-deploy-2C2C2C?style=for-the-badge&logo=docker&labelColor=1E1E1E)]()

</div>

A system for creating and managing automated news Telegram channels for Russian cities. Three components work together: a FastAPI backend (single source of truth for the database), an admin Telegram bot, and a scout module that discovers relevant VK groups and Telegram channels per city using relevance scoring.

## ■ Features

- ❖ **City-based channels** — one automated news channel per city, sourced from local media
- ❖ **VK scouting** — discovers relevant VK groups by city via VK API search and relevance scoring
- ❖ **Telegram scouting** — finds local Telegram channels using Telethon client API
- ❖ **Relevance scoring** — 0-100 relevance assessment for each discovered source
- ❖ **Admin bot** — Telegram interface for managing cities, sources, and channel status
- ❖ **REST API** — FastAPI backend with Swagger UI, all data access through HTTP
- ❖ **City loader** — imports Russian cities from CSV (Rosstat) and Wikipedia
- ❖ **Docker deployment** — docker-compose setup for backend and bot services

## ■ Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + uvicorn |
| Bot | aiogram 3.x |
| Scout | VK API, Telethon |
| Database | SQLite (aiosqlite) |
| HTTP Client | aiohttp |
| Schemas | Pydantic (BaseModel) |
| Config | python-dotenv |
| Deploy | Docker Compose |

## ■ Architecture

```
Telegram Admin <-> Bot (aiogram) -> HTTP -> Backend (FastAPI) -> SQLite
                                                 ^
                   Scout (VK/TG search) ---------+
```

## ■ Usage

```bash
make install          # venv + dependencies
make api              # start backend (port 8000)
make run              # start bot (polling)
make cities           # load Russian cities
make scout            # VK scouting for all cities
make scout CITY=Name  # VK scouting for one city
make tg-auth          # Telethon auth (interactive)
make tg-scout         # Telegram scouting
make clean            # remove venv + database

# Docker
docker compose build backend bot
docker compose up -d
```

## ■ Screenshots

![Screenshot](screenshots/main.png)

## ■ License

MIT © [pluttan](https://github.com/pluttan)
