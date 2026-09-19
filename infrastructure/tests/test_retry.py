"""Тесты корректного поведения retry при timeout."""

from unittest.mock import patch, MagicMock

import pytest

from infrastructure.event_infrastructure.config.models import RetryConfig


@pytest.mark.asyncio
async def test_read_retries_on_timeout(router, clean_db):
    """read() должен повторять попытку при timeout (идемпотентная операция)."""
    call_count = 0
    original_execute = router._db.execute

    async def mock_execute(channel, sql, params=None, timeout=None):
        nonlocal call_count
        if "SELECT" in sql and "test_roles" in sql:
            call_count += 1
            if call_count == 1:
                return MagicMock(success=False, error_code=408, error_message="Timeout after 30s")
        return await original_execute(channel, sql, params, timeout)

    with patch.object(router._db, "execute", side_effect=mock_execute):
        role = await router.create("test_roles", {"name": "retry_test"})
        assert role.success
        item_id = role.data[0]["id"]

        read_result = await router.read("test_roles", item_id)
        assert read_result.success
        assert call_count == 2


@pytest.mark.asyncio
async def test_create_does_not_retry_on_timeout(router, clean_db):
    """create() НЕ должен повторять попытку при timeout (неидемпотентная операция)."""
    call_count = 0
    original_execute = router._db.execute

    async def mock_execute(channel, sql, params=None, timeout=None):
        nonlocal call_count
        if "INSERT" in sql:
            call_count += 1
            if call_count == 1:
                return MagicMock(success=False, error_code=408, error_message="Timeout after 30s")
        return await original_execute(channel, sql, params, timeout)

    with patch.object(router._db, "execute", side_effect=mock_execute):
        result = await router.create("test_roles", {"name": "no_retry_test"})
        assert not result.success
        assert result.error.code == 408
        assert call_count == 1


@pytest.mark.asyncio
async def test_custom_does_not_retry_on_timeout(router, clean_db):
    """custom() НЕ должен повторять попытку при timeout (неизвестная идемпотентность)."""
    call_count = 0
    original_execute = router._db.execute

    async def mock_execute(channel, sql, params=None, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MagicMock(success=False, error_code=408, error_message="Timeout after 30s")
        return await original_execute(channel, sql, params, timeout)

    with patch.object(router._db, "execute", side_effect=mock_execute):
        result = await router.custom("SELECT 1")
        assert not result.success
        assert result.error.code == 408
        assert call_count == 1


@pytest.mark.asyncio
async def test_retry_on_timeout_disabled_by_default():
    """По умолчанию retry_on_timeout=False — timeout НЕ ретраится."""
    rc = RetryConfig()
    assert rc.retry_on_timeout is False


@pytest.mark.asyncio
async def test_retry_on_timeout_configurable():
    """retry_on_timeout можно включить через конфиг."""
    rc = RetryConfig(retry_on_timeout=True)
    assert rc.retry_on_timeout is True
