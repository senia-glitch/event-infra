"""Тест нагрузки на чтение и запись через общий router."""

import asyncio
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None
TABLE = "test_rw"


async def test_read_write_load():
    r = await router.execute("admin", f'CREATE TABLE IF NOT EXISTS "{TABLE}" (id SERIAL, val INT)')
    assert r.success, f"Create failed: {r.error}"
    logger.info("Table created")

    try:
        for i in range(100):
            r = await router.execute("write", f'INSERT INTO "{TABLE}" (val) VALUES ({i})')
            assert r.success
        logger.info("Inserted 100 rows")

        async def read_one():
            return await router.execute("read", f'SELECT count(*) FROM "{TABLE}"')

        start = time.monotonic()
        tasks = [read_one() for _ in range(100)]
        results = await asyncio.gather(*tasks)
        elapsed = time.monotonic() - start

        success = sum(1 for r in results if r.success)
        ops = 100 / elapsed if elapsed > 0 else 0
        logger.info(f"Read: {success}/100, {elapsed:.2f}s, {ops:.0f} ops/sec")
        assert success == 100

    finally:
        await router.execute("admin", f'DROP TABLE IF EXISTS "{TABLE}"')
        logger.info("Cleanup done")