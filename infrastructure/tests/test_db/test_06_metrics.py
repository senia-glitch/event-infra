"""Тест метрик через общий router."""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None


async def test_metrics():
    for _ in range(10):
        await router.execute("read", "SELECT 1")
    for _ in range(5):
        await router.execute("write", "SELECT 1")
    await router.execute("read", "SELEC 1")

    m = router.get_metrics()

    logger.info(f"Processed: {m.total_processed}")
    logger.info(f"Failed: {m.total_failed}")
    for name, ch in m.channels.items():
        logger.info(f"  {name}: done={ch.tasks_processed} err={ch.tasks_failed}")

    assert m.total_processed > 0
    assert m.total_failed >= 1
    assert m.is_accepting is True