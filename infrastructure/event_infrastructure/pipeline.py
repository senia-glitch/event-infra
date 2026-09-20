"""Точка сборки всей инфраструктуры.

Предоставляет фабричные функции для создания и уничтожения pipeline:
- create_pipeline() — создаёт и запускает полный pipeline (пулы, очереди, диспетчеры, роутер)
- shutdown_pipeline() — корректно завершает работу pipeline

Пример использования:
    from infrastructure.event_infrastructure import create_pipeline, shutdown_pipeline

    router = await create_pipeline(
        db_url="postgresql+asyncpg://...",
        channels={"read": ChannelConfig(...), "write": ChannelConfig(...)},
        schemas={"user": User},
    )
    # ... работа с router ...
    await shutdown_pipeline(router)
"""

import logging
from typing import Any, Optional

from .config.models import PipelineConfig, ChannelConfig, RetryConfig, CacheConfig
from .db.orchestrator import Orchestrator
from .router.router import EventRouter

logger = logging.getLogger(__name__)

_PIPELINE_CONFIG_FIELDS = {f.name for f in PipelineConfig.__dataclass_fields__.values()}


async def create_pipeline(
    db_url: str,
    channels: Optional[dict[str, ChannelConfig]] = None,
    schemas: Optional[dict] = None,
    exclude_tables: Optional[set[str]] = None,
    retry: Optional[RetryConfig] = None,
    cache: Optional[CacheConfig] = None,
    **kwargs: Any,
) -> EventRouter:
    """Создаёт и запускает pipeline.

    Args:
        db_url: Строка подключения (postgresql+asyncpg://user:pass@host:port/db)
        channels: {"read": ChannelConfig(...), "write": ChannelConfig(...), ...}
        schemas: {"user": User, "post": Post, ...} — SQLModel схемы
        exclude_tables: Таблицы которые нужно игнорировать (например alembic_version)
        retry: Конфигурация повторных попыток
        cache: Конфигурация кеширования
        **kwargs: pool_recycle, pool_pre_ping, pool_timeout,
                  default_timeout, metrics_enabled, max_concurrency, shutdown_timeout
    """
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in _PIPELINE_CONFIG_FIELDS}

    if channels is not None and len(channels) == 0:
        raise ValueError(
            "channels не может быть пустым словарём. "
            "Передайте каналы явно или не передавайте параметр для дефолтов (read/write/admin)."
        )

    config_kwargs = dict(db_url=db_url, **filtered_kwargs)
    if channels is not None:
        config_kwargs["channels"] = channels
    config = PipelineConfig(**config_kwargs)

    final_retry = retry or config.retry
    final_cache = cache or config.cache

    orchestrator = Orchestrator(config)
    try:
        await orchestrator.start()
    except Exception:
        logger.exception("Ошибка при запуске оркестратора, очистка ресурсов")
        await orchestrator.shutdown()
        raise

    try:
        router = EventRouter(
            orchestrator=orchestrator,
            schemas=schemas or {},
            exclude_tables=exclude_tables,
            default_timeout=config.default_timeout,
            metrics_enabled=config.metrics_enabled,
            max_concurrency=config.max_concurrency,
            retry=final_retry,
            cache=final_cache,
        )
    except Exception:
        logger.exception("Ошибка при создании EventRouter, остановка оркестратора")
        await orchestrator.shutdown()
        raise

    return router


async def shutdown_pipeline(router: EventRouter, timeout: Optional[float] = None) -> None:
    """Graceful shutdown pipeline.

    Порядок завершения:
    1. Прекращение приёма новых задач (QueueManager.stop_accepting)
    2. Доработка текущих задач диспетчерами
    3. Закрытие всех пулов соединений

    Args:
        router: роутер, созданный через create_pipeline()
        timeout: таймаут ожидания завершения (сек). Если None — используется shutdown_timeout из конфига.
    """
    await router.shutdown(timeout)
