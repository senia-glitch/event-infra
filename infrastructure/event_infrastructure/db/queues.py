"""Управление очередями задач."""

import asyncio
from ..config.models import PipelineConfig


class SQLTask:
    """Задача на выполнение SQL-запроса."""
    
    def __init__(self, sql: str, params: dict = None, timeout: float = None):
        self.sql = sql
        self.params = params or {}
        self.timeout = timeout
        self._future = asyncio.get_event_loop().create_future()
    
    def get_future(self) -> asyncio.Future:
        return self._future


class QueueManager:
    """Управляет очередями задач для каждого канала."""
    
    def __init__(self, config: PipelineConfig):
        self._queues: dict[str, asyncio.Queue] = {}
        self._accepting = True
        
        for name, ch in config.channels.items():
            self._queues[name] = asyncio.Queue(maxsize=ch.queue_maxsize)
    
    async def put(self, channel: str, task: SQLTask):
        """Добавляет задачу в очередь канала."""
        if not self._accepting:
            raise RuntimeError(f"Channel '{channel}' is shutting down")
        await self._queues[channel].put(task)
    
    def get(self, channel: str) -> asyncio.Queue:
        """Возвращает очередь канала."""
        return self._queues[channel]
    
    def stop_accepting(self):
        """Прекращает приём новых задач."""
        self._accepting = False