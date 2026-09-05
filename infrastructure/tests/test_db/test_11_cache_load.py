"""Нагрузочный тест кеширования на model_test."""

import asyncio
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = None
TABLE = "model_test"
TOTAL = 100_000


async def test_cache_load():
    # Очищаем таблицу перед тестом
    await router.execute("admin", f'TRUNCATE TABLE "{TABLE}" RESTART IDENTITY CASCADE')
    
    try:
        # Наполняем 100 записей через CRUD (чтобы кеш мог работать)
        for i in range(1, 101):
            r = await router.create(TABLE, {"val": i, "name": f"record_{i}"}, channel="write")
            assert r.success, f"Seed failed: {r.error}"
        logger.info("Seeded 100 rows via CRUD")
        
        stats = {"read_hit": 0, "read_miss": 0, "read_total": 0, "write_total": 0,
                 "create_total": 0, "update_total": 0, "errors": 0}
        latencies = {"read_cached": [], "read_uncached": [], "write": [], "update": []}
        
        start = time.monotonic()
        last_log = start
        
        async def do_read(i: int):
            entity_id = (i % 100) + 1
            t0 = time.monotonic()
            r = await router.read(TABLE, entity_id, cache=True)
            dt = (time.monotonic() - t0) * 1000
            if r.success:
                stats["read_total"] += 1
                if dt < 0.5:
                    stats["read_hit"] += 1
                    latencies["read_cached"].append(dt)
                else:
                    stats["read_miss"] += 1
                    latencies["read_uncached"].append(dt)
            else:
                stats["errors"] += 1
        
        async def do_read_no_cache(i: int):
            entity_id = (i % 100) + 1
            r = await router.read(TABLE, entity_id, cache=False)
            if r.success:
                stats["read_total"] += 1
                stats["read_miss"] += 1
            else:
                stats["errors"] += 1
        
        async def do_write(i: int):
            t0 = time.monotonic()
            r = await router.execute("write", f'UPDATE "{TABLE}" SET val = val + 1 WHERE id = :id',
                                    {"id": (i % 100) + 1})
            dt = (time.monotonic() - t0) * 1000
            if r.success:
                stats["write_total"] += 1
                latencies["write"].append(dt)
            else:
                stats["errors"] += 1
        
        async def do_update(i: int):
            t0 = time.monotonic()
            r = await router.update(TABLE, (i % 100) + 1, {"name": f"updated_{i}"}, channel="write")
            dt = (time.monotonic() - t0) * 1000
            if r.success:
                stats["update_total"] += 1
                latencies["update"].append(dt)
            else:
                stats["errors"] += 1
        
        async def do_create(i: int):
            r = await router.create(TABLE, {"val": 1000 + i, "name": f"bulk_{i}"}, channel="write")
            if r.success:
                stats["create_total"] += 1
            else:
                stats["errors"] += 1
        
        BATCH = 500
        
        # Фаза 1: Прогрев кеша — читаем все 100 записей по 10 раз (1 000 запросов)
        logger.info("Phase 0: Cache warmup (1 000 reads with cache=True)...")
        for i in range(0, 1_000, BATCH):
            batch = [asyncio.create_task(do_read(j)) for j in range(i, min(i + BATCH, 1_000))]
            await asyncio.gather(*batch)
        
        # Фаза 2: Массовое чтение с кешем (50 000)
        logger.info("Phase 1: Cached reads (50 000)...")
        for i in range(0, 50_000, BATCH):
            batch = [asyncio.create_task(do_read(j)) for j in range(i, min(i + BATCH, 50_000))]
            await asyncio.gather(*batch)
            
            now = time.monotonic()
            if now - last_log >= 2.0:
                elapsed = now - start
                done = stats["read_total"] + stats["write_total"] + stats["update_total"] + stats["create_total"]
                logger.info(f"  {done} ops, {done/elapsed:.0f} ops/sec, "
                          f"hits={stats['read_hit']}, misses={stats['read_miss']}, "
                          f"hit_rate={stats['read_hit']/max(stats['read_total'],1)*100:.1f}%")
                last_log = now
        
        # Фаза 3: Чтение без кеша (10 000) — для сравнения
        logger.info("Phase 2: Uncached reads (10 000)...")
        for i in range(0, 10_000, BATCH):
            batch = [asyncio.create_task(do_read_no_cache(j)) for j in range(i, min(i + BATCH, 10_000))]
            await asyncio.gather(*batch)
        
        # Фаза 4: Смешанная с обновлениями через CRUD (25 000)
        logger.info("Phase 3: Mixed with CRUD updates (25 000)...")
        for i in range(0, 25_000, BATCH):
            batch = []
            for j in range(i, min(i + BATCH, 25_000)):
                if j % 5 == 0:
                    batch.append(asyncio.create_task(do_update(j)))
                elif j % 5 == 1:
                    batch.append(asyncio.create_task(do_write(j)))
                else:
                    batch.append(asyncio.create_task(do_read(j)))
            await asyncio.gather(*batch)
        
        # Фаза 5: Создание через CRUD (4 000)
        logger.info("Phase 4: Creates via CRUD (4 000)...")
        for i in range(0, 4_000, BATCH):
            batch = [asyncio.create_task(do_create(j)) for j in range(i, min(i + BATCH, 4_000))]
            await asyncio.gather(*batch)
        
        elapsed = time.monotonic() - start
        total_done = stats["read_total"] + stats["write_total"] + stats["update_total"] + stats["create_total"]
        
        print("\n" + "=" * 60)
        print("  НАГРУЗОЧНЫЙ ТЕСТ КЕШИРОВАНИЯ — 90 000 ОПЕРАЦИЙ")
        print("=" * 60)
        print(f"  Всего операций:     {total_done}")
        print(f"  Ошибок:             {stats['errors']}")
        print(f"  Время:              {elapsed:.1f}s")
        print(f"  Throughput:         {total_done/elapsed:.0f} ops/sec")
        print()
        print(f"  Чтений всего:       {stats['read_total']}")
        print(f"  Чтений из кеша:     {stats['read_hit']} ({stats['read_hit']/max(stats['read_total'],1)*100:.1f}%)")
        print(f"  Чтений мимо кеша:   {stats['read_miss']} ({stats['read_miss']/max(stats['read_total'],1)*100:.1f}%)")
        print(f"  Записей (UPDATE):   {stats['write_total']}")
        print(f"  Обновлений (CRUD):  {stats['update_total']}")
        print(f"  Созданий (CRUD):    {stats['create_total']}")
        print()
        
        if latencies["read_cached"]:
            avg = sum(latencies["read_cached"]) / len(latencies["read_cached"])
            mn = min(latencies["read_cached"])
            mx = max(latencies["read_cached"])
            print(f"  Latency CACHE HIT:    avg={avg:.3f}ms, min={mn:.3f}ms, max={mx:.3f}ms, samples={len(latencies['read_cached'])}")
        if latencies["read_uncached"]:
            avg = sum(latencies["read_uncached"]) / len(latencies["read_uncached"])
            mn = min(latencies["read_uncached"])
            mx = max(latencies["read_uncached"])
            print(f"  Latency CACHE MISS:   avg={avg:.2f}ms, min={mn:.2f}ms, max={mx:.2f}ms, samples={len(latencies['read_uncached'])}")
        if latencies["write"]:
            avg = sum(latencies["write"]) / len(latencies["write"])
            print(f"  Latency write (SQL):  avg={avg:.2f}ms, samples={len(latencies['write'])}")
        if latencies["update"]:
            avg = sum(latencies["update"]) / len(latencies["update"])
            print(f"  Latency update (CRUD):avg={avg:.2f}ms, samples={len(latencies['update'])}")
        
        print("=" * 60)
        
        assert stats["errors"] == 0, f"Errors: {stats['errors']}"
        assert stats["read_hit"] > 0, "Cache hits must be > 0 — кеш не работает!"
        
    finally:
        await router.execute("admin", f'TRUNCATE TABLE "{TABLE}" RESTART IDENTITY CASCADE')
        logger.info(f"Table {TABLE} cleaned")