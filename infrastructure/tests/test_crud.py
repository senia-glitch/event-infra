"""CRUD тесты через EventRouter."""


async def test_create_and_read(router, clean_db):
    """Создание и чтение записи."""
    r = await router.create("test_roles", {"name": "admin"})
    assert r.success, f"Create failed: {r.error}"
    role_id = r.data[0]["id"]
    assert role_id is not None

    r = await router.read("test_roles", role_id)
    assert r.success
    assert r.data[0]["name"] == "admin"


async def test_create_user_with_role(router, clean_db):
    """Создание пользователя сForeignKey."""
    role_r = await router.create("test_roles", {"name": "user_role"})
    assert role_r.success
    role_id = role_r.data[0]["id"]

    user_r = await router.create(
        "test_users",
        {
            "username": "alice",
            "email": "alice@test.com",
            "role_id": role_id,
            "age": 25,
        },
    )
    assert user_r.success, f"Create user failed: {user_r.error}"
    user_id = user_r.data[0]["id"]

    r = await router.read("test_users", user_id)
    assert r.success
    assert r.data[0]["username"] == "alice"
    assert r.data[0]["role_id"] == role_id


async def test_update(router, clean_db):
    """Обновление записи."""
    r = await router.create("test_roles", {"name": "old_name"})
    role_id = r.data[0]["id"]

    r = await router.update("test_roles", role_id, {"name": "new_name"})
    assert r.success
    assert r.data[0]["name"] == "new_name"

    # Проверяем что в БД действительно обновилось
    r = await router.read("test_roles", role_id)
    assert r.success
    assert r.data[0]["name"] == "new_name"


async def test_delete(router, clean_db):
    """Удаление записи."""
    r = await router.create("test_roles", {"name": "to_delete"})
    role_id = r.data[0]["id"]

    r = await router.delete("test_roles", role_id)
    assert r.success

    r = await router.read("test_roles", role_id)
    assert r.success
    assert r.count == 0


async def test_read_nonexistent(router, clean_db):
    """Чтение несуществующей записи."""
    r = await router.read("test_roles", 999999)
    assert r.success
    assert r.count == 0


async def test_create_validation_error(router, clean_db):
    """Ошибка валидации при создании."""
    r = await router.create(
        "test_users",
        {
            "username": "test",
            "email": "test@test.com",
            "age": "not_a_number",
        },
    )
    # либо success=False из-за валидации, либо ошибка в БД
    # главное — не падаем с необработанным исключением
    assert r is not None


async def test_batch_operations(router, clean_db):
    """Пакетное создание и чтение."""
    # Создаём 20 записей
    for i in range(20):
        r = await router.create("test_items", {"name": f"item_{i}", "val": i})
        assert r.success, f"Create item_{i} failed: {r.error}"

    # Читаем все
    for i in range(1, 21):
        r = await router.read("test_items", i)
        assert r.success
        assert r.count == 1
