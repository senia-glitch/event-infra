"""Автономная асинхронная инфраструктура для PostgreSQL + SQLModel.

Предоставляет:
- Настраиваемые каналы (read/write/admin + любые свои)
- Универсальный CRUD на основе SQLModel-схем
- Интеграцию с db_migrator (единый источник истины)
"""

from .pipeline import create_pipeline, shutdown_pipeline
from .router.router import EventRouter

__all__ = ["create_pipeline", "shutdown_pipeline", "EventRouter"]