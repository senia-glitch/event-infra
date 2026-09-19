"""Модуль запуска инфраструктурного слоя.

Предоставляет функцию start_infrastructure(), которая:
1. Загружает настройки из .infra.env (или файла, указанного в INFRA_ENV_FILE).
2. Применяет миграции к БД.
3. Создаёт и запускает EventRouter.

Использование:
    from run_infrastructure import start_infrastructure

    router = await start_infrastructure()
    # работа с router
    await router.shutdown()
"""

from __future__ import annotations

import asyncio
import os
import sys
import logging
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from infrastructure.config_loader import load_config_from_env
from infrastructure.db_migrator import run_migration
from infrastructure.event_infrastructure import create_pipeline

if TYPE_CHECKING:
    from infrastructure.event_infrastructure.router.router import EventRouter


def _resolve_sync_db_url(db_url: str, driver: str) -> str:
    """Подставляет sync-драйвер в URL, если он не указан явно.

    Если db_url уже содержит схему вида postgresql+xxx://, URL возвращается как есть.
    Если db_url = postgresql://..., к нему дописывается +{driver}.
    """
    scheme, rest = db_url.split("://", 1)
    if "+" not in scheme:
        return f"{scheme}+{driver}://{rest}"
    return db_url


async def start_infrastructure(
    schemas_fn: Optional[Callable[[], dict]] = None,
) -> "EventRouter":
    """Запускает инфраструктуру и возвращает готовый EventRouter.

    Все настройки читаются из .infra.env (или файла, указанного через INFRA_ENV_FILE).
    Пути к models.py и alembic/ определяются относительно расположения этого модуля.

    Args:
        schemas_fn: Опциональная функция для получения схем.
            Если передана — используется вместо get_all_schemas() из models.py.
            Должна возвращать dict {"table_name": SQLModel_class, ...}.

    Returns:
        EventRouter: готовый к использованию роутер.

    Raises:
        RuntimeError: если не удалось применить миграции или не заданы URL БД.
    """
    # 1. Настройка логирования
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    numeric_level = getattr(logging, log_level, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 2. Загрузка конфигурации из env
    config = load_config_from_env(base_dir=Path(__file__).parent)

    if not config.db_url:
        raise RuntimeError("Не задан DB_URL_ASYNC в .infra.env")

    # 3. Определяем sync URL для миграций
    db_url_sync = os.getenv("DB_URL")
    if not db_url_sync:
        raise RuntimeError("Не задан DB_URL в .infra.env (нужен для миграций)")

    sync_driver = os.getenv("DB_SYNC_DRIVER", "psycopg")
    db_url_sync = _resolve_sync_db_url(db_url_sync, sync_driver)

    # 4. Миграции
    base_dir = Path(__file__).parent
    models_path = base_dir / "models.py"
    alembic_dir = base_dir / "alembic"

    success = run_migration(
        db_url=db_url_sync,
        schema_path=str(models_path),
        alembic_dir=str(alembic_dir),
    )
    if not success:
        raise RuntimeError("Не удалось применить миграции. Проверьте настройки БД и models.py")

    # 5. Получение схем
    if schemas_fn is not None:
        schemas = schemas_fn()
    else:
        module_name = models_path.stem
        models_module = sys.modules.get(module_name)
        if models_module is None:
            raise RuntimeError(f"Модуль {module_name} не был загружен после миграции")
        if not hasattr(models_module, "get_all_schemas"):
            raise AttributeError(f"В {models_path} отсутствует функция get_all_schemas()")
        schemas = models_module.get_all_schemas()

    # 6. Таблицы для игнорирования
    exclude_raw = os.getenv("EXCLUDE_TABLES", "alembic_version")
    exclude_tables = {t.strip() for t in exclude_raw.split(",") if t.strip()}

    # 7. Создание pipeline
    router = await create_pipeline(
        db_url=config.db_url,
        channels=config.channels,
        schemas=schemas,
        exclude_tables=exclude_tables,
        pool_recycle=config.pool_recycle,
        pool_pre_ping=config.pool_pre_ping,
        pool_timeout=config.pool_timeout,
        default_timeout=config.default_timeout,
        shutdown_timeout=config.shutdown_timeout,
        max_concurrency=config.max_concurrency,
        metrics_enabled=config.metrics_enabled,
        retry=config.retry,
        cache=config.cache,
    )

    return router


async def _main(run_tests: bool = False):
    if run_tests and not _run_tests():
        return

    router = await start_infrastructure()
    print("Инфраструктура запущена. Нажмите Ctrl+C для остановки.")
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await router.shutdown()


def _run_tests() -> bool:
    """Запускает тесты перед стартом инфраструктуры.

    Returns:
        True если тесты прошли (или пропущены), False если упали.
    """
    import subprocess
    import infrastructure

    test_dir = Path(infrastructure.__file__).parent / "tests"

    if not test_dir.exists():
        print("Тесты не найдены, пропуск.")
        return True

    # Читаем TEST_DB_URL_ASYNC из .infra.env напрямую (без load_dotenv чтобы не засорять окружение)
    test_db_url = os.getenv("TEST_DB_URL_ASYNC")
    if not test_db_url:
        env_file = Path(__file__).parent / ".infra.env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("TEST_DB_URL_ASYNC="):
                    test_db_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

    if not test_db_url:
        print("TEST_DB_URL_ASYNC не задан — тесты пропущены.\n")
        return True

    print("=" * 60)
    print("ЗАПУСК ТЕСТОВ")
    print("=" * 60)
    env = os.environ.copy()
    env["TEST_DB_URL_ASYNC"] = test_db_url
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_dir), "-v", "--tb=short", "--no-header"],
        env=env,
    )
    print("=" * 60)

    # Очистка тестовых таблиц чтобы не мешали миграциям
    _cleanup_test_tables(test_db_url)

    if result.returncode != 0:
        print(f"\nТесты завершились с ошибкой (код {result.returncode}).")
        print("Инфраструктура НЕ запущена.")
        return False

    print("\nВсе тесты прошли.\n")
    return True


def _cleanup_test_tables(db_url: str) -> None:
    """Удаляет тестовые таблицы (test_roles, test_users, test_items) после тестов."""
    try:
        import psycopg

        sync_url = db_url.replace("+asyncpg", "").replace("+psycopg", "")
        with psycopg.connect(sync_url) as conn:
            with conn.cursor() as cur:
                for table in ("test_items", "test_users", "test_roles", "test_items_with_ts", "test_custom_pk"):
                    cur.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
            conn.commit()
    except Exception as e:
        import sys

        print(f"Предупреждение: не удалось очистить тестовые таблицы: {e}", file=sys.stderr)


if __name__ == "__main__":
    try:
        run_tests = "--test" in sys.argv
        asyncio.run(_main(run_tests=run_tests))
    except KeyboardInterrupt:
        print("\nОстановка.")
