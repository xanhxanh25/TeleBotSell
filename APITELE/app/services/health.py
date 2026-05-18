# app/services/health.py
"""
Health / watchdog: RAM, threads, asyncio tasks, storage/cache, reconnect stats.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Any, Dict

from app.services.cache import products_cache, user_balance_cache
from app.services.runtime_state import runtime_state
from app.services.storage import MemoryStorage

log = logging.getLogger("health")

try:
    import psutil

    _PSUTIL = True
except ImportError:
    psutil = None  # type: ignore
    _PSUTIL = False


def _process_snapshot() -> Dict[str, Any]:
    out: Dict[str, Any] = {"psutil": _PSUTIL}
    if not _PSUTIL:
        return out
    try:
        p = psutil.Process()
        with p.oneshot():
            mi = p.memory_info()
            out["rss_mb"] = round(mi.rss / (1024 * 1024), 2)
            out["vms_mb"] = round(mi.vms / (1024 * 1024), 2)
            out["num_threads"] = p.num_threads()
            try:
                out["open_files"] = len(p.open_files())
            except Exception:
                out["open_files"] = None
            try:
                conns = p.connections(kind="inet")
                out["inet_connections"] = len(conns)
            except Exception:
                out["inet_connections"] = None
    except Exception as e:
        out["error"] = str(e)
    return out


def _asyncio_task_count() -> int:
    try:
        return len(asyncio.all_tasks())
    except Exception:
        return -1


class HealthMonitor:
    """Monitor health và performance của bot."""

    def __init__(self, storage: MemoryStorage):
        self.storage = storage
        self.start_time = datetime.now()

    def get_health_status(self) -> Dict[str, Any]:
        uptime = (datetime.now() - self.start_time).total_seconds()
        storage_stats = self.storage.get_stats()
        cache_stats = {
            "products": products_cache.get_stats(),
            "user_balance": user_balance_cache.get_stats(),
        }
        with runtime_state.lock:
            rs = {
                "polling_reconnects": runtime_state.polling_reconnects,
                "last_polling_error": runtime_state.last_polling_error,
                "consecutive_telegram_ping_failures": runtime_state.consecutive_telegram_ping_failures,
            }
        return {
            "status": "healthy",
            "uptime_seconds": int(uptime),
            "uptime_hours": round(uptime / 3600, 2),
            "storage": storage_stats,
            "cache": cache_stats,
            "asyncio_tasks": _asyncio_task_count(),
            "threads": threading.active_count(),
            "runtime": rs,
            "process": _process_snapshot(),
            "timestamp": datetime.now().isoformat(),
        }

    def log_health_status(self) -> None:
        st = self.get_health_status()
        proc = st.get("process") or {}
        log.info(
            "health rss_mb=%s tasks=%s threads=%s sessions=%s cache_p=%s cache_u=%s "
            "reconnects=%s tg_ping_fail=%s open_files=%s inet_conn=%s",
            proc.get("rss_mb"),
            st.get("asyncio_tasks"),
            st.get("threads"),
            st["storage"].get("total_sessions"),
            st["cache"]["products"].get("active_entries"),
            st["cache"]["user_balance"].get("active_entries"),
            st["runtime"]["polling_reconnects"],
            st["runtime"]["consecutive_telegram_ping_failures"],
            proc.get("open_files"),
            proc.get("inet_connections"),
        )

    def start_periodic_logging(self, interval_minutes: int) -> asyncio.Task:
        async def _loop() -> None:
            try:
                self.log_health_status()
            except Exception as e:
                log.error("initial health log: %s", e, exc_info=True)
            while True:
                try:
                    await asyncio.sleep(max(60, interval_minutes * 60))
                    self.log_health_status()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.error("health logging: %s", e, exc_info=True)

        return asyncio.create_task(_loop())


async def watchdog_loop(
    bot,
    health_monitor: HealthMonitor,
    interval_sec: int,
    ping_timeout: float,
    fail_threshold: int,
) -> None:
    """
    Self-ping Telegram (get_me) định kỳ; log process stats; CRITICAL nếu fail liên tiếp.
    """
    log.info("watchdog started interval=%ss threshold=%s", interval_sec, fail_threshold)
    try:
        while True:
            try:
                await asyncio.sleep(interval_sec)
                try:
                    await asyncio.wait_for(bot.get_me(), timeout=ping_timeout)
                    runtime_state.record_telegram_ok()
                except Exception as e:
                    runtime_state.record_telegram_fail()
                    log.warning("watchdog get_me failed: %s", e)
                    with runtime_state.lock:
                        fails = runtime_state.consecutive_telegram_ping_failures
                    if fails >= fail_threshold:
                        log.critical(
                            "watchdog: Telegram unreachable %s times consecutively — check token/network/firewall",
                            fails,
                        )
                st = health_monitor.get_health_status()
                proc = st.get("process") or {}
                log.info(
                    "watchdog ping_ok rss_mb=%s tasks=%s threads=%s reconnects=%s",
                    proc.get("rss_mb"),
                    st.get("asyncio_tasks"),
                    st.get("threads"),
                    st["runtime"]["polling_reconnects"],
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error("watchdog iteration: %s", e, exc_info=True)
    except asyncio.CancelledError:
        log.info("watchdog cancelled")
        raise
