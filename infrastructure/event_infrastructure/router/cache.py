"""In-memory кеш для ответов."""

import time
from typing import Optional
from .response import Response


class MemoryCache:
    """Простой in-memory кеш с TTL и ограничением размера."""
    
    def __init__(self, ttl: float = 60.0, max_size: int = 1000):
        self._cache: dict[str, tuple[float, Response]] = {}
        self._ttl = ttl
        self._max_size = max_size
    
    def get(self, key: str) -> Optional[Response]:
        """Возвращает ответ из кеша, если он есть и не просрочен."""
        if key in self._cache:
            ts, response = self._cache[key]
            age = time.monotonic() - ts
            if age < self._ttl:
                # print(f"CACHE HIT: key={key}, age={age:.3f}s, ttl={self._ttl}s")
                return response
            del self._cache[key]
        return None
    
    def set(self, key: str, response: Response):
        """Сохраняет ответ в кеш."""
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]
        self._cache[key] = (time.monotonic(), response)
    
    def invalidate(self, key: str):
        """Удаляет запись из кеша."""
        self._cache.pop(key, None)
    
    def clear(self):
        """Очищает весь кеш."""
        self._cache.clear()
    
    @property
    def size(self) -> int:
        return len(self._cache)