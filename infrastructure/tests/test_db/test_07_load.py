"""Нагрузочный тест."""

import asyncio
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None
TABLE = "t_load"
OPS = 1000


async def test_load():
    await router.execute("admin", f'CREATE TABLE IF NOT EXISTS "{TABLE}" (id SERIAL, val INT)')
    logger.info(f"Table {TABLE} created, running {OPS} ops...")

    try:
        results = {"ok": 0, "fail": 0}

        async def do(op: str, i: int):
            try:
                if op == "r":
                    r = await router.execute("read", f"SELECT 1 WHERE {i} > 0")
                elif op == "w":
                    r = await router.execute("write", f'INSERT INTO "{TABLE}" (val) VALUES ({i % 1000})')
                else:
                    r = await router.execute("admin", "SELECT 1")
                return r.success
            except Exception:
                return False

        start = time.monotonic()
        batch = []
        for i in range(OPS):
            if i % 10 < 6:
                batch.append(asyncio.create_task(do("r", i)))
            elif i % 10 < 9:
                batch.append(asyncio.create_task(do("w", i)))
            else:
                batch.append(asyncio.create_task(do("a", i)))

        ok_list = await asyncio.gather(*batch)
        results["ok"] = sum(1 for ok in ok_list if ok)
        results["fail"] = sum(1 for ok in ok_list if not ok)

        elapsed = time.monotonic() - start
        throughput = OPS / elapsed if elapsed > 0 else 0

        r = await router.execute("read", f'SELECT count(*) FROM "{TABLE}"')
        rows = r.data[0]["row"][0] if r.success else 0

        logger.info(f"Load: {OPS} ops, {elapsed:.1f}s, {throughput:.0f} ops/sec, {rows} rows in DB")
        logger.info(f"OK: {results['ok']}, FAIL: {results['fail']}")

    finally:
        await router.execute("admin", f'DROP TABLE IF EXISTS "{TABLE}"')
        logger.info(f"Table {TABLE} dropped")