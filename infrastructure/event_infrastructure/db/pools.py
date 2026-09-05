"""Управление пулами асинхронных соединений."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from ..config.models import PipelineConfig


class PoolManager:
    """Создаёт и управляет пулами соединений для каждого канала."""
    
    def __init__(self, config: PipelineConfig):
        self._engines: dict[str, AsyncEngine] = {}
        
        for name, ch in config.channels.items():
            self._engines[name] = create_async_engine(
                config.db_url,
                pool_size=ch.pool_size,
                max_overflow=ch.max_overflow,
                pool_recycle=config.pool_recycle,
                pool_pre_ping=config.pool_pre_ping,
                pool_timeout=config.pool_timeout,
            )
    
    def get(self, channel: str) -> AsyncEngine:
        """Возвращает движок для указанного канала."""
        return self._engines[channel]
    
    async def close_all(self):
        """Закрывает все пулы."""
        for engine in self._engines.values():
            await engine.dispose()