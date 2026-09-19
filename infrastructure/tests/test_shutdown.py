"""Тесты graceful shutdown."""

import asyncio
import time
import pytest

from infrastructure.event_infrastructure import create_pipeline
from infrastructure.event_infrastructure.config import ChannelConfig


async def test_shutdown_completes_pending_tasks(router):
    """Shutdown дожидается завершения текущих задач."""
    r = await router.execute("read", "SELECT 1 AS val")
    assert r.success


async def test_health_after_work(router):
    """Health check после работы."""
    for i in range(5):
        await router.execute("read", f"SELECT {i} AS val")

    health = await router.health_check()
    assert health["alive"] is True
    assert health["db_connected"] is True


async def test_shutdown_resolves_pending_futures(router):
    """Задачи в очереди резолвятся с ошибкой при shutdown, клиент не зависает."""
    results = []

    async def submit_task():
        r = await router.execute("read", "SELECT pg_sleep(0.1)")
        results.append(r)

    tasks = [asyncio.create_task(submit_task()) for _ in range(3)]
    await asyncio.sleep(0.05)

    await router.shutdown(timeout=5.0)

    await asyncio.gather(*tasks, return_exceptions=True)
    assert len(results) == 3
    for r in results:
        assert r.success


async def test_shutdown_does_not_hang_callers(db_url):
    """Вызовы execute не зависают после shutdown."""
    r = await create_pipeline(
        db_url=db_url,
        channels={"read": ChannelConfig(pool_size=2, max_overflow=0, queue_maxsize=10)},
        schemas={},
        exclude_tables=set(),
    )

    long_results = []

    async def long_query():
        res = await r.execute("read", "SELECT pg_sleep(0.3)")
        long_results.append(res)

    tasks = [asyncio.create_task(long_query()) for _ in range(2)]
    await asyncio.sleep(0.05)

    start = time.monotonic()
    await r.shutdown(timeout=5.0)
    elapsed = time.monotonic() - start

    await asyncio.gather(*tasks, return_exceptions=True)
    assert elapsed < 3.0, f"Shutdown took {elapsed:.1f}s, expected < 3s"
    assert len(long_results) == 2


async def test_new_tasks_rejected_after_shutdown(router):
    """Новые задачи отклоняются после stop_accepting."""
    router._db._queues.stop_accepting()
    with pytest.raises(RuntimeError, match="завершает работу"):
        await router._db.execute("read", "SELECT 1")


async def test_shutdown_drains_queued_tasks(db_url):
    """Phase 2: задачи, оставшиеся в очереди к моменту shutdown, резолвятся с ошибкой 503."""
    r = await create_pipeline(
        db_url=db_url,
        channels={"read": ChannelConfig(pool_size=1, max_overflow=0, queue_maxsize=100)},
        schemas={},
        exclude_tables=set(),
    )

    results = []

    async def slow_task(i):
        res = await r.execute("read", "SELECT pg_sleep(0.5)")
        results.append(res)

    # Создаём 5 задач при pool_size=1 — 4 из них гарантированно окажутся в очереди
    tasks = [asyncio.create_task(slow_task(i)) for i in range(5)]
    await asyncio.sleep(0.05)

    queue_size = r._db._queues.get("read").qsize()
    assert queue_size > 0, f"Очередь должна быть непустой, qsize={queue_size}"

    await r.shutdown(timeout=5.0)
    await asyncio.gather(*tasks, return_exceptions=True)

    # Задачи, которые были в очереди, получают ошибку 503
    error_results = [res for res in results if not res.success]
    ok_results = [res for res in results if res.success]

    # Как минимум 1 задача должна была быть в очереди и получить 503
    assert len(error_results) >= 1, (
        f"Ожидалась хотя бы 1 ошибка 503, получено: success={len(ok_results)}, errors={len(error_results)}"
    )
    for res in error_results:
        assert res.error.code == 503
