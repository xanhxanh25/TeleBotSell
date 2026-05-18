# app/services/telegram_utils.py
"""
Helper functions để gửi Telegram messages với retry tự động
Xử lý network errors và timeout một cách graceful
"""
import asyncio
import logging
from typing import Any, Optional
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.exceptions import TelegramNetworkError, TelegramAPIError, TelegramRetryAfter

log = logging.getLogger("telegram_utils")

# Cấu hình retry
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # Base delay 1 giây
MAX_RETRY_DELAY = 10.0  # Tối đa 10 giây delay


async def safe_answer(
    message: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup | ReplyKeyboardMarkup] = None,
    **kwargs
) -> Optional[Message]:
    """
    Gửi message với retry tự động khi gặp network errors.
    Returns Message nếu thành công, None nếu thất bại sau tất cả retries.
    """
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await message.answer(text, reply_markup=reply_markup, **kwargs)
        except TelegramRetryAfter as e:
            # Telegram yêu cầu đợi - tuân thủ ngay
            wait_time = e.retry_after
            log.warning(
                "Rate limited, waiting %s seconds (attempt %s/%s)",
                wait_time, attempt, MAX_RETRIES
            )
            await asyncio.sleep(wait_time)
            # Retry ngay sau khi đợi xong
            try:
                return await message.answer(text, reply_markup=reply_markup, **kwargs)
            except Exception as retry_err:
                last_error = retry_err
                if attempt < MAX_RETRIES:
                    delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
                    await asyncio.sleep(delay)
        except (TelegramNetworkError, asyncio.TimeoutError) as e:
            last_error = e
            log.warning(
                "Network error sending message (attempt %s/%s): %s",
                attempt, MAX_RETRIES, e
            )
            if attempt < MAX_RETRIES:
                # Exponential backoff
                delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
                await asyncio.sleep(delay)
            else:
                log.error("Failed to send message after %s attempts: %s", MAX_RETRIES, e)
        except TelegramAPIError as e:
            # API errors (400, 403, etc.) không nên retry
            log.error("Telegram API error: %s", e)
            return None
        except Exception as e:
            # Các lỗi khác - log và return None
            log.error("Unexpected error sending message: %s", e)
            return None
    
    if last_error:
        log.error("Failed to send message after all retries: %s", last_error)
    return None


async def safe_edit_text(
    message: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    **kwargs
) -> bool:
    """
    Edit message text với retry tự động.
    Returns True nếu thành công, False nếu thất bại.
    """
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await message.edit_text(text, reply_markup=reply_markup, **kwargs)
            return True
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            log.warning(
                "Rate limited editing message, waiting %s seconds (attempt %s/%s)",
                wait_time, attempt, MAX_RETRIES
            )
            await asyncio.sleep(wait_time)
            try:
                await message.edit_text(text, reply_markup=reply_markup, **kwargs)
                return True
            except Exception as retry_err:
                last_error = retry_err
                if attempt < MAX_RETRIES:
                    delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
                    await asyncio.sleep(delay)
        except (TelegramNetworkError, asyncio.TimeoutError) as e:
            last_error = e
            log.warning(
                "Network error editing message (attempt %s/%s): %s",
                attempt, MAX_RETRIES, e
            )
            if attempt < MAX_RETRIES:
                delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
                await asyncio.sleep(delay)
            else:
                log.error("Failed to edit message after %s attempts: %s", MAX_RETRIES, e)
        except TelegramAPIError as e:
            # API errors (message not modified, etc.) - không retry
            log.warning("Telegram API error editing message: %s", e)
            return False
        except Exception as e:
            log.error("Unexpected error editing message: %s", e)
            return False
    
    if last_error:
        log.error("Failed to edit message after all retries: %s", last_error)
    return False


async def safe_answer_callback(
    callback: CallbackQuery,
    text: Optional[str] = None,
    show_alert: bool = False,
    **kwargs
) -> bool:
    """
    Answer callback query với retry tự động.
    Returns True nếu thành công, False nếu thất bại.
    """
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await callback.answer(text=text, show_alert=show_alert, **kwargs)
            return True
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            log.warning(
                "Rate limited answering callback, waiting %s seconds (attempt %s/%s)",
                wait_time, attempt, MAX_RETRIES
            )
            await asyncio.sleep(wait_time)
            try:
                await callback.answer(text=text, show_alert=show_alert, **kwargs)
                return True
            except Exception as retry_err:
                last_error = retry_err
                if attempt < MAX_RETRIES:
                    delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
                    await asyncio.sleep(delay)
        except (TelegramNetworkError, asyncio.TimeoutError) as e:
            last_error = e
            log.warning(
                "Network error answering callback (attempt %s/%s): %s",
                attempt, MAX_RETRIES, e
            )
            if attempt < MAX_RETRIES:
                delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
                await asyncio.sleep(delay)
            else:
                log.error("Failed to answer callback after %s attempts: %s", MAX_RETRIES, e)
        except TelegramAPIError as e:
            # API errors - không retry
            log.warning("Telegram API error answering callback: %s", e)
            return False
        except Exception as e:
            log.error("Unexpected error answering callback: %s", e)
            return False
    
    if last_error:
        log.error("Failed to answer callback after all retries: %s", last_error)
    return False


async def safe_edit_reply_markup(
    message: Message,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    **kwargs
) -> bool:
    """
    Edit reply markup với retry tự động.
    Returns True nếu thành công, False nếu thất bại.
    """
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await message.edit_reply_markup(reply_markup=reply_markup, **kwargs)
            return True
        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            log.warning(
                "Rate limited editing markup, waiting %s seconds (attempt %s/%s)",
                wait_time, attempt, MAX_RETRIES
            )
            await asyncio.sleep(wait_time)
            try:
                await message.edit_reply_markup(reply_markup=reply_markup, **kwargs)
                return True
            except Exception as retry_err:
                last_error = retry_err
                if attempt < MAX_RETRIES:
                    delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
                    await asyncio.sleep(delay)
        except (TelegramNetworkError, asyncio.TimeoutError) as e:
            last_error = e
            log.warning(
                "Network error editing markup (attempt %s/%s): %s",
                attempt, MAX_RETRIES, e
            )
            if attempt < MAX_RETRIES:
                delay = min(RETRY_DELAY_BASE * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
                await asyncio.sleep(delay)
            else:
                log.error("Failed to edit markup after %s attempts: %s", MAX_RETRIES, e)
        except TelegramAPIError as e:
            # API errors - không retry
            log.warning("Telegram API error editing markup: %s", e)
            return False
        except Exception as e:
            log.error("Unexpected error editing markup: %s", e)
            return False
    
    if last_error:
        log.error("Failed to edit markup after all retries: %s", last_error)
    return False

