"""Операция создания записи."""

from __future__ import annotations

import time
from typing import Any, Dict, TYPE_CHECKING

from ..schemas.registry import EntityRegistry
from ..response import Response
from .base import BaseOperation

if TYPE_CHECKING:
    from infrastructure.event_infrastructure.db.orchestrator import Orchestrator


class CreateOperation(BaseOperation):
    """Создание записи в таблице."""

    def __init__(self, db: "Orchestrator", registry: EntityRegistry):
        super().__init__(db)
        self._registry = registry

    async def execute(self, entity: str, data: Dict[str, Any], channel: str = "write") -> Response:
        start_time = time.monotonic()

        try:
            schema = self._registry.get_or_raise(entity)
        except ValueError as e:
            return Response.error_response(
                error_code=404,
                error_message=str(e),
                operation="create",
                entity=entity,
            )

        try:
            validated_data = schema.validate_data(data)
        except Exception as e:
            return Response.error_response(
                error_code=422,
                error_message=f"Validation error: {e}",
                operation="create",
                entity=entity,
            )

        fields = schema.get_insert_fields()
        all_fields = list(schema.get_field_names())
        field_names = [f for f in all_fields if f in fields and f in validated_data]

        if not field_names:
            return Response.error_response(
                error_code=422,
                error_message="No fields to insert",
                operation="create",
                entity=entity,
            )

        placeholders = [f":{name}" for name in field_names]
        sql = f"""
            INSERT INTO "{entity}" ({", ".join(f'"{f}"' for f in field_names)})
            VALUES ({", ".join(placeholders)})
            RETURNING {", ".join(f'"{f}"' for f in all_fields)}
        """

        params = {name: validated_data.get(name) for name in field_names}
        result = await self.db.execute(channel, sql, params)
        elapsed = (time.monotonic() - start_time) * 1000

        return self._handle_db_result(
            result=result,
            operation="create",
            entity=entity,
            column_names=all_fields,
            execution_time_ms=elapsed,
        )
