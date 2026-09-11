"""Модуль запуска инфраструктурного слоя.

Предоставляет функцию start_infrastructure(), которая:
1. Загружает настройки из .infra.env (или файла, указанного в INFRA_ENV_FILE).
2. Применяет миграции к БД.
3. Создаёт и запускает EventRouter.

Использование:
    from run_infrastructure import start_infrastructure

    router = await start_infrastructure()
    # работа с router
    await router.shutdown()
"""

import os
import sys
from pathlib import Path

from infrastructure.config_loader import load_dotenv
from infrastructure.db_migrator import run_migration
from infrastructure.event_infrastructure import create_pipeline
from infrastructure.event_infrastructure.config import ChannelConfig, RetryConfig, CacheConfig


async def start_infrastructure():
    """Запускает инфраструктуру и возвращает готовый EventRouter.

    Все настройки читаются из .infra.env (или файла, указанного через INFRA_ENV_FILE).
    Пути к models.py и alembic/ определяются относительно расположения этого модуля.

    Returns:
        EventRouter: готовый к использованию роутер.

    Raises:
        RuntimeError: если не удалось применить миграции или не заданы URL БД.
    """
    # 1. Загрузка конфигурации
    config_file = os.getenv("INFRA_ENV_FILE", ".infra.env")
    load_dotenv(config_file)

    base_dir = Path(__file__).parent
    models_path = base_dir / "models.py"
    alembic_dir = base_dir / "alembic"

    db_url = os.getenv("DB_URL")
    db_url_async = os.getenv("DB_URL_ASYNC")

    if not db_url or not db_url_async:
        raise RuntimeError("Не заданы DB_URL и/или DB_URL_ASYNC в .infra.env")

    # 2. Миграции
    success = run_migration(
        db_url=db_url,
        schema_path=str(models_path),
        alembic_dir=str(alembic_dir),
    )
    if not success:
        raise RuntimeError("Не удалось применить миграции. Проверьте настройки БД и models.py")

    # 3. Получение схем из models.py (модуль уже загружен run_migration)
    module_name = models_path.stem
    models_module = sys.modules.get(module_name)
    if models_module is None:
        raise RuntimeError(f"Модуль {module_name} не был загружен после миграции")
    if not hasattr(models_module, "get_all_schemas"):
        raise AttributeError(f"В {models_path} отсутствует функция get_all_schemas()")
    schemas = models_module.get_all_schemas()

    # 4. Построение конфигурации каналов
    channel_names = [
        name.strip()
        for name in os.getenv("CHANNELS", "read,write,admin").split(",")
        if name.strip()
    ]
    channels = {}
    for name in channel_names:
        prefix = name.upper()
        channels[name] = ChannelConfig(
            pool_size=int(os.getenv(f"{prefix}_POOL_SIZE", 10)),
            max_overflow=int(os.getenv(f"{prefix}_MAX_OVERFLOW", 5)),
            queue_maxsize=int(os.getenv(f"{prefix}_QUEUE_MAXSIZE", 1000)),
        )

    # 5. Retry и Cache
    retry = RetryConfig(
        max_retries=int(os.getenv("RETRY_MAX_RETRIES", 3)),
        delay_seconds=float(os.getenv("RETRY_DELAY_SECONDS", 0.5)),
        backoff_multiplier=float(os.getenv("RETRY_BACKOFF_MULTIPLIER", 2.0)),
    )

    cache = CacheConfig(
        enabled=os.getenv("CACHE_ENABLED", "True").lower() in ("1", "true", "yes", "on"),
        ttl_seconds=float(os.getenv("CACHE_TTL_SECONDS", 3.0)),
        max_size=int(os.getenv("CACHE_MAX_SIZE", 5000)),
    )

    # 6. Создание и запуск pipeline
    router = await create_pipeline(
        db_url=db_url_async,
        channels=channels,
        schemas=schemas,
        exclude_tables={"alembic_version"},
        pool_recycle=int(os.getenv("POOL_RECYCLE", 3600)),
        pool_pre_ping=os.getenv("POOL_PRE_PING", "True").lower() in ("1", "true", "yes", "on"),
        pool_timeout=int(os.getenv("POOL_TIMEOUT", 30)),
        default_timeout=float(os.getenv("DEFAULT_TIMEOUT", 30.0)),
        shutdown_timeout=float(os.getenv("SHUTDOWN_TIMEOUT", 10.0)),
        max_concurrency=int(os.getenv("MAX_CONCURRENCY", 100000)),
        retry=retry,
        cache=cache,
    )

    return router