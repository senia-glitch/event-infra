"""Корутины-обработчики для выполнения SQL из очереди."""

import asyncio
import logging
import time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.exc import (
    IntegrityError,
    DataError,
    OperationalError,
    ProgrammingError,
    InterfaceError,
    DBAPIError,
)
from .queues import SQLTask
from .models import TaskResult

logger = logging.getLogger(__name__)

_ERROR_TYPE_MAP: dict[type, tuple[str, int]] = {
    IntegrityError: ("database_error", 500),
    DataError: ("data_error", 422),
    OperationalError: ("connection_error", 503),
    ProgrammingError: ("database_error", 500),
    InterfaceError: ("connection_error", 503),
}


def _classify_db_error(exc: Exception) -> tuple[str, int, int]:
    """Классифицирует ошибку БД и возвращает (error_type, error_code, http_status).

    error_type — строковый тип для Response.error.type (unique_constraint, foreign_key, и т.д.)
    error_code — код ошибки для Response.error.code
    http_status — HTTP-статус для Response.error.code
    """
    if isinstance(exc, IntegrityError):
        msg = str(exc).lower()
        if "unique" in msg or "duplicate" in msg:
            return ("unique_constraint", 409, 409)
        if "foreign key" in msg or "referential" in msg:
            return ("foreign_key", 422, 422)
        if "check" in msg or "not null" in msg:
            return ("check_violation", 422, 422)
        return ("integrity_error", 422, 422)

    if isinstance(exc, DataError):
        return ("data_error", 422, 422)

    if isinstance(exc, OperationalError):
        msg = str(exc).lower()
        if "timeout" in msg or "timed out" in msg:
            return ("query_timeout", 408, 408)
        if "connection" in msg or "could not connect" in msg or "pool" in msg:
            return ("connection_error", 503, 503)
        return ("operational_error", 500, 500)

    if isinstance(exc, InterfaceError):
        return ("connection_error", 503, 503)

    if isinstance(exc, ProgrammingError):
        return ("syntax_error", 400, 400)

    if isinstance(exc, DBAPIError):
        msg = str(exc).lower()
        if "timeout" in msg or "timed out" in msg:
            return ("query_timeout", 408, 408)
        if "connection" in msg:
            return ("connection_error", 503, 503)
        return ("database_error", 500, 500)

    return ("unknown_error", 500, 500)


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
            finally:
                self._queue.task_done()

    async def _execute(self, task: SQLTask) -> TaskResult:
        try:
            coro = self._do_execute(task)
            if task.timeout:
                return await asyncio.wait_for(coro, timeout=task.timeout)
            return await coro
        except asyncio.TimeoutError:
            return TaskResult(
                success=False,
                error_code=408,
                error_message=f"Timeout after {task.timeout}s",
                error_type="query_timeout",
            )
        except Exception as e:
            error_type, error_code, _ = _classify_db_error(e)
            return TaskResult(
                success=False,
                error_code=error_code,
                error_message=str(e),
                error_type=error_type,
            )

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
