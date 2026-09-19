# Changelog

## 0.2.0 — 2026-09-19

### Added
- `MemoryCache` с TTL + LRU eviction (алгоритм LRU для вытеснения при переполнении)
- Кеш работает только для SELECT-запросов, автоматически инвалидируется при INSERT/UPDATE/DELETE
- `RETRY_MAX_TOTAL_TIMEOUT` — общий таймаут всех повторных попыток
- `RETRY_ON_TIMEOUT` — настройка retry при timeout (по умолчанию False для мутаций, True для read)
- `EXCLUDE_TABLES` — настраиваемый список игнорируемых таблиц
- `schemas_fn` — поддержка кастомной функции для загрузки схем
- `start_infrastructure()` — полная конфигурация через env variables
- CLI команды: `infra-init`, `infra-monitor`, `infra-reset`, `infra` (главная точка входа)
- Мониторинг в реальном времени через `infra-monitor`
- Health check через `router.health_check()`
- Метрики: `router.get_metrics()`, `router.print_metrics()`
- **Пагинация** — `router.list()` с limit, offset, order_by, filters
- **Кастомные primary key** — автоопределение PK из SQLModel-схемы
- **Graceful shutdown** — drain-фаза, resolve futures при отмене, параллельная остановка диспетчеров
- `py.typed` — маркер для type stubs

### Fixed
- `SQLTask._future` теперь ленивый — нет падений вне async-контекста
- `Dispatcher._run()` логирует traceback при необработанных исключениях
- `QueueManager` валидирует имена каналов при `put()`
- `PoolManager.get()` выбрасывает `ValueError` для неизвестных каналов
- Логи диспетчеров теперь на уровне WARNING (не INFO)
- `_detect_exclude_fields` — `default_factory` больше не исключается из INSERT
- `_is_retryable_error` — timeout не ретраится для create/update/delete по умолчанию
- `create_pipeline(channels=None)` — используется default_factory из PipelineConfig
- Graceful shutdown — futures резолвятся при отмене, клиент не зависает
- Все логи на русском языке

### Changed
- Python 3.10+ (обновлено с 3.9+)
- README полностью переписан: быстрый старт, конфигурация, API reference, troubleshooting
- `load_dotenv()` теперь принимает параметр `override` для явного управления приоритетом env vars
- `create_pipeline()` — явные параметры `retry` и `cache` вместо скрытых через `**kwargs`
- `Orchestrator.execute()` — применяет `default_timeout` из конфига, если timeout не указан явно
- Shutdown диспетчеров теперь параллельный

### Removed
- Старые тесты (`test_db/`, `test_router/`) — заменены на pytest

## 0.1.0 — 2026-09-15

### Added
- Начальная версия инфраструктурного пакета
- Alembic миграции через `db_migrator`
- Async SQLAlchemy пулы с retry
- Event Router: CRUD операции + произвольный SQL
- Диспетчер задач с автоматическим распределением нагрузки
- Конфигурация через `.infra.env`
