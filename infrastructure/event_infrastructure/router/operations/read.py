"""Операция чтения записи."""

from typing import Any
import time

from ..schemas.registry import EntityRegistry
from ..response import Response
from .base import BaseOperation


class ReadOperation(BaseOperation):
    """Чтение записи по ID."""
    
    def __init__(self, db, registry: EntityRegistry):
        super().__init__(db)
        self._registry = registry
    
    async def execute(self, entity: str, id: Any, channel: str = "read") -> Response:
        start_time = time.monotonic()
        
        try:
            schema = self._registry.get_or_raise(entity)
        except ValueError as e:
            return Response.error_response(
                error_code=100, error_message=str(e), operation="read", entity=entity
            )
        
        pk = schema.primary_key
        all_fields = list(schema.get_field_names())
        select_clause = ", ".join(f'"{f}"' for f in all_fields)
        
        sql = f"""
            SELECT {select_clause}
            FROM "{entity}"
            WHERE "{pk}" = :{pk}
        """
        
        result = await self.db.execute(channel, sql, {pk: id})
        elapsed = (time.monotonic() - start_time) * 1000
        
        return self._handle_db_result(
            result=result, operation="read", entity=entity,
            column_names=all_fields, execution_time_ms=elapsed
        )