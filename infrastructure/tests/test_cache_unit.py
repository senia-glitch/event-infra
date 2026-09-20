"""Unit-тесты для MemoryCache."""

import time
from infrastructure.event_infrastructure.router.cache import MemoryCache
from infrastructure.event_infrastructure.router.response import Response


class TestMemoryCache:
    def test_get_miss(self):
        cache = MemoryCache(ttl=1.0, max_size=10)
        assert cache.get("missing") is None

    def test_set_and_get_hit(self):
        cache = MemoryCache(ttl=10.0, max_size=10)
        resp = Response.success_response(data=[{"id": 1}], operation="test")
        cache.set("key1", resp)
        result = cache.get("key1")
        assert result is resp
        assert cache.size == 1

    def test_get_expired(self):
        cache = MemoryCache(ttl=0.0, max_size=10)
        resp = Response.success_response(data=[], operation="test")
        cache.set("key1", resp)
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_set_evicts_oldest(self):
        cache = MemoryCache(ttl=10.0, max_size=2)
        r1 = Response.success_response(data=[], operation="test")
        r2 = Response.success_response(data=[], operation="test")
        r3 = Response.success_response(data=[], operation="test")
        cache.set("a", r1)
        cache.set("b", r2)
        cache.set("c", r3)
        assert cache.size == 2
        assert cache.get("a") is None
        assert cache.get("b") is not None
        assert cache.get("c") is not None

    def test_set_overwrite(self):
        cache = MemoryCache(ttl=10.0, max_size=10)
        r1 = Response.success_response(data=[{"x": 1}], operation="test")
        r2 = Response.success_response(data=[{"x": 2}], operation="test")
        cache.set("key", r1)
        cache.set("key", r2)
        assert cache.size == 1
        assert cache.get("key") is r2

    def test_invalidate(self):
        cache = MemoryCache(ttl=10.0, max_size=10)
        resp = Response.success_response(data=[], operation="test")
        cache.set("key", resp)
        cache.invalidate("key")
        assert cache.get("key") is None

    def test_invalidate_missing_key(self):
        cache = MemoryCache(ttl=10.0, max_size=10)
        cache.invalidate("nonexistent")

    def test_clear(self):
        cache = MemoryCache(ttl=10.0, max_size=10)
        cache.set("a", Response.success_response(data=[], operation="t"))
        cache.set("b", Response.success_response(data=[], operation="t"))
        cache.clear()
        assert cache.size == 0

    def test_size_property(self):
        cache = MemoryCache(ttl=10.0, max_size=5)
        assert cache.size == 0
        cache.set("a", Response.success_response(data=[], operation="t"))
        assert cache.size == 1
