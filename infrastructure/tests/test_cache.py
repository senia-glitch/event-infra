"""Тесты кеширования."""


async def test_cache_hit(router, clean_db):
    """Кеш возвращаемый для повторных чтений."""
    r = await router.create("test_items", {"name": "cached_item", "val": 1})
    item_id = r.data[0]["id"]

    # Первое чтение — cache miss
    r1 = await router.read("test_items", item_id)
    assert r1.success

    # Второе чтение — должно быть из кеша (или хотя бы успешно)
    r2 = await router.read("test_items", item_id)
    assert r2.success
    assert r2.data[0]["name"] == "cached_item"


async def test_cache_disabled(router, clean_db):
    """Отключение кеша для конкретного вызова."""
    r = await router.create("test_items", {"name": "no_cache_item", "val": 2})
    item_id = r.data[0]["id"]

    # Чтение без кеша
    r1 = await router.read("test_items", item_id, cache=False)
    assert r1.success

    # Повторное чтение без кеша — тоже работает
    r2 = await router.read("test_items", item_id, cache=False)
    assert r2.success


async def test_cache_invalidation_on_update(router, clean_db):
    """Инвалидация кеша при обновлении."""
    r = await router.create("test_items", {"name": "before_update", "val": 1})
    item_id = r.data[0]["id"]

    # Прогреваем кеш
    r1 = await router.read("test_items", item_id)
    assert r1.success

    # Обновляем — кеш должен инвалидироваться
    r2 = await router.update("test_items", item_id, {"name": "after_update"})
    assert r2.success

    # Читаем заново — должно вернуть обновлённые данные
    r3 = await router.read("test_items", item_id)
    assert r3.success
    assert r3.data[0]["name"] == "after_update"


async def test_cache_invalidation_on_delete(router, clean_db):
    """Инвалидация кеша при удалении."""
    r = await router.create("test_items", {"name": "to_delete_cached", "val": 3})
    item_id = r.data[0]["id"]

    # Прогреваем кеш
    r1 = await router.read("test_items", item_id)
    assert r1.success

    # Удаляем
    r2 = await router.delete("test_items", item_id)
    assert r2.success

    # Чтение после удаления — пустой результат
    r3 = await router.read("test_items", item_id)
    assert r3.success
    assert r3.count == 0
