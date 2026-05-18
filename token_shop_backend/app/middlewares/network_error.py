# app/middlewares/network_error.py
"""
Middleware để xử lý network errors một cách graceful
Log errors nhưng không làm crash bot
"""
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from aiogram.exceptions import TelegramNetworkError, TelegramAPIError

# Import SkipHandler để không log nó như error
try:
    from aiogram.exceptions import SkipHandler
except ImportError:
    try:
        from aiogram.dispatcher.handler import SkipHandler
    except ImportError:
        from aiogram.dispatcher.event.bases import SkipHandler

log = logging.getLogger("network_error")


class NetworkErrorMiddleware(BaseMiddleware):
    """
    Middleware để catch và log network errors
    Không block request nhưng log để theo dõi
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except SkipHandler:
            # SkipHandler không phải là error - đây là cơ chế bình thường của aiogram
            # để bỏ qua handler hiện tại và tiếp tục với handler khác
            # Không log và re-raise để aiogram xử lý
            raise
        except TelegramNetworkError as e:
            # Log network errors nhưng không crash
            log.warning(
                "TelegramNetworkError in handler: %s (update_id=%s)",
                e,
                getattr(event, "update_id", None) if isinstance(event, Update) else None
            )
            # Re-raise để aiogram có thể retry nếu cần
            raise
        except TelegramAPIError as e:
            # API errors (400, 403, etc.) - log nhưng không retry
            log.warning(
                "TelegramAPIError in handler: %s (update_id=%s)",
                e,
                getattr(event, "update_id", None) if isinstance(event, Update) else None
            )
            # Re-raise để handler có thể xử lý
            raise
        except Exception as e:
            # Các lỗi khác - log và re-raise
            log.error(
                "Unexpected error in handler: %s (update_id=%s)",
                e,
                getattr(event, "update_id", None) if isinstance(event, Update) else None,
                exc_info=True
            )
            raise

