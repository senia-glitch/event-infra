"""Тесты корректной работы default_factory в INSERT."""

import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_create_with_default_factory_inserts_value(router, clean_db):
    """Поле с default_factory должно попадать в INSERT и сохранять значение."""
    result = await router.create(
        "test_items_with_ts",
        {"name": "test", "val": 42},
    )
    assert result.success
    assert len(result.data) == 1
    row = result.data[0]
    assert row["name"] == "test"
    assert row["val"] == 42
    assert row["created_at"] is not None
    assert isinstance(row["created_at"], datetime)


@pytest.mark.asyncio
async def test_create_with_explicit_default_factory_field(router, clean_db):
    """Явно переданное значение default_factory поля должно использоваться."""
    explicit_time = datetime(2025, 6, 15, 12, 0, 0)
    result = await router.create(
        "test_items_with_ts",
        {"name": "explicit", "val": 1, "created_at": explicit_time},
    )
    assert result.success
    row = result.data[0]
    assert row["created_at"] == explicit_time


@pytest.mark.asyncio
async def test_read_after_create_with_default_factory(router, clean_db):
    """Read должен возвращать созданное значение, а не NULL."""
    create_result = await router.create(
        "test_items_with_ts",
        {"name": "readback", "val": 7},
    )
    assert create_result.success
    item_id = create_result.data[0]["id"]

    read_result = await router.read("test_items_with_ts", item_id)
    assert read_result.success
    assert read_result.data[0]["created_at"] is not None
    assert isinstance(read_result.data[0]["created_at"], datetime)
