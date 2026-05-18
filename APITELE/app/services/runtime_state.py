"""
Trạng thái runtime dùng cho health log / watchdog (một process = một bot).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class BotRuntimeState:
    """Đếm reconnect, lỗi polling, heartbeat Telegram."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    polling_reconnects: int = 0
    last_polling_error: str | None = None
    last_polling_error_at: float = 0.0
    last_telegram_ok_at: float = field(default_factory=time.monotonic)
    consecutive_telegram_ping_failures: int = 0
    last_watchdog_log_at: float = 0.0

    def record_polling_error(self, err: BaseException) -> None:
        with self.lock:
            self.polling_reconnects += 1
            self.last_polling_error = f"{type(err).__name__}: {err!s}"
            self.last_polling_error_at = time.monotonic()

    def record_telegram_ok(self) -> None:
        with self.lock:
            self.last_telegram_ok_at = time.monotonic()
            self.consecutive_telegram_ping_failures = 0

    def record_telegram_fail(self) -> None:
        with self.lock:
            self.consecutive_telegram_ping_failures += 1


runtime_state = BotRuntimeState()
