"""Unit-тесты для pipeline и config."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from infrastructure.event_infrastructure.pipeline import create_pipeline, shutdown_pipeline
from infrastructure.event_infrastructure.config.models import (
    ChannelConfig,
    RetryConfig,
    CacheConfig,
    PipelineConfig,
)


class TestPipeline:
    @pytest.mark.asyncio
    async def test_create_pipeline(self):
        with patch("infrastructure.event_infrastructure.pipeline.Orchestrator") as MockOrch:
            mock_orch = MagicMock()
            mock_orch.start = AsyncMock()
            MockOrch.return_value = mock_orch
            await create_pipeline(
                db_url="postgresql+asyncpg://test",
                schemas={},
            )
            mock_orch.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_pipeline_empty_channels_raises(self):
        with pytest.raises(ValueError, match="не может быть пустым"):
            await create_pipeline(
                db_url="postgresql+asyncpg://test",
                channels={},
            )

    @pytest.mark.asyncio
    async def test_shutdown_pipeline(self):
        with patch("infrastructure.event_infrastructure.pipeline.Orchestrator") as MockOrch:
            mock_orch = MagicMock()
            mock_orch.start = AsyncMock()
            mock_orch.shutdown = AsyncMock()
            MockOrch.return_value = mock_orch
            router = await create_pipeline(
                db_url="postgresql+asyncpg://test",
                schemas={},
            )
            await shutdown_pipeline(router, timeout=5.0)
            mock_orch.shutdown.assert_called_once_with(5.0)

    @pytest.mark.asyncio
    async def test_create_pipeline_default_channels(self):
        with patch("infrastructure.event_infrastructure.pipeline.Orchestrator") as MockOrch:
            mock_orch = MagicMock()
            mock_orch.start = AsyncMock()
            MockOrch.return_value = mock_orch
            await create_pipeline(
                db_url="postgresql+asyncpg://test",
                schemas={},
            )
            config = MockOrch.call_args[0][0]
            assert "read" in config.channels
            assert "write" in config.channels
            assert "admin" in config.channels

    @pytest.mark.asyncio
    async def test_create_pipeline_custom_retry(self):
        with patch("infrastructure.event_infrastructure.pipeline.Orchestrator") as MockOrch:
            mock_orch = MagicMock()
            mock_orch.start = AsyncMock()
            MockOrch.return_value = mock_orch
            retry = RetryConfig(max_retries=5)
            router = await create_pipeline(
                db_url="postgresql+asyncpg://test",
                schemas={},
                retry=retry,
            )
            assert router._retry.max_retries == 5

    @pytest.mark.asyncio
    async def test_create_pipeline_custom_cache(self):
        with patch("infrastructure.event_infrastructure.pipeline.Orchestrator") as MockOrch:
            mock_orch = MagicMock()
            mock_orch.start = AsyncMock()
            MockOrch.return_value = mock_orch
            cache = CacheConfig(enabled=True, ttl_seconds=30.0, max_size=500)
            router = await create_pipeline(
                db_url="postgresql+asyncpg://test",
                schemas={},
                cache=cache,
            )
            assert router._cache is not None


class TestChannelConfig:
    def test_defaults(self):
        c = ChannelConfig()
        assert c.pool_size == 10
        assert c.max_overflow == 5
        assert c.queue_maxsize == 1000
        assert c.workers == 0

    def test_effective_workers_default(self):
        c = ChannelConfig(pool_size=8)
        assert c.effective_workers == 8

    def test_effective_workers_explicit(self):
        c = ChannelConfig(pool_size=8, workers=3)
        assert c.effective_workers == 3

    def test_negative_pool_size(self):
        with pytest.raises(ValueError, match="pool_size"):
            ChannelConfig(pool_size=-1)

    def test_negative_max_overflow(self):
        with pytest.raises(ValueError, match="max_overflow"):
            ChannelConfig(max_overflow=-1)

    def test_zero_queue_maxsize(self):
        with pytest.raises(ValueError, match="queue_maxsize"):
            ChannelConfig(queue_maxsize=0)

    def test_negative_workers(self):
        with pytest.raises(ValueError, match="workers"):
            ChannelConfig(workers=-1)


class TestRetryConfig:
    def test_defaults(self):
        c = RetryConfig()
        assert c.max_retries == 3
        assert c.delay_seconds == 0.5
        assert c.backoff_multiplier == 2.0
        assert c.max_total_timeout == 0.0
        assert c.retry_on_timeout is False

    def test_negative_max_retries(self):
        with pytest.raises(ValueError, match="max_retries"):
            RetryConfig(max_retries=-1)

    def test_negative_delay(self):
        with pytest.raises(ValueError, match="delay_seconds"):
            RetryConfig(delay_seconds=-1)

    def test_backoff_too_low(self):
        with pytest.raises(ValueError, match="backoff_multiplier"):
            RetryConfig(backoff_multiplier=0.5)

    def test_negative_total_timeout(self):
        with pytest.raises(ValueError, match="max_total_timeout"):
            RetryConfig(max_total_timeout=-1)


class TestCacheConfig:
    def test_defaults(self):
        c = CacheConfig()
        assert c.enabled is False
        assert c.ttl_seconds == 60.0
        assert c.max_size == 1000

    def test_negative_ttl(self):
        with pytest.raises(ValueError, match="ttl_seconds"):
            CacheConfig(ttl_seconds=-1)

    def test_zero_max_size(self):
        with pytest.raises(ValueError, match="max_size"):
            CacheConfig(max_size=0)


class TestPipelineConfig:
    def test_empty_db_url(self):
        with pytest.raises(ValueError, match="db_url"):
            PipelineConfig(db_url="")

    def test_defaults(self):
        c = PipelineConfig(db_url="postgresql+asyncpg://test")
        assert c.pool_recycle == 3600
        assert c.pool_pre_ping is True
        assert c.pool_timeout == 30
        assert c.default_timeout == 30.0
        assert c.max_concurrency == 200
        assert c.shutdown_timeout == 10.0

    def test_negative_pool_recycle(self):
        with pytest.raises(ValueError, match="pool_recycle"):
            PipelineConfig(db_url="test", pool_recycle=-1)

    def test_negative_pool_timeout(self):
        with pytest.raises(ValueError, match="pool_timeout"):
            PipelineConfig(db_url="test", pool_timeout=-1)

    def test_negative_default_timeout(self):
        with pytest.raises(ValueError, match="default_timeout"):
            PipelineConfig(db_url="test", default_timeout=-1)

    def test_negative_max_concurrency(self):
        with pytest.raises(ValueError, match="max_concurrency"):
            PipelineConfig(db_url="test", max_concurrency=-1)

    def test_negative_shutdown_timeout(self):
        with pytest.raises(ValueError, match="shutdown_timeout"):
            PipelineConfig(db_url="test", shutdown_timeout=-1)
