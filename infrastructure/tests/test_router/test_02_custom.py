"""Кастомные SQL запросы через EventRouter."""

import asyncio

router = None

TABLE = "users"


async def _clean():
    await router.execute("admin", f'TRUNCATE TABLE "{TABLE}" RESTART IDENTITY CASCADE')
    await router.execute("admin", 'TRUNCATE TABLE "roles" RESTART IDENTITY CASCADE')


async def _create_role():
    r = await router.create("roles", {"name": "test_role"}, channel="write")
    assert r.success, f"Create role failed: {r.error}"
    return r.data[0]["id"]


async def _seed():
    role_id = await _create_role()
    await router.create(TABLE, {"role_id": role_id, "username": "alice", "personal_number": "PN_A", "password_hash": "hash"})
    await router.create(TABLE, {"role_id": role_id, "username": "bob", "personal_number": "PN_B", "password_hash": "hash"})
    await router.create(TABLE, {"role_id": role_id, "username": "charlie", "personal_number": "PN_C", "password_hash": "hash"})


async def test_select_with_params():
    await _clean()
    await _seed()

    r = await router.custom(
        'SELECT * FROM "users" WHERE username = :name',
        {"name": "alice"}, channel="read"
    )
    assert r.success
    assert r.count == 1
    print(f"  SELECT: {r.count} rows")


async def test_insert_with_returning():
    await _clean()
    role_id = await _create_role()

    r = await router.custom(
        'INSERT INTO "users" (role_id, username, personal_number, password_hash) VALUES (:role_id, :username, :pn, :hash) RETURNING id, username',
        {"role_id": role_id, "username": "diana", "pn": "PN_D", "hash": "hash"}, channel="write"
    )
    assert r.success
    print(f"  INSERT: {r.count} rows")


async def test_update_with_params():
    await _clean()
    await _seed()

    r = await router.custom(
        'UPDATE "users" SET username = :new_name WHERE username = :old_name',
        {"new_name": "robert", "old_name": "bob"}, channel="write"
    )
    assert r.success
    print("  UPDATE OK")


async def test_aggregate():
    await _clean()
    await _seed()

    r = await router.custom(
        'SELECT COUNT(*) as cnt FROM "users"',
        channel="read"
    )
    assert r.success
    print(f"  Aggregate: {r.data}")


async def run_all_tests():
    tests = [
        ("select_with_params", test_select_with_params),
        ("insert_with_returning", test_insert_with_returning),
        ("update_with_params", test_update_with_params),
        ("aggregate", test_aggregate),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
            print(f"  ✅ {name}")
        except Exception as e:
            failed += 1
            print(f"  ❌ {name}: {e}")
    
    print(f"  Custom: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    asyncio.run(run_all_tests())