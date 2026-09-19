"""Управление очередями задач."""

import asyncio
import logging
from ..config.models import PipelineConfig

logger = logging.getLogger(__name__)


class SQLTask:
    """Задача на выполнение SQL-запроса."""

    def __init__(self, sql: str, params: dict = None, timeout: float = None):
        self.sql = sql
        self.params = params or {}
        self.timeout = timeout
        self._future: asyncio.Future | None = None

    def get_future(self) -> asyncio.Future:
        if self._future is None:
            self._future = asyncio.get_running_loop().create_future()
        return self._future


class QueueManager:
    """Управляет очередями задач для каждого канала."""

    def __init__(self, config: PipelineConfig):
        self._queues: dict[str, asyncio.Queue] = {}
        self._accepting = True

        for name, ch in config.channels.items():
            self._queues[name] = asyncio.Queue(maxsize=ch.queue_maxsize)
            logger.debug("Очередь создана для канала '%s', maxsize=%d", name, ch.queue_maxsize)

    async def put(self, channel: str, task: SQLTask) -> None:
        """Добавляет задачу в очередь канала."""
        if not self._accepting:
            raise RuntimeError(f"Канал '{channel}' завершает работу — новые задачи не принимаются")
        if channel not in self._queues:
            available = ", ".join(sorted(self._queues.keys()))
            raise ValueError(f"Канал '{channel}' не найден. Доступные каналы: {available}")
        await self._queues[channel].put(task)

    def get(self, channel: str) -> asyncio.Queue:
        """Возвращает очередь канала."""
        return self._queues[channel]

    def stop_accepting(self) -> None:
        """Прекращает приём новых задач."""
        self._accepting = False
        logger.info("Очереди: новые задачи не принимаются")
