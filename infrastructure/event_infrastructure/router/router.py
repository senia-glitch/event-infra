"""Универсальный маршрутизатор событий с автоматической регистрацией сущностей."""

import asyncio
import dataclasses
import logging
import time
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, Optional, Set, Type

from sqlmodel import SQLModel

from infrastructure.event_infrastructure.db import Orchestrator, InfrastructureMetrics
from .schemas import EntitySchema, EntityRegistry
from .operations import (
    CreateOperation,
    ReadOperation,
    UpdateOperation,
    DeleteOperation,
    CustomOperation,
    ListOperation,
)
from .response import Response
from .cache import MemoryCache
from .health import HealthCheckResult, HealthStatus
from ..config.models import RetryConfig, CacheConfig

logger = logging.getLogger(__name__)


class EventRouter:
    """Единый интерфейс для всех операций с БД.

    Все методы принимают channel — явное указание канала.
    Все методы возвращают Response.

    Поддерживает:
    - CRUD операции (create, read, update, delete) через EntityRegistry
    - Произвольные SQL-запросы (execute, custom)
    - Повторные попытки (retry) при ошибках соединения
    - Кеширование (cache) с настраиваемым TTL
    - Health check с проверкой пулов
    - Сбор метрик по каналам

    Пример использования:
        router = await create_pipeline(db_url="...", channels={...}, schemas={...})
        result = await router.create("users", {"name": "Alice"}, channel="write")
        health = await router.health_check()
        await router.shutdown()
    """

    def __init__(
        self,
        orchestrator: Orchestrator,
        schemas: Dict[str, Type[SQLModel]],
        exclude_tables: Optional[Set[str]] = None,
        default_timeout: float = 30.0,
        metrics_enabled: bool = True,
        max_concurrency: int = 100,
        retry: Optional[RetryConfig] = None,
        cache: Optional[CacheConfig] = None,
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
            primary_key = self._detect_primary_key(schema)

            self._registry.register(
                EntitySchema(
                    table_name=table_name,
                    schema=schema,
                    primary_key=primary_key,
                    exclude_from_insert=exclude_insert,
                    exclude_from_update=exclude_update,
                )
            )

        logger.info(
            "Зарегистрировано %d сущностей: %s",
            len(self._registry.get_all()),
            ", ".join(self._registry.get_all().keys()),
        )

        self._create_op = CreateOperation(self._db, self._registry)
        self._read_op = ReadOperation(self._db, self._registry)
        self._update_op = UpdateOperation(self._db, self._registry)
        self._delete_op = DeleteOperation(self._db, self._registry)
        self._custom_op = CustomOperation(self._db)
        self._list_op = ListOperation(self._db, self._registry)

    def _detect_exclude_fields(self, schema: Type[SQLModel]) -> tuple[Set[str], Set[str]]:
        """Определяет поля, исключаемые из INSERT и UPDATE.

        INSERT: только primary key с default=None (auto-generate ID).
                default_factory НЕ исключается — Pydantic вычислит значение
                и оно должно попасть в SQL-запрос.
        UPDATE: только primary key поля (по признаку primary_key=True)
        """
        from pydantic_core import PydanticUndefined

        exclude_insert: Set[str] = set()
        exclude_update: Set[str] = set()

        for field_name, field_info in schema.model_fields.items():
            is_pk = getattr(field_info, "primary_key", None) is True

            is_auto_id = is_pk and field_info.default is None and field_info.default is not PydanticUndefined
            if is_auto_id:
                exclude_insert.add(field_name)

            if is_pk:
                exclude_update.add(field_name)

        return exclude_insert, exclude_update

    @staticmethod
    def _detect_primary_key(schema: Type[SQLModel]) -> str:
        """Определяет имя primary key поля из SQLModel-схемы.

        Ищет поле с primary_key=True. Если не найдено — возвращает 'id'.
        """
        for field_name, field_info in schema.model_fields.items():
            if getattr(field_info, "primary_key", None) is True:
                return field_name
        return "id"

    async def _execute_with_semaphore(self, coro: Coroutine) -> Response:
        if self._semaphore:
            async with self._semaphore:
                return await coro
        return await coro

    def _is_retryable_error(self, error_message: str, config: RetryConfig) -> bool:
        retryable = ["connection", "deadlock", "serialization", "server closed", "connection was closed"]
        if config.retry_on_timeout:
            retryable.append("timeout")
        msg_lower = error_message.lower()
        return any(keyword in msg_lower for keyword in retryable)

    async def _with_retry(
        self,
        coro: Callable[[], Coroutine],
        retry_config: Optional[RetryConfig] = None,
    ) -> Response:
        rc = retry_config or self._retry
        last_response = None
        delay = rc.delay_seconds
        total_start = time.monotonic()

        for attempt in range(rc.max_retries + 1):
            try:
                response = await coro()
            except Exception as e:
                logger.exception("Неперехваченное исключение в _with_retry (попытка %d): %s", attempt, e)
                last_response = Response.error_response(
                    error_code=500,
                    error_message=str(e),
                    operation=last_response.meta.operation if last_response else "unknown",
                )
                if attempt < rc.max_retries:
                    if rc.max_total_timeout > 0:
                        elapsed = time.monotonic() - total_start
                        if elapsed + delay >= rc.max_total_timeout:
                            break
                    logger.debug(
                        "Повтор %d/%d (исключение) через %.2fs", attempt + 1, rc.max_retries, delay
                    )
                    await asyncio.sleep(delay)
                    delay *= rc.backoff_multiplier
                else:
                    break
                continue

            if response.success:
                response.meta.retries = attempt
                return response

            last_response = response

            if attempt < rc.max_retries and self._is_retryable_error(
                response.error.message if response.error else "", rc
            ):
                if rc.max_total_timeout > 0:
                    elapsed = time.monotonic() - total_start
                    if elapsed + delay >= rc.max_total_timeout:
                        break
                logger.debug(
                    "Повтор %d/%d для %s через %.2fs", attempt + 1, rc.max_retries, response.meta.operation, delay
                )
                await asyncio.sleep(delay)
                delay *= rc.backoff_multiplier
            else:
                break

        if last_response:
            last_response.meta.retries = attempt
            return last_response
        return Response.error_response(
            error_code=500,
            error_message="Unknown error: no response from operation",
            operation="unknown",
        )

    def _cache_key(self, entity: str, id: Any) -> str:
        return f"{entity}:{id}"

    # ================================================================
    # CRUD
    # ================================================================

    async def create(
        self,
        entity: str,
        data: Dict[str, Any],
        channel: str = "write",
        retry: Optional[RetryConfig] = None,
        cache: Optional[bool] = None,
    ) -> Response:
        """Создание записи в таблице.

        Args:
            entity: Имя таблицы (зарегистрированной схемы)
            data: Словарь {имя_поля: значение} для INSERT
            channel: Канал для выполнения запроса
            retry: Кастомная конфигурация повторных попыток
            cache: Включить кеш (None = по умолчанию из конфига)

        Returns:
            Response с созданными данными (включая сгенерированный ID)
        """
        async def _do() -> Response:
            return await self._create_op.execute(entity, data, channel)

        return await self._execute_with_semaphore(self._with_retry(_do, retry))

    async def read(
        self,
        entity: str,
        id: int,
        channel: str = "read",
        retry: Optional[RetryConfig] = None,
        cache: Optional[bool] = None,
    ) -> Response:
        """Чтение записи по ID.

        Args:
            entity: Имя таблицы
            id: Значение primary key
            channel: Канал для выполнения запроса
            retry: Кастомная конфигурация повторных попыток
            cache: Включить кеш (None = по умолчанию из конфига)

        Returns:
            Response с найденной записью или ошибкой 404
        """
        use_cache = cache if cache is not None else (self._cache is not None)

        if use_cache and self._cache:
            cached = self._cache.get(self._cache_key(entity, id))
            if cached is not None:
                return cached

        base_retry = retry or self._retry
        read_retry = dataclasses.replace(base_retry, retry_on_timeout=True)

        async def _do() -> Response:
            return await self._read_op.execute(entity, id, channel)

        response = await self._execute_with_semaphore(self._with_retry(_do, read_retry))

        if response.success and use_cache and self._cache:
            self._cache.set(self._cache_key(entity, id), response)

        return response

    async def update(
        self,
        entity: str,
        id: int,
        data: Dict[str, Any],
        channel: str = "write",
        retry: Optional[RetryConfig] = None,
        cache: Optional[bool] = None,
    ) -> Response:
        """Обновление записи по ID.

        Args:
            entity: Имя таблицы
            id: Значение primary key
            data: Словарь {имя_поля: значение} для UPDATE
            channel: Канал для выполнения запроса
            retry: Кастомная конфигурация повторных попыток
            cache: Включить кеш (None = по умолчанию из конфига)

        Returns:
            Response с обновлёнными данными
        """
        async def _do() -> Response:
            return await self._update_op.execute(entity, id, data, channel)

        response = await self._execute_with_semaphore(self._with_retry(_do, retry))

        if response.success and self._cache and cache is not False:
            self._cache.invalidate(self._cache_key(entity, id))

        return response

    async def delete(
        self,
        entity: str,
        id: int,
        channel: str = "write",
        retry: Optional[RetryConfig] = None,
        cache: Optional[bool] = None,
    ) -> Response:
        """Удаление записи по ID.

        Args:
            entity: Имя таблицы
            id: Значение primary key
            channel: Канал для выполнения запроса
            retry: Кастомная конфигурация повторных попыток
            cache: Включить кеш (None = по умолчанию из конфига)

        Returns:
            Response с подтверждением удаления
        """
        async def _do() -> Response:
            return await self._delete_op.execute(entity, id, channel)

        response = await self._execute_with_semaphore(self._with_retry(_do, retry))

        if response.success and self._cache and cache is not False:
            self._cache.invalidate(self._cache_key(entity, id))

        return response

    async def custom(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        channel: str = "read",
        retry: Optional[RetryConfig] = None,
    ) -> Response:
        """Произвольный SQL-запрос (прямой доступ к БД).

        Args:
            sql: SQL-запрос с named parameters (:param_name)
            params: Словарь параметров для запроса
            channel: Канал для выполнения
            retry: Кастомная конфигурация повторных попыток

        Returns:
            Response с результатом запроса
        """
        async def _do() -> Response:
            return await self._custom_op.execute(sql, params, channel)

        return await self._execute_with_semaphore(self._with_retry(_do, retry))

    async def execute(
        self,
        channel: str,
        sql: str,
        params: Optional[dict] = None,
        retry: Optional[RetryConfig] = None,
    ) -> Response:
        """SQL-запрос через очередь канала.

        Отличие от custom(): запрос проходит через очередь диспетчера,
        что обеспечивает соблюдение лимитов concurrency.

        Args:
            channel: Имя канала (read/write/admin)
            sql: SQL-запрос с named parameters (:param_name)
            params: Словарь параметров
            retry: Кастомная конфигурация повторных попыток

        Returns:
            Response с результатом (data = [{"row": asyncpg.Row}, ...])
        """
        t0 = time.monotonic()

        async def _do() -> Response:
            result = await self._db.execute(channel, sql, params)
            dt = (time.monotonic() - t0) * 1000

            if result.success:
                data = [{"row": row} for row in (result.data or [])]
                return Response.success_response(data=data, operation="execute", execution_time_ms=dt)
            return Response.error_response(
                error_code=result.error_code,
                error_message=result.error_message,
                operation="execute",
                execution_time_ms=dt,
            )

        return await self._execute_with_semaphore(self._with_retry(_do, retry))

    # ================================================================
    # List (пагинация)
    # ================================================================

    async def list(
        self,
        entity: str,
        channel: str = "read",
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        filters: Optional[Dict[str, Any]] = None,
        retry: Optional[RetryConfig] = None,
    ) -> Response:
        """Получение списка записей с пагинацией.

        Args:
            entity: Имя таблицы
            channel: Канал для выполнения запроса
            limit: Максимальное количество записей (0-10000, по умолчанию 100)
            offset: Смещение от начала (для пагинации)
            order_by: Поле для сортировки
            order_desc: Сортировка по убыванию
            filters: Словарь фильтров {"field": value}
            retry: Конфигурация повторных попыток
        """

        async def _do() -> Response:
            return await self._list_op.execute(
                entity=entity,
                channel=channel,
                limit=limit,
                offset=offset,
                order_by=order_by,
                order_desc=order_desc,
                filters=filters,
            )

        return await self._execute_with_semaphore(self._with_retry(_do, retry))

    # ================================================================
    # Health Check
    # ================================================================

    async def health_check(self) -> dict:
        """Проверка работоспособности всех каналов и пулов.

        Проверяет БД напрямую через PoolManager (без очереди).

        Returns:
            Словарь: alive, db_connected, pools, uptime_seconds, channels, cache_size, error
        """
        result: dict[str, Any] = {
            "alive": True,
            "db_connected": False,
            "pools": {},
            "uptime_seconds": 0.0,
            "channels": {},
            "cache_size": 0,
            "error": None,
        }

        # Проверка БД напрямую через PoolManager (без очереди — без задержек)
        try:
            pool_health = await self._db.health_check()
            result["pools"] = pool_health
            result["db_connected"] = any(pool_health.values())
            result["alive"] = result["db_connected"]
        except Exception as e:
            result["alive"] = False
            result["error"] = str(e)
            result["pools"] = {name: False for name in self._db.channel_names}

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
        """Быстрая проверка доступности БД.

        Returns:
            True если хотя бы один пул подключён к БД
        """
        try:
            pool_health = await self._db.health_check()
            return any(pool_health.values())
        except Exception:
            return False

    async def health(self) -> HealthCheckResult:
        """Стабильный публичный контракт health-check.

        Возвращает структурированный объект со статусом и компонентами:
        - status: "ok" | "degraded" | "down"
        - checks: {database: {...}, pools: {...}, queues: {...}, cache: {...}}
        - uptime_seconds: float

        Статус:
        - ok: все каналы здоровы
        - degraded: хотя бы один канал недоступен
        - down: ни один канал не доступен

        Returns:
            HealthCheckResult со статусом и деталями компонентов
        """
        checks: dict[str, Any] = {}

        # Проверка БД через PoolManager
        try:
            pool_health = await self._db.health_check()
        except Exception as e:
            pool_health = {name: False for name in self._db.channel_names}
            checks["database"] = {"status": "down", "error": str(e)}

        healthy_count = sum(1 for v in pool_health.values() if v)
        total_count = len(pool_health)

        if "database" not in checks:
            if healthy_count == total_count:
                checks["database"] = {"status": "ok"}
            elif healthy_count > 0:
                checks["database"] = {"status": "degraded"}
            else:
                checks["database"] = {"status": "down"}

        checks["pools"] = {
            name: {"healthy": healthy, "channel": name}
            for name, healthy in pool_health.items()
        }

        # Метрики каналов
        m = self._db.get_metrics()
        checks["queues"] = {}
        for name, ch in m.channels.items():
            checks["queues"][name] = {
                "size": ch.queue_size,
                "maxsize": ch.queue_maxsize,
                "accepting": m.is_accepting,
                "active_workers": ch.active_workers,
                "pool_size": ch.pool_size,
            }

        # Кеш
        if self._cache:
            checks["cache"] = {"status": "ok", "size": self._cache.size}
        else:
            checks["cache"] = {"status": "disabled"}

        # Определение общего статуса
        if healthy_count == 0:
            status = HealthStatus.DOWN
            message = "All channels are unavailable"
        elif healthy_count < total_count:
            status = HealthStatus.DEGRADED
            message = f"{healthy_count}/{total_count} channels healthy"
        else:
            status = HealthStatus.OK
            message = ""

        return HealthCheckResult(
            status=status,
            checks=checks,
            uptime_seconds=m.uptime_seconds,
            message=message,
        )

    # ================================================================
    # Метрики и статистика
    # ================================================================

    def get_metrics(self) -> "InfrastructureMetrics":
        """Получение метрик инфраструктуры.

        Returns:
            InfrastructureMetrics с uptime, processed, failed, queued, channels
        """
        return self._db.get_metrics()

    def print_metrics(self, full: bool = False) -> None:
        """Вывод метрик в stdout.

        Args:
            full: Если True — детализация по каждому каналу
        """
        m = self._db.get_metrics()
        server_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "",
            "=" * 60,
            f"  СЕРВЕРНОЕ ВРЕМЯ: {server_time}",
            f"  UPTIME: {m.uptime_seconds:.1f}s",
            f"  ВСЕГО ОБРАБОТАНО: {m.total_processed}",
            f"  ОШИБОК: {m.total_failed}",
            f"  В ОЧЕРЕДЯХ: {m.total_queued}",
            f"  ПРИНИМАЕТ ЗАДАЧИ: {'Да' if m.is_accepting else 'Нет'}",
            f"  ЗАРЕГИСТРИРОВАНО СУЩНОСТЕЙ: {len(self._registry.get_all())}",
        ]
        if self._cache:
            lines.append(f"  КЕШ: {self._cache.size} записей")

        if full:
            lines.append("")
            lines.append("  ДЕТАЛИЗАЦИЯ ПО КАНАЛАМ:")
            for name, ch in m.channels.items():
                lines.append("")
                lines.append(f"  [{name.upper()}]")
                lines.append(f"    Pool:       {ch.active_workers}/{ch.pool_size} workers")
                lines.append(f"    Queue:      {ch.queue_size}/{ch.queue_maxsize}")
                lines.append(f"    Processed:  {ch.tasks_processed}")
                lines.append(f"    Failed:     {ch.tasks_failed}")
                lines.append(f"    Avg time:   {ch.avg_time_ms:.2f}ms")
                if ch.last_error:
                    lines.append(f"    Last error: {ch.last_error[:80]}")

        lines.append("=" * 60)
        lines.append("")
        logger.info("\n".join(lines))

    def get_registry(self) -> Dict[str, EntitySchema]:
        """Получение реестра зарегистрированных сущностей.

        Returns:
            Словарь {"table_name": EntitySchema}
        """
        return self._registry.get_all()

    def has_entity(self, name: str) -> bool:
        """Проверка наличия зарегистрированной сущности.

        Args:
            name: Имя таблицы

        Returns:
            True если сущность зарегистрирована
        """
        return self._registry.has(name)

    async def shutdown(self, timeout: Optional[float] = None) -> None:
        """Graceful shutdown инфраструктуры.

        Фаза 1: drain — ожидание завершения текущих задач.
        Фаза 2: resolve — задачи в очереди получают ошибку 503.
        Фаза 3: cancel — отмена воркеров и закрытие пулов.

        Args:
            timeout: Общий таймаут shutdown (сек). None = из конфига.
        """
        await self._db.shutdown(timeout)

    async def __aenter__(self) -> "EventRouter":
        """Вход в async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Выход из async context manager — автоматический shutdown."""
        await self.shutdown()
        return False
