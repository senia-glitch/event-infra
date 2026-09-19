"""Pytest fixtures для тестирования event_infrastructure.

Требует PostgreSQL. URL задаётся через переменную окружения TEST_DB_URL_ASYNC.
"""

import os
from datetime import datetime

import pytest
import pytest_asyncio
from sqlmodel import SQLModel, Field
from typing import Optional


class TestRole(SQLModel, table=True):
    __tablename__ = "test_roles"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True)


class TestUser(SQLModel, table=True):
    __tablename__ = "test_users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, unique=True)
    email: str = Field(max_length=255)
    role_id: Optional[int] = Field(default=None, foreign_key="test_roles.id")
    age: Optional[int] = Field(default=None)


class TestItem(SQLModel, table=True):
    __tablename__ = "test_items"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    val: int = Field(default=0)


class TestItemWithTimestamp(SQLModel, table=True):
    __tablename__ = "test_items_with_ts"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    val: int = Field(default=0)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)


class TestCustomPK(SQLModel, table=True):
    __tablename__ = "test_custom_pk"
    uuid: str = Field(max_length=36, primary_key=True)
    label: str = Field(max_length=100)


def get_test_schemas():
    return {
        "test_roles": TestRole,
        "test_users": TestUser,
        "test_items": TestItem,
        "test_items_with_ts": TestItemWithTimestamp,
        "test_custom_pk": TestCustomPK,
    }


@pytest.fixture(scope="session")
def db_url():
    url = os.getenv("TEST_DB_URL_ASYNC")
    if not url:
        pytest.skip("TEST_DB_URL_ASYNC не задан — пропуск тестов, требующих PostgreSQL")
    return url


@pytest_asyncio.fixture
async def router(db_url):
    from infrastructure.event_infrastructure import create_pipeline, shutdown_pipeline
    from infrastructure.event_infrastructure.config import ChannelConfig, CacheConfig
    from sqlalchemy import create_engine, text

    schemas = get_test_schemas()
    channels = {
        "read": ChannelConfig(pool_size=5, max_overflow=2, queue_maxsize=100),
        "write": ChannelConfig(pool_size=5, max_overflow=2, queue_maxsize=100),
        "admin": ChannelConfig(pool_size=1, max_overflow=0, queue_maxsize=50),
    }

    sync_url = db_url.replace("+asyncpg", "+psycopg")
    engine = create_engine(sync_url)
    with engine.connect() as conn:
        for table in ["test_users", "test_roles", "test_items", "test_items_with_ts", "test_custom_pk"]:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
        conn.commit()
    SQLModel.metadata.create_all(engine)
    engine.dispose()

    router_instance = await create_pipeline(
        db_url=db_url,
        channels=channels,
        schemas=schemas,
        exclude_tables=set(),
        pool_recycle=3600,
        pool_pre_ping=False,
        pool_timeout=30,
        default_timeout=30.0,
        shutdown_timeout=5.0,
        max_concurrency=50,
        cache=CacheConfig(enabled=True, ttl_seconds=10.0, max_size=100),
    )

    yield router_instance

    await shutdown_pipeline(router_instance)


@pytest_asyncio.fixture
async def clean_db(router):
    await router.execute("admin", 'TRUNCATE TABLE "test_users" RESTART IDENTITY CASCADE')
    await router.execute("admin", 'TRUNCATE TABLE "test_roles" RESTART IDENTITY CASCADE')
    await router.execute("admin", 'TRUNCATE TABLE "test_items" RESTART IDENTITY CASCADE')
    await router.execute("admin", 'TRUNCATE TABLE "test_items_with_ts" RESTART IDENTITY CASCADE')
    await router.execute("admin", 'TRUNCATE TABLE "test_custom_pk" RESTART IDENTITY CASCADE')
    yield
