# event-infra

Инфраструктурный слой для проектов на PostgreSQL + SQLModel.
Поставляется как устанавливаемый Python-пакет. Обеспечивает миграции, асинхронный доступ к БД с пулами соединений, очередями задач, универсальным CRUD, кешированием и мониторингом.

## Шпаргалка (30 секунд)

```bash
pip install git+https://github.com/senia-glitch/event-infra.git  # установка
infra init                        # создать models.py, run_infrastructure.py, .infra.env, alembic/
infra validate                    # проверить конфигурацию и БД
infra cheat                       # показать шпаргалку в терминале
```

```python
# Быстрый старт — context manager, всё работает
from infrastructure.event_infrastructure import create_pipeline

router = await create_pipeline(
    db_url="postgresql+asyncpg://user:pass@localhost/db",
    channels={"read": ..., "write": ...},
    schemas={"users": User},
)
async with router:
    await router.create("users", {"name": "Alice"})      # CREATE
    await router.read("users", 1)                          # READ
    await router.update("users", 1, {"name": "Bob"})      # UPDATE
    await router.delete("users", 1)                        # DELETE
    await router.list("users", limit=10, offset=0)         # LIST с пагинацией
    await router.custom("SELECT count(*) FROM users")      # произвольный SQL
    await router.health_check()                             # health: dict
    await router.get_metrics()                              # метрики
```

| API | Описание |
|-----|----------|
| `router.create(entity, data)` | Создание записи |
| `router.read(entity, id)` | Чтение по ID |
| `router.update(entity, id, data)` | Обновление по ID |
| `router.delete(entity, id)` | Удаление по ID |
| `router.list(entity, limit, offset, order_by, filters)` | Пагинация + фильтры |
| `router.execute(channel, sql, params)` | SQL через очередь |
| `router.custom(sql, params)` | SQL напрямую |
| `router.health_check()` | Проверка всех каналов |
| `router.get_metrics()` | Метрики + uptime |
| `router.shutdown()` | Graceful остановка |

| CLI | Описание |
|-----|----------|
| `infra init [-y]` | Инициализация проекта (с подтверждением) |
| `infra validate` | Проверка конфигурации |
| `infra monitor [interval]` | Мониторинг в реальном времени |
| `infra reset <db_url> [-y]` | Полный сброс БД (с подтверждением) |
| `infra test` | Запуск тестов |
| `infra cheat` | Шпаргалка в терминале |

| Конфиг (.infra.env) | По умолчанию |
|---------------------|--------------|
| `DB_URL_ASYNC` | — (обязательный) |
| `CHANNELS` | `read,write,admin` |
| `{NAME}_POOL_SIZE` | 10 |
| `CACHE_ENABLED` | False |
| `RETRY_MAX_RETRIES` | 3 |

Подробнее см. ниже.

## Возможности

- **Миграции** — автоматическое сравнение SQLModel-моделей с БД и применение изменений (на основе Alembic)
- **Асинхронная инфраструктура** — пулы соединений (asyncpg), очереди задач, диспетчеры с несколькими воркерами на канал
- **Универсальный CRUD** — создание, чтение, обновление, удаление записей на основе зарегистрированных моделей
- **Произвольные SQL-запросы** — выполнение кастомных запросов с параметрами через любой канал
- **Гибкая конфигурация** — все настройки в `.infra.env`, поддержка произвольного количества каналов
- **Кеширование** — in-memory кеш для операций чтения с настраиваемым TTL и размером
- **Повторные попытки (retry)** — автоматические ретраи при ошибках соединения с экспоненциальной задержкой
- **Мониторинг** — команды `infra monitor` и встроенные метрики
- **Graceful shutdown** — корректное завершение всех воркеров и закрытие пулов
- **Health check** — проверка работоспособности всех каналов и пулов

## Требования

- Python 3.10+
- PostgreSQL 9.6+
- Установленный пакет

## Установка

```bash
pip install git+https://github.com/senia-glitch/event-infra.git
```

## Быстрый старт

### 1. Установка и инициализация

```bash
pip install git+https://github.com/senia-glitch/event-infra.git
mkdir my_project && cd my_project
infra init
infra validate          # проверить что всё настроено
```

Будут созданы:
- `models.py` — шаблон SQLModel-моделей
- `run_infrastructure.py` — модуль с `start_infrastructure()`
- `.infra.env` — файл конфигурации
- `alembic/` — папка для миграций

### 2. Настройка БД

Отредактируйте `.infra.env`:

```env
DB_URL=postgresql+psycopg://postgres:123@localhost:5432/mydb
DB_URL_ASYNC=postgresql+asyncpg://postgres:123@localhost:5432/mydb
```

### 3. Кастомные primary key

Пакет автоматически определяет primary key из SQLModel-схемы. Поддерживаются любые типы PK:

```python
from sqlmodel import SQLModel, Field

# Стандартный int PK
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

# Кастомный строковый PK
class Product(SQLModel, table=True):
    sku: str = Field(primary_key=True)
    name: str

# UUID PK
class Session(SQLModel, table=True):
    uuid: str = Field(max_length=36, primary_key=True)
    data: str
```

### 4. Использование

```python
import asyncio
from infrastructure.event_infrastructure import create_pipeline
from run_infrastructure import start_infrastructure

async def main():
    # Context manager — автоматический shutdown
    router = await start_infrastructure()
    async with router:
        user = await router.create("users", {"name": "Alice"})
        data = await router.read("users", user.data[0]["id"])
        print(data.data)

    # Или вручную
    router = await start_infrastructure()
    try:
        await router.create("users", {"name": "Bob"})
    finally:
        await router.shutdown()

asyncio.run(main())
```

## Конфигурация

Все настройки хранятся в `.infra.env` (по умолчанию). Файл может включать:
- Кавычки: `KEY="value"` или `KEY='value'`
- Inline комментарии: `KEY=value # comment`
- Продолжение строк: `KEY=value\` (backslash)

### Основные параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `DB_URL` | Sync URL для миграций | — |
| `DB_URL_ASYNC` | Async URL для работы | — |
| `CHANNELS` | Список каналов через запятую | `read,write,admin` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

### Каналы

Для каждого канала `{NAME}`:

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `{NAME}_POOL_SIZE` | Размер пула | 10 |
| `{NAME}_MAX_OVERFLOW` | Доп. соединения | 5 |
| `{NAME}_QUEUE_MAXSIZE` | Макс. размер очереди | 1000 |
| `{NAME}_WORKERS` | Кол-во воркеров (0=pool_size) | 0 |

### Пулы соединений

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `POOL_RECYCLE` | Время жизни соединения (сек) | 3600 |
| `POOL_PRE_PING` | Проверка соединения | True |
| `POOL_TIMEOUT` | Таймаут ожидания (сек) | 30 |

### Retry

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `RETRY_MAX_RETRIES` | Макс. число попыток | 3 |
| `RETRY_DELAY_SECONDS` | Начальная задержка (сек) | 0.5 |
| `RETRY_BACKOFF_MULTIPLIER` | Множитель задержки | 2.0 |
| `RETRY_MAX_TOTAL_TIMEOUT` | Общий таймаут (0=без ограничений) | 0.0 |
| `RETRY_ON_TIMEOUT` | Ретраить при timeout для мутаций | False |

> **Примечание:** `read` операции всегда ретраятся при timeout (идемпотентны). Для `create`/`update`/`delete` timeout ретраится только при `RETRY_ON_TIMEOUT=true`.

### Кеш

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `CACHE_ENABLED` | Включить кеш | False |
| `CACHE_TTL_SECONDS` | Время жизни записи (сек) | 60.0 |
| `CACHE_MAX_SIZE` | Макс. записей | 1000 |

### Пример: добавление канала `report`

```env
CHANNELS=read,write,admin,report
REPORT_POOL_SIZE=5
REPORT_MAX_OVERFLOW=2
REPORT_QUEUE_MAXSIZE=100
REPORT_WORKERS=3
```

## API Reference

### EventRouter

```python
# Context manager — автоматический shutdown
router = await create_pipeline(...)
async with router:
    # CRUD
    result = await router.create(entity, data, channel="write")
    result = await router.read(entity, id, channel="read")
    result = await router.update(entity, id, data, channel="write")
    result = await router.delete(entity, id, channel="write")

    # Пагинация (поддержка кастомных primary key)
    result = await router.list(entity, channel="read", limit=100, offset=0, order_by="name", order_desc=False, filters={"status": "active"})

    # Произвольный SQL
    result = await router.execute(channel, sql, params)
    result = await router.custom(sql, params, channel="read")

    # Health check (проверяет БД напрямую через PoolManager, без очереди)
    health = await router.health_check()  # dict с "alive", "db_connected", "pools", "channels"
    alive = await router.is_alive()       # bool

    # Метрики
    metrics = router.get_metrics()        # InfrastructureMetrics
    router.print_metrics(full=True)       # вывод в stdout

# Или вручную
router = await create_pipeline(...)
try:
    await router.create(entity, data)
finally:
    await router.shutdown()
```

### Response

```python
result = await router.create("users", {"name": "Alice"})

result.success          # True/False
result.data             # [{"id": 1, "name": "Alice"}] или None
result.count            # 1
result.error            # ErrorInfo(code=422, message="...") или None
result.meta.entity      # "users"
result.meta.operation   # "create"
result.meta.affected_rows   # 1
result.meta.execution_time_ms  # 1.2
result.meta.retries     # 0
```

### PipelineConfig

```python
from infrastructure.event_infrastructure.config import PipelineConfig, ChannelConfig, RetryConfig, CacheConfig

config = PipelineConfig(
    db_url="postgresql+asyncpg://...",
    channels={"read": ChannelConfig(pool_size=20), "write": ChannelConfig(pool_size=10)},
    pool_recycle=3600,
    default_timeout=30.0,
    retry=RetryConfig(max_retries=3),
    cache=CacheConfig(enabled=True, ttl_seconds=60.0),
)
```

### start_infrastructure()

```python
from run_infrastructure import start_infrastructure

# Базовый вариант — схемы берутся из models.py
router = await start_infrastructure()

# С кастомной функцией схем
router = await start_infrastructure(schemas_fn=my_get_schemas)
```

### create_pipeline()

```python
from infrastructure.event_infrastructure import create_pipeline

router = await create_pipeline(
    db_url="postgresql+asyncpg://...",
    channels={"read": ChannelConfig(pool_size=20)},
    schemas={"users": User, "roles": Role},
    exclude_tables={"alembic_version"},
)
```

## Команды CLI

```bash
infra init [--force] [-y]         Инициализация проекта (с подтверждением)
infra validate                    Проверка конфигурации и подключения к БД
infra monitor [интервал]          Мониторинг запущенной инфраструктуры
infra reset <db_url> [-y]         Полный сброс БД (с подтверждением)
infra test [-v, --verbose]        Запуск тестов
infra cheat                       Шпаргалка по API
infra help                        Справка
```

> Флаг `-y` / `--yes` отключает интерактивное подтверждение (полезно в скриптах).

## Тестирование

```bash
# Установка тестовых зависимостей
pip install -e ".[test]"

# Запуск тестов (требуется PostgreSQL)
TEST_DB_URL_ASYNC=postgresql+asyncpg://user:pass@localhost:5432/testdb pytest
```

## Архитектура

```
infrastructure/
├── config_loader.py              # Загрузка .env, load_config_from_env()
├── cli.py                        # Точки входа CLI (init/validate/monitor/reset/test/cheat)
├── validator.py                  # Валидация конфигурации и подключения к БД
├── monitor.py                    # HTTP-мониторинг
├── event_infrastructure/
│   ├── config/models.py          # PipelineConfig, ChannelConfig, RetryConfig, CacheConfig
│   ├── db/
│   │   ├── pools.py              # PoolManager — управление пулами
│   │   ├── queues.py             # QueueManager — очереди задач
│   │   ├── dispatcher.py         # Dispatcher — N корутин на канал
│   │   ├── orchestrator.py       # Orchestrator — фасад
│   │   └── models.py             # TaskResult, ChannelMetrics, InfrastructureMetrics
│   ├── router/
│   │   ├── router.py             # EventRouter — публичный интерфейс (с context manager)
│   │   ├── response.py           # Response, ErrorInfo, MetaInfo
│   │   ├── cache.py              # MemoryCache
│   │   ├── operations/           # CreateOp, ReadOp, UpdateOp, DeleteOp, CustomOp, ListOp
│   │   └── schemas/              # EntitySchema, EntityRegistry
│   └── pipeline.py               # create_pipeline(), shutdown_pipeline()
├── db_migrator/
│   ├── core.py                   # run_migration()
│   └── reset.py                  # reset()
├── templates/                    # Шаблоны для infra-init
├── tests/                        # pytest-тесты
└── example.py                    # Полный пример всех возможностей
```

## Troubleshooting

### Ошибка "Канал 'xxx' не найден"

Убедитесь, что канал объявлен в `CHANNELS` и его имя совпадает (регистр важен).

### Ошибка "Не задан DB_URL_ASYNC"

Проверьте, что файл `.infra.env` существует и содержит `DB_URL_ASYNC=...`.

### Миграции не применяются

1. Проверьте `DB_URL` (синхронный URL для миграций)
2. Убедитесь, что PostgreSQL доступен
3. Проверьте `models.py` — должна быть функция `get_all_schemas()`

### Кеш не работает

Установите `CACHE_ENABLED=True` в `.infra.env`.

### Мониторинг не подключается

Убедитесь, что API_URL доступен (по умолчанию `http://localhost:8000`).

## Лицензия

MIT
