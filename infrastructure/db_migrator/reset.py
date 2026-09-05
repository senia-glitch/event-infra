"""
Скрипт полного сброса: удаляет все миграции, кеш и очищает БД.
Ожидает, что в текущей директории есть папка alembic (создаётся infra-init).
"""

import sys
import os
import shutil
from pathlib import Path
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset(db_url: str, alembic_dir: str = None):
    """
    Полный сброс утилиты и базы данных.

    Args:
        db_url: строка подключения к БД
        alembic_dir: путь к папке alembic (если None, ищет ./alembic)
    """
    if alembic_dir is None:
        alembic_dir = Path.cwd() / "alembic"
    else:
        alembic_dir = Path(alembic_dir)

    if not alembic_dir.exists():
        logger.error(f"Папка alembic не найдена: {alembic_dir}")
        logger.error("Сначала выполните infra-init в корне проекта")
        return False

    versions_dir = alembic_dir / "versions"

    # 1. Удаляем файлы миграций и __pycache__
    if versions_dir.exists():
        for f in versions_dir.glob("*.py"):
            if f.name != "__init__.py":
                f.unlink()
                logger.info(f"Удалён файл миграции: {f.name}")
        pycache = versions_dir / "__pycache__"
        if pycache.exists():
            shutil.rmtree(pycache)
            logger.info("Удалён __pycache__ в versions")
    else:
        logger.warning("Папка versions не найдена, пропускаем")

    # 2. Удаляем __pycache__ в корне alembic
    pycache_root = alembic_dir / "__pycache__"
    if pycache_root.exists():
        shutil.rmtree(pycache_root)
        logger.info("Удалён __pycache__ в alembic")

    # 3. Очищаем кеш модулей (если они загружены)
    modules_to_remove = [name for name in sys.modules if 'models' in name.lower() or 'alembic' in name.lower()]
    for module_name in modules_to_remove:
        if module_name in sys.modules:
            del sys.modules[module_name]
            logger.info(f"Модуль {module_name} удалён из sys.modules")

    # 4. Очищаем БД
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SET session_replication_role = 'replica'"))
            conn.commit()

            result = conn.execute(text("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """))
            tables = [row[0] for row in result]

            for table in tables:
                conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                logger.info(f"Удалена таблица: {table}")

            conn.commit()
            logger.info("База данных очищена")
    except Exception as e:
        logger.error(f"Ошибка при очистке БД: {e}")
        return False

    logger.info("Сброс выполнен успешно")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python -m infrastructure.db_migrator.reset postgresql://user:pass@localhost:5432/dbname")
        sys.exit(1)

    db_url = sys.argv[1]
    # Можно передать второй аргумент – путь к alembic (по умолчанию ./alembic)
    alembic_dir = sys.argv[2] if len(sys.argv) > 2 else None
    success = reset(db_url, alembic_dir)
    sys.exit(0 if success else 1)