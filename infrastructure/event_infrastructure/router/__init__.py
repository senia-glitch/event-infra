"""Универсальный маршрутизатор событий."""

from .router import EventRouter
from .response import Response, ErrorInfo, MetaInfo
from .schemas import EntitySchema, EntityRegistry

__all__ = [
    "EventRouter",
    "Response",
    "ErrorInfo",
    "MetaInfo",
    "EntitySchema",
    "EntityRegistry",
]