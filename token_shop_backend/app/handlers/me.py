from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import asyncio
from app.i18n import t
from app.utils import format_amount

router = Router()

@router.message(Command("me"))
async def cmd_me(message: Message, **data):
    storage = data["storage"]
    s = storage.get(message.from_user.id)
    username = message.from_user.username or "none"

    order_api = data["order_api"]
    telegram_user = message.from_user.username  # Có thể là None
    try:
        me = await asyncio.wait_for(
            order_api.me(message.from_user.id, telegram_user),
            timeout=4.0,
        )
    except Exception:
        await message.answer(t(s.lang, "server_error"))
        return
    
    # ✅ Nếu user bị ban thì hiển thị thông báo ban
    if me.get("is_banned", False):
        await message.answer(t(s.lang, "user_banned"))
        return
    
    balance = me.get("balance", 0)
    currency = me.get("currency", "USD")

    await message.answer(
        t(s.lang, "me_format",
          tid=message.from_user.id,
          username=username,
          user_lang=s.lang,
          balance=format_amount(balance),
          currency=currency)
    )

