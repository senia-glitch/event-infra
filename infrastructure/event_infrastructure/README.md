```markdown
# event_infrastructure

Асинхронная инфраструктура для PostgreSQL. Пулы соединений, очереди задач, универсальный CRUD на основе SQLModel-схем.

## Архитектура

```
config/models.py       PipelineConfig, ChannelConfig, RetryConfig
db/
  pools.py             PoolManager — пулы соединений (asyncpg)
  queues.py            QueueManager — очереди asyncio.Queue + SQLTask
  dispatcher.py        Dispatcher — N корутин-обработчиков на канал
  orchestrator.py      Orchestrator — фасад над pools/queues/dispatchers
  models.py            TaskResult, ChannelMetrics, InfrastructureMetrics
router/
  router.py            EventRouter — единый публичный интерфейс
  response.py          Response, ErrorInfo, MetaInfo
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
from event_infrastructure import create_pipeline, shutdown_pipeline
from event_infrastructure.config import ChannelConfig, RetryConfig

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

Канал указывается явно. По умолчанию: `create/update/delete` → `"write"`, `read` → `"read"`.

### Произвольный SQL

```python
result = await router.execute("read", "SELECT * FROM \"user\" WHERE age > :min", {"min": 18})
result = await router.custom("SELECT COUNT(*) FROM \"user\"", channel="read")
```

`execute()` и `custom()` отличаются только реализацией — оба выполняют SQL в указанном канале, оба возвращают Response.

### Повторные попытки (retry)

Глобально при создании:

```python
router = await create_pipeline(..., retry=RetryConfig(max_retries=5, delay_seconds=1.0))
```

Per-call (переопределяет глобальный):

```python
result = await router.create("user", data, retry=RetryConfig(max_retries=2))
result = await router.read("user", 1, retry=RetryConfig(max_retries=0))  # без ретраев
```

Ретраятся: `connection refused`, `timeout`, `deadlock`, `serialization error`, `server closed`. Не ретраятся: ошибки валидации, синтаксиса, уникальности.

### Health Check

```python
alive = await router.is_alive()           # bool
health = await router.health_check()      # dict
```

`health_check()` возвращает:
```python
{
    "alive": True,
    "db_connected": True,
    "uptime_seconds": 120.5,
    "channels": {
        "read": {"active_workers": 20, "pool_size": 20, "queue_size": 0},
        ...
    },
    "error": None
}
```

### Метрики

```python
router.print_metrics(full=True)   # полные: с детализацией по каналам
router.print_metrics(full=False)  # минимальные: uptime, processed, failed
metrics = router.get_metrics()    # InfrastructureMetrics dataclass
```

### Shutdown

```python
await shutdown_pipeline(router, timeout=10.0)
```

Порядок: прекращается приём новых задач → pending задачи дорабатываются → закрываются все пулы.

## Response

Все методы возвращают Response:
```python
{
    "success": True,
    "data": [{"id": 1, "name": "Alice"}],
    "count": 1,
    "error": None,
    "meta": {
        "entity": "user",
        "operation": "create",
        "affected_rows": 1,
        "execution_time_ms": 1.2,
        "retries": 0
    }
}
```

При ошибке: `success=False`, `data=None`, `error={"code": 100, "message": "..."}`.

## Конфигурация

### ChannelConfig

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| pool_size | int | 10 | Базовый размер пула |
| max_overflow | int | 5 | Доп. соединения при пике |
| queue_maxsize | int | 1000 | Макс. размер очереди задач |

### RetryConfig

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| max_retries | int | 3 | Число повторных попыток |
| delay_seconds | float | 0.5 | Начальная задержка |
| backoff_multiplier | float | 2.0 | Множитель задержки |

### PipelineConfig

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| pool_recycle | int | 3600 | Пересоздание соединений (сек) |
| pool_pre_ping | bool | True | Проверка соединения перед использованием |
| pool_timeout | int | 30 | Таймаут ожидания соединения из пула |
| default_timeout | float | 30.0 | Таймаут выполнения задачи |
| max_concurrency | int | 100 | Макс. одновременных операций |
| shutdown_timeout | float | 10.0 | Таймаут graceful shutdown |

## Соединения с БД

- `pool_pre_ping=True` — перед каждым использованием соединения выполняется `SELECT 1`
- `pool_recycle=3600` — соединения принудительно пересоздаются каждый час
- При обрыве asyncpg + SQLAlchemy переподключаются автоматически
- Каждый канал имеет независимый пул соединений

## Ограничения

- Только PostgreSQL (драйвер asyncpg)
- Одна БД на инстанс
- FIFO очереди без приоритетов
- Нет шардирования/репликации на уровне инфраструктуры
```