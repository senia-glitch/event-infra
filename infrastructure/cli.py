import argparse
import asyncio
import sys
from pathlib import Path
from importlib import resources
import shutil


def _copy_template(template_name: str, dest: Path, force: bool = False) -> bool:
    if dest.exists() and not force:
        print(f"Файл {dest} уже существует. Используйте --force для перезаписи.")
        return False
    content = resources.files("infrastructure.templates").joinpath(template_name).read_text(encoding="utf-8")
    dest.write_text(content, encoding="utf-8")
    print(f"Создан: {dest}")
    return True


def _create_alembic_dir(force: bool = False) -> bool:
    """Создаёт папку alembic с минимальным содержимым."""
    alembic_path = Path.cwd() / "alembic"
    if alembic_path.exists():
        if not force:
            print(f"Папка {alembic_path} уже существует. Используйте --force для перезаписи.")
            return False
        else:
            shutil.rmtree(alembic_path)
            print(f"Папка {alembic_path} удалена (--force)")

    alembic_path.mkdir(parents=True)
    versions_path = alembic_path / "versions"
    versions_path.mkdir()

    # env.py
    (alembic_path / "env.py").write_text("""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import sys
target_metadata = None
for module in sys.modules.values():
    if hasattr(module, 'metadata') and hasattr(module.metadata, 'tables'):
        target_metadata = module.metadata
        break

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=False,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
""", encoding="utf-8")

    # script.py.mako
    (alembic_path / "script.py.mako").write_text("""
\"\"\"${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

\"\"\"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

def upgrade() -> None:
    \"\"\"Upgrade schema.\"\"\"
    ${upgrades if upgrades else "pass"}

def downgrade() -> None:
    \"\"\"Downgrade schema.\"\"\"
    ${downgrades if downgrades else "pass"}
""", encoding="utf-8")

    # versions/__init__.py
    (versions_path / "__init__.py").write_text("", encoding="utf-8")

    print(f"Создана папка: {alembic_path}")
    return True


def init():
    parser = argparse.ArgumentParser(description="Инициализация инфраструктурного слоя в текущей директории")
    parser.add_argument("--force", action="store_true", help="Перезаписать существующие файлы")
    args = parser.parse_args()

    cwd = Path.cwd()
    ok1 = _copy_template("models_template.py", cwd / "models.py", args.force)
    ok2 = _copy_template("run_infrastructure_template.py", cwd / "run_infrastructure.py", args.force)
    ok3 = _copy_template("env_template.txt", cwd / ".infra.env", args.force)   # <-- изменено имя
    ok4 = _create_alembic_dir(args.force)

    if ok1 and ok2 and ok3 and ok4:
        print("\nГотово. Теперь можно запустить инфраструктуру: python run_infrastructure.py")
    else:
        print("\nИнициализация завершена с предупреждениями.")


def reset():
    from infrastructure.db_migrator.reset import reset as reset_db
    parser = argparse.ArgumentParser(description="Полный сброс БД и миграций")
    parser.add_argument("db_url", help="Строка подключения к БД")
    parser.add_argument("--alembic-dir", default=None, help="Путь к папке alembic (по умолчанию ./alembic)")
    args = parser.parse_args()

    success = reset_db(args.db_url, args.alembic_dir)
    sys.exit(0 if success else 1)


def monitor():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print("Использование: infra-monitor [интервал_в_секундах]")
        print("По умолчанию интервал 0.5 секунды")
        return

    from infrastructure.monitor import monitor as _monitor
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    try:
        asyncio.run(_monitor(interval))
    except KeyboardInterrupt:
        print("\nStopped.")
