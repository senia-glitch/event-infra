"""Управление пулами асинхронных соединений."""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from ..config.models import PipelineConfig

logger = logging.getLogger(__name__)


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
            logger.debug(
                "Пул создан для канала '%s': pool_size=%d, max_overflow=%d",
                name,
                ch.pool_size,
                ch.max_overflow,
            )

    def get(self, channel: str) -> AsyncEngine:
        """Возвращает движок для указанного канала."""
        if channel not in self._engines:
            available = ", ".join(sorted(self._engines.keys()))
            raise ValueError(f"Канал '{channel}' не найден. Доступные каналы: {available}")
        return self._engines[channel]

    @property
    def channels(self) -> list[str]:
        """Возвращает список имён каналов."""
        return list(self._engines.keys())

    async def health_check(self) -> dict[str, bool]:
        """Проверяет работоспособность каждого канала (SELECT 1).

        Returns:
            dict: {channel_name: True/False}
        """
        results: dict[str, bool] = {}
        for name, engine in self._engines.items():
            try:
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                results[name] = True
            except Exception as e:
                logger.warning("Health check для канала '%s' провален: %s", name, e)
                results[name] = False
        return results

    async def close_all(self) -> None:
        """Закрывает все пулы."""
        for name, engine in self._engines.items():
            await engine.dispose()
            logger.debug("Пул для канала '%s' закрыт", name)
        logger.info("Все пулы соединений закрыты")
