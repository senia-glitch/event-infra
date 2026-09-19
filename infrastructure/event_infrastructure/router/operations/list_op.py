"""Операция получения списка записей с пагинацией."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..schemas.registry import EntityRegistry
from ..response import Response
from .base import BaseOperation

if TYPE_CHECKING:
    from infrastructure.event_infrastructure.db.orchestrator import Orchestrator


class ListOperation(BaseOperation):
    """Получение списка записей с поддержкой пагинации, сортировки и фильтрации."""

    def __init__(self, db: "Orchestrator", registry: EntityRegistry):
        super().__init__(db)
        self._registry = registry

    async def execute(
        self,
        entity: str,
        channel: str = "read",
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Response:
        start_time = time.monotonic()

        try:
            schema = self._registry.get_or_raise(entity)
        except ValueError as e:
            return Response.error_response(
                error_code=404,
                error_message=str(e),
                operation="list",
                entity=entity,
            )

        all_fields = list(schema.get_field_names())
        select_clause = ", ".join(f'"{f}"' for f in all_fields)

        where_clause = ""
        params: Dict[str, Any] = {}
        if filters:
            conditions = []
            for col, val in filters.items():
                if col not in all_fields:
                    return Response.error_response(
                        error_code=422,
                        error_message=f"Поле '{col}' не существует в схеме '{entity}'",
                        operation="list",
                        entity=entity,
                    )
                param_name = f"filter_{col}"
                conditions.append(f'"{col}" = :{param_name}')
                params[param_name] = val
            where_clause = "WHERE " + " AND ".join(conditions)

        order_clause = ""
        if order_by:
            if order_by not in all_fields:
                return Response.error_response(
                    error_code=422,
                    error_message=f"Поле '{order_by}' не существует в схеме '{entity}'",
                    operation="list",
                    entity=entity,
                )
            direction = "DESC" if order_desc else "ASC"
            order_clause = f'ORDER BY "{order_by}" {direction}'

        limit = max(0, min(limit, 10000))
        offset = max(0, offset)

        sql = f"""
            SELECT {select_clause}
            FROM "{entity}"
            {where_clause}
            {order_clause}
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = limit
        params["offset"] = offset

        result = await self.db.execute(channel, sql, params)
        elapsed = (time.monotonic() - start_time) * 1000

        count_sql = f'SELECT COUNT(*) FROM "{entity}" {where_clause}'
        count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
        count_result = await self.db.execute(channel, count_sql, count_params)
        total_count = 0
        if count_result.success and count_result.data:
            total_count = count_result.data[0][0]

        response = self._handle_db_result(
            result=result,
            operation="list",
            entity=entity,
            column_names=all_fields,
            execution_time_ms=elapsed,
        )

        if response.success:
            response.meta.affected_rows = total_count

        return response
