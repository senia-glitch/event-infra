"""Тест граничных случаев."""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None
TABLE = "t_edge"


async def test_edge_cases():
    await router.execute("admin", f'CREATE TABLE IF NOT EXISTS "{TABLE}" (id SERIAL, val INT, name VARCHAR(100))')

    try:
        # Пустой SELECT
        r = await router.execute("read", f'SELECT * FROM "{TABLE}"')
        assert r.success
        assert r.count == 0
        logger.info("Empty SELECT: OK")

        # INSERT с NULL
        r = await router.execute("write", f'INSERT INTO "{TABLE}" (val, name) VALUES (1, NULL)')
        assert r.success
        logger.info("INSERT with NULL: OK")

        # SELECT несуществующей записи
        r = await router.execute("read", f'SELECT * FROM "{TABLE}" WHERE id = 99999')
        assert r.success
        assert r.count == 0
        logger.info("SELECT non-existent: OK")

        # UPDATE несуществующей записи
        r = await router.execute("write", f'UPDATE "{TABLE}" SET val = 999 WHERE id = 99999')
        assert r.success
        logger.info("UPDATE non-existent: OK")

        # DELETE несуществующей записи
        r = await router.execute("write", f'DELETE FROM "{TABLE}" WHERE id = 99999')
        assert r.success
        logger.info("DELETE non-existent: OK")

        # Пустая строка
        r = await router.execute("write", f"INSERT INTO \"{TABLE}\" (val, name) VALUES (0, '')")
        assert r.success
        logger.info("INSERT empty string: OK")

        # Очень длинная строка
        long_name = "x" * 100
        r = await router.execute("write", f"INSERT INTO \"{TABLE}\" (val, name) VALUES (99, :name)", {"name": long_name})
        assert r.success
        logger.info("INSERT long string: OK")

        # Спецсимволы
        r = await router.execute("write", f"INSERT INTO \"{TABLE}\" (val, name) VALUES (42, :name)", {"name": "O'Brien"})
        assert r.success
        logger.info("INSERT special chars: OK")

    finally:
        await router.execute("admin", f'DROP TABLE IF EXISTS "{TABLE}"')