"""Оркестратор — фасад над pools, queues и dispatchers."""

import asyncio
import logging
import time
from ..config.models import PipelineConfig
from .pools import PoolManager
from .queues import QueueManager, SQLTask
from .dispatcher import Dispatcher
from .models import TaskResult, InfrastructureMetrics, ChannelMetrics

logger = logging.getLogger(__name__)


class Orchestrator:
    """Центральный компонент — связывает пулы, очереди и обработчики.

    Предоставляет методы:
    - execute(channel, sql, params) — выполнить SQL в указанном канале
    - read/write/admin(sql, params) — convenience методы для стандартных каналов
    - get_metrics() — метрики всех каналов
    - shutdown() — graceful shutdown
    """

    def __init__(self, config: PipelineConfig):
        self._config = config
        self._pools = PoolManager(config)
        self._queues = QueueManager(config)
        self._dispatchers: dict[str, Dispatcher] = {}
        self._start_time = 0.0

        for name, ch in config.channels.items():
            self._dispatchers[name] = Dispatcher(
                name=name,
                engine=self._pools.get(name),
                queue=self._queues.get(name),
                workers=ch.effective_workers,
            )

    async def start(self) -> None:
        self._start_time = time.time()
        for d in self._dispatchers.values():
            await d.start()
        logger.info("Оркестратор запущен с %d каналами", len(self._dispatchers))

    async def execute(self, channel: str, sql: str, params: dict = None, timeout: float = None) -> TaskResult:
        """Выполняет SQL в указанном канале.

        Args:
            channel: Имя канала (read/write/admin/...)
            sql: SQL-запрос с плейсхолдерами (:name)
            params: Параметры запроса
            timeout: Таймаут выполнения (сек). Если None — используется default_timeout из конфига.
        """
        effective_timeout = timeout if timeout is not None else self._config.default_timeout
        task = SQLTask(sql=sql, params=params, timeout=effective_timeout)
        await self._queues.put(channel, task)
        return await task.get_future()

    async def read(self, sql: str, params: dict = None, timeout: float = None) -> TaskResult:
        return await self.execute("read", sql, params, timeout)

    async def write(self, sql: str, params: dict = None, timeout: float = None) -> TaskResult:
        return await self.execute("write", sql, params, timeout)

    async def admin(self, sql: str, params: dict = None, timeout: float = None) -> TaskResult:
        return await self.execute("admin", sql, params, timeout)

    def get_metrics(self) -> InfrastructureMetrics:
        channels = {}
        total_processed = 0
        total_failed = 0
        total_queued = 0

        for name, d in self._dispatchers.items():
            q = self._queues.get(name)
            channels[name] = ChannelMetrics(
                name=name,
                queue_size=q.qsize(),
                queue_maxsize=q.maxsize,
                active_workers=d.active_count,
                pool_size=d._workers,
                tasks_processed=d.tasks_processed,
                tasks_failed=d.tasks_failed,
                avg_time_ms=d.avg_time_ms,
                last_error=d.last_error,
            )
            total_processed += d.tasks_processed
            total_failed += d.tasks_failed
            total_queued += q.qsize()

        return InfrastructureMetrics(
            channels=channels,
            uptime_seconds=time.time() - self._start_time,
            total_processed=total_processed,
            total_failed=total_failed,
            total_queued=total_queued,
            is_accepting=self._queues._accepting,
            start_time=self._start_time,
        )

    async def health_check(self) -> dict[str, bool]:
        """Проверяет работоспособность всех каналов."""
        return await self._pools.health_check()

    async def shutdown(self, timeout: float = None) -> None:
        if timeout is None:
            timeout = self._config.shutdown_timeout

        self._queues.stop_accepting()

        # Параллельный shutdown всех диспетчеров
        await asyncio.gather(*[d.shutdown(timeout) for d in self._dispatchers.values()])

        await self._pools.close_all()
        logger.info("Оркестратор остановлен")
