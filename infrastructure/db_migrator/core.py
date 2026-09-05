import importlib.util
import sys
import shutil
from pathlib import Path
from importlib import resources
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


def _ensure_alembic_dir(schema_path: str) -> Path:
    """Определяет или создаёт папку alembic рядом с models.py."""
    schema_path = Path(schema_path).resolve()
    alembic_dir = schema_path.parent / "alembic"
    if not alembic_dir.exists():
        logger.info(f"Папка alembic не найдена рядом с {schema_path}. Создаю из шаблона...")
        template_dir = resources.files("infrastructure.db_migrator").joinpath("alembic")
        shutil.copytree(template_dir, alembic_dir)
        # Удаляем __pycache__, если он попал
        pycache = alembic_dir / "__pycache__"
        if pycache.exists():
            shutil.rmtree(pycache)
    return alembic_dir


def run_migration(db_url: str, schema_path: str, alembic_dir: str = None) -> bool:
    """
    Основная функция миграции.
    Если alembic_dir не указан, будет использована/создана папка alembic рядом с models.py.
    Возвращает True если миграция прошла успешно или изменений нет.
    Возвращает False если произошла ошибка.
    """
    try:
        module = load_models(schema_path)

        if alembic_dir is None:
            alembic_dir = _ensure_alembic_dir(schema_path)
        else:
            alembic_dir = Path(alembic_dir)

        # Используем Config без ini-файла, задаём параметры напрямую
        alembic_cfg = Config()
        alembic_cfg.set_main_option("script_location", str(alembic_dir))
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

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