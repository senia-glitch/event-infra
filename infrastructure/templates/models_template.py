"""SQLModel-модели для инфраструктурного слоя.

Добавьте свои таблицы ниже. Каждая модель должна:
- Иметь __tablename__
- Иметь primary key (id или кастомный)
- Быть зарегистрирована в get_all_schemas()

Примеры:
    class User(SQLModel, table=True):
        __tablename__ = "users"
        id: Optional[int] = Field(default=None, primary_key=True)
        name: str

    class Post(SQLModel, table=True):
        __tablename__ = "posts"
        id: Optional[int] = Field(default=None, primary_key=True)
        user_id: int = Field(foreign_key="users.id")
        title: str
"""

from datetime import datetime
from typing import List, Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import JSON

metadata = SQLModel.metadata


# ============================================================
# ПРИМЕРЫ МОДЕЛЕЙ (удалите и замените на свои)
# ============================================================


class User(SQLModel, table=True):
    """Пользователь системы."""

    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, unique=True)
    email: str = Field(max_length=255, unique=True)
    full_name: Optional[str] = Field(default=None, max_length=255)
    # default_factory — Pydantic вычислит значение и подставит в INSERT автоматически
    created_at: Optional[datetime] = Field(default_factory=datetime.now)


class Post(SQLModel, table=True):
    """Публикация пользователя."""

    __tablename__ = "posts"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    title: str = Field(max_length=255)
    body: Optional[str] = None
    # JSON-поле — работает автоматически через sa_type=JSON
    tags: Optional[List[str]] = Field(default=None, sa_type=JSON)


# ============================================================
# АВТОМАТИЧЕСКАЯ РЕГИСТРАЦИЯ
# ============================================================


def get_all_schemas():
    """Возвращает все SQLModel-таблицы как dict {"tablename": Model}."""
    import sys

    module = sys.modules[__name__]
    schemas = {}
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, SQLModel) and attr != SQLModel and hasattr(attr, "__table__"):
            schemas[attr.__tablename__] = attr
    return schemas
