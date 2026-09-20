"""Типизированные исключения для ошибок БД.

Иерархия исключений, которые event-infra бросает вместо пробрасывания
сырых asyncpg/SQLAlchemy исключений. Сценарий ловит конкретный класс
и переводит его в appropriate HTTP-статус:

    except UniqueConstraintError:
        return ConflictError(409)
    except ForeignKeyError:
        return ValidationError(422)

Исключения НЕ должны содержать детали asyncpg — это граница ответственности
инфраструктурного слоя.
"""


class InfrastructureError(Exception):
    """Базовое исключение инфраструктуры event-infra."""

    def __init__(self, message: str = "", detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(message)


class DatabaseError(InfrastructureError):
    """Базовое исключение ошибок БД."""


class UniqueConstraintError(DatabaseError):
    """Нарушение уникального ограничения (UNIQUE constraint).

    HTTP-статус: 409 Conflict.
    Пример: попытка создать пользователя с уже существующим email.
    """


class ForeignKeyError(DatabaseError):
    """Нарушение внешнего ключа (FOREIGN KEY constraint).

    HTTP-статус: 422 Unprocessable Entity.
    Пример: создание записи со ссылкой на несуществующую сущность.
    """


class DatabaseDataError(DatabaseError):
    """Ошибка данных (неверный тип, нарушение CHECK constraint).

    HTTP-статус: 422 Unprocessable Entity.
    Пример: вставка строки в числовое поле.
    """


class DatabaseConnectionError(DatabaseError):
    """Ошибка соединения с БД.

    HTTP-statuses: 503 Service Unavailable.
    Пример: БД недоступна, пул соединений исчерпан.
    """


class QueryTimeoutError(DatabaseError):
    """Таймаут выполнения запроса.

    HTTP-статус: 408 Request Timeout.
    Пример: запрос выполнялся дольше установленного лимита.
    """


class PipelineError(InfrastructureError):
    """Ошибка инфраструктурного pipeline."""


class ChannelError(InfrastructureError):
    """Ошибка конкретного канала (не найден, завершает работу)."""


class ValidationError(InfrastructureError):
    """Ошибка валидации данных (на уровне инфраструктуры)."""


__all__ = [
    "InfrastructureError",
    "DatabaseError",
    "UniqueConstraintError",
    "ForeignKeyError",
    "DatabaseDataError",
    "DatabaseConnectionError",
    "QueryTimeoutError",
    "PipelineError",
    "ChannelError",
    "ValidationError",
]
