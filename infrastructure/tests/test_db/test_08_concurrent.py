"""Тест конкурентного доступа."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None
TABLE = "t_concurrent"


async def test_concurrent():
    await router.execute("admin", f'CREATE TABLE IF NOT EXISTS "{TABLE}" (id SERIAL, val INT)')

    try:
        async def writer(i: int):
            r = await router.execute("write", f'INSERT INTO "{TABLE}" (val) VALUES ({i})')
            return r.success

        # 50 конкурентных вставок
        tasks = [writer(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        ok = sum(1 for r in results if r)

        # Проверяем что все 50 записались
        r = await router.execute("read", f'SELECT count(*) FROM "{TABLE}"')
        count = r.data[0]["row"][0] if r.success else 0

        logger.info(f"Concurrent insert: {ok}/50 success, {count} rows in table")
        assert ok == 50
        assert count == 50

    finally:
        await router.execute("admin", f'DROP TABLE IF EXISTS "{TABLE}"')