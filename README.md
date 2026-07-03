<div align="center">

# news

**Automated news Telegram channels for Russian cities**


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

<div align="center">

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

</div>

## ■ How It Works

```
1. Scout module queries VK API and Telegram (via Telethon) for local groups and channels per city, assigning each a 0-100 relevance score.
2. Discovered sources are registered in the FastAPI backend via HTTP and persisted in SQLite.
3. The admin Telegram bot (aiogram) lets operators add cities, review sources, and manage channel status — all requests go through the REST API.
4. Docker Compose bundles the backend and bot services for deployment.
```

## ■ Screenshots

<div align="center">

![Screenshot](screenshots/main.png)

*Main admin bot interface showing city and source management*

</div>

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

## ■ License

MIT © [pluttan](https://github.com/pluttan)
