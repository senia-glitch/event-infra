"""Унифицированный формат ответов."""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ErrorInfo:
    """Информация об ошибке."""
    code: int
    message: str


@dataclass
class MetaInfo:
    """Мета-информация об операции."""
    entity: Optional[str] = None
    operation: str = ""
    affected_rows: int = 0
    execution_time_ms: float = 0.0


@dataclass
class Response:
    """Универсальный ответ."""
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    count: int = 0
    error: Optional[ErrorInfo] = None
    meta: MetaInfo = field(default_factory=MetaInfo)
    
    @classmethod
    def success_response(
        cls,
        data: List[Dict[str, Any]],
        operation: str,
        entity: Optional[str] = None,
        affected_rows: int = 0,
        execution_time_ms: float = 0.0
    ) -> "Response":
        """Создаёт успешный ответ."""
        return cls(
            success=True,
            data=data,
            count=len(data),
            meta=MetaInfo(
                entity=entity,
                operation=operation,
                affected_rows=affected_rows or len(data),
                execution_time_ms=execution_time_ms
            )
        )
    
    @classmethod
    def error_response(
        cls,
        error_code: int,
        error_message: str,
        operation: str,
        entity: Optional[str] = None,
        execution_time_ms: float = 0.0
    ) -> "Response":
        """Создаёт ответ с ошибкой."""
        return cls(
            success=False,
            data=None,
            count=0,
            error=ErrorInfo(code=error_code, message=error_message),
            meta=MetaInfo(
                entity=entity,
                operation=operation,
                execution_time_ms=execution_time_ms
            )
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует ответ в словарь."""
        result = {
            "success": self.success,
            "data": self.data,
            "count": self.count,
            "meta": {
                "entity": self.meta.entity,
                "operation": self.meta.operation,
                "affected_rows": self.meta.affected_rows,
                "execution_time_ms": self.meta.execution_time_ms
            }
        }
        if self.error:
            result["error"] = {
                "code": self.error.code,
                "message": self.error.message
            }
        else:
            result["error"] = None
        return result