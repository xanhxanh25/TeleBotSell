# Báo cáo audit & sửa bot Telegram (APITELE) — production stability

## 1. Bot dừng vì đâu (root cause trong code)

Không có log production từ server của bạn trong repo; phân tích **tĩnh trên toàn bộ source** chỉ ra các đường thoát/khối **chắc chắn** sau:

### A. Process thoát hẳn sau lỗi polling (nguyên nhân “chạy nửa ngày rồi tắt” phổ biến nhất)

**File:** `app/main.py` (phiên bản cũ)

- Vòng `for restart_attempt in range(max_restart_attempts)` với `max_restart_attempts = 5`.
- Sau 5 lần `dp.start_polling` ném exception (mạng Telegram, DNS, timeout, SSL, v.v.), code log `Max restart attempts reached` và **`raise RuntimeError(...)`** → `asyncio.run()` kết thúc → **tiến trình Python dừng** (trừ khi có systemd/docker restart).
- Đây là **exit có điều kiện duy nhất** trong code không phụ thuộc Ctrl+C.

### B. Tràn RAM theo thời gian (nhiều user khác nhau)

**Files:** `app/middlewares/rate_limit.py`, `app/middlewares/antiflood.py`

- `self.hits[uid]` / `self.buff[uid]` dùng `defaultdict(deque)`: sau khi deque được trim hết phần tử cũ, **key `uid` vẫn tồn tại** với deque rỗng.
- `self._user_locks[uid]` **không bao giờ** bị xóa theo user cũ.
- Kết quả: số entry ~ số user từng tương tác bot → **tăng monotonic** (hàng nghìn / hàng chục nghìn user → hàng MB–hàng trăm MB tùy tải).

### C. Cache in-memory không giới hạn số key

**File:** `app/services/cache.py` (phiên bản cũ)

- `dict` không giới hạn; chỉ TTL theo thời gian. Nếu key đa dạng (vd. kết hợp `lang`), vẫn có thể phình.

### D. Shutdown không await cleanup task

**Files:** `app/services/storage.py`, `app/services/cache.py`

- Chỉ `task.cancel()` mà không `await` → có thể cảnh báo “task was destroyed” hoặc tài nguyên chưa flush trong edge cases.

### E. Health không đủ để vận hành

**File:** `app/services/health.py` (phiên bản cũ)

- Log mỗi **24 giờ** và không có RSS/task/thread → khó thấy trước khi OOM hoặc khi process đã chết.

---

## 2. File đã sửa / thêm

| File | Thay đổi |
|------|----------|
| `app/main.py` | Polling **vô hạn** + **backoff có jitter**; bỏ `raise RuntimeError` fatal; watchdog + health log tần suất hợp lý; shutdown `await` cleanup cache/storage; import `products_cache` rõ ràng. |
| `app/config.py` | Thêm: `POLLING_BACKOFF_*`, `WATCHDOG_*`, `HEALTH_LOG_INTERVAL_MIN`, `MIDDLEWARE_MAX_TRACKED_USERS`, `PRODUCTS_CACHE_MAX_KEYS`, `USER_BALANCE_CACHE_MAX_KEYS`. |
| `app/services/health.py` | `psutil` (optional): RSS, threads, inet connections; log định kỳ có RAM/tasks/reconnects; `watchdog_loop` self-ping `get_me`. |
| `app/services/runtime_state.py` | **Mới**: đếm reconnect / lỗi polling / streak ping Telegram fail. |
| `app/services/cache.py` | `OrderedDict` + `max_keys` + LRU-style eviction; `stop_cleanup_task_async`. |
| `app/services/storage.py` | `stop_cleanup_task_async`. |
| `app/middlewares/rate_limit.py` | `_prune_stale` + giới hạn tracked users. |
| `app/middlewares/antiflood.py` | `_prune_stale` tương tự. |
| `app/services/http_client.py` | `close()` kiểm tra `session.closed`. |
| `requirements.txt` | Thêm `psutil>=5.9.0`. |

---

## 3. Cơ chế giữ sống & tự phục hồi

1. **Reconnect polling vô hạn** với exponential backoff (trần `POLLING_BACKOFF_MAX_SEC`, mặc định 300s) + jitter — tránh reconnect storm.
2. **Watchdog** (`watchdog_loop`): định kỳ `bot.get_me()`; đếm fail liên tiếp; log `CRITICAL` khi vượt ngưỡng (token/mạng).
3. **Keepalive** (giữ nguyên ý tưởng): ping Telegram + `/health` backend + jitter sleep.
4. **Health log** mỗi `HEALTH_LOG_INTERVAL_MIN` (mặc định 15 phút) + **log ngay khi start** — có RSS, tasks, threads, sessions, cache, reconnect count.

---

## 4. Chống nghẽn & chống tràn RAM

| Vấn đề | Cách xử lý |
|--------|------------|
| Dict middleware phình | Prune deque rỗng + cắt khi vượt `MIDDLEWARE_MAX_TRACKED_USERS`. |
| Cache phình | `PRODUCTS_CACHE_MAX_KEYS` / `USER_BALANCE_CACHE_MAX_KEYS` + eviction LRU. |
| Không thấy trước OOM | Health log RSS (psutil) + watchdog. |
| Task leak shutdown | `await stop_cleanup_task_async` cho storage & cache. |

---

## 5. Log xoay vòng

**File:** `app/logging_setup.py` — đã có `RotatingFileHandler` (5MB × 5). **Không đổi** trong đợt này.

---

## 6. Việc cần làm trên server (ngoài code)

- Chạy bot dưới **systemd** / **docker restart policy** để đỡ sập khi OOM hoặc lỗi hệ thống.
- Theo dõi **`journalctl` / file log** sau deploy: tìm `Polling error`, `watchdog: Telegram unreachable`, `rate_limit: forced prune`.
- Cài đủ dependency: `pip install -r requirements.txt` (có `psutil`).

---

## 7. Điều không thể khẳng định chỉ từ code

- **OOM killer** (Linux), **Windows service kill**, **token Telegram bị revoke**, **firewall** — cần log hệ thống tại thời điểm sự cố.

---

*Tài liệu này khớp với các thay đổi trong cùng commit/tree chứa `REPORT_FIX.md`.*
