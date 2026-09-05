"""Корутины-обработчики для выполнения SQL из очереди."""

import asyncio
import time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from .queues import SQLTask
from .models import TaskResult


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
    
    async def start(self):
        self._tasks = [
            asyncio.create_task(self._run(i), name=f"disp-{self.name}-{i}")
            for i in range(self._workers)
        ]
    
    async def _run(self, index: int):
        while True:
            task = None
            try:
                task = await self._queue.get()
            except asyncio.CancelledError:
                return
            except Exception:
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
                
                future = task.get_future()
                if not future.done():
                    future.set_result(result)
                
                self._queue.task_done()
            except asyncio.CancelledError:
                return
            except Exception as e:
                self.tasks_failed += 1
                self.last_error = str(e)
                if task:
                    future = task.get_future()
                    if not future.done():
                        future.set_result(TaskResult(success=False, error_code=100, error_message=str(e)))
                    self._queue.task_done()
    
    async def _execute(self, task: SQLTask) -> TaskResult:
        try:
            coro = self._do_execute(task)
            if task.timeout:
                return await asyncio.wait_for(coro, timeout=task.timeout)
            return await coro
        except asyncio.TimeoutError:
            return TaskResult(success=False, error_code=100, error_message=f"Timeout after {task.timeout}s")
        except Exception as e:
            return TaskResult(success=False, error_code=100, error_message=str(e))
    
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
    
    async def shutdown(self, timeout: float):
        for t in self._tasks:
            t.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            pass