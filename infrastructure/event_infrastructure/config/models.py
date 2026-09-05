from dataclasses import dataclass, field


@dataclass
class ChannelConfig:
    """Конфигурация одного канала."""
    pool_size: int = 10
    max_overflow: int = 5
    queue_maxsize: int = 1000


@dataclass
class RetryConfig:
    """Конфигурация повторных попыток."""
    max_retries: int = 3
    delay_seconds: float = 0.5
    backoff_multiplier: float = 2.0


@dataclass
class CacheConfig:
    """Конфигурация кеширования."""
    enabled: bool = False
    ttl_seconds: float = 60.0
    max_size: int = 1000
    

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
    db_url: str
    
    channels: dict[str, ChannelConfig] = field(default_factory=lambda: {
        "read": ChannelConfig(pool_size=20, max_overflow=10, queue_maxsize=500),
        "write": ChannelConfig(pool_size=10, max_overflow=5, queue_maxsize=200),
        "admin": ChannelConfig(pool_size=2, max_overflow=0, queue_maxsize=50),
    })
    
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    pool_timeout: int = 30
    
    default_timeout: float = 30.0
    metrics_enabled: bool = True
    max_concurrency: int = 200
    retry: RetryConfig = field(default_factory=RetryConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    
    shutdown_timeout: float = 10.0