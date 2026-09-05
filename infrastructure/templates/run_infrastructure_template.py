"""Скрипт запуска инфраструктурного слоя.

Перед запуском можно задать переменные окружения или создать файл .env
(рекомендуется). Значения из .env подхватываются автоматически,
но переменные окружения имеют приоритет.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Загружаем .env, если он есть в текущей директории
from infrastructure.config_loader import load_dotenv

load_dotenv(str(Path(__file__).parent / ".env"))

logging.basicConfig(level=logging.INFO)

# Добавляем текущую директорию в sys.path, чтобы импортировался models.py
sys.path.insert(0, str(Path(__file__).parent))

from models import get_all_schemas
from infrastructure.db_migrator import run_migration
from infrastructure.event_infrastructure import create_pipeline, shutdown_pipeline
from infrastructure.event_infrastructure.config import ChannelConfig, CacheConfig

ALL_SCHEMAS = get_all_schemas()

# --- Чтение параметров из окружения (с дефолтами из .env, если заданы) ---
def _int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    return int(val) if val is not None else default

def _float_env(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val is not None else default

def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")

DB_URL = os.getenv("DB_URL", "postgresql://postgres:123@localhost:5432/Proj_v2")
DB_URL_ASYNC = os.getenv("DB_URL_ASYNC", "postgresql+asyncpg://postgres:123@localhost:5432/Proj_v2")

CHANNELS = {
    "read": ChannelConfig(
        pool_size=_int_env("READ_POOL_SIZE", 39),
        max_overflow=_int_env("READ_MAX_OVERFLOW", 10),
        queue_maxsize=_int_env("READ_QUEUE_MAXSIZE", 50000),
    ),
    "write": ChannelConfig(
        pool_size=_int_env("WRITE_POOL_SIZE", 60),
        max_overflow=_int_env("WRITE_MAX_OVERFLOW", 5),
        queue_maxsize=_int_env("WRITE_QUEUE_MAXSIZE", 50000),
    ),
    "admin": ChannelConfig(
        pool_size=_int_env("ADMIN_POOL_SIZE", 1),
        max_overflow=_int_env("ADMIN_MAX_OVERFLOW", 0),
        queue_maxsize=_int_env("ADMIN_QUEUE_MAXSIZE", 5000),
    ),
}

POOL_TIMEOUT = _int_env("POOL_TIMEOUT", 30)
DEFAULT_TIMEOUT = _float_env("DEFAULT_TIMEOUT", 30.0)
SHUTDOWN_TIMEOUT = _float_env("SHUTDOWN_TIMEOUT", 10.0)
MAX_CONCURRENCY = _int_env("MAX_CONCURRENCY", 100000)

CACHE_ENABLED = _bool_env("CACHE_ENABLED", True)
CACHE_TTL_SECONDS = _float_env("CACHE_TTL_SECONDS", 3.0)
CACHE_MAX_SIZE = _int_env("CACHE_MAX_SIZE", 5000)

router = None


async def metrics_loop(router, interval=1.0):
    """Бесконечный цикл вывода метрик."""
    while True:
        await asyncio.sleep(interval)
        os.system("cls" if os.name == "nt" else "clear")
        router.print_metrics(full=True)


async def main():
    global router

    print("=" * 50)
    print("ЗАПУСК ИНФРАСТРУКТУРЫ")
    print("=" * 50)

    print("\n1. Проверка и применение миграций...")
    schema_path = Path(__file__).parent / "models.py"
    alembic_path = Path(__file__).parent / "alembic"
    success = run_migration(db_url=DB_URL, schema_path=str(schema_path), alembic_dir=str(alembic_path))
    if not success:
        print("Ошибка миграций")
        sys.exit(1)
    print("Миграции в порядке")

    print("\n2. Создание event_infrastructure...")
    router = await create_pipeline(
        db_url=DB_URL_ASYNC,
        channels=CHANNELS,
        schemas=ALL_SCHEMAS,
        exclude_tables={"alembic_version"},
        pool_timeout=POOL_TIMEOUT,
        default_timeout=DEFAULT_TIMEOUT,
        shutdown_timeout=SHUTDOWN_TIMEOUT,
        cache=CacheConfig(enabled=CACHE_ENABLED, ttl_seconds=CACHE_TTL_SECONDS, max_size=CACHE_MAX_SIZE),
        max_concurrency=MAX_CONCURRENCY,
    )
    print("Pipeline готов")

    print("\n3. Мониторинг инфраструктуры...")
    print("   Нажмите Ctrl+C для остановки")
    print("=" * 50)

    try:
        await metrics_loop(router)
    except KeyboardInterrupt:
        print("\nОстановка...")
    finally:
        router.print_metrics(full=False)
        await shutdown_pipeline(router)
        print("Проект остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nЗавершено.")