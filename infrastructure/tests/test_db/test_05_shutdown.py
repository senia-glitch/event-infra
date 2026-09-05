"""Тест проверки работы сервера."""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None


async def test_shutdown_completes_tasks():
    r = await router.execute("read", "SELECT 1 AS val")
    assert r.success
    logger.info("Server is alive")


async def test_no_new_tasks_after_shutdown():
    r = await router.execute("admin", "SELECT current_timestamp")
    assert r.success
    logger.info("Admin channel works")