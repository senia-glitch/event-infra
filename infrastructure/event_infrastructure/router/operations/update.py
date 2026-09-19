"""Операция обновления записи."""

from __future__ import annotations

import time
from typing import Any, Dict, TYPE_CHECKING

from ..schemas.registry import EntityRegistry
from ..response import Response
from .base import BaseOperation

if TYPE_CHECKING:
    from infrastructure.event_infrastructure.db.orchestrator import Orchestrator


class UpdateOperation(BaseOperation):
    """Обновление записи по ID."""

    def __init__(self, db: "Orchestrator", registry: EntityRegistry):
        super().__init__(db)
        self._registry = registry

    async def execute(self, entity: str, id: Any, data: Dict[str, Any], channel: str = "write") -> Response:
        start_time = time.monotonic()

        try:
            schema = self._registry.get_or_raise(entity)
        except ValueError as e:
            return Response.error_response(
                error_code=404,
                error_message=str(e),
                operation="update",
                entity=entity,
            )

        pk = schema.primary_key
        all_fields = list(schema.get_field_names())
        update_fields = schema.get_update_fields()
        existing_fields = set(data.keys())
        fields_to_update = [f for f in all_fields if f in update_fields and f in existing_fields]

        if not fields_to_update:
            return Response.error_response(
                error_code=422,
                error_message="No fields to update",
                operation="update",
                entity=entity,
            )

        set_clause = ", ".join([f'"{name}" = :{name}' for name in fields_to_update])
        returning_clause = ", ".join(f'"{f}"' for f in all_fields)

        sql = f"""
            UPDATE "{entity}"
            SET {set_clause}
            WHERE "{pk}" = :{pk}
            RETURNING {returning_clause}
        """

        params = {name: data.get(name) for name in fields_to_update}
        params[pk] = id

        result = await self.db.execute(channel, sql, params)
        elapsed = (time.monotonic() - start_time) * 1000

        return self._handle_db_result(
            result=result,
            operation="update",
            entity=entity,
            column_names=all_fields,
            execution_time_ms=elapsed,
        )
