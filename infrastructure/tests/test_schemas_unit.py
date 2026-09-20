"""Unit-тесты для EntitySchema и EntityRegistry."""

import pytest
from enum import Enum
from sqlmodel import SQLModel, Field
from typing import Optional

from infrastructure.event_infrastructure.router.schemas.base import EntitySchema
from infrastructure.event_infrastructure.router.schemas.registry import EntityRegistry


class ColorEnum(str, Enum):
    RED = "red"
    BLUE = "blue"


class TestEntity(SQLModel, table=True):
    __tablename__ = "test_schema_entity"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50)
    color: Optional[ColorEnum] = Field(default=None)


class CustomPKSchema(SQLModel):
    uuid: str = Field(max_length=36, primary_key=True)
    label: str = Field(max_length=100)


class TestEntitySchema:
    def test_basic(self):
        schema = EntitySchema(table_name="test", schema=TestEntity)
        assert schema.table_name == "test"
        assert schema.primary_key == "id"
        assert schema.get_field_names() == {"id", "name", "color"}

    def test_get_insert_fields_excludes_auto_id(self):
        schema = EntitySchema(
            table_name="test",
            schema=TestEntity,
            exclude_from_insert={"id"},
        )
        fields = schema.get_insert_fields()
        assert "id" not in fields
        assert "name" in fields

    def test_get_update_fields_excludes_pk(self):
        schema = EntitySchema(
            table_name="test",
            schema=TestEntity,
            primary_key="id",
        )
        fields = schema.get_update_fields()
        assert "id" not in fields
        assert "name" in fields

    def test_validate_data(self):
        schema = EntitySchema(table_name="test", schema=TestEntity)
        result = schema.validate_data({"name": "Alice", "color": "red"})
        assert result["name"] == "Alice"
        assert result["color"] == "red"

    def test_validate_data_invalid(self):
        schema = EntitySchema(table_name="test", schema=TestEntity)
        result = schema.validate_data({"name": 12345})
        assert "name" in result

    def test_custom_pk(self):
        schema = EntitySchema(table_name="cpk", schema=CustomPKSchema, primary_key="uuid")
        assert schema.primary_key == "uuid"
        assert "label" in schema.get_update_fields()


class TestEntityRegistry:
    def test_register_and_get(self):
        reg = EntityRegistry()
        schema = EntitySchema(table_name="users", schema=TestEntity)
        reg.register(schema)
        assert reg.get("users") is schema

    def test_register_duplicate_raises(self):
        reg = EntityRegistry()
        schema = EntitySchema(table_name="users", schema=TestEntity)
        reg.register(schema)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(schema)

    def test_get_nonexistent(self):
        reg = EntityRegistry()
        assert reg.get("nope") is None

    def test_has(self):
        reg = EntityRegistry()
        schema = EntitySchema(table_name="users", schema=TestEntity)
        reg.register(schema)
        assert reg.has("users") is True
        assert reg.has("nope") is False

    def test_get_or_raise(self):
        reg = EntityRegistry()
        schema = EntitySchema(table_name="users", schema=TestEntity)
        reg.register(schema)
        assert reg.get_or_raise("users") is schema

    def test_get_or_raise_nonexistent(self):
        reg = EntityRegistry()
        with pytest.raises(ValueError, match="not registered"):
            reg.get_or_raise("nope")

    def test_get_all_returns_copy(self):
        reg = EntityRegistry()
        schema = EntitySchema(table_name="users", schema=TestEntity)
        reg.register(schema)
        all_schemas = reg.get_all()
        all_schemas["extra"] = EntitySchema(table_name="extra", schema=TestEntity)
        assert reg.get("extra") is None
