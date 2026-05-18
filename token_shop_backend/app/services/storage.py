from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict
import asyncio
import threading
from datetime import datetime, timedelta

@dataclass
class UserSession:
    lang: str = "en"  # Mặc định tiếng Anh
    state: str = "idle"
    product_id: Optional[str] = None
    qty: Optional[int] = None
    coupon: Optional[str] = None
    topup_network: Optional[str] = None
    topup_coin: Optional[str] = None
    # History pagination
    history_month: Optional[int] = None
    history_year: Optional[int] = None
    history_page: Optional[int] = None
    # Error/Warranty flow
    error_order_id: Optional[str] = None
    error_reason: Optional[str] = None  # Lý do bảo hành
    last_activity: datetime = field(default_factory=datetime.now)  # Track last activity

class MemoryStorage:
    def __init__(self, cleanup_interval_hours: int = 24, inactive_hours: int = 168):
        """
        Args:
            cleanup_interval_hours: Chạy cleanup mỗi X giờ (mặc định 24h)
            inactive_hours: Xóa sessions không hoạt động sau X giờ (mặc định 7 ngày)
        """
        self.sessions = defaultdict(UserSession)
        # Dùng threading.RLock cho thread-safety với GIL (nhanh hơn asyncio.Lock cho simple operations)
        # Mỗi user có lock riêng để tối ưu concurrent access
        self._user_locks: dict[int, threading.RLock] = {}
        self._locks_lock = threading.Lock()  # Lock để tạo user locks
        self._cleanup_lock = threading.Lock()  # Lock cho cleanup operations
        self.cleanup_interval = timedelta(hours=cleanup_interval_hours)
        self.inactive_threshold = timedelta(hours=inactive_hours)
        self._cleanup_task: Optional[asyncio.Task] = None

    def _get_user_lock(self, tid: int) -> threading.RLock:
        """Lấy lock cho user cụ thể - thread-safe"""
        # Double-checked locking pattern để tối ưu
        if tid not in self._user_locks:
            with self._locks_lock:
                if tid not in self._user_locks:
                    self._user_locks[tid] = threading.RLock()
        return self._user_locks[tid]

    def get(self, tid: int) -> UserSession:
        """
        Thread-safe get session - tối ưu cho concurrent access
        Mỗi user có lock riêng để không block các users khác
        """
        user_lock = self._get_user_lock(tid)
        with user_lock:
            session = self.sessions[tid]
            session.last_activity = datetime.now()  # Update activity time
            return session

    def set_lang(self, tid: int, lang: str):
        """Thread-safe set language"""
        user_lock = self._get_user_lock(tid)
        with user_lock:
            s = self.sessions[tid]
            s.lang = lang
            s.last_activity = datetime.now()

    def reset_flow(self, tid: int):
        """Thread-safe reset flow"""
        user_lock = self._get_user_lock(tid)
        with user_lock:
            s = self.sessions[tid]
            s.state = "idle"
            s.product_id = None
            s.qty = None
            s.coupon = None
            s.topup_network = None
            s.topup_coin = None
            s.last_activity = datetime.now()
    
    async def cleanup_inactive_sessions(self) -> int:
        """
        Xóa các sessions không hoạt động quá lâu
        Returns: Số lượng sessions đã xóa
        Note: Chạy trong executor để tránh block event loop
        """
        def _cleanup():
            with self._cleanup_lock:
                now = datetime.now()
                to_remove = []
                # Tạo copy của keys để tránh modify dict trong khi iterate
                for tid in list(self.sessions.keys()):
                    user_lock = self._get_user_lock(tid)
                    with user_lock:
                        session = self.sessions.get(tid)
                        if session and now - session.last_activity > self.inactive_threshold:
                            to_remove.append(tid)
                
                # Xóa sessions và locks
                for tid in to_remove:
                    with self._locks_lock:
                        self.sessions.pop(tid, None)
                        self._user_locks.pop(tid, None)
                
                return len(to_remove)
        
        # Chạy trong executor để tránh block event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _cleanup)
    
    def start_cleanup_task(self):
        """Bắt đầu background task để cleanup định kỳ"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Background loop để cleanup định kỳ"""
        import logging
        log = logging.getLogger("storage")
        
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval.total_seconds())
                deleted = await self.cleanup_inactive_sessions()
                if deleted > 0:
                    log.info(f"Cleaned up {deleted} inactive sessions. Active sessions: {len(self.sessions)}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in storage cleanup: {e}", exc_info=True)
    
    def stop_cleanup_task(self):
        """Dừng cleanup task"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
    
    def get_stats(self) -> dict:
        """Lấy thống kê về storage"""
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": sum(
                1 for s in self.sessions.values()
                if datetime.now() - s.last_activity < timedelta(hours=1)
            ),
        }
