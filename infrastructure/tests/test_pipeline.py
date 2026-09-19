"""Тесты создания pipeline."""


async def test_config_loader_load_dotenv(tmp_path):
    """Тест загрузки .env файла."""
    from infrastructure.config_loader import load_dotenv
    import os

    env_file = tmp_path / "test.env"
    env_file.write_text('TEST_KEY=hello\nTEST_QUOTED="world"\nTEST_COMMENT=value # comment\n')

    load_dotenv(str(env_file))

    assert os.getenv("TEST_KEY") == "hello"
    assert os.getenv("TEST_QUOTED") == "world"
    assert os.getenv("TEST_COMMENT") == "value"


async def test_config_loader_load_config_from_env(tmp_path):
    """Тест построения PipelineConfig из env."""
    from infrastructure.config_loader import load_config_from_env

    env_file = tmp_path / "test.env"
    env_file.write_text("""
DB_URL_ASYNC=postgresql+asyncpg://localhost/testdb
CHANNELS=read,write,admin
READ_POOL_SIZE=20
READ_MAX_OVERFLOW=5
READ_QUEUE_MAXSIZE=500
WRITE_POOL_SIZE=10
ADMIN_POOL_SIZE=2
POOL_RECYCLE=1800
DEFAULT_TIMEOUT=60.0
RETRY_MAX_RETRIES=5
CACHE_ENABLED=true
CACHE_TTL_SECONDS=10.0
CACHE_MAX_SIZE=500
""")

    config = load_config_from_env(env_file=str(env_file))

    assert config.db_url == "postgresql+asyncpg://localhost/testdb"
    assert "read" in config.channels
    assert "write" in config.channels
    assert "admin" in config.channels
    assert config.channels["read"].pool_size == 20
    assert config.channels["write"].pool_size == 10
    assert config.channels["admin"].pool_size == 2
    assert config.pool_recycle == 1800
    assert config.default_timeout == 60.0
    assert config.retry.max_retries == 5
    assert config.cache.enabled is True
    assert config.cache.ttl_seconds == 10.0


async def test_config_loader_workers_from_env(tmp_path):
    """Тест загрузки workers из env."""
    from infrastructure.config_loader import load_config_from_env

    env_file = tmp_path / "test.env"
    env_file.write_text("""
DB_URL_ASYNC=postgresql+asyncpg://localhost/testdb
CHANNELS=read
READ_WORKERS=7
""")

    config = load_config_from_env(env_file=str(env_file))
    assert config.channels["read"].workers == 7


async def test_config_loader_retry_max_total_timeout(tmp_path):
    """Тест загрузки RETRY_MAX_TOTAL_TIMEOUT из env."""
    from infrastructure.config_loader import load_config_from_env

    env_file = tmp_path / "test.env"
    env_file.write_text("""
DB_URL_ASYNC=postgresql+asyncpg://localhost/testdb
RETRY_MAX_TOTAL_TIMEOUT=30.0
""")

    config = load_config_from_env(env_file=str(env_file))
    assert config.retry.max_total_timeout == 30.0
