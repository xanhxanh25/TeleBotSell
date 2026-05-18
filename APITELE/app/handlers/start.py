from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import asyncio

from app.i18n import t, normalize
from app.keyboards.reply import main_reply_kb
from app.services.telegram_utils import safe_answer

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, **data):
    storage = data["storage"]
    s = storage.get(message.from_user.id)

    # Mặc định tiếng Anh, không tự động detect từ Telegram settings
    # User có thể đổi ngôn ngữ bằng /lang nếu muốn
    if not s.lang or s.lang not in ("vi", "en", "ru", "zh"):
        storage.set_lang(message.from_user.id, "en")
        s = storage.get(message.from_user.id)

    # ✅ Tạo user lần đầu và lưu username khi user start bot
    order_api = data.get("order_api")
    if order_api:
        try:
            telegram_user = message.from_user.username  # Có thể là None
            await asyncio.wait_for(
                order_api.me(message.from_user.id, telegram_user),
                timeout=2.5,
            )
        except Exception:
            # Nếu lỗi thì bỏ qua, không block welcome message
            pass

    text = (
        f"{t(s.lang, 'welcome_title')}\n\n"
        f"{t(s.lang, 'welcome_features')}\n\n"
        f"{t(s.lang, 'welcome_commands')}\n\n"
        f"{t(s.lang, 'welcome_tip')}"
    )

    await safe_answer(message, text, reply_markup=main_reply_kb(s.lang))
