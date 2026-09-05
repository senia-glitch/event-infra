"""Точка сборки всей инфраструктуры."""

from .config.models import PipelineConfig, ChannelConfig, RetryConfig, CacheConfig
from .db.orchestrator import Orchestrator
from .router.router import EventRouter


async def create_pipeline(
    db_url: str,
    channels: dict[str, ChannelConfig] = None,
    schemas: dict = None,
    exclude_tables: set[str] = None,
    **kwargs,
) -> EventRouter:
    """Создаёт и запускает pipeline.
    
    Args:
        db_url: Строка подключения (postgresql+asyncpg://user:pass@host:port/db)
        channels: {"read": ChannelConfig(...), "write": ChannelConfig(...), ...}
        schemas: {"user": User, "post": Post, ...} — SQLModel схемы
        exclude_tables: Таблицы которые нужно игнорировать (например alembic_version)
        **kwargs: pool_recycle, pool_pre_ping, pool_timeout,
                  default_timeout, metrics_enabled, max_concurrency,
                  retry (RetryConfig), shutdown_timeout
    """
    config = PipelineConfig(
        db_url=db_url,
        channels=channels or {},
        **{k: v for k, v in kwargs.items() if hasattr(PipelineConfig, k)},
    )
    
    orchestrator = Orchestrator(config)
    await orchestrator.start()
    
    router = EventRouter(
        orchestrator=orchestrator,
        schemas=schemas or {},
        exclude_tables=exclude_tables,
        default_timeout=config.default_timeout,
        metrics_enabled=config.metrics_enabled,
        max_concurrency=config.max_concurrency,
        retry=kwargs.get("retry", config.retry),
        cache=kwargs.get("cache", config.cache),
    )
    
    return router


async def shutdown_pipeline(router: EventRouter, timeout: float = None):
    """Graceful shutdown pipeline."""
    await router.shutdown(timeout)