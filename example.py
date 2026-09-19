"""Полный пример всех возможностей event-infra.

Запуск:
    cd event-infra
    python example.py

Требуется .infra.env в текущей директории с DB_URL_ASYNC.
"""

import asyncio
from datetime import datetime
from typing import List, Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import JSON, create_engine, text

from infrastructure.event_infrastructure import create_pipeline
from infrastructure.event_infrastructure.config import ChannelConfig
from infrastructure.config_loader import load_config_from_env


# ============================================================
# 1. МОДЕЛИ
# ============================================================


class User(SQLModel, table=True):
    __tablename__ = "example_users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, unique=True)
    email: str = Field(max_length=255)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)


class Post(SQLModel, table=True):
    __tablename__ = "example_posts"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="example_users.id")
    title: str = Field(max_length=255)
    tags: Optional[List[str]] = Field(default=None, sa_type=JSON)


# ============================================================
# 2. ПРИМЕРЫ ВСЕХ API
# ============================================================


async def example_crud(router):
    """CRUD операции."""
    print("\n=== CRUD ===")

    result = await router.create("example_users", {"username": "alice", "email": "alice@test.com"})
    user_id = result.data[0]["id"]
    print(f"CREATE: id={user_id}, username={result.data[0]['username']}")

    result = await router.read("example_users", user_id)
    print(f"READ:   id={result.data[0]['id']}, email={result.data[0]['email']}")

    result = await router.update("example_users", user_id, {"email": "alice@new.com"})
    print(f"UPDATE: id={result.data[0]['id']}, email={result.data[0]['email']}")

    result = await router.delete("example_users", user_id)
    print(f"DELETE: success={result.success}")


async def example_list(router):
    """Пагинация и фильтрация."""
    print("\n=== LIST (пагинация) ===")

    for i in range(5):
        await router.create("example_users", {"username": f"user_{i}", "email": f"user_{i}@test.com"})

    result = await router.list("example_users", limit=3, offset=0, order_by="username")
    print(f"LIST:   {len(result.data)} записей (limit=3)")
    for u in result.data:
        print(f"  - {u['username']}")

    result = await router.list("example_users", limit=2, order_by="username", order_desc=True)
    print(f"LIST:   {len(result.data)} записей (order_desc, limit=2)")
    for u in result.data:
        print(f"  - {u['username']}")
        await router.delete("example_users", u["id"])


async def example_custom_sql(router):
    """Произвольные SQL-запросы."""
    print("\n=== CUSTOM SQL ===")

    result = await router.execute(
        "read",
        'SELECT COUNT(*) as cnt FROM "example_users" WHERE username LIKE :pattern',
        {"pattern": "user_%"},
    )
    print(f"EXECUTE: количество user_* = {result.data[0]['cnt']}")

    result = await router.custom(
        'SELECT username, email FROM "example_users" ORDER BY username LIMIT 2',
        channel="read",
    )
    print(f"CUSTOM:  найдено {len(result.data)} записей")


async def example_health_and_metrics(router):
    """Health check и метрики."""
    print("\n=== HEALTH & METRICS ===")

    health = await router.health_check()
    print(f"HEALTH:  alive={health['alive']}, db_connected={health['db_connected']}")

    metrics = router.get_metrics()
    print(f"METRICS: uptime={metrics.uptime_seconds:.1f}s")


# ============================================================
# 3. ТОЧКА ВХОДА
# ============================================================


async def main():
    print("=" * 60)
    print("  EVENT-INFRA: ПОЛНЫЙ ПРИМЕР ВСЕХ ВОЗМОЖНОСТЕЙ")
    print("=" * 60)

    config = load_config_from_env()
    if not config.db_url:
        print("\nDB_URL_ASYNC не задан в .infra.env")
        print("Создайте .infra.env с содержимым:")
        print("  DB_URL_ASYNC=postgresql+asyncpg://user:pass@localhost/dbname")
        return

    # Создание таблиц
    sync_url = config.db_url.replace("+asyncpg", "+psycopg")
    engine = create_engine(sync_url)
    SQLModel.metadata.create_all(engine)
    engine.dispose()

    schemas = {"example_users": User, "example_posts": Post}

    # Context manager — автоматический shutdown
    router = await create_pipeline(
        db_url=config.db_url,
        channels={
            "read": ChannelConfig(pool_size=2, max_overflow=1, queue_maxsize=10),
            "write": ChannelConfig(pool_size=2, max_overflow=1, queue_maxsize=10),
        },
        schemas=schemas,
        exclude_tables=set(),
    )
    async with router:
        await example_crud(router)
        await example_list(router)
        await example_custom_sql(router)
        await example_health_and_metrics(router)

    print("\n" + "=" * 60)
    print("  ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ")
    print("=" * 60)

    # Очистка
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        for table in ("example_users", "example_posts"):
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
        conn.commit()
    engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
