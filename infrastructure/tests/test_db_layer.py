"""Unit-тесты для DB-слоя: dispatcher, orchestrator, pools, queues."""

import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from infrastructure.event_infrastructure.db.queues import SQLTask, QueueManager
from infrastructure.event_infrastructure.db.dispatcher import Dispatcher
from infrastructure.event_infrastructure.db.orchestrator import Orchestrator
from infrastructure.event_infrastructure.db.pools import PoolManager
from infrastructure.event_infrastructure.db.models import TaskResult, InfrastructureMetrics
from infrastructure.event_infrastructure.config.models import PipelineConfig, ChannelConfig


# ================================================================
# SQLTask
# ================================================================


class TestSQLTask:
    def test_init_defaults(self):
        task = SQLTask(sql="SELECT 1")
        assert task.sql == "SELECT 1"
        assert task.params == {}
        assert task.timeout is None
        assert task._future is None

    def test_init_with_params(self):
        task = SQLTask(sql="SELECT :id", params={"id": 1}, timeout=5.0)
        assert task.params == {"id": 1}
        assert task.timeout == 5.0

    def test_get_future_creates_once(self):
        task = SQLTask(sql="SELECT 1")
        task._future = asyncio.get_event_loop().create_future()
        f2 = task.get_future()
        assert task._future is f2


# ================================================================
# QueueManager
# ================================================================


class TestQueueManager:
    def _make_config(self, channels=None):
        if channels is None:
            channels = {
                "read": ChannelConfig(pool_size=5, max_overflow=2, queue_maxsize=10),
                "write": ChannelConfig(pool_size=5, max_overflow=2, queue_maxsize=10),
            }
        return PipelineConfig(db_url="postgresql+asyncpg://test", channels=channels)

    def test_init_creates_queues(self):
        config = self._make_config()
        qm = QueueManager(config)
        assert "read" in qm._queues
        assert "write" in qm._queues

    def test_get_queue(self):
        config = self._make_config()
        qm = QueueManager(config)
        q = qm.get("read")
        assert isinstance(q, asyncio.Queue)

    def test_is_accepting_default(self):
        config = self._make_config()
        qm = QueueManager(config)
        assert qm.is_accepting is True

    def test_stop_accepting(self):
        config = self._make_config()
        qm = QueueManager(config)
        qm.stop_accepting()
        assert qm.is_accepting is False

    @pytest.mark.asyncio
    async def test_put_rejects_when_not_accepting(self):
        config = self._make_config()
        qm = QueueManager(config)
        qm.stop_accepting()
        task = SQLTask(sql="SELECT 1")
        with pytest.raises(RuntimeError, match="не принимаются"):
            await qm.put("read", task)

    @pytest.mark.asyncio
    async def test_put_rejects_unknown_channel(self):
        config = self._make_config()
        qm = QueueManager(config)
        task = SQLTask(sql="SELECT 1")
        with pytest.raises(ValueError, match="не найден"):
            await qm.put("nonexistent", task)

    @pytest.mark.asyncio
    async def test_put_adds_to_queue(self):
        config = self._make_config()
        qm = QueueManager(config)
        task = SQLTask(sql="SELECT 1")
        await qm.put("read", task)
        assert qm.get("read").qsize() == 1


# ================================================================
# PoolManager
# ================================================================


class TestPoolManager:
    def _make_config(self):
        return PipelineConfig(
            db_url="postgresql+asyncpg://user:pass@localhost/test",
            channels={
                "read": ChannelConfig(pool_size=5),
                "write": ChannelConfig(pool_size=3),
            },
        )

    def test_init_creates_engines(self):
        config = self._make_config()
        pm = PoolManager(config)
        assert "read" in pm._engines
        assert "write" in pm._engines

    def test_channels_property(self):
        config = self._make_config()
        pm = PoolManager(config)
        channels = pm.channels
        assert sorted(channels) == ["read", "write"]

    def test_get_existing(self):
        config = self._make_config()
        pm = PoolManager(config)
        engine = pm.get("read")
        assert engine is pm._engines["read"]

    def test_get_nonexistent_raises(self):
        config = self._make_config()
        pm = PoolManager(config)
        with pytest.raises(ValueError, match="не найден"):
            pm.get("nonexistent")

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self):
        config = self._make_config()
        pm = PoolManager(config)
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_ctx
        pm._engines = {"read": mock_engine, "write": mock_engine}
        result = await pm.health_check()
        assert result["read"] is True
        assert result["write"] is True

    @pytest.mark.asyncio
    async def test_health_check_one_fails(self):
        config = self._make_config()
        pm = PoolManager(config)
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_ctx_ok = AsyncMock()
        mock_ctx_ok.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_ctx_ok.__aexit__ = AsyncMock(return_value=False)
        mock_ok = MagicMock()
        mock_ok.connect.return_value = mock_ctx_ok
        mock_bad = MagicMock()
        mock_bad.connect.side_effect = Exception("connection refused")
        pm._engines = {"read": mock_ok, "write": mock_bad}
        result = await pm.health_check()
        assert result["read"] is True
        assert result["write"] is False

    @pytest.mark.asyncio
    async def test_close_all(self):
        config = self._make_config()
        pm = PoolManager(config)
        mock_engine = AsyncMock()
        pm._engines = {"read": mock_engine, "write": mock_engine}
        await pm.close_all()
        assert mock_engine.dispose.call_count == 2


# ================================================================
# Dispatcher
# ================================================================


class TestDispatcher:
    def _make_dispatcher(self, workers=2):
        engine = MagicMock()
        queue = asyncio.Queue()
        return Dispatcher(name="test", engine=engine, queue=queue, workers=workers)

    def test_init(self):
        d = self._make_dispatcher(workers=3)
        assert d.name == "test"
        assert d._workers == 3
        assert d.tasks_processed == 0
        assert d.tasks_failed == 0
        assert d.last_error == ""

    def test_avg_time_ms_no_tasks(self):
        d = self._make_dispatcher()
        assert d.avg_time_ms == 0.0

    def test_avg_time_ms_with_tasks(self):
        d = self._make_dispatcher()
        d.tasks_processed = 10
        d._total_time = 1.0
        assert d.avg_time_ms == 100.0

    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        d = self._make_dispatcher()
        task = SQLTask(sql="SELECT pg_sleep(10)", timeout=0.001)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.side_effect = asyncio.TimeoutError()
        mock_ctx.__aexit__.return_value = False
        d._engine.begin.return_value = mock_ctx
        result = await d._execute(task)
        assert result.success is False
        assert result.error_code == 408
        assert result.error_type == "query_timeout"

    @pytest.mark.asyncio
    async def test_execute_success(self):
        d = self._make_dispatcher()
        mock_result = MagicMock()
        mock_result.returns_rows = True
        mock_result.fetchall.return_value = [(1,)]
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        d._engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        d._engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        task = SQLTask(sql="SELECT 1")
        result = await d._execute(task)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_db_error(self):
        d = self._make_dispatcher()
        from sqlalchemy.exc import IntegrityError

        d._engine.begin.return_value.__aenter__ = AsyncMock(
            side_effect=IntegrityError("INSERT", {}, Exception('duplicate key "uniq"'))
        )
        d._engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        task = SQLTask(sql="INSERT INTO test VALUES (1)")
        result = await d._execute(task)
        assert result.success is False
        assert result.error_type == "unique_constraint"
        assert result.error_code == 409

    @pytest.mark.asyncio
    async def test_do_execute_no_return(self):
        d = self._make_dispatcher()
        mock_result = MagicMock()
        mock_result.returns_rows = False
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_result
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        d._engine.begin.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        d._engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        task = SQLTask(sql="INSERT INTO test VALUES (1)")
        result = await d._do_execute(task)
        assert result.success is True
        assert result.data is None

    @pytest.mark.asyncio
    async def test_run_processes_task(self):
        d = self._make_dispatcher(workers=1)
        task = SQLTask(sql="SELECT 1")
        task.get_future()
        await d._queue.put(task)

        mock_result = MagicMock(success=True, data=[(1,)], error_code=0, error_message="")
        with patch.object(d, "_execute", return_value=mock_result):
            d._tasks = [asyncio.create_task(d._run(0))]
            await asyncio.sleep(0.1)
            d._tasks[0].cancel()
            await asyncio.sleep(0.05)

        assert d.tasks_processed == 1

    @pytest.mark.asyncio
    async def test_run_handles_exception(self):
        d = self._make_dispatcher(workers=1)
        task = SQLTask(sql="SELECT 1")
        task.get_future()
        await d._queue.put(task)

        with patch.object(d, "_execute", side_effect=Exception("boom")):
            d._tasks = [asyncio.create_task(d._run(0))]
            await asyncio.sleep(0.1)
            d._tasks[0].cancel()
            await asyncio.sleep(0.05)

        assert task.get_future().done()
        result = task.get_future().result()
        assert result.success is False
        assert result.error_code == 500

    @pytest.mark.asyncio
    async def test_run_cancelled_error_with_task(self):
        d = self._make_dispatcher(workers=1)
        task = SQLTask(sql="SELECT 1")
        task.get_future()
        await d._queue.put(task)

        mock_result = MagicMock(success=False, error_code=503, error_message="shutdown")
        with patch.object(d, "_execute", return_value=mock_result):
            d._tasks = [asyncio.create_task(d._run(0))]
            await asyncio.sleep(0.05)
            d._tasks[0].cancel()
            await asyncio.sleep(0.05)

        result = task.get_future().result()
        assert result.error_code == 503

    @pytest.mark.asyncio
    async def test_shutdown_drain(self):
        d = self._make_dispatcher(workers=0)
        await d.shutdown(timeout=1.0)
        assert d.tasks_processed == 0

    @pytest.mark.asyncio
    async def test_shutdown_drains_queued_tasks(self):
        d = self._make_dispatcher(workers=0)
        task = SQLTask(sql="SELECT 1")
        task.get_future()
        await d._queue.put(task)
        await d.shutdown(timeout=1.0)
        assert task.get_future().done()
        result = task.get_future().result()
        assert result.error_code == 503

    def test_active_count(self):
        d = self._make_dispatcher(workers=1)
        d._tasks = [MagicMock(done=MagicMock(return_value=False))]
        assert d.active_count == 1
        d._tasks = [MagicMock(done=MagicMock(return_value=True))]
        assert d.active_count == 0


# ================================================================
# Orchestrator
# ================================================================


class TestOrchestrator:
    def _make_config(self):
        return PipelineConfig(
            db_url="postgresql+asyncpg://test",
            channels={
                "read": ChannelConfig(pool_size=2),
                "write": ChannelConfig(pool_size=2),
            },
        )

    @pytest.mark.asyncio
    async def test_start(self):
        orch = Orchestrator(self._make_config())
        with patch.object(Dispatcher, "start", new_callable=AsyncMock):
            await orch.start()
        assert orch._start_time > 0

    @pytest.mark.asyncio
    async def test_execute(self):
        orch = Orchestrator(self._make_config())
        mock_future = asyncio.get_event_loop().create_future()
        mock_future.set_result(TaskResult(success=True, data=[(1,)]))
        with patch("infrastructure.event_infrastructure.db.dispatcher.Dispatcher.start", new_callable=AsyncMock):
            await orch.start()
        with patch.object(orch._queues, "put", new_callable=AsyncMock) as mock_put:
            async def fake_put(ch, task):
                task.get_future().set_result(TaskResult(success=True, data=[(1,)]))
            mock_put.side_effect = fake_put
            result = await orch.execute("read", "SELECT 1")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_read_write_admin(self):
        orch = Orchestrator(self._make_config())
        with patch("infrastructure.event_infrastructure.db.dispatcher.Dispatcher.start", new_callable=AsyncMock):
            await orch.start()
        with patch.object(orch, "execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = TaskResult(success=True)
            await orch.read("SELECT 1")
            mock_exec.assert_called_with("read", "SELECT 1", None, None)
            await orch.write("INSERT INTO t VALUES (1)")
            mock_exec.assert_called_with("write", "INSERT INTO t VALUES (1)", None, None)
            await orch.admin("DROP TABLE t")
            mock_exec.assert_called_with("admin", "DROP TABLE t", None, None)

    def test_get_metrics(self):
        orch = Orchestrator(self._make_config())
        m = orch.get_metrics()
        assert isinstance(m, InfrastructureMetrics)
        assert "read" in m.channels
        assert "write" in m.channels

    @pytest.mark.asyncio
    async def test_health_check(self):
        orch = Orchestrator(self._make_config())
        with patch.object(orch._pools, "health_check", new_callable=AsyncMock, return_value={"read": True, "write": True}):
            result = await orch.health_check()
        assert result["read"] is True

    def test_channel_names(self):
        orch = Orchestrator(self._make_config())
        assert sorted(orch.channel_names) == ["read", "write"]

    def test_is_accepting(self):
        orch = Orchestrator(self._make_config())
        assert orch._queues.is_accepting is True
        orch._queues.stop_accepting()
        assert orch._queues.is_accepting is False

    @pytest.mark.asyncio
    async def test_shutdown(self):
        orch = Orchestrator(self._make_config())
        with patch("infrastructure.event_infrastructure.db.dispatcher.Dispatcher.start", new_callable=AsyncMock):
            await orch.start()
        with patch.object(Dispatcher, "shutdown", new_callable=AsyncMock):
            with patch.object(orch._pools, "close_all", new_callable=AsyncMock):
                await orch.shutdown(timeout=1.0)
        assert orch._queues.is_accepting is False

    @pytest.mark.asyncio
    async def test_shutdown_continues_even_if_dispatcher_fails(self):
        orch = Orchestrator(self._make_config())
        with patch("infrastructure.event_infrastructure.db.dispatcher.Dispatcher.start", new_callable=AsyncMock):
            await orch.start()
        call_count = 0
        async def failing_shutdown(timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("dispatcher crash")
        with patch.object(Dispatcher, "shutdown", side_effect=failing_shutdown):
            with patch.object(orch._pools, "close_all", new_callable=AsyncMock) as mock_close:
                await orch.shutdown(timeout=1.0)
        mock_close.assert_called_once()
