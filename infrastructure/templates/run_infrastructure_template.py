"""Скрипт запуска инфраструктурного слоя.

Перед запуском создайте файл .infra.env (команда infra-init).
Все настройки читаются из этого файла.
Имя файла можно переопределить через переменную окружения INFRA_ENV_FILE.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Загружаем конфигурационный файл (по умолчанию .infra.env)
from infrastructure.config_loader import load_dotenv

config_file = os.getenv("INFRA_ENV_FILE", ".infra.env")
load_dotenv(config_file)

logging.basicConfig(level=logging.INFO)

# Добавляем текущую директорию в sys.path для импорта models.py
sys.path.insert(0, str(Path(__file__).parent))

from models import get_all_schemas
from infrastructure.db_migrator import run_migration
from infrastructure.event_infrastructure import create_pipeline, shutdown_pipeline
from infrastructure.event_infrastructure.config import ChannelConfig, CacheConfig, RetryConfig

ALL_SCHEMAS = get_all_schemas()

# --- Вспомогательные функции для чтения из окружения ---
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

# --- Чтение основных параметров ---
DB_URL = os.getenv("DB_URL", "postgresql://postgres:123@localhost:5432/Proj_v2")
DB_URL_ASYNC = os.getenv("DB_URL_ASYNC", "postgresql+asyncpg://postgres:123@localhost:5432/Proj_v2")

# --- Построение конфигурации каналов ---
channel_names = [name.strip() for name in os.getenv("CHANNELS", "read,write,admin").split(",") if name.strip()]
CHANNELS = {}

for name in channel_names:
    prefix = name.upper()
    CHANNELS[name] = ChannelConfig(
        pool_size=_int_env(f"{prefix}_POOL_SIZE", 10),
        max_overflow=_int_env(f"{prefix}_MAX_OVERFLOW", 5),
        queue_maxsize=_int_env(f"{prefix}_QUEUE_MAXSIZE", 1000),
    )

# --- Общие параметры ---
POOL_RECYCLE = _int_env("POOL_RECYCLE", 3600)
POOL_PRE_PING = _bool_env("POOL_PRE_PING", True)
POOL_TIMEOUT = _int_env("POOL_TIMEOUT", 30)
DEFAULT_TIMEOUT = _float_env("DEFAULT_TIMEOUT", 30.0)
SHUTDOWN_TIMEOUT = _float_env("SHUTDOWN_TIMEOUT", 10.0)
MAX_CONCURRENCY = _int_env("MAX_CONCURRENCY", 100000)

# --- Retry ---
RETRY_MAX_RETRIES = _int_env("RETRY_MAX_RETRIES", 3)
RETRY_DELAY_SECONDS = _float_env("RETRY_DELAY_SECONDS", 0.5)
RETRY_BACKOFF_MULTIPLIER = _float_env("RETRY_BACKOFF_MULTIPLIER", 2.0)

# --- Cache ---
CACHE_ENABLED = _bool_env("CACHE_ENABLED", True)
CACHE_TTL_SECONDS = _float_env("CACHE_TTL_SECONDS", 3.0)
CACHE_MAX_SIZE = _int_env("CACHE_MAX_SIZE", 5000)

# --- Глобальный объект роутера ---
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
        pool_recycle=POOL_RECYCLE,
        pool_pre_ping=POOL_PRE_PING,
        pool_timeout=POOL_TIMEOUT,
        default_timeout=DEFAULT_TIMEOUT,
        shutdown_timeout=SHUTDOWN_TIMEOUT,
        max_concurrency=MAX_CONCURRENCY,
        retry=RetryConfig(
            max_retries=RETRY_MAX_RETRIES,
            delay_seconds=RETRY_DELAY_SECONDS,
            backoff_multiplier=RETRY_BACKOFF_MULTIPLIER,
        ),
        cache=CacheConfig(
            enabled=CACHE_ENABLED,
            ttl_seconds=CACHE_TTL_SECONDS,
            max_size=CACHE_MAX_SIZE,
        ),
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
