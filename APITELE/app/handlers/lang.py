from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.i18n import t, normalize
from app.keyboards.lang import kb_lang
from app.keyboards.reply import main_reply_kb
from app.services.telegram_utils import safe_answer

router = Router()

@router.message(Command("lang"))
async def cmd_lang(message: Message, **data):
    storage = data["storage"]
    s = storage.get(message.from_user.id)
    await message.answer(t(s.lang, "lang_choose"), reply_markup=kb_lang())

@router.callback_query(lambda c: c.data and c.data.startswith("lang:"))
async def cb_lang(cb: CallbackQuery, **data):
    storage = data["storage"]
    s = storage.get(cb.from_user.id)
    old_lang = s.lang
    
    lang = cb.data.split(":")[1]
    new_lang = normalize(lang)
    
    # Chỉ update nếu ngôn ngữ thay đổi
    if old_lang != new_lang:
        storage.set_lang(cb.from_user.id, new_lang)
        s = storage.get(cb.from_user.id)
        
        # Edit message chọn ngôn ngữ
        await cb.message.edit_text(t(s.lang, "lang_choose"), reply_markup=kb_lang())
        
        # Tự động gửi welcome message với ngôn ngữ mới (tương tự /start)
        text = (
            f"{t(s.lang, 'welcome_title')}\n\n"
            f"{t(s.lang, 'welcome_features')}\n\n"
            f"{t(s.lang, 'welcome_commands')}\n\n"
            f"{t(s.lang, 'welcome_tip')}"
        )
        
        # Gửi welcome message với keyboard mới
        await cb.message.answer(text, reply_markup=main_reply_kb(s.lang))
        
        await cb.answer(f"✅ Language changed to {new_lang.upper()}")
    else:
        # Nếu cùng ngôn ngữ, chỉ answer mà không edit
        await cb.answer("ℹ️ Already selected", show_alert=False)
