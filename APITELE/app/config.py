from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl, Field

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"

# Runtime env (Docker/K8s/server) phải ưu tiên, .env chỉ là fallback local.
load_dotenv(ENV_FILE, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")

    BOT_TOKEN: str

    ORDER_API_BASE: AnyUrl
    PAYMENT_API_BASE: AnyUrl
    ADMIN_API_BASE: AnyUrl | None = None
    BACKEND_BOT_API_KEY: str = Field(default="change_me_bot")

    ENV: str = "prod"
    LOG_DIR: str = "logs"

    # Rate limiting - tối ưu cho 4-50 người sử dụng cùng lúc
    RATE_LIMIT_PER_MIN: int = 60  # Tăng từ 30 lên 60 requests/phút cho high concurrency
    FLOOD_WINDOW_SEC: int = 6  # Window 6 giây để kiểm tra flood
    FLOOD_MAX_MSG: int = 8  # Cho phép 8 messages trong 6 giây (vừa đủ cho user bình thường)

    # Backend có thể >5s khi DB bận; tránh kết hợp với sock_read quá ngắn (đã bỏ trong HttpClient).
    HTTP_TIMEOUT_SEC: int = 20
    HTTP_RETRIES: int = 2  # Giữ nguyên 2 lần retry

    # Telegram API settings - timeout và retry cho Telegram API calls
    TELEGRAM_API_TIMEOUT: int = 60  # Timeout 60 giây cho Telegram API requests
    TELEGRAM_API_RETRIES: int = 3  # Số lần retry cho Telegram API calls
    TELEGRAM_VERIFY_ON_START: bool = False  # Skip verification khi start (aiogram sẽ tự verify khi polling)

    TOPUP_POLL_INTERVAL_SEC: int = 10
    TOPUP_POLL_MAX_TIMES: int = 190  # 10s × 190 = 1900s ≈ 31.7 phút (đủ cover 30 phút)

    # Keep warm connections to avoid first-request cold latency after idle periods.
    KEEPALIVE_ENABLED: bool = True
    KEEPALIVE_INTERVAL_SEC: int = 300
    KEEPALIVE_TIMEOUT_SEC: int = 8

    # Polling: không giới hạn số lần restart; backoff exponential (tránh exit process).
    POLLING_BACKOFF_BASE_SEC: float = 5.0
    POLLING_BACKOFF_MAX_SEC: float = 300.0
    POLLING_BACKOFF_JITTER_RATIO: float = 0.15

    # Watchdog: self-ping Telegram + log RAM/tasks định kỳ
    WATCHDOG_INTERVAL_SEC: int = 60
    WATCHDOG_TELEGRAM_FAIL_THRESHOLD: int = 5

    # Health log (RAM, queue ước lượng, reconnect) — không chờ 24h mới log lần đầu
    HEALTH_LOG_INTERVAL_MIN: int = 15

    # Giới hạn kích thước middleware dicts / cache (chống tràn RAM khi nhiều user lướt qua)
    MIDDLEWARE_MAX_TRACKED_USERS: int = 50_000
    PRODUCTS_CACHE_MAX_KEYS: int = 10_000
    USER_BALANCE_CACHE_MAX_KEYS: int = 50_000


settings = Settings()
