"""Тесты конфигурации."""


async def test_metrics_available(router):
    """Метрики доступны после запуска."""
    metrics = router.get_metrics()
    assert metrics is not None
    assert metrics.uptime_seconds >= 0
    assert "read" in metrics.channels
    assert "write" in metrics.channels
    assert "admin" in metrics.channels


async def test_print_metrics(router):
    """print_metrics не падает с ошибкой."""
    router.print_metrics(full=False)
    router.print_metrics(full=True)


async def test_registry(router):
    """Реестр сущностей содержит зарегистрированные таблицы."""
    registry = router.get_registry()
    assert "test_roles" in registry
    assert "test_users" in registry
    assert "test_items" in registry


async def test_has_entity(router):
    """has_entity возвращает корректные значения."""
    assert router.has_entity("test_roles") is True
    assert router.has_entity("nonexistent_table") is False
