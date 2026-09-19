"""Тесты конфигурации данных (config models)."""

import pytest
from infrastructure.event_infrastructure.config.models import (
    ChannelConfig,
    RetryConfig,
    CacheConfig,
    PipelineConfig,
)


class TestChannelConfig:
    def test_defaults(self):
        cfg = ChannelConfig()
        assert cfg.pool_size == 10
        assert cfg.max_overflow == 5
        assert cfg.queue_maxsize == 1000
        assert cfg.workers == 0

    def test_effective_workers_default(self):
        cfg = ChannelConfig(pool_size=20)
        assert cfg.effective_workers == 20

    def test_effective_workers_explicit(self):
        cfg = ChannelConfig(pool_size=20, workers=5)
        assert cfg.effective_workers == 5

    def test_negative_pool_size_raises(self):
        with pytest.raises(ValueError, match="pool_size"):
            ChannelConfig(pool_size=-1)

    def test_negative_max_overflow_raises(self):
        with pytest.raises(ValueError, match="max_overflow"):
            ChannelConfig(max_overflow=-1)

    def test_zero_queue_maxsize_raises(self):
        with pytest.raises(ValueError, match="queue_maxsize"):
            ChannelConfig(queue_maxsize=0)


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.delay_seconds == 0.5
        assert cfg.backoff_multiplier == 2.0
        assert cfg.max_total_timeout == 0.0

    def test_negative_max_retries_raises(self):
        with pytest.raises(ValueError, match="max_retries"):
            RetryConfig(max_retries=-1)

    def test_backoff_multiplier_too_low_raises(self):
        with pytest.raises(ValueError, match="backoff_multiplier"):
            RetryConfig(backoff_multiplier=0.5)


class TestCacheConfig:
    def test_defaults(self):
        cfg = CacheConfig()
        assert cfg.enabled is False
        assert cfg.ttl_seconds == 60.0
        assert cfg.max_size == 1000

    def test_negative_ttl_raises(self):
        with pytest.raises(ValueError, match="ttl_seconds"):
            CacheConfig(ttl_seconds=-1)

    def test_zero_max_size_raises(self):
        with pytest.raises(ValueError, match="max_size"):
            CacheConfig(max_size=0)


class TestPipelineConfig:
    def test_empty_db_url_raises(self):
        with pytest.raises(ValueError, match="db_url"):
            PipelineConfig(db_url="")

    def test_defaults(self):
        cfg = PipelineConfig(db_url="postgresql+asyncpg://localhost/test")
        assert cfg.pool_recycle == 3600
        assert cfg.pool_pre_ping is True
        assert cfg.pool_timeout == 30
        assert cfg.default_timeout == 30.0
        assert cfg.max_concurrency == 200
        assert cfg.shutdown_timeout == 10.0
        assert cfg.metrics_enabled is True

    def test_negative_pool_recycle_raises(self):
        with pytest.raises(ValueError, match="pool_recycle"):
            PipelineConfig(db_url="x", pool_recycle=-1)

    def test_negative_shutdown_timeout_raises(self):
        with pytest.raises(ValueError, match="shutdown_timeout"):
            PipelineConfig(db_url="x", shutdown_timeout=-1)
