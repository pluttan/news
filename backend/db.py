import aiosqlite
from pathlib import Path

from backend.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    population INTEGER,
    status TEXT DEFAULT 'scouted',
    tg_channel_id TEXT,
    max_channel_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id INTEGER NOT NULL REFERENCES cities(id),
    platform TEXT NOT NULL,
    external_id TEXT,
    name TEXT,
    url TEXT,
    subscribers INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    last_parsed_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id INTEGER NOT NULL REFERENCES cities(id),
    source_id INTEGER REFERENCES sources(id),
    title TEXT,
    content TEXT,
    media_url TEXT,
    status TEXT DEFAULT 'draft',
    posted_at TEXT,
    tg_message_id INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS channel_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id INTEGER NOT NULL REFERENCES cities(id),
    subscribers INTEGER DEFAULT 0,
    views_avg INTEGER DEFAULT 0,
    posts_today INTEGER DEFAULT 0,
    recorded_at TEXT DEFAULT (datetime('now'))
);
"""


def _ensure_dir() -> None:
    Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(settings.DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


_MIGRATIONS = [
    "ALTER TABLE sources ADD COLUMN relevance INTEGER DEFAULT 0",
]


async def init_db() -> None:
    _ensure_dir()
    db = await get_db()
    try:
        await db.executescript(_SCHEMA)
        for sql in _MIGRATIONS:
            try:
                await db.execute(sql)
            except Exception:
                pass  # column already exists
        await db.commit()
    finally:
        await db.close()


# --------------- cities CRUD ---------------

async def get_all_cities() -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM cities ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_city(city_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM cities WHERE id = ?", (city_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def find_city_by_name(name: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM cities WHERE name LIKE ?",
            (f"%{name}%",),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def create_city(
    name: str,
    population: int | None = None,
    status: str = "scouted",
    tg_channel_id: str | None = None,
    max_channel_id: str | None = None,
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO cities (name, population, status, tg_channel_id, max_channel_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, population, status, tg_channel_id, max_channel_id),
        )
        await db.commit()
        city_id = cursor.lastrowid
        return (await get_city(city_id))  # type: ignore[return-value]
    finally:
        await db.close()


async def update_city(city_id: int, **fields: str | int | None) -> dict | None:
    if not fields:
        return await get_city(city_id)

    set_parts: list[str] = []
    values: list[str | int | None] = []
    for key, value in fields.items():
        set_parts.append(f"{key} = ?")
        values.append(value)

    set_parts.append("updated_at = datetime('now')")
    values.append(city_id)

    db = await get_db()
    try:
        await db.execute(
            f"UPDATE cities SET {', '.join(set_parts)} WHERE id = ?",
            values,
        )
        await db.commit()
    finally:
        await db.close()

    return await get_city(city_id)


async def update_city_status(city_id: int, status: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE cities SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, city_id),
        )
        await db.commit()
    finally:
        await db.close()


# --------------- sources CRUD ---------------

async def get_sources_by_city(city_id: int) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM sources WHERE city_id = ? ORDER BY created_at",
            (city_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def create_source(
    city_id: int,
    platform: str,
    external_id: str | None = None,
    name: str | None = None,
    url: str | None = None,
    subscribers: int = 0,
    relevance: int = 0,
) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO sources (city_id, platform, external_id, name, url, subscribers, relevance) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (city_id, platform, external_id, name, url, subscribers, relevance),
        )
        await db.commit()
        source_id = cursor.lastrowid
        row_cursor = await db.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        )
        row = await row_cursor.fetchone()
        return dict(row)  # type: ignore[arg-type]
    finally:
        await db.close()


async def get_sources_count(city_id: int) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM sources WHERE city_id = ? AND is_active = 1",
            (city_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"]
    finally:
        await db.close()


async def get_total_sources_count() -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM sources WHERE is_active = 1"
        )
        row = await cursor.fetchone()
        return row["cnt"]
    finally:
        await db.close()


# --------------- posts CRUD ---------------

async def get_posts_today(city_id: int | None = None) -> int:
    db = await get_db()
    try:
        if city_id is not None:
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM posts "
                "WHERE city_id = ? AND status = 'posted' AND date(posted_at) = date('now')",
                (city_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT COUNT(*) as cnt FROM posts "
                "WHERE status = 'posted' AND date(posted_at) = date('now')"
            )
        row = await cursor.fetchone()
        return row["cnt"]
    finally:
        await db.close()


async def get_posts_week(city_id: int) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM posts "
            "WHERE city_id = ? AND status = 'posted' "
            "AND posted_at >= datetime('now', '-7 days')",
            (city_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"]
    finally:
        await db.close()


async def get_last_post_time() -> str | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT posted_at FROM posts WHERE status = 'posted' "
            "ORDER BY posted_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return row["posted_at"] if row else None
    finally:
        await db.close()


# --------------- metrics CRUD ---------------

async def get_latest_metrics(city_id: int) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM channel_metrics WHERE city_id = ? "
            "ORDER BY recorded_at DESC LIMIT 1",
            (city_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


# --------------- top cities ---------------

async def get_top_cities(limit: int = 10) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT
                c.id, c.name, c.population, c.status,
                COALESCE(vk.total_subs, 0)  AS vk_demand,
                COALESCE(vk.group_count, 0) AS vk_count,
                COALESCE(tg.total_subs, 0)  AS tg_supply,
                COALESCE(tg.ch_count, 0)    AS tg_count,
                CASE
                    WHEN COALESCE(vk.total_subs, 0) > 0
                    THEN CAST(vk.total_subs AS REAL) / (COALESCE(tg.total_subs, 0) + 1)
                    ELSE 0
                END AS ratio
            FROM cities c
            LEFT JOIN (
                SELECT city_id,
                       SUM(subscribers) AS total_subs,
                       COUNT(*)         AS group_count
                FROM sources
                WHERE platform = 'vk' AND relevance > 0 AND is_active = 1
                GROUP BY city_id
            ) vk ON vk.city_id = c.id
            LEFT JOIN (
                SELECT city_id,
                       SUM(subscribers) AS total_subs,
                       COUNT(*)         AS ch_count
                FROM sources
                WHERE platform = 'tg' AND relevance > 0 AND is_active = 1
                GROUP BY city_id
            ) tg ON tg.city_id = c.id
            WHERE COALESCE(vk.total_subs, 0) > 0 OR COALESCE(tg.total_subs, 0) > 0
            ORDER BY ratio DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


# --------------- агрегаты для отчётов ---------------

async def get_cities_summary() -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT status, COUNT(*) as cnt FROM cities GROUP BY status"
        )
        rows = await cursor.fetchall()
        return {r["status"]: r["cnt"] for r in rows}
    finally:
        await db.close()


async def get_daily_report_data() -> dict:
    db = await get_db()
    try:
        posts_cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM posts "
            "WHERE status = 'posted' AND date(posted_at) = date('now')"
        )
        posts_row = await posts_cursor.fetchone()

        cities_cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM cities WHERE status = 'active'"
        )
        cities_row = await cities_cursor.fetchone()

        return {
            "posts_today": posts_row["cnt"],
            "active_cities": cities_row["cnt"],
        }
    finally:
        await db.close()


async def get_weekly_report_data() -> dict:
    db = await get_db()
    try:
        posts_cursor = await db.execute(
            "SELECT c.name, COUNT(p.id) as cnt "
            "FROM posts p JOIN cities c ON p.city_id = c.id "
            "WHERE p.status = 'posted' AND p.posted_at >= datetime('now', '-7 days') "
            "GROUP BY c.name ORDER BY cnt DESC"
        )
        top_cities = [dict(r) for r in await posts_cursor.fetchall()]

        total_cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM posts "
            "WHERE status = 'posted' AND posted_at >= datetime('now', '-7 days')"
        )
        total_row = await total_cursor.fetchone()

        return {
            "posts_week": total_row["cnt"],
            "top_cities": top_cities,
        }
    finally:
        await db.close()
