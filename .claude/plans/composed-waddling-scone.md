# План: ratio привлекательности городов

## Контекст

Из TODO проекта: «Считаем ratio спрос_ВК / предложение_ТГ → чем выше, тем свободнее ниша».
Сейчас `/top` показывает `population / tg_channel_subscribers` — это не то. Нужен ratio на основе данных скаутинга: сколько VK-подписчиков (спрос/аудитория) vs сколько TG-каналов (конкуренция).

Данные уже в базе — таблица `sources` хранит и VK-группы (`platform='vk'`), и TG-каналы (`platform='tg'`) с полями `subscribers` и `relevance`.

## Формула

```
demand   = SUM(sources.subscribers) WHERE platform='vk'  AND relevance > 0
supply   = COUNT(*)                 WHERE platform='tg'  AND relevance > 0
tg_subs  = SUM(sources.subscribers) WHERE platform='tg'  AND relevance > 0

ratio = demand / (tg_subs + 1)
```

- `demand` — суммарная VK-аудитория (сколько людей читают городские паблики в VK)
- `supply` — кол-во релевантных TG-каналов (конкуренты)
- `tg_subs` — суммарная аудитория TG-конкурентов
- Делим на `tg_subs + 1` чтобы: города без TG-каналов → ratio ≈ demand (максимальная привлекательность)
- Только `relevance > 0` — отсекаем мусор

## Изменения

### 1. `backend/db.py` — заменить `get_top_cities()`

Текущий запрос (строки 319-346) использует `channel_metrics` и `population`. Заменяем на:

```sql
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
```

Фильтр `WHERE ... > 0` — исключаем города, по которым скаутинг ещё не прошёл.

### 2. `backend/schemas.py` — обновить `CityTop`

```python
class CityTop(BaseModel):
    id: int
    name: str
    population: int | None = None
    status: str
    vk_demand: int = 0     # суммарные VK подписчики
    vk_count: int = 0      # кол-во VK-групп
    tg_supply: int = 0     # суммарные TG подписчики
    tg_count: int = 0      # кол-во TG-каналов
    ratio: float = 0.0     # vk_demand / (tg_supply + 1)
```

### 3. `bot/handlers/cities.py` — обновить `cmd_top()` (строки 101-116)

Новый формат вывода:

```
Топ городов (привлекательность)

1. 🔵 Абаза — нас. 15,000
   VK: 45,230 👥 (12 групп) | TG: 0 📢
   Ratio: 45,230

2. 🔵 Абинск — нас. 42,000
   VK: 89,100 👥 (25 групп) | TG: 2,300 📢 (3 канала)
   Ratio: 38.7
```

### 4. Без изменений

- `bot/api_client.py` — `get_top_cities()` уже вызывает `/api/cities/top`, формат ответа совместим
- `backend/routers/cities.py` — endpoint `/api/cities/top` уже есть, возвращает `list[CityTop]`

## Файлы

| Файл | Изменение |
|------|-----------|
| `backend/db.py` | Заменить SQL в `get_top_cities()` |
| `backend/schemas.py` | Обновить поля `CityTop` |
| `bot/handlers/cities.py` | Обновить форматирование `/top` |

## Деплой

```bash
scp backend/db.py backend/schemas.py bot/handlers/cities.py → сервер
docker compose build bot backend && docker compose up -d
```

## Проверка

```bash
# В боте: /top — должен показать города с VK/TG разбивкой
# API: curl http://localhost:8100/api/cities/top?limit=5
# Города без скаутинга не должны появляться
# Города с VK > 0 и TG = 0 должны быть вверху (максимальный ratio)
```
