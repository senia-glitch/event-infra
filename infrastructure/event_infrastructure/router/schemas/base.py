"""Базовая схема для сущностей."""

from typing import Type, Dict, Any, Optional, Set
from sqlmodel import SQLModel
from enum import Enum


class EntitySchema:
    """Мета-информация о сущности."""
    
    def __init__(
        self,
        table_name: str,
        schema: Type[SQLModel],
        primary_key: str = "id",
        exclude_from_insert: Optional[Set[str]] = None,
        exclude_from_update: Optional[Set[str]] = None,
    ):
        self.table_name = table_name
        self.schema = schema
        self.primary_key = primary_key
        self.exclude_from_insert = exclude_from_insert or set()
        self.exclude_from_update = exclude_from_update or set()
        self.exclude_from_update.add(primary_key)
    
    def get_field_names(self) -> Set[str]:
        return set(self.schema.model_fields.keys())
    
    def get_insert_fields(self) -> Set[str]:
        return self.get_field_names() - self.exclude_from_insert
    
    def get_update_fields(self) -> Set[str]:
        return self.get_field_names() - self.exclude_from_update
    
    def validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        validated = self.schema(**data)
        result = {}
        for field_name, value in validated.model_dump().items():
            if isinstance(value, Enum):
                result[field_name] = value.value
            else:
                result[field_name] = value
        return result