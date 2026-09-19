"""Тест подключения и базовых операций."""

import pytest


async def test_connection_read(router):
    """Проверка подключения через канал read."""
    r = await router.execute("read", "SELECT 1 AS val")
    assert r.success, f"Read failed: {r.error}"


async def test_connection_write(router):
    """Проверка подключения через канал write."""
    r = await router.execute("write", "SELECT 1 AS val")
    assert r.success, f"Write failed: {r.error}"


async def test_connection_admin(router):
    """Проверка подключения через канал admin."""
    r = await router.execute("admin", "SELECT 1 AS val")
    assert r.success, f"Admin failed: {r.error}"


async def test_invalid_channel_raises(router):
    """Попытка использовать несуществующий канал."""
    with pytest.raises((ValueError, KeyError)):
        await router.execute("nonexistent", "SELECT 1")


async def test_health_check(router):
    """Проверка health check."""
    health = await router.health_check()
    assert health["alive"] is True
    assert health["db_connected"] is True
    assert "pools" in health


async def test_is_alive(router):
    """Проверка is_alive."""
    alive = await router.is_alive()
    assert alive is True
