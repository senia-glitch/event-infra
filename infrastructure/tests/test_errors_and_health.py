"""Unit-тесты для типизированных ошибок БД и health-check."""

import pytest

from infrastructure.event_infrastructure.db.dispatcher import _classify_db_error
from infrastructure.event_infrastructure.db.models import TaskResult
from infrastructure.event_infrastructure.router.response import Response
from infrastructure.event_infrastructure.router.health import HealthCheckResult, HealthStatus
from infrastructure.event_infrastructure.exceptions import (
    InfrastructureError,
    DatabaseError,
    UniqueConstraintError,
    ForeignKeyError,
    DatabaseDataError,
    DatabaseConnectionError,
    QueryTimeoutError,
)


# ================================================================
# 1. Тесты _classify_db_error
# ================================================================


class TestClassifyDbError:
    """Тесты классификации ошибок БД."""

    def test_unique_violation(self):
        from sqlalchemy.exc import IntegrityError

        exc = IntegrityError("INSERT", {}, Exception('duplicate key value violates unique constraint "users_email_key"'))
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "unique_constraint"
        assert error_code == 409
        assert http_status == 409

    def test_foreign_key_violation(self):
        from sqlalchemy.exc import IntegrityError

        exc = IntegrityError(
            "INSERT",
            {},
            Exception('insert or update on table "posts" violates foreign key constraint "posts_author_id_fkey"'),
        )
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "foreign_key"
        assert error_code == 422
        assert http_status == 422

    def test_check_violation(self):
        from sqlalchemy.exc import IntegrityError

        exc = IntegrityError("INSERT", {}, Exception('new row violates check constraint "age_check"'))
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "check_violation"
        assert error_code == 422
        assert http_status == 422

    def test_generic_integrity_error(self):
        from sqlalchemy.exc import IntegrityError

        exc = IntegrityError("INSERT", {}, Exception("some other integrity error"))
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "integrity_error"
        assert error_code == 422
        assert http_status == 422

    def test_data_error(self):
        from sqlalchemy.exc import DataError

        exc = DataError("SELECT", {}, Exception("invalid input syntax for type integer"))
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "data_error"
        assert error_code == 422
        assert http_status == 422

    def test_operational_timeout(self):
        from sqlalchemy.exc import OperationalError

        exc = OperationalError("SELECT", {}, Exception("timeout expired"))
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "query_timeout"
        assert error_code == 408
        assert http_status == 408

    def test_operational_connection_error(self):
        from sqlalchemy.exc import OperationalError

        exc = OperationalError("SELECT", {}, Exception("could not connect to server"))
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "connection_error"
        assert error_code == 503
        assert http_status == 503

    def test_interface_error(self):
        from sqlalchemy.exc import InterfaceError

        exc = InterfaceError("connection closed", None, None)
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "connection_error"
        assert error_code == 503
        assert http_status == 503

    def test_programming_error(self):
        from sqlalchemy.exc import ProgrammingError

        exc = ProgrammingError("SELECT", {}, Exception("relation does not exist"))
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "syntax_error"
        assert error_code == 400
        assert http_status == 400

    def test_generic_exception(self):
        exc = ValueError("some random error")
        error_type, error_code, http_status = _classify_db_error(exc)
        assert error_type == "unknown_error"
        assert error_code == 500
        assert http_status == 500


# ================================================================
# 2. Тесты TaskResult с error_type
# ================================================================


class TestTaskResultErrorType:
    """Тесты что TaskResult корректно хранит error_type."""

    def test_success_result(self):
        result = TaskResult(success=True, data=[(1,)])
        assert result.error_type is None

    def test_error_result_with_type(self):
        result = TaskResult(
            success=False,
            error_code=409,
            error_message="unique violation",
            error_type="unique_constraint",
        )
        assert result.error_type == "unique_constraint"
        assert result.error_code == 409

    def test_error_result_without_type(self):
        result = TaskResult(success=False, error_code=500, error_message="error")
        assert result.error_type is None


# ================================================================
# 3. Тесты Response с error.type
# ================================================================


class TestResponseErrorType:
    """Тесты что Response корректно пробрасывает error.type."""

    def test_error_response_with_type(self):
        resp = Response.error_response(
            error_code=409,
            error_message="duplicate email",
            operation="create",
            error_type="unique_constraint",
        )
        assert resp.error is not None
        assert resp.error.type == "unique_constraint"
        assert resp.error.code == 409

    def test_error_response_without_type(self):
        resp = Response.error_response(
            error_code=500,
            error_message="error",
            operation="create",
        )
        assert resp.error is not None
        assert resp.error.type == "unknown_error"

    def test_to_dict_includes_type(self):
        resp = Response.error_response(
            error_code=409,
            error_message="duplicate",
            operation="create",
            error_type="unique_constraint",
        )
        d = resp.to_dict()
        assert d["error"]["type"] == "unique_constraint"
        assert d["error"]["code"] == 409

    def test_to_dict_no_error(self):
        resp = Response.success_response(data=[], operation="test")
        d = resp.to_dict()
        assert d["error"] is None


# ================================================================
# 4. Тесты HealthCheckResult
# ================================================================


class TestHealthCheckResult:
    """Тесты структурированного health-check."""

    def test_ok_status(self):
        result = HealthCheckResult(
            status=HealthStatus.OK,
            checks={"database": {"status": "ok"}},
            uptime_seconds=100.0,
        )
        d = result.to_dict()
        assert d["status"] == "ok"
        assert d["uptime_seconds"] == 100.0
        assert "message" not in d

    def test_degraded_status(self):
        result = HealthCheckResult(
            status=HealthStatus.DEGRADED,
            checks={"database": {"status": "degraded"}},
            uptime_seconds=50.0,
            message="1/2 channels healthy",
        )
        d = result.to_dict()
        assert d["status"] == "degraded"
        assert d["message"] == "1/2 channels healthy"

    def test_down_status(self):
        result = HealthCheckResult(
            status=HealthStatus.DOWN,
            checks={"database": {"status": "down"}},
            uptime_seconds=0.0,
            message="All channels are unavailable",
        )
        d = result.to_dict()
        assert d["status"] == "down"

    def test_health_status_enum_values(self):
        assert HealthStatus.OK.value == "ok"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.DOWN.value == "down"


# ================================================================
# 5. Тесты исключений
# ================================================================


class TestExceptions:
    """Тесты иерархии исключений."""

    def test_inheritance(self):
        assert issubclass(UniqueConstraintError, DatabaseError)
        assert issubclass(ForeignKeyError, DatabaseError)
        assert issubclass(DatabaseDataError, DatabaseError)
        assert issubclass(DatabaseConnectionError, DatabaseError)
        assert issubclass(QueryTimeoutError, DatabaseError)
        assert issubclass(DatabaseError, InfrastructureError)
        assert issubclass(InfrastructureError, Exception)

    def test_exception_message(self):
        exc = UniqueConstraintError("duplicate email", detail="users_email_key")
        assert exc.message == "duplicate email"
        assert exc.detail == "users_email_key"
        assert str(exc) == "duplicate email"

    def test_exception_catch_as_database_error(self):
        with pytest.raises(DatabaseError):
            raise UniqueConstraintError("test")

    def test_exception_catch_as_infrastructure_error(self):
        with pytest.raises(InfrastructureError):
            raise DatabaseConnectionError("db down")
