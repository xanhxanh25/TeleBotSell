import asyncio
import logging
from contextlib import asynccontextmanager

log = logging.getLogger("flow_runtime")


class UserActionGuard:
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def _get_lock(self, user_id: int) -> asyncio.Lock:
        async with self._guard:
            lock = self._locks.get(user_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[user_id] = lock
            return lock

    async def try_acquire(self, user_id: int, timeout_sec: float = 0.05) -> bool:
        lock = await self._get_lock(user_id)
        try:
            await asyncio.wait_for(lock.acquire(), timeout=timeout_sec)
            return True
        except asyncio.TimeoutError:
            return False

    async def release(self, user_id: int) -> None:
        lock = await self._get_lock(user_id)
        if lock.locked():
            lock.release()

    @asynccontextmanager
    async def hold(self, user_id: int, timeout_sec: float = 0.05):
        acquired = await self.try_acquire(user_id, timeout_sec=timeout_sec)
        try:
            yield acquired
        finally:
            if acquired:
                await self.release(user_id)


class UserTaskRegistry:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: dict[int, dict[str, asyncio.Task]] = {}

    async def register_singleton(self, user_id: int, key: str, task: asyncio.Task) -> None:
        async with self._lock:
            user_tasks = self._tasks.setdefault(user_id, {})
            old = user_tasks.get(key)
            if old and not old.done():
                old.cancel()
            user_tasks[key] = task
            task.add_done_callback(lambda _: asyncio.create_task(self._cleanup_key(user_id, key)))

    async def _cleanup_key(self, user_id: int, key: str) -> None:
        async with self._lock:
            user_tasks = self._tasks.get(user_id)
            if not user_tasks:
                return
            cur = user_tasks.get(key)
            if cur is None or cur.done():
                user_tasks.pop(key, None)
            if not user_tasks:
                self._tasks.pop(user_id, None)

    async def cancel_user_tasks(self, user_id: int) -> int:
        async with self._lock:
            user_tasks = self._tasks.pop(user_id, {})
        cancelled = 0
        for task in user_tasks.values():
            if not task.done():
                task.cancel()
                cancelled += 1
        return cancelled

    async def stats(self) -> dict:
        async with self._lock:
            users = len(self._tasks)
            active_tasks = sum(len(v) for v in self._tasks.values())
        return {"tracked_users": users, "active_tasks": active_tasks}


action_guard = UserActionGuard()
task_registry = UserTaskRegistry()


async def reset_user_flow(storage, user_id: int, reason: str = "") -> None:
    storage.reset_flow(user_id)
    cancelled = await task_registry.cancel_user_tasks(user_id)
    if cancelled > 0:
        log.info("flow_reset user=%s reason=%s cancelled_tasks=%s", user_id, reason or "-", cancelled)
