# event_infrastructure

Асинхронная инфраструктура для PostgreSQL. Пулы соединений, очереди задач, универсальный CRUD на основе SQLModel-схем.

## Архитектура

```
config/models.py       PipelineConfig, ChannelConfig, RetryConfig, CacheConfig
db/
  pools.py             PoolManager — пулы соединений (asyncpg)
  queues.py            QueueManager — очереди asyncio.Queue + SQLTask
  dispatcher.py        Dispatcher — N корутин-обработчиков на канал
  orchestrator.py      Orchestrator — фасад над pools/queues/dispatchers
  models.py            TaskResult, ChannelMetrics, InfrastructureMetrics
router/
  router.py            EventRouter — единый публичный интерфейс
  response.py          Response, ErrorInfo, MetaInfo
  cache.py             MemoryCache
  operations/          CreateOp, ReadOp, UpdateOp, DeleteOp, CustomOp
  schemas/             EntitySchema, EntityRegistry
pipeline.py            create_pipeline(), shutdown_pipeline()
```

## Установка

```bash
pip install sqlalchemy asyncpg sqlmodel
```

## Использование

### Создание pipeline

```python
from infrastructure.event_infrastructure import create_pipeline, shutdown_pipeline
from infrastructure.event_infrastructure.config import ChannelConfig, RetryConfig, CacheConfig

router = await create_pipeline(
    db_url="postgresql+asyncpg://user:pass@localhost:5432/db",
    channels={
        "read": ChannelConfig(pool_size=20, max_overflow=10, queue_maxsize=500),
        "write": ChannelConfig(pool_size=10, max_overflow=5, queue_maxsize=200),
        "admin": ChannelConfig(pool_size=2, max_overflow=0, queue_maxsize=50),
    },
    schemas={"user": User, "post": Post},
    exclude_tables={"alembic_version"},
    pool_timeout=30,
    default_timeout=30.0,
    max_concurrency=100,
    retry=RetryConfig(max_retries=3, delay_seconds=0.5, backoff_multiplier=2.0),
    cache=CacheConfig(enabled=True, ttl_seconds=60.0),
    shutdown_timeout=10.0,
)
```

### CRUD

```python
result = await router.create("user", {"name": "Alice", "email": "a@mail.com", "age": 25}, channel="write")
result = await router.read("user", 1, channel="read")
result = await router.update("user", 1, {"age": 26}, channel="write")
result = await router.delete("user", 1, channel="write")
```

### Произвольный SQL

```python
result = await router.execute("read", 'SELECT * FROM "user" WHERE age > :min', {"min": 18})
result = await router.custom('SELECT COUNT(*) FROM "user"', channel="read")
```

### Health Check

```python
health = await router.health_check()
# {"alive": True, "db_connected": True, "pools": {"read": True, ...}, "channels": {...}}
```

### Метрики

```python
router.print_metrics(full=True)
router.print_metrics(full=False)
metrics = router.get_metrics()
```

### Shutdown

```python
await shutdown_pipeline(router, timeout=10.0)
```

## Конфигурация

### ChannelConfig

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| pool_size | int | 10 | Базовый размер пула |
| max_overflow | int | 5 | Доп. соединения при пике |
| queue_maxsize | int | 1000 | Макс. размер очереди задач |
| workers | int | 0 | Воркеров на канал (0 = pool_size) |

### RetryConfig

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| max_retries | int | 3 | Число повторных попыток |
| delay_seconds | float | 0.5 | Начальная задержка |
| backoff_multiplier | float | 2.0 | Множитель задержки |
| max_total_timeout | float | 0.0 | Общий таймаут (0 = без ограничений) |

### CacheConfig

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| enabled | bool | False | Включить кеш |
| ttl_seconds | float | 60.0 | Время жизни записи |
| max_size | int | 1000 | Макс. записей |

### PipelineConfig

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| pool_recycle | int | 3600 | Пересоздание соединений (сек) |
| pool_pre_ping | bool | True | Проверка соединения |
| pool_timeout | int | 30 | Таймаут ожидания соединения |
| default_timeout | float | 30.0 | Таймаут выполнения задачи |
| max_concurrency | int | 200 | Макс. одновременных операций |
| shutdown_timeout | float | 10.0 | Таймаут graceful shutdown |
| metrics_enabled | bool | True | Сбор метрик |

## Соединения с БД

- `pool_pre_ping=True` — проверка соединения перед использованием
- `pool_recycle=3600` — пересоздание соединений каждый час
- Автоматическое переподключение при обрывах
- Каждый канал имеет независимый пул

## Ограничения

- Только PostgreSQL (драйвер asyncpg)
- Одна БД на инстанс
- FIFO очереди без приоритетов
- Нет шардирования/репликации
