"""Модуль валидации конфигурации и подключения к БД.

Проверяет все компоненты инфраструктуры до запуска приложения.
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass


@dataclass
class CheckResult:
    status: str  # "ok", "warn", "fail"
    message: str


def validate_env_file(env_file: str = ".infra.env") -> list[CheckResult]:
    """Проверяет наличие и читаемость .infra.env файла."""
    results = []
    path = Path(env_file)

    if not path.exists():
        results.append(CheckResult("fail", f"Файл {env_file} не найден"))
        return results

    results.append(CheckResult("ok", f"Файл {env_file} найден"))

    try:
        content = path.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
        results.append(CheckResult("ok", f"Содержит {len(lines)} переменных"))
    except Exception as e:
        results.append(CheckResult("fail", f"Ошибка чтения {env_file}: {e}"))

    return results


def validate_db_urls(env_file: str = ".infra.env") -> list[CheckResult]:
    """Проверяет наличие DB_URL и DB_URL_ASYNC."""
    from infrastructure.config_loader import load_dotenv

    load_dotenv(env_file)
    results = []

    db_url = os.getenv("DB_URL")
    db_url_async = os.getenv("DB_URL_ASYNC")

    if db_url:
        results.append(CheckResult("ok", f"DB_URL задан: {db_url[:50]}..."))
    else:
        results.append(CheckResult("fail", "DB_URL не задан (нужен для миграций)"))

    if db_url_async:
        results.append(CheckResult("ok", f"DB_URL_ASYNC задан: {db_url_async[:50]}..."))
    else:
        results.append(CheckResult("fail", "DB_URL_ASYNC не задан (нужен для работы)"))

    return results


def validate_db_connectivity(env_file: str = ".infra.env") -> list[CheckResult]:
    """Проверяет подключение к БД."""
    from infrastructure.config_loader import load_dotenv

    load_dotenv(env_file)
    results = []
    db_url_async = os.getenv("DB_URL_ASYNC")

    if not db_url_async:
        results.append(CheckResult("fail", "Пропуск проверки БД: DB_URL_ASYNC не задан"))
        return results

    try:
        import psycopg

        db_url_sync = os.getenv("DB_URL", "")
        sync_url = db_url_sync.replace("+asyncpg", "").replace("+psycopg", "")
        if not sync_url:
            sync_url = db_url_async.replace("+asyncpg", "")

        with psycopg.connect(sync_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            results.append(CheckResult("ok", "PostgreSQL доступен (sync)"))
    except ImportError:
        results.append(CheckResult("warn", "psycopg не установлен — пропуск sync-проверки"))
    except Exception as e:
        results.append(CheckResult("fail", f"PostgreSQL недоступен: {e}"))

    return results


def validate_models(models_path: str = "models.py") -> list[CheckResult]:
    """Проверяет наличие models.py и функции get_all_schemas()."""
    results = []
    path = Path(models_path)

    if not path.exists():
        results.append(CheckResult("fail", f"{models_path} не найден"))
        return results

    results.append(CheckResult("ok", f"{models_path} найден"))

    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("models_check", str(path.absolute()))
        module = importlib.util.module_from_spec(spec)
        sys.modules["models_check"] = module
        spec.loader.exec_module(module)

        if hasattr(module, "get_all_schemas"):
            schemas = module.get_all_schemas()
            results.append(CheckResult("ok", f"get_all_schemas() → {len(schemas)} таблиц"))
        else:
            results.append(CheckResult("fail", "Отсутствует get_all_schemas()"))
    except Exception as e:
        results.append(CheckResult("fail", f"Ошибка загрузки models.py: {e}"))

    return results


def validate_alembic(alembic_dir: str = "alembic") -> list[CheckResult]:
    """Проверяет наличие папки alembic."""
    path = Path(alembic_dir)

    if not path.exists():
        return [CheckResult("fail", f"Папка {alembic_dir}/ не найдена")]

    required = ["env.py", "script.py.mako"]
    missing = [f for f in required if not (path / f).exists()]

    if missing:
        return [CheckResult("warn", f"В {alembic_dir}/ отсутствуют: {', '.join(missing)}")]

    return [CheckResult("ok", f"Папка {alembic_dir}/ настроена корректно")]


def validate_all(
    env_file: str = ".infra.env",
    models_path: str = "models.py",
    alembic_dir: str = "alembic",
) -> list[CheckResult]:
    """Запускает все проверки и возвращает общий результат."""
    results = []

    results.extend(validate_env_file(env_file))
    results.extend(validate_db_urls(env_file))
    results.extend(validate_db_connectivity(env_file))
    results.extend(validate_models(models_path))
    results.extend(validate_alembic(alembic_dir))

    return results
