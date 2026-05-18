from aiogram import Dispatcher, Bot

from app.services.storage import MemoryStorage
from app.services.order_api import OrderAPI
from app.services.payment_api import PaymentAPI
from app.services.admin_api import AdminAPI

from .start import router as start_router
from .menu import router as menu_router
from .lang import router as lang_router
from .me import router as me_router
from .help import router as help_router
from .topup import router as topup_router
from .history import router as history_router
from .tickets import router as tickets_router
from .quick_actions import router as quick_actions_router

def register_all_handlers(dp: Dispatcher, bot: Bot, storage: MemoryStorage, order_api: OrderAPI, payment_api: PaymentAPI, admin_api: AdminAPI | None):
    # inject shared dependencies through dp["..."]
    dp["storage"] = storage
    dp["order_api"] = order_api
    dp["payment_api"] = payment_api
    dp["admin_api"] = admin_api
    dp["bot"] = bot

    dp.include_router(start_router)
    dp.include_router(menu_router)
    dp.include_router(lang_router)
    dp.include_router(me_router)
    dp.include_router(help_router)
    dp.include_router(topup_router)
    dp.include_router(history_router)
    dp.include_router(tickets_router)
    dp.include_router(quick_actions_router)
