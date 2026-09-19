"""Модели конфигурации event_infrastructure."""

from dataclasses import dataclass, field


@dataclass
class ChannelConfig:
    """Конфигурация одного канала."""

    pool_size: int = 10
    max_overflow: int = 5
    queue_maxsize: int = 1000
    workers: int = 0

    def __post_init__(self) -> None:
        if self.pool_size < 0:
            raise ValueError(f"pool_size must be >= 0, got {self.pool_size}")
        if self.max_overflow < 0:
            raise ValueError(f"max_overflow must be >= 0, got {self.max_overflow}")
        if self.queue_maxsize < 1:
            raise ValueError(f"queue_maxsize must be >= 1, got {self.queue_maxsize}")
        if self.workers < 0:
            raise ValueError(f"workers must be >= 0, got {self.workers}")

    @property
    def effective_workers(self) -> int:
        """Количество воркеров: явное значение или pool_size по умолчанию."""
        return self.workers if self.workers > 0 else self.pool_size


@dataclass
class RetryConfig:
    """Конфигурация повторных попыток."""

    max_retries: int = 3
    delay_seconds: float = 0.5
    backoff_multiplier: float = 2.0
    max_total_timeout: float = 0.0
    retry_on_timeout: bool = False

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {self.max_retries}")
        if self.delay_seconds < 0:
            raise ValueError(f"delay_seconds must be >= 0, got {self.delay_seconds}")
        if self.backoff_multiplier < 1.0:
            raise ValueError(f"backoff_multiplier must be >= 1.0, got {self.backoff_multiplier}")
        if self.max_total_timeout < 0:
            raise ValueError(f"max_total_timeout must be >= 0, got {self.max_total_timeout}")


@dataclass
class CacheConfig:
    """Конфигурация кеширования."""

    enabled: bool = False
    ttl_seconds: float = 60.0
    max_size: int = 1000

    def __post_init__(self) -> None:
        if self.ttl_seconds < 0:
            raise ValueError(f"ttl_seconds must be >= 0, got {self.ttl_seconds}")
        if self.max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {self.max_size}")


@dataclass
class PipelineConfig:
    """Полная конфигурация event_infrastructure.

    Attributes:
        db_url: Строка подключения (postgresql+asyncpg://...)
        channels: Словарь каналов {"имя": ChannelConfig, ...}
        pool_recycle: Время жизни соединения в секундах
        pool_pre_ping: Проверка живучести перед использованием
        pool_timeout: Таймаут ожидания соединения из пула
        default_timeout: Таймаут выполнения задачи
        metrics_enabled: Включить сбор метрик
        max_concurrency: Максимальная конкурентность
        retry: Конфигурация повторных попыток
        shutdown_timeout: Таймаут graceful shutdown
    """

    db_url: str = ""

    channels: dict[str, ChannelConfig] = field(
        default_factory=lambda: {
            "read": ChannelConfig(pool_size=20, max_overflow=10, queue_maxsize=500),
            "write": ChannelConfig(pool_size=10, max_overflow=5, queue_maxsize=200),
            "admin": ChannelConfig(pool_size=2, max_overflow=0, queue_maxsize=50),
        }
    )

    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    pool_timeout: int = 30

    default_timeout: float = 30.0
    metrics_enabled: bool = True
    max_concurrency: int = 200
    retry: RetryConfig = field(default_factory=RetryConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)

    shutdown_timeout: float = 10.0

    def __post_init__(self) -> None:
        if not self.db_url:
            raise ValueError("db_url must not be empty")
        if self.pool_recycle < 0:
            raise ValueError(f"pool_recycle must be >= 0, got {self.pool_recycle}")
        if self.pool_timeout < 0:
            raise ValueError(f"pool_timeout must be >= 0, got {self.pool_timeout}")
        if self.default_timeout < 0:
            raise ValueError(f"default_timeout must be >= 0, got {self.default_timeout}")
        if self.max_concurrency < 0:
            raise ValueError(f"max_concurrency must be >= 0, got {self.max_concurrency}")
        if self.shutdown_timeout < 0:
            raise ValueError(f"shutdown_timeout must be >= 0, got {self.shutdown_timeout}")
