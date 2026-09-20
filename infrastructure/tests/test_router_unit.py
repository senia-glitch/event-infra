"""Unit-тесты для EventRouter через моки."""

import asyncio
from unittest.mock import MagicMock, AsyncMock
import pytest
from sqlmodel import SQLModel, Field
from typing import Optional

from infrastructure.event_infrastructure.router.router import EventRouter
from infrastructure.event_infrastructure.router.response import Response
from infrastructure.event_infrastructure.router.health import HealthStatus
from infrastructure.event_infrastructure.db.models import TaskResult, InfrastructureMetrics, ChannelMetrics
from infrastructure.event_infrastructure.config.models import RetryConfig, CacheConfig


class SimpleTable(SQLModel, table=True):
    __tablename__ = "test_router_simple"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50)


class AnotherTable(SQLModel, table=True):
    __tablename__ = "test_router_another"
    id: Optional[int] = Field(default=None, primary_key=True)
    val: int = Field(default=0)


def _make_router(schemas=None, cache_enabled=False, max_concurrency=0, retry=None, exclude_tables=None):
    db = MagicMock()
    db.health_check = AsyncMock(return_value={"read": True, "write": True})
    db.channel_names = ["read", "write"]
    db.get_metrics = MagicMock(return_value=InfrastructureMetrics(
        channels={
            "read": ChannelMetrics(name="read", queue_size=0, queue_maxsize=100, active_workers=2, pool_size=5),
            "write": ChannelMetrics(name="write", queue_size=0, queue_maxsize=100, active_workers=2, pool_size=5),
        },
        uptime_seconds=100.0,
        total_processed=50,
        total_failed=2,
        total_queued=0,
        is_accepting=True,
    ))
    db.shutdown = AsyncMock()
    db.execute = AsyncMock(return_value=TaskResult(success=True, data=[(1, "test")]))
    cache_cfg = CacheConfig(enabled=cache_enabled, ttl_seconds=10.0, max_size=100)
    router = EventRouter(
        orchestrator=db,
        schemas=schemas or {"test_router_simple": SimpleTable},
        exclude_tables=exclude_tables,
        retry=retry,
        cache=cache_cfg,
        max_concurrency=max_concurrency,
    )
    return router


# ================================================================
# Инициализация
# ================================================================


class TestEventRouterInit:
    def test_basic_init(self):
        router = _make_router()
        assert router.has_entity("test_router_simple")
        assert not router.has_entity("nope")

    def test_init_with_exclude(self):
        router = _make_router(schemas={"test_router_simple": SimpleTable, "test_router_another": AnotherTable}, exclude_tables={"test_router_another"})
        assert router.has_entity("test_router_simple")
        assert not router.has_entity("test_router_another")

    def test_init_with_custom_pk(self):
        router = _make_router(schemas={"test_router_simple": SimpleTable})
        reg = router.get_registry()
        assert reg["test_router_simple"].primary_key == "id"

    def test_get_registry(self):
        router = _make_router()
        reg = router.get_registry()
        assert "test_router_simple" in reg

    def test_has_entity(self):
        router = _make_router()
        assert router.has_entity("test_router_simple") is True
        assert router.has_entity("missing") is False


# ================================================================
# CRUD
# ================================================================


class TestRouterCreate:
    @pytest.mark.asyncio
    async def test_success(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "test")]
        )
        result = await router.create("test_router_simple", {"name": "test"})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_entity_not_found(self):
        router = _make_router()
        result = await router.create("nope", {"name": "x"})
        assert result.success is False
        assert result.error.code == 404


class TestRouterRead:
    @pytest.mark.asyncio
    async def test_success(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "test")]
        )
        result = await router.read("test_router_simple", 1)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_read_with_cache(self):
        router = _make_router(cache_enabled=True)
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "test")]
        )
        r1 = await router.read("test_router_simple", 1)
        assert r1.success is True
        router._db.execute.reset_mock()
        r2 = await router.read("test_router_simple", 1)
        assert r2.success is True
        router._db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_read_cache_disabled_explicit(self):
        router = _make_router(cache_enabled=True)
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "test")]
        )
        await router.read("test_router_simple", 1)
        router._db.execute.reset_mock()
        result = await router.read("test_router_simple", 1, cache=False)
        assert result.success is True
        router._db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_read_no_cache_configured(self):
        router = _make_router(cache_enabled=False)
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "test")]
        )
        result = await router.read("test_router_simple", 1)
        assert result.success is True


class TestRouterUpdate:
    @pytest.mark.asyncio
    async def test_success(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "new")]
        )
        result = await router.update("test_router_simple", 1, {"name": "new"})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_update_invalidates_cache(self):
        router = _make_router(cache_enabled=True)
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "test")]
        )
        await router.read("test_router_simple", 1)
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "new")]
        )
        result = await router.update("test_router_simple", 1, {"name": "new"}, cache=True)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_update_cache_false(self):
        router = _make_router(cache_enabled=True)
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "test")]
        )
        await router.read("test_router_simple", 1)
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "new")]
        )
        await router.update("test_router_simple", 1, {"name": "new"}, cache=False)
        router._db.execute.reset_mock()
        r = await router.read("test_router_simple", 1)
        assert r.success is True


class TestRouterDelete:
    @pytest.mark.asyncio
    async def test_success(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1,)]
        )
        result = await router.delete("test_router_simple", 1)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_delete_invalidates_cache(self):
        router = _make_router(cache_enabled=True)
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "test")]
        )
        await router.read("test_router_simple", 1)
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1,)]
        )
        await router.delete("test_router_simple", 1, cache=True)


# ================================================================
# Custom / Execute
# ================================================================


class TestRouterCustom:
    @pytest.mark.asyncio
    async def test_success(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1,)]
        )
        result = await router.custom("SELECT 1")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_custom_with_params(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(success=True, data=[])
        result = await router.custom("SELECT :x", {"x": 1})
        assert result.success is True


class TestRouterExecute:
    @pytest.mark.asyncio
    async def test_success(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "test")]
        )
        result = await router.execute("read", "SELECT * FROM simple")
        assert result.success is True
        assert result.data[0]["row"] == (1, "test")

    @pytest.mark.asyncio
    async def test_execute_error(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=False, error_code=500, error_message="db error"
        )
        result = await router.execute("read", "INVALID")
        assert result.success is False
        assert result.error.code == 500


# ================================================================
# List
# ================================================================


class TestRouterList:
    @pytest.mark.asyncio
    async def test_success(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "a"), (2, "b")]
        )
        result = await router.list("test_router_simple", limit=10)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_list_with_filters(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=True, data=[(1, "a")]
        )
        result = await router.list("test_router_simple", filters={"name": "a"})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_list_with_order(self):
        router = _make_router()
        router._db.execute.return_value = TaskResult(
            success=True, data=[]
        )
        result = await router.list("test_router_simple", order_by="name", order_desc=True)
        assert result.success is True


# ================================================================
# Health
# ================================================================


class TestRouterHealthCheck:
    @pytest.mark.asyncio
    async def test_all_healthy(self):
        router = _make_router()
        health = await router.health_check()
        assert health["alive"] is True
        assert health["db_connected"] is True

    @pytest.mark.asyncio
    async def test_db_error(self):
        router = _make_router()
        router._db.health_check.side_effect = Exception("db down")
        health = await router.health_check()
        assert health["alive"] is False
        assert health["error"] == "db down"

    @pytest.mark.asyncio
    async def test_is_alive(self):
        router = _make_router()
        assert await router.is_alive() is True

    @pytest.mark.asyncio
    async def test_is_alive_db_error(self):
        router = _make_router()
        router._db.health_check.side_effect = Exception("down")
        assert await router.is_alive() is False


class TestRouterHealth:
    @pytest.mark.asyncio
    async def test_ok(self):
        router = _make_router()
        result = await router.health()
        assert result.status == HealthStatus.OK
        d = result.to_dict()
        assert d["status"] == "ok"

    @pytest.mark.asyncio
    async def test_degraded(self):
        router = _make_router()
        router._db.health_check.return_value = {"read": True, "write": False}
        result = await router.health()
        assert result.status == HealthStatus.DEGRADED
        assert "1/2" in result.message

    @pytest.mark.asyncio
    async def test_down(self):
        router = _make_router()
        router._db.health_check.return_value = {"read": False, "write": False}
        result = await router.health()
        assert result.status == HealthStatus.DOWN

    @pytest.mark.asyncio
    async def test_db_exception(self):
        router = _make_router()
        router._db.health_check.side_effect = Exception("db crash")
        result = await router.health()
        assert result.status == HealthStatus.DOWN
        assert "database" in result.checks
        assert result.checks["database"]["status"] == "down"

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        router = _make_router(cache_enabled=False)
        result = await router.health()
        assert result.checks["cache"]["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_cache_enabled(self):
        router = _make_router(cache_enabled=True)
        result = await router.health()
        assert result.checks["cache"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_queues_info(self):
        router = _make_router()
        result = await router.health()
        assert "read" in result.checks["queues"]
        assert "write" in result.checks["queues"]


# ================================================================
# Метрики и вывод
# ================================================================


class TestRouterMetrics:
    def test_get_metrics(self):
        router = _make_router()
        m = router.get_metrics()
        assert isinstance(m, InfrastructureMetrics)

    def test_print_metrics(self, caplog):
        import logging
        router = _make_router()
        with caplog.at_level(logging.INFO):
            router.print_metrics()
        assert "UPTIME" in caplog.text

    def test_print_metrics_full(self, caplog):
        import logging
        router = _make_router()
        with caplog.at_level(logging.INFO):
            router.print_metrics(full=True)
        assert "ДЕТАЛИЗАЦИЯ" in caplog.text

    def test_print_metrics_with_cache(self, caplog):
        import logging
        router = _make_router(cache_enabled=True)
        with caplog.at_level(logging.INFO):
            router.print_metrics()
        assert "КЕШ" in caplog.text

    def test_print_metrics_with_last_error(self, caplog):
        import logging
        router = _make_router()
        router._db.get_metrics.return_value = InfrastructureMetrics(
            channels={
                "read": ChannelMetrics(name="read", last_error="some error happened here"),
            },
            uptime_seconds=10.0,
        )
        with caplog.at_level(logging.INFO):
            router.print_metrics(full=True)
        assert "Last error" in caplog.text


# ================================================================
# Retry
# ================================================================


class TestRouterRetry:
    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        router = _make_router(retry=RetryConfig(max_retries=2, delay_seconds=0.01))
        call_count = 0

        async def mock_execute(channel, sql, params=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return TaskResult(success=False, error_code=500, error_message="connection lost")
            return TaskResult(success=True, data=[(1, "ok")])

        router._db.execute = mock_execute
        result = await router.read("test_router_simple", 1)
        assert result.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        router = _make_router(retry=RetryConfig(max_retries=2, delay_seconds=0.01))
        call_count = 0

        async def mock_execute(channel, sql, params=None, timeout=None):
            nonlocal call_count
            call_count += 1
            return TaskResult(success=False, error_code=422, error_message="validation error")

        router._db.execute = mock_execute
        result = await router.read("test_router_simple", 1)
        assert result.success is False
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_exception_returns_error_response(self):
        router = _make_router(retry=RetryConfig(max_retries=1, delay_seconds=0.01))

        async def bad_coro():
            raise RuntimeError("boom")

        result = await router._with_retry(bad_coro)
        assert result.success is False
        assert result.error.code == 500

    @pytest.mark.asyncio
    async def test_retry_total_timeout_exceeded(self):
        router = _make_router(retry=RetryConfig(
            max_retries=10, delay_seconds=0.5, max_total_timeout=0.1
        ))
        call_count = 0

        async def mock_execute(channel, sql, params=None, timeout=None):
            nonlocal call_count
            call_count += 1
            return TaskResult(success=False, error_code=503, error_message="connection dead")

        router._db.execute = mock_execute
        result = await router.read("test_router_simple", 1)
        assert result.success is False
        assert call_count < 10

    @pytest.mark.asyncio
    async def test_retry_max_retries_zero(self):
        router = _make_router(retry=RetryConfig(max_retries=0))
        result = await router._with_retry(
            lambda: asyncio.coroutine(lambda: Response.error_response(500, "err", "test"))()
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_retry_max_retries_zero_exception(self):
        router = _make_router(retry=RetryConfig(max_retries=0))

        async def boom():
            raise ValueError("oops")

        result = await router._with_retry(boom)
        assert result.success is False
        assert "oops" in result.error.message


# ================================================================
# is_retryable_error
# ================================================================


class TestIsRetryable:
    def test_connection(self):
        router = _make_router()
        rc = RetryConfig()
        assert router._is_retryable_error("connection refused", rc) is True

    def test_deadlock(self):
        router = _make_router()
        rc = RetryConfig()
        assert router._is_retryable_error("deadlock detected", rc) is True

    def test_serialization(self):
        router = _make_router()
        rc = RetryConfig()
        assert router._is_retryable_error("serialization failure", rc) is True

    def test_timeout_not_retryable_by_default(self):
        router = _make_router()
        rc = RetryConfig(retry_on_timeout=False)
        assert router._is_retryable_error("timeout expired", rc) is False

    def test_timeout_retryable_when_enabled(self):
        router = _make_router()
        rc = RetryConfig(retry_on_timeout=True)
        assert router._is_retryable_error("timeout expired", rc) is True

    def test_not_retryable(self):
        router = _make_router()
        rc = RetryConfig()
        assert router._is_retryable_error("unique violation", rc) is False

    def test_server_closed(self):
        router = _make_router()
        rc = RetryConfig()
        assert router._is_retryable_error("server closed the connection", rc) is True


# ================================================================
# Semaphore
# ================================================================


class TestSemaphore:
    @pytest.mark.asyncio
    async def test_with_semaphore(self):
        router = _make_router(max_concurrency=2)
        assert router._semaphore is not None

    def test_without_semaphore(self):
        router = _make_router(max_concurrency=0)
        assert router._semaphore is None


# ================================================================
# Context manager
# ================================================================


class TestContextManager:
    @pytest.mark.asyncio
    async def test_aenter_aexit(self):
        router = _make_router()
        router._db.shutdown = AsyncMock()
        async with router as r:
            assert r is router
        router._db.shutdown.assert_called_once()


# ================================================================
# Shutdown
# ================================================================


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown(self):
        router = _make_router()
        router._db.shutdown = AsyncMock()
        await router.shutdown(timeout=5.0)
        router._db.shutdown.assert_called_once_with(5.0)
