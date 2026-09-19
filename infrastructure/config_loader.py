"""Утилита загрузки переменных из .env файла и построения конфигурации."""

import os
import logging
from pathlib import Path
from typing import Optional

from infrastructure.event_infrastructure.config.models import (
    PipelineConfig,
    ChannelConfig,
    RetryConfig,
    CacheConfig,
)

logger = logging.getLogger(__name__)


def load_dotenv(path: str = ".env", override: bool = False) -> None:
    r"""Читает файл .env и добавляет переменные в os.environ.

    Поддерживаемый формат:
        KEY=VALUE
        KEY="VALUE"
        KEY='VALUE'
        KEY=VALUE # inline comment
        # full-line comment
        KEY=VALUE\  (backslash continuation — значение продолжается на следующей строке)

    По умолчанию существующие переменные окружения НЕ перезаписываются
    (env vars имеют приоритет над .env файлом).
    С override=True — перезаписывает все значения из .env файла.
    """
    env_path = Path(path)
    if not env_path.exists():
        return

    with env_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    pending_value: Optional[str] = None
    pending_key: Optional[str] = None

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        i += 1
        line = raw_line.rstrip("\n\r")

        # Склеивание строк (backslash continuation)
        if pending_key is not None:
            pending_value = (pending_value or "") + line.strip()
            if pending_value.endswith("\\"):
                # Проверяем следующую строку: если это новый ключ или комментарий,
                # backslash — литерал (Windows-путь), а не continuation
                next_stripped = ""
                for j in range(i, len(lines)):
                    candidate = lines[j].strip()
                    if candidate and not candidate.startswith("#"):
                        next_stripped = candidate
                        break
                if next_stripped and ("=" in next_stripped.split("#")[0] or next_stripped.startswith("#")):
                    # Следующая строка — ключ/значение или комментарий, continuation прерван
                    _set_env(pending_key, pending_value, override)
                    pending_key = None
                    pending_value = None
                else:
                    pending_value = pending_value[:-1]
                    continue
            else:
                _set_env(pending_key, pending_value, override)
                pending_key = None
                pending_value = None
            continue

        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        # Убираем inline комментарий (только если значение не в кавычках)
        if value.startswith(('"', "'")):
            quote = value[0]
            end = value.find(quote, 1)
            if end != -1:
                value = value[1:end]
            else:
                # Незакрытая кавычка — берём всё после первой
                value = value[1:]
        else:
            # Убираем inline комментарий
            comment_pos = value.find("#")
            if comment_pos != -1:
                value = value[:comment_pos].rstrip()

        # Продолжение строки
        if value.endswith("\\"):
            # Проверяем следующую строку: если это новый ключ или комментарий,
            # backslash — литерал (Windows-путь), а не continuation
            next_stripped = ""
            for j in range(i, len(lines)):
                candidate = lines[j].strip()
                if candidate and not candidate.startswith("#"):
                    next_stripped = candidate
                    break
            if next_stripped and ("=" in next_stripped.split("#")[0] or next_stripped.startswith("#")):
                _set_env(key, value, override)
            else:
                pending_key = key
                pending_value = value[:-1]
                continue

        _set_env(key, value, override)


def _set_env(key: str, value: str, override: bool = False) -> None:
    """Устанавливает переменную окружения.

    По умолчанию не перезаписывает существующие переменные (env vars имеют приоритет).
    С override=True перезаписывает — полезно для тестов или переопределения.
    """
    if override or key not in os.environ:
        os.environ[key] = value


def _parse_bool(value: str) -> bool:
    """Парсит строку в bool (True: 1, true, yes, on)."""
    return value.lower() in ("1", "true", "yes", "on")


def _env_float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return _parse_bool(raw)


def load_config_from_env(
    env_file: Optional[str] = None,
    base_dir: Optional[Path] = None,
) -> PipelineConfig:
    """Загружает конфигурацию из .infra.env файла.

    Читает переменные окружения и строит PipelineConfig со всеми параметрами:
    - Подключение к БД (DB_URL_ASYNC)
    - Каналы (CHANNELS, {NAME}_POOL_SIZE, {NAME}_MAX_OVERFLOW, {NAME}_QUEUE_MAXSIZE, {NAME}_WORKERS)
    - Пулы (POOL_RECYCLE, POOL_PRE_PING, POOL_TIMEOUT)
    - Таймауты (DEFAULT_TIMEOUT, SHUTDOWN_TIMEOUT, MAX_CONCURRENCY)
    - Retry (RETRY_MAX_RETRIES, RETRY_DELAY_SECONDS, RETRY_BACKOFF_MULTIPLIER, RETRY_MAX_TOTAL_TIMEOUT)
    - Кеш (CACHE_ENABLED, CACHE_TTL_SECONDS, CACHE_MAX_SIZE)

    Args:
        env_file: Путь к .env файлу. Если None — читает INFRA_ENV_FILE или .infra.env
        base_dir: Базовая директория для поиска env_file по умолчанию

    Returns:
        PipelineConfig: готовая конфигурация
    """
    # Определяем путь к env файлу
    if env_file is None:
        env_file = os.getenv("INFRA_ENV_FILE", ".infra.env")
    if base_dir is not None:
        env_path = Path(base_dir) / env_file
    else:
        env_path = Path(env_file)

    load_dotenv(str(env_path))

    # DB URL
    db_url = os.getenv("DB_URL_ASYNC", "")

    # Каналы
    channel_names = [name.strip() for name in os.getenv("CHANNELS", "read,write,admin").split(",") if name.strip()]

    channels = {}
    for name in channel_names:
        prefix = name.upper()
        channels[name] = ChannelConfig(
            pool_size=_env_int(f"{prefix}_POOL_SIZE", 10),
            max_overflow=_env_int(f"{prefix}_MAX_OVERFLOW", 5),
            queue_maxsize=_env_int(f"{prefix}_QUEUE_MAXSIZE", 1000),
            workers=_env_int(f"{prefix}_WORKERS", 0),
        )

    # Retry
    retry = RetryConfig(
        max_retries=_env_int("RETRY_MAX_RETRIES", 3),
        delay_seconds=_env_float("RETRY_DELAY_SECONDS", 0.5),
        backoff_multiplier=_env_float("RETRY_BACKOFF_MULTIPLIER", 2.0),
        max_total_timeout=_env_float("RETRY_MAX_TOTAL_TIMEOUT", 0.0),
        retry_on_timeout=_env_bool("RETRY_ON_TIMEOUT", False),
    )

    # Кеш
    cache = CacheConfig(
        enabled=_env_bool("CACHE_ENABLED", False),
        ttl_seconds=_env_float("CACHE_TTL_SECONDS", 60.0),
        max_size=_env_int("CACHE_MAX_SIZE", 1000),
    )

    # Пулы и таймауты
    config = PipelineConfig(
        db_url=db_url,
        channels=channels,
        pool_recycle=_env_int("POOL_RECYCLE", 3600),
        pool_pre_ping=_env_bool("POOL_PRE_PING", True),
        pool_timeout=_env_int("POOL_TIMEOUT", 30),
        default_timeout=_env_float("DEFAULT_TIMEOUT", 30.0),
        metrics_enabled=_env_bool("METRICS_ENABLED", True),
        max_concurrency=_env_int("MAX_CONCURRENCY", 200),
        retry=retry,
        cache=cache,
        shutdown_timeout=_env_float("SHUTDOWN_TIMEOUT", 10.0),
    )

    logger.info(
        "Конфигурация загружена: каналы=%s, retry=%d, кеш=%s",
        list(channels.keys()),
        retry.max_retries,
        "вкл" if cache.enabled else "выкл",
    )

    return config
