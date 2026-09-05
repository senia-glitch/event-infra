import argparse
import asyncio
import sys
from pathlib import Path
from importlib import resources


def _copy_template(template_name: str, dest: Path, force: bool = False) -> bool:
    if dest.exists() and not force:
        print(f"Файл {dest} уже существует. Используйте --force для перезаписи.")
        return False
    content = resources.files("infrastructure.templates").joinpath(template_name).read_text(encoding="utf-8")
    dest.write_text(content, encoding="utf-8")
    print(f"Создан: {dest}")
    return True


def init():
    parser = argparse.ArgumentParser(description="Инициализация инфраструктурного слоя в текущей директории")
    parser.add_argument("--force", action="store_true", help="Перезаписать существующие файлы")
    args = parser.parse_args()

    cwd = Path.cwd()
    ok1 = _copy_template("models_template.py", cwd / "models.py", args.force)
    ok2 = _copy_template("run_infrastructure_template.py", cwd / "run_infrastructure.py", args.force)
    ok3 = _copy_template("env_template.txt", cwd / ".env", args.force)

    if ok1 and ok2 and ok3:
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
    from infrastructure.monitor import monitor as _monitor
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    try:
        asyncio.run(_monitor(interval))
    except KeyboardInterrupt:
        print("\nStopped.")