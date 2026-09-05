"""Мониторинг статистики инфраструктуры и сценариев в реальном времени.

Использование:
    python monitor.py                # обновление каждые 0.5 секунды
    python monitor.py 1.0            # обновление каждую секунду
    python monitor.py 0.25           # обновление 4 раза в секунду

Остановка: Ctrl+C
"""

import sys
import os
import asyncio
import httpx


BASE_URL = os.getenv("API_URL", "http://localhost:8000")
INFRA_ENDPOINT = "/system/stats"
SCENARIO_ENDPOINT = "/system/scenario-metrics"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    hours = minutes // 60
    minutes = minutes % 60
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


def print_infra_stats(stats: dict, interval: float):
    uptime = format_duration(stats["uptime_seconds"])

    print("=" * 70)
    print(f"  EVENT INFRASTRUCTURE MONITOR")
    print(f"  Uptime: {uptime}  |  Interval: {interval}s  |  Ctrl+C to stop")
    print("=" * 70)
    print()
    print(f"  TOTAL PROCESSED: {stats['total_processed']:<8}  "
          f"FAILED: {stats['total_failed']:<6}  "
          f"QUEUED: {stats['total_queued']:<6}  "
          f"CACHE: {stats['cache_size']}")
    print(f"  ACCEPTING TASKS: {'YES' if stats['is_accepting'] else 'NO'}")
    print()
    print(f"  {'CHANNEL':<10} {'WORKERS':<10} {'POOL':<8} {'QUEUE':<8} "
          f"{'PROCESSED':<12} {'FAILED':<8} {'AVG TIME':<10}")
    print(f"  {'-'*10} {'-'*10} {'-'*8} {'-'*8} {'-'*12} {'-'*8} {'-'*10}")

    for name, ch in stats["channels"].items():
        workers = f"{ch['active_workers']}/{ch['pool_size']}"
        queue = f"{ch['queue_size']}"
        avg = f"{ch['avg_time_ms']:.1f}ms"
        print(f"  {name:<10} {workers:<10} {ch['pool_size']:<8} "
              f"{queue:<8} {ch['tasks_processed']:<12} {ch['tasks_failed']:<8} {avg:<10}")

    print()


def print_scenario_stats(data: dict):
    scenarios = data.get("scenarios", [])
    if not scenarios:
        print("=" * 70)
        print(f"  CORE SCENARIO METRICS — no data yet")
        print("=" * 70)
        return

    print("=" * 70)
    print(f"  CORE SCENARIO METRICS")
    print("=" * 70)
    print(f"  {'SCENARIO':<30} {'CALLS':>6} {'AVG':>8} {'MIN':>8} {'MAX':>8} {'ERR':>5}  ERROR CODES")
    print(f"  {'-'*30} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*5}  {'-'*30}")

    for s in scenarios:
        codes_str = ", ".join(f"{k}:{v}" for k, v in s.get("error_codes", {}).items())
        print(f"  {s['scenario']:<30} {s['calls']:>6} {s['avg_ms']:>7.1f}ms {s['min_ms']:>7.1f}ms {s['max_ms']:>7.1f}ms {s['errors']:>5}  {codes_str}")

    total_calls = sum(s['calls'] for s in scenarios)
    total_errors = sum(s['errors'] for s in scenarios)
    print(f"  {'-'*30} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*5}")
    print(f"  {'TOTAL':<30} {total_calls:>6} {'':>8} {'':>8} {'':>8} {total_errors:>5}")
    print("=" * 70)


async def monitor(interval: float = 0.5):
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=5.0) as client:
        while True:
            try:
                infra_resp = await client.get(INFRA_ENDPOINT)
                scenario_resp = await client.get(SCENARIO_ENDPOINT)

                if infra_resp.status_code == 200:
                    clear_screen()
                    print_infra_stats(infra_resp.json(), interval)

                    if scenario_resp.status_code == 200:
                        print_scenario_stats(scenario_resp.json())
                else:
                    print(f"Error: {infra_resp.status_code}")
            except httpx.ConnectError:
                print(f"Waiting for server at {BASE_URL}...")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

            await asyncio.sleep(interval)


if __name__ == "__main__":
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
    try:
        asyncio.run(monitor(interval))
    except KeyboardInterrupt:
        print("\nStopped.")