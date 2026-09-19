"""Тесты операции list с пагинацией."""

import pytest


@pytest.mark.asyncio
async def test_list_returns_all_items(router, clean_db):
    """list() возвращает все записи."""
    await router.create("test_items", {"name": "a", "val": 1})
    await router.create("test_items", {"name": "b", "val": 2})
    await router.create("test_items", {"name": "c", "val": 3})

    result = await router.list("test_items")
    assert result.success
    assert len(result.data) == 3


@pytest.mark.asyncio
async def test_list_with_limit(router, clean_db):
    """list(limit=2) возвращает не более 2 записей."""
    await router.create("test_items", {"name": "a", "val": 1})
    await router.create("test_items", {"name": "b", "val": 2})
    await router.create("test_items", {"name": "c", "val": 3})

    result = await router.list("test_items", limit=2)
    assert result.success
    assert len(result.data) == 2


@pytest.mark.asyncio
async def test_list_with_offset(router, clean_db):
    """list(offset=1) пропускает первую запись."""
    await router.create("test_items", {"name": "a", "val": 1})
    await router.create("test_items", {"name": "b", "val": 2})
    await router.create("test_items", {"name": "c", "val": 3})

    result = await router.list("test_items", offset=1)
    assert result.success
    assert len(result.data) == 2
    assert result.data[0]["name"] == "b"


@pytest.mark.asyncio
async def test_list_with_order_by(router, clean_db):
    """list(order_by='val', order_desc=True) сортирует по убыванию."""
    await router.create("test_items", {"name": "a", "val": 3})
    await router.create("test_items", {"name": "b", "val": 1})
    await router.create("test_items", {"name": "c", "val": 2})

    result = await router.list("test_items", order_by="val", order_desc=True)
    assert result.success
    assert [r["val"] for r in result.data] == [3, 2, 1]


@pytest.mark.asyncio
async def test_list_with_filters(router, clean_db):
    """list(filters={'name': 'b'}) фильтрует по значению."""
    await router.create("test_items", {"name": "a", "val": 1})
    await router.create("test_items", {"name": "b", "val": 2})
    await router.create("test_items", {"name": "c", "val": 3})

    result = await router.list("test_items", filters={"name": "b"})
    assert result.success
    assert len(result.data) == 1
    assert result.data[0]["name"] == "b"


@pytest.mark.asyncio
async def test_list_invalid_field_returns_error(router, clean_db):
    """list(order_by='nonexistent') возвращает ошибку 422."""
    result = await router.list("test_items", order_by="nonexistent")
    assert not result.success
    assert result.error.code == 422


@pytest.mark.asyncio
async def test_list_nonexistent_entity(router, clean_db):
    """list('nonexistent') возвращает ошибку 404."""
    result = await router.list("nonexistent")
    assert not result.success
    assert result.error.code == 404


@pytest.mark.asyncio
async def test_list_empty_table(router, clean_db):
    """list() на пустой таблице возвращает пустой список."""
    result = await router.list("test_items")
    assert result.success
    assert len(result.data) == 0
