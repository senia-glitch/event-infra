"""Реестр зарегистрированных сущностей."""

from typing import Dict, Optional
from .base import EntitySchema


class EntityRegistry:
    """Реестр сущностей для CRUD операций."""
    
    def __init__(self):
        self._entities: Dict[str, EntitySchema] = {}
    
    def register(self, entity_schema: EntitySchema) -> None:
        name = entity_schema.table_name
        if name in self._entities:
            raise ValueError(f"Entity '{name}' already registered")
        self._entities[name] = entity_schema
    
    def get(self, name: str) -> Optional[EntitySchema]:
        return self._entities.get(name)
    
    def has(self, name: str) -> bool:
        return name in self._entities
    
    def get_or_raise(self, name: str) -> EntitySchema:
        schema = self.get(name)
        if not schema:
            raise ValueError(f"Entity '{name}' not registered")
        return schema
    
    def get_all(self) -> Dict[str, EntitySchema]:
        return self._entities.copy()