from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from app.i18n import t

router = Router()

@router.message(Command("help"))
async def cmd_help(message: Message, **data):
    storage = data["storage"]
    s = storage.get(message.from_user.id)
    await message.answer(t(s.lang, "help"))
