from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

def kb_one_button(text: str, cb: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=text, callback_data=cb)
    return b.as_markup()
