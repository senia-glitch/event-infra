"""CRUD тесты через EventRouter."""

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


async def test_create_and_read():
    await _clean()
    role_id = await _create_role()

    r = await router.create(TABLE, {"role_id": role_id, "username": "alice", "personal_number": "PN001", "password_hash": "hash"})
    assert r.success, f"Create failed: {r.error}"
    user_id = r.data[0]["id"]
    print(f"  Created user id={user_id}")

    r = await router.read(TABLE, user_id)
    assert r.success
    assert r.data[0]["username"] == "alice"
    print("  Read OK")


async def test_update():
    await _clean()
    role_id = await _create_role()

    r = await router.create(TABLE, {"role_id": role_id, "username": "bob", "personal_number": "PN002", "password_hash": "hash"})
    user_id = r.data[0]["id"]

    r = await router.update(TABLE, user_id, {"username": "robert"})
    assert r.success
    assert r.data[0]["username"] == "robert"
    print("  Update OK")


async def test_delete():
    await _clean()
    role_id = await _create_role()

    r = await router.create(TABLE, {"role_id": role_id, "username": "charlie", "personal_number": "PN003", "password_hash": "hash"})
    user_id = r.data[0]["id"]

    r = await router.delete(TABLE, user_id)
    assert r.success
    print("  Delete OK")

    r = await router.read(TABLE, user_id)
    assert r.success and r.count == 0
    print("  Read after delete: empty")


async def test_validation_error():
    await _clean()

    r = await router.create(TABLE, {"role_id": "not_a_number", "username": "test", "personal_number": "PN004", "password_hash": "hash"})
    assert not r.success
    print("  Validation error caught")


async def run_all_tests(verbose: bool = False):
    tests = [
        ("create_and_read", test_create_and_read),
        ("update", test_update),
        ("delete", test_delete),
        ("validation_error", test_validation_error),
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
    
    print(f"  CRUD: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    asyncio.run(run_all_tests())
