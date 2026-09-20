"""Модели для health-check ответов."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict


class HealthStatus(str, Enum):
    """Статус здоровья инфраструктуры."""

    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass
class ComponentHealth:
    """Состояние одного компонента (канал, пул)."""

    name: str
    healthy: bool
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Структурированный результат health-check.

    Стабильный публичный контракт для health-роутов, Kubernetes
    и мониторинга. Формат ответа:

        {
            "status": "ok" | "degraded" | "down",
            "checks": {
                "database": {"status": "ok", "channels": {"read": true, ...}},
                "pools": {"read": {"healthy": true}, ...},
                "queues": {"read": {"size": 0, "accepting": true}, ...},
                "cache": {"status": "ok", "size": 42}
            },
            "uptime_seconds": 123.45,
            "message": ""
        }
    """

    status: HealthStatus
    checks: Dict[str, Any] = field(default_factory=dict)
    uptime_seconds: float = 0.0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует ответ в словарь для сериализации."""
        result: Dict[str, Any] = {
            "status": self.status.value,
            "checks": self.checks,
            "uptime_seconds": self.uptime_seconds,
        }
        if self.message:
            result["message"] = self.message
        return result


__all__ = [
    "HealthStatus",
    "ComponentHealth",
    "HealthCheckResult",
]
