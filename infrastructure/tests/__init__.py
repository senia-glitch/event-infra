"""Тесты инфраструктурного слоя."""

import asyncio
import os
import sys
from pathlib import Path
from importlib import resources

from infrastructure.db_migrator import run_migration
from infrastructure.event_infrastructure import create_pipeline, shutdown_pipeline
from infrastructure.event_infrastructure.config import ChannelConfig
from . import run_all


async def _run_tests_async(db_url: str, db_url_async: str, verbose: bool = False) -> bool:
    # 1. Загружаем модели из шаблона
    schema_path = resources.files("infrastructure.templates") / "models_template.py"
    
    # 2. Применяем миграции (используем исходный run_migration без alembic_dir)
    run_migration(db_url, str(schema_path))
    
    # 3. Получаем загруженный модуль из sys.modules
    models = sys.modules.get('models_template')
    if models is None:
        raise RuntimeError("Модуль models_template не загружен")
    schemas = models.get_all_schemas()

    # 4. Создаём каналы с параметрами из исходного проекта (run_infrastructure.py)
    channels = {
        "read": ChannelConfig(pool_size=39, max_overflow=10, queue_maxsize=50000),
        "write": ChannelConfig(pool_size=60, max_overflow=5, queue_maxsize=50000),
        "admin": ChannelConfig(pool_size=1, max_overflow=0, queue_maxsize=5000),
    }

    # 5. Создаём роутер с параметрами из исходного проекта
    router = await create_pipeline(
        db_url=db_url_async,
        channels=channels,
        schemas=schemas,
        exclude_tables={"alembic_version"},
        pool_timeout=30,
        default_timeout=30.0,
        shutdown_timeout=10.0,
        max_concurrency=100000,
        pool_recycle=3600,
        pool_pre_ping=True,
    )

    # 6. Запускаем все тесты
    success = await run_all.run(router, verbose=verbose)

    # 7. Завершаем работу
    await shutdown_pipeline(router)

    return success


def run_tests(db_url: str = None, db_url_async: str = None, verbose: bool = False) -> bool:
    if db_url is None:
        db_url = os.getenv("TEST_DB_URL", "postgresql://postgres:123@localhost:5432/test_infra")
    if db_url_async is None:
        db_url_async = os.getenv("TEST_DB_URL_ASYNC", "postgresql+asyncpg://postgres:123@localhost:5432/test_infra")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_tests_async(db_url, db_url_async, verbose))
    finally:
        loop.close()
