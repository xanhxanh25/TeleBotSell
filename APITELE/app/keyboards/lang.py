from aiogram.utils.keyboard import InlineKeyboardBuilder

def kb_lang():
    b = InlineKeyboardBuilder()
    b.button(text="🇻🇳 Việt", callback_data="lang:vi")
    b.button(text="🇬🇧 English", callback_data="lang:en")
    b.button(text="🇷🇺 Рус", callback_data="lang:ru")
    b.button(text="🇨🇳 中文", callback_data="lang:zh")
    b.adjust(2, 2)
    return b.as_markup()
