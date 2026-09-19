"""Тесты поведения create_pipeline при channels=None и channels={}."""

import pytest

from infrastructure.event_infrastructure.pipeline import create_pipeline


@pytest.mark.asyncio
async def test_create_pipeline_channels_none_uses_defaults(db_url):
    """create_pipeline(channels=None) должен использовать дефолтные каналы."""
    router = await create_pipeline(
        db_url=db_url,
        channels=None,
        schemas={},
        exclude_tables={"alembic_version"},
    )
    try:
        assert router.has_entity("nonexistent") is False
        health = await router.health_check()
        assert health["alive"]
        assert "read" in health["channels"]
        assert "write" in health["channels"]
        assert "admin" in health["channels"]
    finally:
        await router.shutdown()


@pytest.mark.asyncio
async def test_create_pipeline_empty_channels_raises(db_url):
    """create_pipeline(channels={}) должен выбросить ValueError."""
    with pytest.raises(ValueError, match="channels не может быть пустым"):
        await create_pipeline(
            db_url=db_url,
            channels={},
            schemas={},
        )
