from aiogram.utils.keyboard import InlineKeyboardBuilder
# app/keyboards/topup.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def kb_topup_methods() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        # [InlineKeyboardButton(text="⚡ USDT-TRC20 for TRON", callback_data="topup:net:TRON:USDT_TRC20")],  # Tạm thời tắt
        [InlineKeyboardButton(text="🔵 USDT-ERC20 (Ethereum)", callback_data="topup:net:ETH:USDT_ERC20")],
        [InlineKeyboardButton(text="🟣 USDT-ERC20 (Polygon)", callback_data="topup:net:POLYGON:USDT-ERC20")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="topup:cancel")],
    ])

def kb_topup_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="topup:cancel")]
    ])

def kb_topup_pending_actions(topup_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel pending", callback_data=f"topup:cancel_pending:{topup_id}")],
    ])
