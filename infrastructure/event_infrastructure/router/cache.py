"""In-memory кеш для ответов."""

import logging
import time
from collections import OrderedDict
from typing import Optional
from .response import Response

logger = logging.getLogger(__name__)


class MemoryCache:
    """In-memory кеш с TTL и ограничением размера.

    Использует OrderedDict для O(1) eviction при превышении max_size.
    """

    def __init__(self, ttl: float = 60.0, max_size: int = 1000):
        self._cache: OrderedDict[str, tuple[float, Response]] = OrderedDict()
        self._ttl = ttl
        self._max_size = max_size

    def get(self, key: str) -> Optional[Response]:
        """Возвращает ответ из кеша, если он есть и не просрочен."""
        if key in self._cache:
            ts, response = self._cache[key]
            age = time.monotonic() - ts
            if age < self._ttl:
                self._cache.move_to_end(key)
                return response
            del self._cache[key]
        return None

    def set(self, key: str, response: Response) -> None:
        """Сохраняет ответ в кеш."""
        if key in self._cache:
            del self._cache[key]
        elif len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
        self._cache[key] = (time.monotonic(), response)

    def invalidate(self, key: str) -> None:
        """Удаляет запись из кеша."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Очищает весь кеш."""
        self._cache.clear()
        logger.debug("Кеш очищен")

    @property
    def size(self) -> int:
        return len(self._cache)
