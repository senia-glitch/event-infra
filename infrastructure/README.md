# infrastructure

Инфраструктурный слой проекта. Содержит независимые блоки:

- `db_migrator` — утилита миграций PostgreSQL
- `event_infrastructure` — асинхронная инфраструктура (пулы, очереди, CRUD)
- `tests` — тесты всех компонентов

## Структура

```
infrastructure/
├── __init__.py              # Пакет, __version__
├── cli.py                   # Точки входа CLI (infra init/validate/monitor/reset/test/cheat)
├── config_loader.py         # Загрузка .env, load_config_from_env()
├── monitor.py               # HTTP-мониторинг
├── validator.py             # Валидация конфигурации и подключения к БД
├── db_migrator/             # Миграции через Alembic
├── event_infrastructure/    # Ядро: пулы, очереди, CRUD
├── templates/               # Шаблоны для infra-init
└── tests/                   # pytest-тесты
```

## CRUD: важные особенности

### Поля с `default=None` и `primary_key=True` исключаются из INSERT

`_detect_exclude_fields()` добавляет в `exclude_from_insert` только primary key поля с `default=None` (auto-generate ID). Поля с `default_factory` (например `datetime.now`) НЕ исключаются — Pydantic вычисляет значение, и оно попадает в SQL-запрос.

### JSON-поля через `router.custom()` требуют `json.dumps`

```python
await router.custom("INSERT INTO t (data) VALUES (:d)", {"d": json.dumps([1, 2])}, channel="write")
```

### asyncpg.Row — не словарь

`custom()` возвращает `[{"row": <asyncpg.Row>}]`. Для доступа по имени колонки:

```python
row = result.data[0]["row"]
d = dict(row._mapping)
```

### Пагинация через `router.list()`

```python
# Получить 10 записей со страницы 2, отсортированных по name
result = await router.list(
    "users",
    limit=10,
    offset=10,
    order_by="name",
    order_desc=False,
    filters={"status": "active"},
)
print(result.data)  # список словарей
print(result.meta.affected_rows)  # общее количество записей (без учёта limit/offset)
```
