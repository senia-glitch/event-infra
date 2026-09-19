"""Операция удаления записи."""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

from ..schemas.registry import EntityRegistry
from ..response import Response
from .base import BaseOperation

if TYPE_CHECKING:
    from infrastructure.event_infrastructure.db.orchestrator import Orchestrator


class DeleteOperation(BaseOperation):
    """Удаление записи по ID."""

    def __init__(self, db: "Orchestrator", registry: EntityRegistry):
        super().__init__(db)
        self._registry = registry

    async def execute(self, entity: str, id: Any, channel: str = "write") -> Response:
        start_time = time.monotonic()

        try:
            schema = self._registry.get_or_raise(entity)
        except ValueError as e:
            return Response.error_response(
                error_code=404,
                error_message=str(e),
                operation="delete",
                entity=entity,
            )

        pk = schema.primary_key

        sql = f"""
            DELETE FROM "{entity}"
            WHERE "{pk}" = :{pk}
            RETURNING "{pk}"
        """

        result = await self.db.execute(channel, sql, {pk: id})
        elapsed = (time.monotonic() - start_time) * 1000

        if result.success and result.data:
            data = [{pk: row[0]} for row in result.data]
            return Response.success_response(
                data=data,
                operation="delete",
                entity=entity,
                affected_rows=len(data),
                execution_time_ms=elapsed,
            )
        elif result.success:
            return Response.success_response(
                data=[],
                operation="delete",
                entity=entity,
                affected_rows=0,
                execution_time_ms=elapsed,
            )
        else:
            return Response.error_response(
                error_code=result.error_code or 500,
                error_message=result.error_message or "Delete failed",
                operation="delete",
                entity=entity,
                execution_time_ms=elapsed,
            )
