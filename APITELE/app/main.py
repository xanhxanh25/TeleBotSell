import asyncio
import logging
import random

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import settings
from app.logging_setup import setup_logging
from app.middlewares.rate_limit import RateLimitMiddleware
from app.middlewares.antiflood import AntiFloodMiddleware
from app.middlewares.network_error import NetworkErrorMiddleware

from app.services.http_client import HttpClient
from app.services.order_api import OrderAPI
from app.services.payment_api import PaymentAPI
from app.services.admin_api import AdminAPI
from app.services.storage import MemoryStorage
from app.services.health import HealthMonitor, watchdog_loop
from app.services.runtime_state import runtime_state
from app.services.cache import products_cache

from app.handlers import register_all_handlers

log = logging.getLogger("boot")


async def setup_commands(bot: Bot, timeout: float = 30.0) -> bool:
    """
    Đăng ký danh sách lệnh chạy ngầm (Background Task).
    """
    default_commands = [
        BotCommand(command="start", description="Start / Restart"),
        BotCommand(command="menu", description="View products"),
        BotCommand(command="topup", description="Top up balance"),
        BotCommand(command="me", description="Profile"),
        BotCommand(command="history", description="Order history"),
        BotCommand(command="tickets", description="View warranty tickets"),
        BotCommand(command="help", description="How to use"),
        BotCommand(command="warranty", description="Warranty / report issue"),
        BotCommand(command="error", description="Report an error"),
        BotCommand(command="lang", description="Change language"),
    ]

    vietnamese_commands = [
        BotCommand(command="start", description="Bắt đầu / Reset"),
        BotCommand(command="menu", description="Xem danh sách sản phẩm"),
        BotCommand(command="topup", description="Nạp tiền"),
        BotCommand(command="me", description="Thông tin cá nhân"),
        BotCommand(command="history", description="Lịch sử đơn hàng"),
        BotCommand(command="tickets", description="Xem ticket bảo hành"),
        BotCommand(command="help", description="Hướng dẫn sử dụng"),
        BotCommand(command="warranty", description="Bảo hành / báo lỗi"),
        BotCommand(command="error", description="Báo lỗi"),
        BotCommand(command="lang", description="Đổi ngôn ngữ"),
    ]

    russian_commands = [
        BotCommand(command="start", description="Начать / Перезапустить"),
        BotCommand(command="menu", description="Просмотр товаров"),
        BotCommand(command="topup", description="Пополнить баланс"),
        BotCommand(command="me", description="Профиль"),
        BotCommand(command="history", description="История заказов"),
        BotCommand(command="tickets", description="Тикеты гарантии"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="warranty", description="Гарантия / сообщить о проблеме"),
        BotCommand(command="error", description="Сообщить об ошибке"),
        BotCommand(command="lang", description="Изменить язык"),
    ]

    chinese_commands = [
        BotCommand(command="start", description="开始 / 重启"),
        BotCommand(command="menu", description="查看商品"),
        BotCommand(command="topup", description="充值"),
        BotCommand(command="me", description="个人资料"),
        BotCommand(command="history", description="订单历史"),
        BotCommand(command="tickets", description="保修工单"),
        BotCommand(command="help", description="帮助"),
        BotCommand(command="warranty", description="保修 / 报告问题"),
        BotCommand(command="error", description="报告错误"),
        BotCommand(command="lang", description="更改语言"),
    ]

    max_retries = 3
    retry_delay = 5.0

    for attempt in range(max_retries):
        try:
            results = await asyncio.gather(
                asyncio.wait_for(bot.set_my_commands(default_commands), timeout=timeout),
                asyncio.wait_for(bot.set_my_commands(vietnamese_commands, language_code="vi"), timeout=timeout),
                asyncio.wait_for(bot.set_my_commands(russian_commands, language_code="ru"), timeout=timeout),
                asyncio.wait_for(bot.set_my_commands(chinese_commands, language_code="zh"), timeout=timeout),
                return_exceptions=True,
            )

            errors = []
            success_count = 0
            lang_names = ["Default", "Vi", "Ru", "Zh"]
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    err_name = res.__class__.__name__
                    errors.append(f"{lang_names[i]}: {err_name}")
                else:
                    success_count += 1

            if success_count >= 2:
                log.info(
                    "Bot commands registered successfully (%s/4 languages) on attempt %s",
                    success_count,
                    attempt + 1,
                )
                return True

            if attempt < max_retries - 1:
                log.warning("Cmd registration partial/fail (%s). Retrying...", ", ".join(errors))
                await asyncio.sleep(retry_delay)
        except Exception as e:
            log.error("Unexpected error in setup_commands: %r", e)

    return False


def _backoff_seconds(attempt: int) -> float:
    base = float(settings.POLLING_BACKOFF_BASE_SEC)
    cap = float(settings.POLLING_BACKOFF_MAX_SEC)
    jitter = float(settings.POLLING_BACKOFF_JITTER_RATIO)
    raw = min(cap, base * (2 ** min(attempt, 12)))
    return raw * (1.0 + random.uniform(-jitter, jitter))


async def main() -> None:
    setup_logging(settings.LOG_DIR)

    background_tasks: list[asyncio.Task] = []

    session = AiohttpSession(timeout=float(settings.TELEGRAM_API_TIMEOUT))

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )

    dp = Dispatcher()

    storage = MemoryStorage(cleanup_interval_hours=24, inactive_hours=168)
    storage.start_cleanup_task()

    http = HttpClient(
        timeout_sec=settings.HTTP_TIMEOUT_SEC,
        retries=settings.HTTP_RETRIES,
        limit_per_host=20,
        default_headers={"X-Bot-Api-Key": settings.BACKEND_BOT_API_KEY},
    )

    products_cache.start_cleanup_task(interval_seconds=300)

    health_monitor = HealthMonitor(storage)
    health_log_task = health_monitor.start_periodic_logging(interval_minutes=settings.HEALTH_LOG_INTERVAL_MIN)
    background_tasks.append(health_log_task)

    watchdog_task = asyncio.create_task(
        watchdog_loop(
            bot,
            health_monitor,
            interval_sec=max(30, settings.WATCHDOG_INTERVAL_SEC),
            ping_timeout=min(30.0, float(settings.TELEGRAM_API_TIMEOUT)),
            fail_threshold=max(3, settings.WATCHDOG_TELEGRAM_FAIL_THRESHOLD),
        )
    )
    background_tasks.append(watchdog_task)  # cùng cleanup với các task khác trong finally

    order_api = OrderAPI(http, str(settings.ORDER_API_BASE))
    payment_api = PaymentAPI(http, str(settings.PAYMENT_API_BASE))
    admin_api = AdminAPI(http, str(settings.ADMIN_API_BASE)) if settings.ADMIN_API_BASE else None

    async def keepalive_loop() -> None:
        interval = max(60, int(settings.KEEPALIVE_INTERVAL_SEC or 300))
        timeout = max(3, int(settings.KEEPALIVE_TIMEOUT_SEC or 8))
        order_health_url = f"{str(settings.ORDER_API_BASE).rstrip('/')}/health"
        payment_health_url = f"{str(settings.PAYMENT_API_BASE).rstrip('/')}/health"
        while True:
            try:
                await asyncio.wait_for(bot.get_me(), timeout=timeout)
            except Exception as e:
                log.debug("keepalive telegram ping failed: %s", e)

            try:
                await asyncio.wait_for(http.request("GET", order_health_url), timeout=timeout)
            except Exception as e:
                log.debug("keepalive order health ping failed: %s", e)

            try:
                await asyncio.wait_for(http.request("GET", payment_health_url), timeout=timeout)
            except Exception as e:
                log.debug("keepalive payment health ping failed: %s", e)

            jitter = interval * random.uniform(0.0, 0.1)
            await asyncio.sleep(interval + jitter)

    dp.message.middleware(NetworkErrorMiddleware())
    dp.callback_query.middleware(NetworkErrorMiddleware())
    dp.message.middleware(RateLimitMiddleware(max_per_min=settings.RATE_LIMIT_PER_MIN))
    dp.callback_query.middleware(RateLimitMiddleware(max_per_min=settings.RATE_LIMIT_PER_MIN))
    dp.message.middleware(
        AntiFloodMiddleware(
            window_sec=settings.FLOOD_WINDOW_SEC,
            max_msg=settings.FLOOD_MAX_MSG,
            spam_ban_minutes=10,
        )
    )

    register_all_handlers(dp, bot, storage, order_api, payment_api, admin_api)

    async def setup_commands_wrapper() -> None:
        try:
            await setup_commands(bot)
        except Exception as e:
            log.error("Background setup_commands failed: %s", e, exc_info=True)

    setup_commands_task = asyncio.create_task(setup_commands_wrapper())
    background_tasks.append(setup_commands_task)

    if settings.KEEPALIVE_ENABLED:
        keepalive_task = asyncio.create_task(keepalive_loop())
        background_tasks.append(keepalive_task)

    log.info("Bot starting polling (infinite reconnect with backoff)...")

    consecutive_failures = 0
    try:
        # Chỉ xóa webhook 1 lần khi boot, tránh drop pending updates ở mỗi lần reconnect.
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception as e:
            log.warning("delete_webhook on startup failed: %s", e)

        while True:
            try:
                await dp.start_polling(
                    bot,
                    allowed_updates=["message", "callback_query"],
                    handle_signals=True,
                )
                consecutive_failures = 0
                log.warning("start_polling returned unexpectedly; restarting in 5s")
                await asyncio.sleep(5.0)
            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
            except Exception as e:
                runtime_state.record_polling_error(e)
                consecutive_failures += 1
                delay = _backoff_seconds(consecutive_failures - 1)
                log.error(
                    "Polling error (consecutive_failures=%s, next backoff %.1fs): %r",
                    consecutive_failures,
                    delay,
                    e,
                    exc_info=True,
                )
                await asyncio.sleep(delay)
    finally:
        log.info("Shutting down...")

        try:
            final_status = health_monitor.get_health_status()
            log.info("Final health status: %s", final_status)
        except Exception as e:
            log.warning("Error getting final stats: %s", e)

        health_log_task.cancel()
        try:
            await asyncio.wait_for(health_log_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        watchdog_task.cancel()
        try:
            await asyncio.wait_for(watchdog_task, timeout=3.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass

        try:
            await storage.stop_cleanup_task_async()
        except Exception as e:
            log.warning("Error stopping storage cleanup: %s", e)

        try:
            await products_cache.stop_cleanup_task_async()
        except Exception as e:
            log.warning("Error stopping cache cleanup: %s", e)

        for task in background_tasks:
            try:
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, timeout=1.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
            except Exception as e:
                log.warning("Error cancelling background task: %s", e)

        try:
            await asyncio.wait_for(http.close(), timeout=5.0)
        except (asyncio.TimeoutError, Exception) as e:
            log.warning("Error closing HTTP client: %s", e)

        try:
            await asyncio.wait_for(bot.session.close(), timeout=5.0)
        except (asyncio.TimeoutError, Exception) as e:
            log.warning("Error closing bot session: %s", e)

        log.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
