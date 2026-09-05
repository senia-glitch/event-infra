## `db_migrator/README.md`

```markdown
# db_migrator

Автономная утилита миграций PostgreSQL. Сравнивает SQLModel-модели с реальной БД и применяет изменения.

## Требования

- Python 3.8+
- PostgreSQL
- Зависимости: `alembic`, `sqlalchemy`, `sqlmodel`, `psycopg2-binary`

```bash
pip install alembic sqlalchemy sqlmodel psycopg2-binary
```

## Внедрение в проект

1. Скопировать папку `db_migrator` в любое место проекта
2. Импортировать с учётом расположения:

```python
# если db_migrator в корне:
from db_migrator import run_migration

# если в подпапке:
from libs.db_migrator import run_migration
```

## Файл моделей

Единственный источник истины о схеме БД. Обязательно экспортировать `metadata`:

```python
from sqlmodel import SQLModel, Field

metadata = SQLModel.metadata

class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True)
```

## Использование

### Запуск миграции

```python
from db_migrator import run_migration

success = run_migration(
    db_url="postgresql://user:pass@localhost:5432/dbname",
    schema_path="./models.py"
)
```

- Есть изменения в моделях → создаст и применит миграцию
- Нет изменений → ничего не делает
- Возвращает `True` при успехе, `False` при ошибке

### Полный сброс

Удаляет все миграции, кеш и очищает БД:

```bash
python -m db_migrator.reset postgresql://user:pass@localhost:5432/dbname
```

## Перенос между проектами

Скопировать папку `db_migrator` в новый проект. Установить зависимости. Готово.

Если нужна чистая история — удалить старые миграции перед переносом:

```bash
rm db_migrator/alembic/versions/*.py
rm -rf db_migrator/alembic/versions/__pycache__
```
```