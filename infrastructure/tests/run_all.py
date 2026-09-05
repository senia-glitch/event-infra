"""Запуск всех тестов с общим router."""

import infrastructure.tests.test_db.test_01_connection as t01
import infrastructure.tests.test_db.test_02_read_write as t02
import infrastructure.tests.test_db.test_03_mixed as t03
import infrastructure.tests.test_db.test_04_errors as t04
import infrastructure.tests.test_db.test_05_shutdown as t05
import infrastructure.tests.test_db.test_06_metrics as t06
import infrastructure.tests.test_db.test_07_load as t07
import infrastructure.tests.test_db.test_08_concurrent as t08
import infrastructure.tests.test_db.test_09_edge_cases as t09
import infrastructure.tests.test_db.test_10_graceful_shutdown as t10
import infrastructure.tests.test_router.test_01_crud as crud
import infrastructure.tests.test_router.test_02_custom as custom
import infrastructure.tests.test_db.test_11_cache_load as t11


async def run(router):
    """Запускает все тесты, используя переданный router."""
    
    # Передаём router в DB тесты
    t01.router = router
    t02.router = router
    t03.router = router
    t04.router = router
    t05.router = router
    t06.router = router
    t07.router = router
    t08.router = router
    t09.router = router
    t10.router = router
    t11.router = router

    # Передаём router в Router тесты
    crud.router = router
    custom.router = router

    print("\n" + "=" * 50)
    print("ЗАПУСК ВСЕХ ТЕСТОВ")
    print("=" * 50)

    all_passed = True

    # DB тесты
    print("\n--- DB Tests ---")
    db_tests = [
        ("connection", t01.test_connection),
        ("read_write_load", t02.test_read_write_load),
        ("mixed_load", t03.test_mixed_load),
        ("errors", t04.test_errors),
        ("shutdown_completes_tasks", t05.test_shutdown_completes_tasks),
        ("no_new_tasks_after_shutdown", t05.test_no_new_tasks_after_shutdown),
        ("metrics", t06.test_metrics),
        ("load", t07.test_load),
        ("concurrent", t08.test_concurrent),
        ("edge_cases", t09.test_edge_cases),
        ("graceful_shutdown", t10.test_graceful_shutdown),
        ("cache_load", t11.test_cache_load),
    ]

    passed = 0
    failed = 0
    for name, test_func in db_tests:
        try:
            await test_func()
            passed += 1
            print(f"  ✅ {name}")
        except Exception as e:
            failed += 1
            all_passed = False
            print(f"  ❌ {name}: {e}")

    print(f"  DB Tests: {passed} passed, {failed} failed")

    # Router тесты
    print("\n--- Router Tests ---")
    crud_ok = await crud.run_all_tests()
    custom_ok = await custom.run_all_tests()

    if not crud_ok or not custom_ok:
        all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    else:
        print("НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
    print("=" * 50)

    return all_passed