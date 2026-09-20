import argparse
import asyncio
import re
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path
from typing import Optional
from urllib.request import urlopen


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
    (alembic_path / "env.py").write_text(
        """
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
""",
        encoding="utf-8",
    )

    # script.py.mako
    (alembic_path / "script.py.mako").write_text(
        """
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
""",
        encoding="utf-8",
    )

    # versions/__init__.py
    (versions_path / "__init__.py").write_text("", encoding="utf-8")

    print(f"Создана папка: {alembic_path}")
    return True


# === Старые команды (обратная совместимость) ===


def _confirm(prompt: str) -> bool:
    """Запрашивает подтверждение у пользователя (y/N)."""
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nОтмена.")
        return False
    return answer in ("y", "yes", "да")


# === CLI upgrade ===

REPO_URL = "https://github.com/senia-glitch/event-infra.git"
RAW_PYPROJECT_URL = (
    "https://raw.githubusercontent.com/senia-glitch/event-infra/main/pyproject.toml"
)


def _get_local_version() -> str:
    try:
        from importlib.metadata import version as get_version
        return get_version("event-infra")
    except Exception:
        return "0.0.0"


def _fetch_remote_pyproject() -> Optional[str]:
    try:
        with urlopen(RAW_PYPROJECT_URL, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"Не удалось загрузить pyproject.toml с GitHub: {e}")
        return None


def _parse_version(toml_text: str) -> Optional[tuple[int, ...]]:
    m = re.search(r'^version\s*=\s*"([^"]+)"', toml_text, re.MULTILINE)
    if not m:
        return None
    try:
        return tuple(int(x) for x in m.group(1).split("."))
    except ValueError:
        return None


def _parse_requires_python(toml_text: str) -> Optional[str]:
    m = re.search(r'^requires-python\s*=\s*"([^"]+)"', toml_text, re.MULTILINE)
    return m.group(1) if m else None


def _parse_python_bounds(spec: str) -> tuple[Optional[int], Optional[int]]:
    low, high = None, None
    m = re.search(r'>=\s*(\d+)', spec)
    if m:
        low = int(m.group(1))
    m = re.search(r'<\s*(\d+)', spec)
    if m:
        high = int(m.group(1)) - 1
    if not re.search(r'>=', spec):
        m = re.search(r'==\s*(\d+)', spec)
        if m:
            low = high = int(m.group(1))
    return low, high


def _find_pip() -> Optional[list[str]]:
    if shutil.which("pip"):
        return ["pip"]
    r = subprocess.run([sys.executable, "-m", "pip", "--version"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        return [sys.executable, "-m", "pip"]
    return None


def upgrade(args: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description="Обновление пакета event-infra до последней версии"
    )
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Не спрашивать подтверждение при несовместимости Python")
    parsed = parser.parse_args(args)

    local_ver_str = _get_local_version()
    try:
        local_ver = tuple(int(x) for x in local_ver_str.split("."))
    except ValueError:
        print(f"Ошибка: не удалось распознать текущую версию '{local_ver_str}'")
        return
    print(f"Текущая версия: {local_ver_str}")

    print("Проверка обновлений на GitHub ...")
    toml = _fetch_remote_pyproject()
    if toml is None:
        print("Обновление невозможно — не удалось получить данные с GitHub.")
        return

    remote_ver = _parse_version(toml)
    if remote_ver is None:
        print("Обновление невозможно — не удалось определить версию пакета.")
        return

    remote_ver_str = ".".join(str(x) for x in remote_ver)
    print(f"Последняя версия: {remote_ver_str}")

    if remote_ver <= local_ver:
        print("Установлена последняя версия. Обновление не требуется.")
        return

    rp = _parse_requires_python(toml)
    if rp:
        low, high = _parse_python_bounds(rp)
        cur = sys.version_info[:2]
        in_range = True
        if low is not None and cur < (low, 0):
            in_range = False
        if high is not None and cur > (high, 0):
            in_range = False

        if not in_range:
            py_ver = f"{cur[0]}.{cur[1]}"
            print(f"\nВНИМАНИЕ: версия {remote_ver_str} требует Python {rp}.")
            print(f"Текущая версия Python: {py_ver}")
            if not parsed.yes and not _confirm("Продолжить установку несмотря на несовместимость?"):
                print("Отмена.")
                return

    pip = _find_pip()
    if pip is None:
        print("pip не найден. Установите pip перед обновлением.")
        return

    cmd = pip + ["install", "--upgrade", f"git+{REPO_URL}"]
    print(f"\nВыполняю: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    if result.returncode == 0:
        new_ver = _get_local_version()
        print(f"\nГотово. Установлена версия: {new_ver}")
    else:
        print(f"\nОшибка обновления (код возврата: {result.returncode}).")


def init(args: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Инициализация инфраструктурного слоя в текущей директории")
    parser.add_argument("--force", action="store_true", help="Перезаписать существующие файлы")
    parser.add_argument("-y", "--yes", action="store_true", help="Не спрашивать подтверждение")
    parsed = parser.parse_args(args)

    if not parsed.yes:
        if not _confirm("Создать файлы проекта (models.py, run_infrastructure.py, .infra.env, alembic/)?"):
            print("Отмена.")
            return

    cwd = Path.cwd()
    ok1 = _copy_template("models_template.py", cwd / "models.py", parsed.force)
    ok2 = _copy_template("run_infrastructure_template.py", cwd / "run_infrastructure.py", parsed.force)
    ok3 = _copy_template("env_template.txt", cwd / ".infra.env", parsed.force)
    ok4 = _create_alembic_dir(parsed.force)

    if ok1 and ok2 and ok3 and ok4:
        print("\nГотово. Теперь вы можете использовать инфраструктуру в своём коде:")
        print("    from run_infrastructure import start_infrastructure")
        print("    router = await start_infrastructure()")
        print("    # ... работа с router ...")
        print("    await router.shutdown()")
    else:
        print("\nИнициализация завершена с предупреждениями.")


def reset(args: list[str] | None = None):
    from infrastructure.db_migrator.reset import reset as reset_db

    parser = argparse.ArgumentParser(description="Полный сброс БД и миграций")
    parser.add_argument("db_url", help="Строка подключения к БД")
    parser.add_argument("--alembic-dir", default=None, help="Путь к папке alembic (по умолчанию ./alembic)")
    parser.add_argument("-y", "--yes", action="store_true", help="Не спрашивать подтверждение")
    parsed = parser.parse_args(args)

    if not parsed.yes:
        print("ВНИМАНИЕ: Все таблицы будут УДАЛЕНЫ из БД:")
        print(f"  {parsed.db_url}")
        if not _confirm("Продолжить?"):
            print("Отмена.")
            return

    success = reset_db(parsed.db_url, parsed.alembic_dir)
    sys.exit(0 if success else 1)


def monitor(args: list[str] | None = None):
    if args and args[0] in ("-h", "--help"):
        print("Использование: infra-monitor [интервал_в_секундах]")
        print("По умолчанию интервал 0.5 секунды")
        return

    from infrastructure.monitor import monitor as _monitor

    try:
        interval = float(args[0]) if args else 0.5
    except (ValueError, IndexError):
        print("Ошибка: интервал должен быть числом (например, 0.5)")
        return
    try:
        asyncio.run(_monitor(interval))
    except KeyboardInterrupt:
        print("\nStopped.")


# === Новая команда `infra` с подкомандами ===


def validate(args: list[str] | None = None):
    from infrastructure.validator import validate_all

    parser = argparse.ArgumentParser(description="Проверка конфигурации и подключения к БД")
    parser.add_argument("--env-file", default=".infra.env", help="Путь к .env файлу")
    parser.add_argument("--models", default="models.py", help="Путь к models.py")
    parser.add_argument("--alembic-dir", default="alembic", help="Путь к папке alembic")
    parsed = parser.parse_args(args)

    results = validate_all(
        env_file=parsed.env_file,
        models_path=parsed.models,
        alembic_dir=parsed.alembic_dir,
    )

    icons = {"ok": "[OK]  ", "warn": "[WARN]", "fail": "[FAIL]"}
    for r in results:
        print(f"  {icons[r.status]}  {r.message}")

    fails = sum(1 for r in results if r.status == "fail")
    if fails:
        print(f"\nОбнаружено ошибок: {fails}. Исправьте их перед запуском.")
        sys.exit(1)
    else:
        print("\nВсе проверки пройдены.")


def cheat(args: list[str] | None = None):
    print("""
=== EVENT-INFRA: ШПАРГАЛКА ===

--- БЫСТРЫЙ СТАРТ ---

  infra init                    # создать файлы проекта
  infra validate                # проверить конфигурацию

  from infrastructure.event_infrastructure import create_pipeline

  router = await create_pipeline(
      db_url="postgresql+asyncpg://user:pass@localhost/db",
      channels={"read": ..., "write": ...},
      schemas={"users": User},
  )
  async with router:
      ...

--- CRUD ---

  await router.create("users", {"name": "Alice"})
  await router.read("users", 1)
  await router.update("users", 1, {"name": "Bob"})
  await router.delete("users", 1)

--- ПАГИНАЦИЯ ---

  await router.list("users", limit=10, offset=0, order_by="name", filters={"status": "active"})

--- ПРОИЗВОЛЬНЫЙ SQL ---

  await router.execute("read", "SELECT * FROM users WHERE id > :id", {"id": 0})
  await router.custom("SELECT count(*) FROM users", channel="read")

--- HEALTH & METRICS ---

  await router.health_check()     # dict: alive, db_connected, pools, channels
  await router.get_metrics()      # InfrastructureMetrics
  await router.shutdown()         # graceful shutdown

--- КОНФИГУРАЦИЯ (.infra.env) ---

  DB_URL_ASYNC=postgresql+asyncpg://user:pass@localhost/db
  CHANNELS=read,write,admin
  {NAME}_POOL_SIZE=10
  CACHE_ENABLED=True
  RETRY_MAX_RETRIES=3

--- CLI ---

  infra init [--force] [-y]        инициализация
  infra validate                  проверка конфигурации
  infra upgrade [-y]              обновление пакета с GitHub
  infra monitor [interval]        мониторинг
  infra reset <db_url> [-y]       сброс БД
  infra test [-v]                 тесты
  infra cheat                     эта шпаргалка
""")


def run_tests(verbose: bool = False):
    """Запускает встроенные тесты."""
    from infrastructure.tests import run_tests as _run_tests

    success = _run_tests(verbose=verbose)
    sys.exit(0 if success else 1)


def help_command():
    print("""
Доступные команды инфраструктурного слоя:

  infra init [--force] [-y]        Инициализация проекта (создание моделей, конфига, alembic)
  infra validate                    Проверка конфигурации и подключения к БД
  infra monitor [интервал]          Мониторинг запущенной инфраструктуры (подключение к API)
  infra reset <db_url> [-y]         Полный сброс БД и удаление миграций
  infra upgrade [-y]                Обновление пакета до последней версии с GitHub
  infra test [-v, --verbose]        Запуск встроенных тестов (требуется тестовая БД)
  infra cheat                       Шпаргалка по API
  infra help                        Показать эту справку

После инициализации используйте в своём коде:
    from run_infrastructure import start_infrastructure
    router = await start_infrastructure()

Для обратной совместимости также доступны отдельные команды:
  infra-init, infra-monitor, infra-reset
""")


def main():
    if len(sys.argv) < 2:
        help_command()
        return

    command = sys.argv[1].lower()
    # Оставляем аргументы без имени команды
    args = sys.argv[2:]

    if command == "init":
        init(args)
    elif command == "validate":
        validate(args)
    elif command == "cheat":
        cheat(args)
    elif command == "monitor":
        monitor(args)
    elif command == "reset":
        reset(args)
    elif command == "test":
        verbose = "-v" in args or "--verbose" in args
        run_tests(verbose=verbose)
    elif command == "upgrade":
        upgrade(args)
    elif command in ("help", "-h", "--help"):
        help_command()
    else:
        print(f"Неизвестная команда: {command}")
        help_command()
        sys.exit(1)
