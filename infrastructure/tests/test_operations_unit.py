"""Unit-тесты для операций CRUD через моки."""

from unittest.mock import AsyncMock
import pytest
from sqlmodel import SQLModel, Field
from typing import Optional

from infrastructure.event_infrastructure.router.operations.create import CreateOperation
from infrastructure.event_infrastructure.router.operations.read import ReadOperation
from infrastructure.event_infrastructure.router.operations.update import UpdateOperation
from infrastructure.event_infrastructure.router.operations.delete import DeleteOperation
from infrastructure.event_infrastructure.router.operations.custom import CustomOperation
from infrastructure.event_infrastructure.router.operations.list_op import ListOperation
from infrastructure.event_infrastructure.router.schemas.base import EntitySchema
from infrastructure.event_infrastructure.router.schemas.registry import EntityRegistry
from infrastructure.event_infrastructure.db.models import TaskResult


class SimpleTable(SQLModel, table=True):
    __tablename__ = "test_ops_simple"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50)
    val: int = Field(default=0)


def _make_registry():
    reg = EntityRegistry()
    schema = EntitySchema(
        table_name="test_ops_simple",
        schema=SimpleTable,
        primary_key="id",
        exclude_from_insert={"id"},
        exclude_from_update={"id"},
    )
    reg.register(schema)
    return reg


def _make_db():
    db = AsyncMock()
    return db


class TestCreateOperation:
    @pytest.mark.asyncio
    async def test_success(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(
            success=True, data=[(1, "test", 0)]
        )
        op = CreateOperation(db, reg)
        result = await op.execute("test_ops_simple", {"name": "test"}, "write")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_entity_not_found(self):
        db = _make_db()
        reg = _make_registry()
        op = CreateOperation(db, reg)
        result = await op.execute("nonexistent", {"name": "x"})
        assert result.success is False
        assert result.error.code == 404

    @pytest.mark.asyncio
    async def test_validation_error(self):
        db = _make_db()
        reg = _make_registry()
        op = CreateOperation(db, reg)
        result = await op.execute("test_ops_simple", {"name": "test"})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_no_fields_to_insert(self):
        db = _make_db()
        reg = _make_registry()
        op = CreateOperation(db, reg)
        result = await op.execute("test_ops_simple", {})
        assert result.success is True


class TestReadOperation:
    @pytest.mark.asyncio
    async def test_success(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(
            success=True, data=[(1, "test", 0)]
        )
        op = ReadOperation(db, reg)
        result = await op.execute("test_ops_simple", 1, "read")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(success=True, data=[])
        op = ReadOperation(db, reg)
        result = await op.execute("test_ops_simple", 999, "read")
        assert result.success is True
        assert result.count == 0

    @pytest.mark.asyncio
    async def test_entity_not_registered(self):
        db = _make_db()
        reg = _make_registry()
        op = ReadOperation(db, reg)
        result = await op.execute("nope", 1)
        assert result.success is False
        assert result.error.code == 404


class TestUpdateOperation:
    @pytest.mark.asyncio
    async def test_success(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(
            success=True, data=[(1, "new", 5)]
        )
        op = UpdateOperation(db, reg)
        result = await op.execute("test_ops_simple", 1, {"name": "new"}, "write")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_validation_error(self):
        db = _make_db()
        reg = _make_registry()
        op = CreateOperation(db, reg)
        result = await op.execute("test_ops_simple", {"name": None})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_no_fields_to_insert(self):
        db = _make_db()
        reg = _make_registry()
        op = CreateOperation(db, reg)
        result = await op.execute("test_ops_simple", {})
        assert result.success is True


class TestDeleteOperation:
    @pytest.mark.asyncio
    async def test_success(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(success=True, data=[(1,)])
        op = DeleteOperation(db, reg)
        result = await op.execute("test_ops_simple", 1, "write")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(success=True, data=[])
        op = DeleteOperation(db, reg)
        result = await op.execute("test_ops_simple", 999)
        assert result.success is True
        assert len(result.data) == 0

    @pytest.mark.asyncio
    async def test_entity_not_registered(self):
        db = _make_db()
        reg = _make_registry()
        op = DeleteOperation(db, reg)
        result = await op.execute("nope", 1)
        assert result.success is False
        assert result.error.code == 404

    @pytest.mark.asyncio
    async def test_db_error(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(success=False, error_code=500, error_message="db error")
        op = DeleteOperation(db, reg)
        result = await op.execute("test_ops_simple", 1)
        assert result.success is False
        assert result.error.code == 500


class TestCustomOperation:
    @pytest.mark.asyncio
    async def test_success(self):
        db = _make_db()
        op = CustomOperation(db)
        db.execute.return_value = TaskResult(success=True, data=[(1,), (2,)])
        result = await op.execute("SELECT * FROM t")
        assert result.success is True
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_no_data(self):
        db = _make_db()
        op = CustomOperation(db)
        db.execute.return_value = TaskResult(success=True, data=None)
        result = await op.execute("DROP TABLE t")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_error(self):
        db = _make_db()
        op = CustomOperation(db)
        db.execute.return_value = TaskResult(success=False, error_code=400, error_message="syntax error")
        result = await op.execute("INVALID SQL")
        assert result.success is False
        assert result.error.code == 400

    @pytest.mark.asyncio
    async def test_with_params(self):
        db = _make_db()
        op = CustomOperation(db)
        db.execute.return_value = TaskResult(success=True, data=[])
        result = await op.execute("SELECT :x", {"x": 1})
        assert result.success is True


class TestListOperation:
    @pytest.mark.asyncio
    async def test_success(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(
            success=True, data=[(1, "a", 10), (2, "b", 20)]
        )
        op = ListOperation(db, reg)
        result = await op.execute("test_ops_simple", "read", limit=10, offset=0)
        assert result.success is True
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_entity_not_found(self):
        db = _make_db()
        reg = _make_registry()
        op = ListOperation(db, reg)
        result = await op.execute("nope")
        assert result.success is False
        assert result.error.code == 404

    @pytest.mark.asyncio
    async def test_invalid_filter_field(self):
        db = _make_db()
        reg = _make_registry()
        op = ListOperation(db, reg)
        result = await op.execute("test_ops_simple", filters={"nonexistent_field": 1})
        assert result.success is False
        assert result.error.code == 422

    @pytest.mark.asyncio
    async def test_invalid_order_by(self):
        db = _make_db()
        reg = _make_registry()
        op = ListOperation(db, reg)
        result = await op.execute("test_ops_simple", order_by="nonexistent_field")
        assert result.success is False
        assert result.error.code == 422

    @pytest.mark.asyncio
    async def test_with_filters(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(success=True, data=[(1, "a", 10)])
        op = ListOperation(db, reg)
        result = await op.execute("test_ops_simple", filters={"name": "a"})
        assert result.success is True

    @pytest.mark.asyncio
    async def test_order_desc(self):
        db = _make_db()
        reg = _make_registry()
        db.execute.return_value = TaskResult(
            success=True, data=[(2, "b", 20), (1, "a", 10)]
        )
        op = ListOperation(db, reg)
        result = await op.execute("test_ops_simple", order_by="name", order_desc=True)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_count_query(self):
        db = _make_db()
        reg = _make_registry()
        data_result = TaskResult(success=True, data=[(1, "a", 10)])
        count_result = TaskResult(success=True, data=[(5,)])
        db.execute = AsyncMock(side_effect=[data_result, count_result])
        op = ListOperation(db, reg)
        result = await op.execute("test_ops_simple")
        assert result.success is True
        assert result.meta.affected_rows == 5
