"""Тест обработки ошибок через общий router."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None


async def test_errors():
    r = await router.execute("read", "SELEC 1")
    assert not r.success
    logger.info(f"Syntax error caught: {r.error.message[:50]}...")

    r = await router.execute("read", "SELECT * FROM nonexistent_table_12345")
    assert not r.success
    logger.info(f"Missing table caught: {r.error.message[:50]}...")

    r = await router.execute("read", "SELECT 1 AS recovery")
    assert r.success
    logger.info("Recovery OK")

    async def bad():
        return await router.execute("read", "BAD SQL")

    async def good():
        return await router.execute("read", "SELECT 2 AS ok")

    results = await asyncio.gather(*([bad() for _ in range(10)] + [good() for _ in range(10)]))
    bad_ok = sum(1 for r in results[:10] if not r.success)
    good_ok = sum(1 for r in results[10:] if r.success)

    assert bad_ok == 10
    assert good_ok == 10
    logger.info(f"Mixed errors: {bad_ok} bad, {good_ok} good")