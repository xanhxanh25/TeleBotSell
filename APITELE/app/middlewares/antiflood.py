import time
import asyncio
import threading
import logging
from collections import defaultdict, deque
from aiogram import BaseMiddleware
from aiogram.types import Message
from app.i18n import t
from app.config import settings

log = logging.getLogger("antiflood")


class AntiFloodMiddleware(BaseMiddleware):
    def __init__(
        self,
        window_sec: int = 6,
        max_msg: int = 6,
        spam_ban_minutes: int = 10,
        max_tracked_users: int | None = None,
    ):
        """
        Args:
            window_sec: Time window để kiểm tra flood (giây)
            max_msg: Số message tối đa trong window trước khi cảnh báo
            spam_ban_minutes: Số phút chặn khi phát hiện spam
        """
        self.window_sec = window_sec
        self.max_msg = max_msg
        self.spam_ban_minutes = spam_ban_minutes
        self.max_tracked_users = max_tracked_users or settings.MIDDLEWARE_MAX_TRACKED_USERS
        self.buff = defaultdict(lambda: deque())
        # Dictionary lưu thời gian bị chặn: {user_id: ban_until_timestamp}
        self.banned_until = {}
        # Set để đánh dấu đã gửi thông báo chặn (chỉ gửi 1 lần khi mới chặn)
        self.ban_notification_sent = set()
        # Lock riêng cho mỗi user để tối ưu concurrent access
        self._user_locks: dict[int, threading.RLock] = {}
        self._locks_lock = threading.Lock()  # Lock để tạo user locks
        self._global_lock = threading.Lock()  # Lock cho banned_until và ban_notification_sent

    def _get_user_lock(self, uid: int) -> threading.RLock:
        """Lấy lock cho user cụ thể - thread-safe"""
        if uid not in self._user_locks:
            with self._locks_lock:
                if uid not in self._user_locks:
                    self._user_locks[uid] = threading.RLock()
        return self._user_locks[uid]

    def _prune_stale(self) -> None:
        if len(self.buff) < 4096:
            return
        empty_uids = [uid for uid, q in self.buff.items() if not q]
        for uid in empty_uids:
            if uid in self.banned_until:
                continue
            try:
                del self.buff[uid]
            except KeyError:
                pass
            with self._locks_lock:
                self._user_locks.pop(uid, None)
        if len(self.buff) > self.max_tracked_users:
            overflow = len(self.buff) - self.max_tracked_users
            for uid in list(self.buff.keys())[: max(overflow + 500, 0)]:
                if uid in self.banned_until:
                    continue
                try:
                    del self.buff[uid]
                except KeyError:
                    pass
                with self._locks_lock:
                    self._user_locks.pop(uid, None)
            log.warning("antiflood: forced prune ~%s buff entries", overflow + 500)

    def _is_banned(self, uid: int, now: float) -> bool:
        """Kiểm tra user có đang bị chặn không - thread-safe"""
        with self._global_lock:
            if uid not in self.banned_until:
                return False
            ban_until = self.banned_until[uid]
            if now >= ban_until:
                # Hết hạn chặn, xóa khỏi dict và notification set
                del self.banned_until[uid]
                self.ban_notification_sent.discard(uid)
                return False
            return True

    def _ban_user(self, uid: int, now: float):
        """Chặn user trong spam_ban_minutes phút - thread-safe"""
        with self._global_lock:
            ban_until = now + (self.spam_ban_minutes * 60)
            self.banned_until[uid] = ban_until

    async def __call__(self, handler, event, data):
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        uid = event.from_user.id
        now = time.time()
        
        # Khởi tạo biến để tránh UnboundLocalError
        should_ban = False
        is_flood = False
        
        # Kiểm tra ban status TRƯỚC - nhanh nhất có thể để bỏ qua banned users ngay
        # Điều này giúp bot không tốn tài nguyên xử lý message từ users đã bị chặn
        if self._is_banned(uid, now):
            # User đang bị chặn - bỏ qua message hoàn toàn, không xử lý gì cả
            # Return ngay lập tức để không block event loop
            return
        
        # Kiểm tra flood - dùng lock riêng cho user để không block users khác
        user_lock = self._get_user_lock(uid)
        with user_lock:
            q = self.buff[uid]
            # Cleanup old entries
            while q and (now - q[0]) > self.window_sec:
                q.popleft()
            
            q.append(now)
            msg_count = len(q)
            
            # Phát hiện spam nghiêm trọng
            if msg_count > self.max_msg * 2:
                should_ban = True
                self._ban_user(uid, now)
                is_flood = True
            elif msg_count > self.max_msg:
                violation_count = msg_count - self.max_msg
                if violation_count >= 3:
                    # Vi phạm 3 lần liên tiếp - chặn
                    should_ban = True
                    self._ban_user(uid, now)
                    is_flood = True
                else:
                    # Chỉ cảnh báo flood
                    is_flood = True
        
        # Xử lý ngoài lock - banned users đã return ở trên
        
        if should_ban:
            # Spam nghiêm trọng - vừa mới chặn
            # Chỉ gửi thông báo 1 lần duy nhất khi mới chặn (nếu chưa gửi)
            with self._global_lock:
                if uid not in self.ban_notification_sent:
                    self.ban_notification_sent.add(uid)
                    need_notify = True
                else:
                    need_notify = False
            
            if need_notify:
                # Chỉ gửi thông báo lần đầu tiên khi mới chặn - fire and forget để không block
                lang = "vi"
                try:
                    storage = data.get("storage")
                    if storage:
                        s = storage.get(uid)
                        lang = s.lang if hasattr(s, 'lang') else "vi"
                except Exception:
                    pass
                
                message = t(lang, "spam_blocked", minutes=self.spam_ban_minutes)
                # Fire and forget - không await để tránh block event loop
                try:
                    asyncio.create_task(asyncio.wait_for(event.answer(message), timeout=2.0))
                except Exception:
                    # Bỏ qua nếu không tạo được task - không block bot
                    pass
            # Sau khi gửi thông báo (hoặc không cần), return để không xử lý message này
            self._prune_stale()
            return
        
        if is_flood:
            # Chỉ cảnh báo flood - gửi message nhưng không block nếu lỗi
            lang = "vi"
            try:
                storage = data.get("storage")
                if storage:
                    s = storage.get(uid)
                    lang = s.lang if hasattr(s, 'lang') else "vi"
            except Exception:
                pass
            
            # Fire and forget để tránh block
            try:
                asyncio.create_task(asyncio.wait_for(event.answer(t(lang, "flood_warning")), timeout=2.0))
            except Exception:
                pass
            self._prune_stale()
            return

        self._prune_stale()
        return await handler(event, data)
