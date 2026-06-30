# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это

Система автоматизированных новостных Telegram-каналов для российских городов.
Три компонента: **backend** (API + БД), **bot** (Telegram-интерфейс админа), **scout** (поиск источников в VK и TG).

## Команды

```bash
make install          # venv + pip install -r requirements.txt
make api              # запуск backend (FastAPI, порт 8000)
make run              # запуск бота (aiogram, polling)
make cities           # загрузка городов РФ из CSV/Wikipedia
make scout            # VK-скаутинг всех городов
make scout CITY=Name  # VK-скаутинг одного города
make tg-auth          # авторизация Telethon (интерактивно)
make tg-scout         # TG-скаутинг всех городов
make tg-scout CITY=Name
make clean            # удалить venv + БД
```

Docker-деплой:
```bash
docker compose build backend bot
docker compose up -d
```

Backend доступен на `127.0.0.1:8100` (проброс на 8000 внутри контейнера).

## Архитектура

```
Telegram Admin ↔ Bot (aiogram) → HTTP → Backend (FastAPI) → SQLite (data/news.db)
                                              ↑
                Scout (VK/TG поиск) ──────────┘
```

- **Backend** — единственный сервис с доступом к БД. Все остальные ходят через REST API.
- **Bot** — фронтенд. Общается с backend через `bot/api_client.py` (`ApiClient`). Умеет запускать scout в фоне.
- **Scout** — поиск VK-групп и TG-каналов по городам. Оценивает релевантность (`scout/relevance.py`), сохраняет источники через backend API.

## Структура

```
backend/
  main.py          # FastAPI app, lifespan → init_db()
  config.py        # DB_PATH, API_HOST, API_PORT
  db.py            # SQLite: схема, CRUD (aiosqlite)
  schemas.py       # Pydantic-модели
  routers/         # cities, sources, status, reports

bot/
  main.py          # Dispatcher + polling + ApiClient lifecycle
  config.py        # Settings из .env
  api_client.py    # aiohttp-обёртка над backend
  handlers/        # start, status, cities, manage (отдельные Router'ы)
  services/        # notifier
  middlewares/     # admin_only (фильтр по ADMIN_ID)

scout/
  main.py          # CLI entry point (argparse: --tg, --city)
  config.py        # VK_TOKEN, TG_API_*, задержки
  api_client.py    # ScoutApiClient для backend
  scanner.py       # VK-поиск групп
  tg_scanner.py    # TG-поиск каналов (Telethon)
  tg_client.py     # Telethon-клиент
  tg_enricher.py   # Обогащение данных TG-каналов
  relevance.py     # Скоринг релевантности (0-100)
  queries.py       # Шаблоны поисковых запросов
  city_loader.py   # Загрузка городов (CSV Росстат / Wikipedia)
  wiki_parser.py   # Парсер Wikipedia для городов
```

## БД

SQLite (`data/news.db`). Таблицы: `cities`, `sources`, `posts`, `channel_metrics`.
Создаётся автоматически при первом запуске backend (`init_db()`).
Swagger UI: `http://localhost:8000/docs`.

## Ключевые переменные (.env)

| Переменная | Сервис | Назначение |
|---|---|---|
| `BOT_TOKEN` | bot | Telegram bot token |
| `ADMIN_ID` | bot | Telegram ID администратора |
| `API_BASE_URL` | bot, scout | Адрес backend (default: `http://127.0.0.1:8000`) |
| `VK_TOKEN` | scout | Токен VK API |
| `TG_API_ID`, `TG_API_HASH`, `TG_PHONE` | scout | Telegram API (Telethon) |
| `DB_PATH` | backend | Путь к SQLite (default: `data/news.db`) |
| `HTTP_PROXY` | bot, scout | SOCKS/HTTP прокси |

## Code style

- Python 3.11+, `from __future__ import annotations`
- Type hints везде
- async/await для всего I/O
- Handlers в отдельных файлах, подключаются через `Router` + `include_router()`
- Конфигурация через Pydantic `Settings` классы

## Стек

- **FastAPI** + **uvicorn** — backend
- **aiogram 3.x** — Telegram Bot API
- **aiohttp** — HTTP-клиент (bot → backend, scout → backend)
- **aiosqlite** — async SQLite
- **Telethon** — Telegram client API (scout)
- **python-dotenv** — переменные окружения
