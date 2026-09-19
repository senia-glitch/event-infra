"""Корутины-обработчики для выполнения SQL из очереди."""

import asyncio
import logging
import time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from .queues import SQLTask
from .models import TaskResult

logger = logging.getLogger(__name__)


class Dispatcher:
    """Запускает N корутин-обработчиков для одного канала."""

    def __init__(self, name: str, engine: AsyncEngine, queue: asyncio.Queue, workers: int):
        self.name = name
        self._engine = engine
        self._queue = queue
        self._workers = workers
        self._tasks: list[asyncio.Task] = []

        self.tasks_processed = 0
        self.tasks_failed = 0
        self._total_time = 0.0
        self.last_error = ""

    async def start(self) -> None:
        self._tasks = [asyncio.create_task(self._run(i), name=f"disp-{self.name}-{i}") for i in range(self._workers)]
        logger.info("Диспетчер '%s': запущено %d воркеров", self.name, self._workers)

    async def _run(self, index: int) -> None:
        while True:
            task = None
            try:
                task = await self._queue.get()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Dispatcher '%s' worker %d: ошибка при получении задачи из очереди", self.name, index)
                continue

            try:
                t0 = time.monotonic()
                result = await self._execute(task)
                dt = time.monotonic() - t0

                self.tasks_processed += 1
                self._total_time += dt

                if not result.success:
                    self.tasks_failed += 1
                    self.last_error = result.error_message
                    logger.warning(
                        "Dispatcher '%s': задача провалилась (%.1fмс): %s",
                        self.name,
                        dt * 1000,
                        result.error_message,
                    )

                future = task.get_future()
                if not future.done():
                    future.set_result(result)

                self._queue.task_done()
            except asyncio.CancelledError:
                future = task.get_future()
                if not future.done():
                    future.set_result(
                        TaskResult(
                            success=False,
                            error_code=503,
                            error_message="Shutdown: задача отменена при завершении работы",
                        )
                    )
                self._queue.task_done()
                return
            except Exception as e:
                self.tasks_failed += 1
                self.last_error = str(e)
                logger.exception(
                    "Dispatcher '%s': необработанное исключение в worker %d: %s",
                    self.name,
                    index,
                    e,
                )
                if task:
                    future = task.get_future()
                    if not future.done():
                        future.set_result(TaskResult(success=False, error_code=500, error_message=str(e)))
                    self._queue.task_done()

    async def _execute(self, task: SQLTask) -> TaskResult:
        try:
            coro = self._do_execute(task)
            if task.timeout:
                return await asyncio.wait_for(coro, timeout=task.timeout)
            return await coro
        except asyncio.TimeoutError:
            return TaskResult(success=False, error_code=408, error_message=f"Timeout after {task.timeout}s")
        except Exception as e:
            return TaskResult(success=False, error_code=500, error_message=str(e))

    async def _do_execute(self, task: SQLTask) -> TaskResult:
        async with self._engine.begin() as conn:
            result = await conn.execute(text(task.sql), task.params)
            if result.returns_rows:
                rows = result.fetchall()
                return TaskResult(success=True, data=rows)
            return TaskResult(success=True)

    @property
    def avg_time_ms(self) -> float:
        if self.tasks_processed == 0:
            return 0.0
        return (self._total_time / self.tasks_processed) * 1000

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tasks if not t.done())

    async def shutdown(self, timeout: float) -> None:
        drain_timeout = timeout * 0.5
        cancel_timeout = timeout - drain_timeout

        # Phase 1: drain — ждём пока очередь опустеет
        try:
            await asyncio.wait_for(self._queue.join(), timeout=drain_timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "Диспетчер '%s': drain завершился по таймауту через %.1fs (в очереди %d задач)",
                self.name,
                drain_timeout,
                self._queue.qsize(),
            )

        # Phase 2: resolve futures для задач, которые остались в очереди
        drained = 0
        while not self._queue.empty():
            try:
                task = self._queue.get_nowait()
                future = task.get_future()
                if not future.done():
                    future.set_result(
                        TaskResult(
                            success=False,
                            error_code=503,
                            error_message="Shutdown: задача не была обработана",
                        )
                    )
                self._queue.task_done()
                drained += 1
            except asyncio.QueueEmpty:
                break
        if drained:
            logger.info("Диспетчер '%s': resolved %d задач из очереди с ошибкой shutdown", self.name, drained)

        # Phase 3: cancel воркеров и ждём завершения
        for t in self._tasks:
            if not t.done():
                t.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True),
                timeout=cancel_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Диспетчер '%s': отмена завершилась по таймауту через %.1fs", self.name, cancel_timeout)
        except asyncio.CancelledError:
            pass

        logger.info(
            "Диспетчер '%s': остановлен (обработано=%d, ошибок=%d)", self.name, self.tasks_processed, self.tasks_failed
        )
