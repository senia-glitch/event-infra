"""Операция выполнения произвольного SQL."""

from typing import Dict, Any, Optional
import time

from ..response import Response
from .base import BaseOperation


class CustomOperation(BaseOperation):
    """Выполнение произвольного SQL."""
    
    async def execute(self, sql: str, params: Optional[Dict[str, Any]] = None, channel: str = "read") -> Response:
        start_time = time.monotonic()
        params = params or {}
        
        result = await self.db.execute(channel, sql, params)
        elapsed = (time.monotonic() - start_time) * 1000
        
        if result.success:
            data = []
            if result.data:
                data = [{"row": row} for row in result.data]
            
            return Response.success_response(
                data=data, operation="custom", entity=None,
                affected_rows=len(data) if data else 0, execution_time_ms=elapsed
            )
        else:
            return Response.error_response(
                error_code=result.error_code or 100,
                error_message=result.error_message or "Custom query failed",
                operation="custom", execution_time_ms=elapsed
            )