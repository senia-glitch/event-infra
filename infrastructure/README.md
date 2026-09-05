```markdown
## CRUD: важные особенности

### Поля с `default=None` исключаются из INSERT

`_detect_exclude_fields()` добавляет в `exclude_from_insert` все поля, у которых `default=None`. Они не попадают в `INSERT` через `router.create()`.

**Обход:** не передавать `None` в `data`, либо использовать `router.custom()` с прямым SQL.

### JSON-поля через `router.custom()` требуют `json.dumps`

```python
await router.custom(
    "INSERT INTO t (data) VALUES (:d)",
    {"d": json.dumps([1, 2])},
    channel="write"
)
```

### `asyncpg.Row` — не словарь

`custom()` возвращает `[{"row": <asyncpg.Row>}]`. Для доступа по имени колонки:

```python
row = result.data[0]["row"]
d = dict(row._mapping)
```