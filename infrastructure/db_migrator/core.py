import importlib.util
import sys
from pathlib import Path
from alembic.config import Config
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_models(schema_path: str):
    """Загружает модуль с моделями, если ещё не загружен."""
    path = Path(schema_path).resolve()
    module_name = path.stem

    if module_name in sys.modules:
        module = sys.modules[module_name]
        if hasattr(module, 'metadata'):
            logger.info(f"Модуль {module_name} уже загружен, таблицы: {', '.join(module.metadata.tables.keys())}")
            return module

    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))

    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    if not hasattr(module, 'metadata'):
        raise AttributeError("Добавьте 'metadata = SQLModel.metadata' в models.py")

    logger.info(f"Загружены таблицы: {', '.join(module.metadata.tables.keys())}")
    return module


def run_migration(db_url: str, schema_path: str, alembic_dir: str = None) -> bool:
    """
    Основная функция миграции.
    Возвращает True если миграция прошла успешно или изменений нет.
    Возвращает False если произошла ошибка.
    """

    try:
        module = load_models(schema_path)

        db_migrator_dir = Path(__file__).parent
        if alembic_dir is None:
            alembic_dir = db_migrator_dir / "alembic"
        else:
            alembic_dir = Path(alembic_dir)

        alembic_ini_path = db_migrator_dir / "alembic.ini"

        # ========== FIX: пересохраняем alembic.ini в UTF-8, если он повреждён ==========
        try:
            with open(alembic_ini_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            logger.warning("alembic.ini не в UTF-8, пробуем cp1251 и пересохраняем...")
            with open(alembic_ini_path, 'r', encoding='cp1251') as f:
                content = f.read()
            with open(alembic_ini_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info("alembic.ini пересохранён в UTF-8")

        # Теперь создаём Config БЕЗ параметра encoding (он не поддерживается)
        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        alembic_cfg.set_main_option("script_location", str(alembic_dir))

        # Проверяем различия
        engine = create_engine(db_url)
        with engine.connect() as conn:
            mc = MigrationContext.configure(conn)
            diff = compare_metadata(mc, module.metadata)
        engine.dispose()

        if not diff:
            logger.info("Схема актуальна, изменений нет")
            return True

        logger.info("Обнаружены изменения в схеме, создаём миграцию...")
        command.revision(alembic_cfg, autogenerate=True, message="auto")
        command.upgrade(alembic_cfg, "head")
        logger.info("Миграция успешно применена")
        return True

    except Exception as e:
        logger.error(f"Ошибка миграции: {e}")
        return False
