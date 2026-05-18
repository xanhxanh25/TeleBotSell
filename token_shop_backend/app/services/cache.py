"""
Simple in-memory cache cho products list với thread-safety
"""
from typing import Optional
from datetime import datetime, timedelta
import asyncio

class SimpleCache:
    def __init__(self, ttl_seconds: int = 30):
        self.cache: dict = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()  # Lock để đảm bảo thread-safety
    
    async def get(self, key: str) -> Optional[any]:
        """Async thread-safe get"""
        async with self._lock:
            if key not in self.cache:
                return None
            value, expire_time = self.cache[key]
            if datetime.now() > expire_time:
                del self.cache[key]
                return None
            return value
    
    def get_sync(self, key: str) -> Optional[any]:
        """Synchronous get (for backwards compatibility)"""
        if key not in self.cache:
            return None
        value, expire_time = self.cache[key]
        if datetime.now() > expire_time:
            del self.cache[key]
            return None
        return value
    
    async def set(self, key: str, value: any):
        """Async thread-safe set"""
        async with self._lock:
            expire_time = datetime.now() + self.ttl
            self.cache[key] = (value, expire_time)
    
    def set_sync(self, key: str, value: any):
        """Synchronous set (for backwards compatibility)"""
        expire_time = datetime.now() + self.ttl
        self.cache[key] = (value, expire_time)
    
    async def clear(self, key: str = None):
        """Async thread-safe clear"""
        async with self._lock:
            if key:
                self.cache.pop(key, None)
            else:
                self.cache.clear()
    
    async def cleanup_expired(self) -> int:
        """
        Xóa tất cả expired entries
        Returns: Số lượng entries đã xóa
        """
        async with self._lock:
            now = datetime.now()
            to_remove = []
            for key, (value, expire_time) in self.cache.items():
                if now > expire_time:
                    to_remove.append(key)
            
            for key in to_remove:
                del self.cache[key]
            
            return len(to_remove)
    
    def start_cleanup_task(self, interval_seconds: int = 300):
        """Bắt đầu background task để cleanup định kỳ (mặc định 5 phút)"""
        import asyncio
        import logging
        log = logging.getLogger("cache")
        
        async def _cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    deleted = await self.cleanup_expired()
                    if deleted > 0:
                        log.debug(f"Cache cleanup: removed {deleted} expired entries")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.error(f"Error in cache cleanup: {e}", exc_info=True)
        
        self._cleanup_task = asyncio.create_task(_cleanup_loop())
    
    def stop_cleanup_task(self):
        """Dừng cleanup task"""
        if hasattr(self, '_cleanup_task') and self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
    
    def get_stats(self) -> dict:
        """Lấy thống kê về cache"""
        now = datetime.now()
        total = len(self.cache)
        expired = sum(1 for _, (_, expire_time) in self.cache.items() if now > expire_time)
        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
        }

# Global cache instance - Tối ưu TTL cho high concurrency
products_cache = SimpleCache(ttl_seconds=15)  # Cache 15 giây để giảm API calls khi nhiều người dùng
user_balance_cache = SimpleCache(ttl_seconds=10)  # Cache balance 10 giây (balance cần update nhanh hơn)

