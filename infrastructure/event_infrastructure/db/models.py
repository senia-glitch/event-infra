"""Модели данных для результатов и метрик."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TaskResult:
    """Результат выполнения SQL-запроса."""
    success: bool
    data: Any = None
    error_code: int = 0
    error_message: str = ""


@dataclass
class ChannelMetrics:
    """Метрики одного канала."""
    name: str = ""
    queue_size: int = 0
    queue_maxsize: int = 0
    active_workers: int = 0
    pool_size: int = 0
    tasks_processed: int = 0
    tasks_failed: int = 0
    avg_time_ms: float = 0.0
    last_error: str = ""


@dataclass
class InfrastructureMetrics:
    """Общие метрики инфраструктуры."""
    channels: dict[str, ChannelMetrics] = field(default_factory=dict)
    uptime_seconds: float = 0.0
    total_processed: int = 0
    total_failed: int = 0
    total_queued: int = 0
    is_accepting: bool = True
    start_time: float = 0.0