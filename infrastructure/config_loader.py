"""Утилита загрузки переменных из .env файла."""

import os
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    """Читает файл .env и добавляет переменные в os.environ, если их там нет.

    Формат файла: КЛЮЧ=ЗНАЧЕНИЕ (одно на строку). Пустые строки и строки с '#' игнорируются.
    Существующие переменные окружения не перезаписываются.
    """
    env_path = Path(path)
    if not env_path.exists():
        return

    with env_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value