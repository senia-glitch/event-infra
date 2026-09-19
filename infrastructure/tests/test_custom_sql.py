"""Тесты произвольных SQL-запросов."""


async def test_custom_select(router, clean_db):
    """Произвольный SELECT."""
    await router.create("test_items", {"name": "alpha", "val": 10})
    await router.create("test_items", {"name": "beta", "val": 20})

    r = await router.custom('SELECT * FROM "test_items" WHERE val > :min_val', {"min_val": 5}, channel="read")
    assert r.success
    assert r.count == 2


async def test_custom_insert_returning(router, clean_db):
    """INSERT с RETURNING."""
    r = await router.custom(
        'INSERT INTO "test_items" (name, val) VALUES (:name, :val) RETURNING id, name',
        {"name": "custom_item", "val": 42},
        channel="write",
    )
    assert r.success
    assert r.count == 1


async def test_custom_aggregate(router, clean_db):
    """Агрегатная функция."""
    await router.create("test_items", {"name": "a", "val": 1})
    await router.create("test_items", {"name": "b", "val": 2})
    await router.create("test_items", {"name": "c", "val": 3})

    r = await router.custom('SELECT SUM(val) as total FROM "test_items"', channel="read")
    assert r.success
    assert r.data[0]["row"][0] == 6


async def test_custom_syntax_error(router):
    """Синтаксическая ошибка в SQL."""
    r = await router.custom("SELEC 1", channel="read")
    assert not r.success
    assert r.error.code in (400, 500)


async def test_custom_nonexistent_table(router):
    """Обращение к несуществующей таблице."""
    r = await router.custom("SELECT * FROM nonexistent_table_xyz", channel="read")
    assert not r.success


async def test_execute_read_channel(router):
    """execute() через канал read."""
    r = await router.execute("read", "SELECT 1 AS val")
    assert r.success


async def test_execute_write_channel(router):
    """execute() через канал write."""
    r = await router.execute("write", "SELECT 1 AS val")
    assert r.success
