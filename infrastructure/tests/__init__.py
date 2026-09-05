"""Тесты инфраструктурного слоя."""

import asyncio
import os
import sys
import shutil
from pathlib import Path
from importlib import resources

from infrastructure.db_migrator import run_migration
from infrastructure.event_infrastructure import create_pipeline, shutdown_pipeline
from infrastructure.event_infrastructure.config import ChannelConfig
from . import run_all


async def _run_tests_async(db_url: str, db_url_async: str, verbose: bool = False) -> bool:
    # 1. Применяем миграции (загружает модуль models_template)
    schema_path = resources.files("infrastructure.templates") / "models_template.py"
    alembic_dir = Path.cwd() / ".test_alembic"
    
    if alembic_dir.exists():
        shutil.rmtree(alembic_dir)
    
    run_migration(db_url, str(schema_path), alembic_dir=str(alembic_dir))

    # 2. Получаем загруженный модуль из sys.modules
    models = sys.modules.get('models_template')
    if models is None:
        raise RuntimeError("Модуль models_template не загружен")
    schemas = models.get_all_schemas()

    # 3. Создаём каналы
    channels = {
        "read": ChannelConfig(pool_size=10, max_overflow=5, queue_maxsize=200),
        "write": ChannelConfig(pool_size=10, max_overflow=5, queue_maxsize=200),
        "admin": ChannelConfig(pool_size=5, max_overflow=2, queue_maxsize=100),
    }

    # 4. Создаём роутер
    router = await create_pipeline(
        db_url=db_url_async,
        channels=channels,
        schemas=schemas,
        exclude_tables={"alembic_version"},
        pool_timeout=10,
        default_timeout=10.0,
        shutdown_timeout=5.0,
        max_concurrency=50,
        pool_recycle=60,
        pool_pre_ping=True,
    )

    # 5. Запускаем все тесты с verbose
    success = await run_all.run(router, verbose=verbose)

    # 6. Завершаем работу
    await shutdown_pipeline(router)

    # 7. Удаляем временную папку alembic
    if alembic_dir.exists():
        shutil.rmtree(alembic_dir)

    return success


def run_tests(db_url: str = None, db_url_async: str = None, verbose: bool = False) -> bool:
    """
    Запускает все тесты.

    Если URL не указаны, используются значения из переменных окружения
    TEST_DB_URL и TEST_DB_URL_ASYNC, либо значения по умолчанию.
    """
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
