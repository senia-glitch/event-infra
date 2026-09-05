"""Одновременная работа всех каналов через общий router."""

import asyncio
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None
TABLE = "test_mixed"


async def test_mixed_load():
    await router.execute("admin", f'CREATE TABLE IF NOT EXISTS "{TABLE}" (id SERIAL, val INT)')

    try:
        async def reader():
            for _ in range(50):
                r = await router.execute("read", f'SELECT count(*) FROM "{TABLE}"')
                assert r.success

        async def writer():
            for i in range(50):
                r = await router.execute("write", f'INSERT INTO "{TABLE}" (val) VALUES ({i})')
                assert r.success

        async def admin():
            for _ in range(10):
                r = await router.execute("admin", "SELECT current_timestamp")
                assert r.success

        start = time.monotonic()
        await asyncio.gather(reader(), writer(), admin())
        elapsed = time.monotonic() - start
        logger.info(f"Mixed: 110 ops, {elapsed:.2f}s")

    finally:
        await router.execute("admin", f'DROP TABLE IF EXISTS "{TABLE}"')