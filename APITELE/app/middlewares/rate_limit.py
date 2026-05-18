import time
import asyncio
import threading
import logging
from collections import defaultdict, deque
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from app.config import settings

log = logging.getLogger("rate_limit")


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, max_per_min: int = 30, max_tracked_users: int | None = None):
        self.max_per_min = max_per_min
        self.max_tracked_users = max_tracked_users or settings.MIDDLEWARE_MAX_TRACKED_USERS
        self.hits = defaultdict(lambda: deque())
        # Lock riêng cho mỗi user để tối ưu concurrent access
        self._user_locks: dict[int, threading.RLock] = {}
        self._locks_lock = threading.Lock()  # Lock để tạo user locks

    def _get_user_lock(self, uid: int) -> threading.RLock:
        """Lấy lock cho user cụ thể - thread-safe"""
        if uid not in self._user_locks:
            with self._locks_lock:
                if uid not in self._user_locks:
                    self._user_locks[uid] = threading.RLock()
        return self._user_locks[uid]

    def _prune_stale(self) -> None:
        """Xóa deque rỗng và cắt bớt khi vượt max — tránh phình dict/lock theo mọi user từng chạm."""
        if len(self.hits) < 4096:
            return
        empty_uids = [uid for uid, q in self.hits.items() if not q]
        for uid in empty_uids:
            try:
                del self.hits[uid]
            except KeyError:
                pass
            with self._locks_lock:
                self._user_locks.pop(uid, None)
        if len(self.hits) > self.max_tracked_users:
            overflow = len(self.hits) - self.max_tracked_users
            for uid in list(self.hits.keys())[: max(overflow + 500, 0)]:
                try:
                    del self.hits[uid]
                except KeyError:
                    pass
                with self._locks_lock:
                    self._user_locks.pop(uid, None)
            log.warning("rate_limit: forced prune ~%s entries (over max_tracked_users)", overflow + 500)

    async def __call__(self, handler, event, data):
        uid = None
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            uid = event.from_user.id
        if uid is None:
            return await handler(event, data)

        # Kiểm tra rate limit - dùng lock riêng cho user để không block users khác
        rate_limited = False
        user_lock = self._get_user_lock(uid)
        with user_lock:
            now = time.time()
            q = self.hits[uid]
            # Cleanup old entries (older than 60 seconds)
            while q and (now - q[0]) > 60:
                q.popleft()
            if not q:
                try:
                    del self.hits[uid]
                except KeyError:
                    pass

            q = self.hits[uid]
            # Check rate limit
            if len(q) >= self.max_per_min:
                rate_limited = True
            else:
                q.append(now)
        
        # Xử lý rate limit ngoài lock - fire and forget để không block
        if rate_limited:
            if isinstance(event, Message):
                try:
                    # Fire and forget - không await để tránh block event loop
                    asyncio.create_task(asyncio.wait_for(
                        event.answer("⏳ Bạn thao tác hơi nhanh, thử lại sau vài giây nhé."), 
                        timeout=2.0
                    ))
                except Exception:
                    # Bỏ qua nếu không tạo được task - không block bot
                    pass
            elif isinstance(event, CallbackQuery):
                try:
                    asyncio.create_task(asyncio.wait_for(
                        event.answer("⏳ Too fast, please try again in a moment."),
                        timeout=2.0,
                    ))
                except Exception:
                    pass
            self._prune_stale()
            return

        self._prune_stale()
        return await handler(event, data)
