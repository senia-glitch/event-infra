"""Тесты инфраструктурного слоя."""

import os
import sys
from pathlib import Path

from infrastructure.db_migrator import run_migration
from infrastructure.event_infrastructure import create_pipeline, shutdown_pipeline
from infrastructure.event_infrastructure.config import CacheConfig, ChannelConfig

__all__ = [
    "run_migration",
    "create_pipeline",
    "shutdown_pipeline",
    "ChannelConfig",
    "CacheConfig",
]

_TEST_DIR = str(Path(__file__).parent)


def _load_test_db_url() -> str | None:
    """Читает TEST_DB_URL_ASYNC из переменной окружения или .infra.env."""
    url = os.getenv("TEST_DB_URL_ASYNC")
    if url:
        return url

    for env_file in (Path.cwd() / ".infra.env", Path(__file__).parent.parent.parent / ".infra.env"):
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("TEST_DB_URL_ASYNC="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def run_tests(verbose: bool = False) -> bool:
    """Запуск тестов через pytest."""
    import subprocess

    test_db_url = _load_test_db_url()
    if not test_db_url:
        print("TEST_DB_URL_ASYNC не задан — тесты пропущены.")
        print("Добавьте TEST_DB_URL_ASYNC=postgresql+asyncpg://user:pass@localhost/db в .infra.env")
        return True

    env = os.environ.copy()
    env["TEST_DB_URL_ASYNC"] = test_db_url

    result = subprocess.run(
        [sys.executable, "-m", "pytest", _TEST_DIR, "-v" if verbose else "-q"],
        env=env,
    )
    return result.returncode == 0
