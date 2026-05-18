from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from app.i18n import t

# Mặc định dùng tiếng Anh để đồng bộ với DEFAULT_LANG và UserSession.lang
def main_reply_kb(lang: str = "en") -> ReplyKeyboardMarkup:
    # Text nút ngắn gọn theo ngôn ngữ
    b = ReplyKeyboardBuilder()
    b.button(text=t(lang, "btn_products"))
    b.button(text=t(lang, "btn_balance"))
    b.button(text=t(lang, "btn_refresh"))
    b.button(text=t(lang, "btn_payment"))
    b.button(text=t(lang, "btn_help"))
    b.adjust(2, 2, 1)

    return b.as_markup(
        resize_keyboard=True,
        is_persistent=True,     # giữ cố định
        one_time_keyboard=False,
        input_field_placeholder=t(lang, "placeholder_quick_buttons")
    )
