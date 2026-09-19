"""Базовый класс для всех операций."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..response import Response

if TYPE_CHECKING:
    from infrastructure.event_infrastructure.db import Orchestrator, TaskResult


class BaseOperation(ABC):
    """Базовый класс для операций."""

    def __init__(self, db: "Orchestrator"):
        self.db = db

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Response:
        """Выполняет операцию."""
        pass

    def _handle_db_result(
        self,
        result: "TaskResult",
        operation: str,
        entity: Optional[str] = None,
        column_names: Optional[List[str]] = None,
        execution_time_ms: float = 0.0,
    ) -> Response:
        """Обрабатывает результат и возвращает унифицированный ответ."""
        if result.success:
            data: List[Dict[str, Any]] = []
            if result.data:
                if column_names:
                    data = [dict(zip(column_names, row)) for row in result.data]
                else:
                    data = [{"row": row} for row in result.data]

            return Response.success_response(
                data=data,
                operation=operation,
                entity=entity,
                affected_rows=len(data) if data else 0,
                execution_time_ms=execution_time_ms,
            )
        else:
            return Response.error_response(
                error_code=result.error_code or 500,
                error_message=result.error_message or "Unknown error",
                operation=operation,
                entity=entity,
                execution_time_ms=execution_time_ms,
            )
