"""Проверка подключения всех каналов через общий router."""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None  # Устанавливается из run_server.py


async def test_connection():
    r = await router.execute("read", "SELECT 1 AS val")
    assert r.success, f"Read failed: {r.error}"
    logger.info("Read OK")

    r = await router.execute("write", "SELECT 1 AS val")
    assert r.success, f"Write failed: {r.error}"
    logger.info("Write OK")

    r = await router.execute("admin", "SELECT version()")
    assert r.success, f"Admin failed: {r.error}"
    logger.info("Admin OK")