"""Тесты поддержки кастомных primary key."""

import pytest


@pytest.mark.asyncio
async def test_create_with_custom_pk(router, clean_db):
    """Создание записи с кастомным primary key (uuid)."""
    result = await router.create("test_custom_pk", {"uuid": "abc-123", "label": "test"})
    assert result.success
    assert result.data[0]["uuid"] == "abc-123"
    assert result.data[0]["label"] == "test"


@pytest.mark.asyncio
async def test_read_with_custom_pk(router, clean_db):
    """Чтение записи по кастомному primary key."""
    await router.create("test_custom_pk", {"uuid": "read-001", "label": "readable"})
    result = await router.read("test_custom_pk", "read-001")
    assert result.success
    assert result.data[0]["uuid"] == "read-001"


@pytest.mark.asyncio
async def test_update_with_custom_pk(router, clean_db):
    """Обновление записи с кастомным primary key."""
    await router.create("test_custom_pk", {"uuid": "upd-001", "label": "old"})
    result = await router.update("test_custom_pk", "upd-001", {"label": "new"})
    assert result.success
    assert result.data[0]["label"] == "new"


@pytest.mark.asyncio
async def test_delete_with_custom_pk(router, clean_db):
    """Удаление записи с кастомным primary key."""
    await router.create("test_custom_pk", {"uuid": "del-001", "label": "doomed"})
    result = await router.delete("test_custom_pk", "del-001")
    assert result.success
    assert result.data[0]["uuid"] == "del-001"

    read_result = await router.read("test_custom_pk", "del-001")
    assert read_result.success
    assert len(read_result.data) == 0


@pytest.mark.asyncio
async def test_list_with_custom_pk(router, clean_db):
    """Получение списка с кастомным primary key."""
    await router.create("test_custom_pk", {"uuid": "list-001", "label": "a"})
    await router.create("test_custom_pk", {"uuid": "list-002", "label": "b"})

    result = await router.list("test_custom_pk")
    assert result.success
    assert len(result.data) == 2
