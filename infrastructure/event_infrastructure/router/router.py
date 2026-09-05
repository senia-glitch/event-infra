"""Универсальный маршрутизатор событий с автоматической регистрацией сущностей."""

from typing import Type, Dict, Any, Optional, Set
from sqlmodel import SQLModel
import asyncio
import time
from datetime import datetime

from infrastructure.event_infrastructure.db import Orchestrator
from .schemas import EntitySchema, EntityRegistry
from .operations import (
    CreateOperation,
    ReadOperation,
    UpdateOperation,
    DeleteOperation,
    CustomOperation,
)
from .response import Response
from .cache import MemoryCache
from ..config.models import RetryConfig, CacheConfig


class EventRouter:
    """Единый интерфейс для всех операций с БД.
    
    Все методы принимают channel — явное указание канала.
    Все методы возвращают Response.
    
    Поддерживает:
    - Повторные попытки (retry) при ошибках соединения
    - Кеширование (cache) с настраиваемым TTL
    """
    
    def __init__(
        self,
        orchestrator: Orchestrator,
        schemas: Dict[str, Type[SQLModel]],
        exclude_tables: Optional[Set[str]] = None,
        default_timeout: float = 30.0,
        metrics_enabled: bool = True,
        max_concurrency: int = 100,
        retry: RetryConfig = None,
        cache: CacheConfig = None,
    ):
        self._db = orchestrator
        self.default_timeout = default_timeout
        self.metrics_enabled = metrics_enabled
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency) if max_concurrency > 0 else None
        self._retry = retry or RetryConfig()
        
        cache_cfg = cache or CacheConfig()
        self._cache = MemoryCache(ttl=cache_cfg.ttl_seconds, max_size=cache_cfg.max_size) if cache_cfg.enabled else None
        
        self._registry = EntityRegistry()
        
        exclude = exclude_tables or set()
        for table_name, schema in schemas.items():
            if table_name in exclude:
                continue
            
            exclude_insert, exclude_update = self._detect_exclude_fields(schema)
            
            self._registry.register(EntitySchema(
                table_name=table_name,
                schema=schema,
                primary_key="id",
                exclude_from_insert=exclude_insert,
                exclude_from_update=exclude_update,
            ))
        
        print(f"Зарегистрировано сущностей: {len(self._registry.get_all())}")
        for name in self._registry.get_all().keys():
            print(f"   - {name}")
        
        self._create_op = CreateOperation(self._db, self._registry)
        self._read_op = ReadOperation(self._db, self._registry)
        self._update_op = UpdateOperation(self._db, self._registry)
        self._delete_op = DeleteOperation(self._db, self._registry)
        self._custom_op = CustomOperation(self._db)
    
    def _detect_exclude_fields(self, schema: Type[SQLModel]) -> tuple[Set[str], Set[str]]:
        exclude_insert = set()
        exclude_update = set()
        for field_name, field_info in schema.model_fields.items():
            if field_info.default is None or field_name == "id":
                exclude_insert.add(field_name)
            if field_name == "id":
                exclude_update.add(field_name)
        return exclude_insert, exclude_update
    
    async def _execute_with_semaphore(self, coro):
        if self._semaphore:
            async with self._semaphore:
                return await coro
        return await coro
    
    def _is_retryable_error(self, error_message: str) -> bool:
        retryable = ["connection", "timeout", "deadlock", "serialization", "server closed", "connection was closed"]
        msg_lower = error_message.lower()
        return any(keyword in msg_lower for keyword in retryable)
    
    async def _with_retry(self, coro, retry_config: RetryConfig = None):
        rc = retry_config or self._retry
        last_response = None
        delay = rc.delay_seconds
        
        for attempt in range(rc.max_retries + 1):
            response = await coro()
            
            if response.success:
                response.meta.retries = attempt
                return response
            
            if attempt < rc.max_retries and self._is_retryable_error(response.error.message if response.error else ""):
                last_response = response
                await asyncio.sleep(delay)
                delay *= rc.backoff_multiplier
            else:
                response.meta.retries = attempt
                return response
        
        if last_response:
            last_response.meta.retries = rc.max_retries
        return last_response
    
    def _cache_key(self, entity: str, id) -> str:
        return f"{entity}:{id}"
    
    # ================================================================
    # CRUD
    # ================================================================
    
    async def create(self, entity: str, data: Dict[str, Any], channel: str = "write",
                     retry: RetryConfig = None, cache: bool = None) -> Response:
        async def _do():
            return await self._create_op.execute(entity, data, channel)
        response = await self._execute_with_semaphore(self._with_retry(_do, retry))
        
        if response.success and self._cache and cache is not False:
            # Инвалидируем кеш для этой сущности (могла измениться)
            pass  # CREATE не инвалидирует — запись новая, кеша для неё ещё нет
        
        return response
    
    async def read(self, entity: str, id: int, channel: str = "read",
                   retry: RetryConfig = None, cache: bool = None) -> Response:
        use_cache = cache if cache is not None else (self._cache is not None)
        
        if use_cache and self._cache:
            cached = self._cache.get(self._cache_key(entity, id))
            if cached is not None:
                return cached
        
        async def _do():
            return await self._read_op.execute(entity, id, channel)
        response = await self._execute_with_semaphore(self._with_retry(_do, retry))
        
        if response.success and use_cache and self._cache:
            self._cache.set(self._cache_key(entity, id), response)
        
        return response
    
    async def update(self, entity: str, id: int, data: Dict[str, Any], channel: str = "write",
                     retry: RetryConfig = None, cache: bool = None) -> Response:
        async def _do():
            return await self._update_op.execute(entity, id, data, channel)
        response = await self._execute_with_semaphore(self._with_retry(_do, retry))
        
        if response.success and self._cache and cache is not False:
            self._cache.invalidate(self._cache_key(entity, id))
        
        return response
    
    async def delete(self, entity: str, id: int, channel: str = "write",
                     retry: RetryConfig = None, cache: bool = None) -> Response:
        async def _do():
            return await self._delete_op.execute(entity, id, channel)
        response = await self._execute_with_semaphore(self._with_retry(_do, retry))
        
        if response.success and self._cache and cache is not False:
            self._cache.invalidate(self._cache_key(entity, id))
        
        return response
    
    async def custom(self, sql: str, params: Dict[str, Any] = None, channel: str = "read",
                     retry: RetryConfig = None) -> Response:
        async def _do():
            return await self._custom_op.execute(sql, params, channel)
        return await self._execute_with_semaphore(self._with_retry(_do, retry))
    
    async def execute(self, channel: str, sql: str, params: dict = None,
                      retry: RetryConfig = None) -> Response:
        t0 = time.monotonic()
        
        async def _do():
            result = await self._db.execute(channel, sql, params)
            dt = (time.monotonic() - t0) * 1000
            
            if result.success:
                data = [{"row": row} for row in (result.data or [])]
                return Response.success_response(data=data, operation="execute", execution_time_ms=dt)
            return Response.error_response(
                error_code=result.error_code,
                error_message=result.error_message,
                operation="execute",
                execution_time_ms=dt
            )
        
        return await self._execute_with_semaphore(self._with_retry(_do, retry))
    
    # ================================================================
    # Health Check
    # ================================================================
    
    async def health_check(self) -> dict:
        result = {
            "alive": True,
            "db_connected": False,
            "uptime_seconds": 0.0,
            "channels": {},
            "cache_size": 0,
            "error": None,
        }
        
        try:
            r = await self._db.execute("admin", "SELECT 1")
            result["db_connected"] = r.success
            if not r.success:
                result["error"] = r.error_message
        except Exception as e:
            result["alive"] = False
            result["error"] = str(e)
        
        m = self._db.get_metrics()
        result["uptime_seconds"] = m.uptime_seconds
        
        for name, ch in m.channels.items():
            result["channels"][name] = {
                "active_workers": ch.active_workers,
                "pool_size": ch.pool_size,
                "queue_size": ch.queue_size,
            }
        
        if self._cache:
            result["cache_size"] = self._cache.size
        
        return result
    
    async def is_alive(self) -> bool:
        try:
            r = await self._db.execute("admin", "SELECT 1")
            return r.success
        except Exception:
            return False
    
    # ================================================================
    # Метрики и статистика
    # ================================================================
    
    def get_metrics(self):
        return self._db.get_metrics()
    
    def print_metrics(self, full: bool = False):
        m = self._db.get_metrics()
        server_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n" + "=" * 60)
        print(f"  СЕРВЕРНОЕ ВРЕМЯ: {server_time}")
        print(f"  UPTIME: {m.uptime_seconds:.1f}s")
        print(f"  ВСЕГО ОБРАБОТАНО: {m.total_processed}")
        print(f"  ОШИБОК: {m.total_failed}")
        print(f"  В ОЧЕРЕДЯХ: {m.total_queued}")
        print(f"  ПРИНИМАЕТ ЗАДАЧИ: {'Да' if m.is_accepting else 'Нет'}")
        print(f"  ЗАРЕГИСТРИРОВАНО СУЩНОСТЕЙ: {len(self._registry.get_all())}")
        if self._cache:
            print(f"  КЕШ: {self._cache.size} записей")
        
        if full:
            print("\n  ДЕТАЛИЗАЦИЯ ПО КАНАЛАМ:")
            for name, ch in m.channels.items():
                print(f"\n  [{name.upper()}]")
                print(f"    Pool:       {ch.active_workers}/{ch.pool_size} workers")
                print(f"    Queue:      {ch.queue_size}/{ch.queue_maxsize}")
                print(f"    Processed:  {ch.tasks_processed}")
                print(f"    Failed:     {ch.tasks_failed}")
                print(f"    Avg time:   {ch.avg_time_ms:.2f}ms")
                if ch.last_error:
                    print(f"    Last error: {ch.last_error[:80]}")
        
        print("=" * 60 + "\n")
    
    def get_registry(self) -> Dict[str, EntitySchema]:
        return self._registry.get_all()
    
    def has_entity(self, name: str) -> bool:
        return self._registry.has(name)
    
    async def shutdown(self, timeout: float = None):
        await self._db.shutdown(timeout)