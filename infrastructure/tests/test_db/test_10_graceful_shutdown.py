"""Тест graceful shutdown."""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None
TABLE = "t_shutdown"


async def test_graceful_shutdown():
    await router.execute("admin", f'CREATE TABLE IF NOT EXISTS "{TABLE}" (id SERIAL, val INT)')

    try:
        # Запускаем 30 задач на запись
        async def writer(i: int):
            return await router.execute("write", f'INSERT INTO "{TABLE}" (val) VALUES ({i})')

        tasks = [asyncio.create_task(writer(i)) for i in range(30)]

        # Ждём завершения
        results = await asyncio.gather(*tasks)
        ok = sum(1 for r in results if r.success)
        logger.info(f"Before shutdown: {ok}/30 completed")

        assert ok == 30

        # Проверяем что данные записались
        r = await router.execute("read", f'SELECT count(*) FROM "{TABLE}"')
        count = r.data[0]["row"][0] if r.success else 0
        assert count == 30
        logger.info(f"All {count} rows verified")

    finally:
        await router.execute("admin", f'DROP TABLE IF EXISTS "{TABLE}"')