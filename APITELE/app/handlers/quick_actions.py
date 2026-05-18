from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.i18n import t
from app.services.storage import MemoryStorage
from app.services.order_api import OrderAPI
from app.keyboards.products import kb_products
from app.services.telegram_utils import safe_answer
from app.handlers.menu import _manual_menu_picker_text

router = Router()

# Cache button texts cho tất cả ngôn ngữ để match nhanh hơn
_supported_langs = ["vi", "en", "ru", "zh"]
_button_texts = {
    "btn_products": {t(lang, "btn_products") for lang in _supported_langs},
    "btn_balance": {t(lang, "btn_balance") for lang in _supported_langs},
    "btn_refresh": {t(lang, "btn_refresh") for lang in _supported_langs},
    "btn_payment": {t(lang, "btn_payment") for lang in _supported_langs},
    "btn_help": {t(lang, "btn_help") for lang in _supported_langs},
}

@router.message(lambda m: m.text and m.text in _button_texts["btn_products"])
async def qa_products(message: Message, **data):
    """Gọi trực tiếp logic menu thay vì answer('/menu')"""
    storage: MemoryStorage = data["storage"]
    order_api: OrderAPI = data["order_api"]
    s = storage.get(message.from_user.id)
    
    products = await order_api.list_products(lang=s.lang)
    s.state = "menu_wait_pick"
    s.menu_product_ids = [str(p.get("id")) for p in products if p.get("id") is not None]
    await safe_answer(message, _manual_menu_picker_text(s.lang, products), reply_markup=kb_products(products))

@router.message(lambda m: m.text and m.text in _button_texts["btn_refresh"])
async def qa_refresh(message: Message, **data):
    """Reload menu với products mới"""
    storage: MemoryStorage = data["storage"]
    order_api: OrderAPI = data["order_api"]
    s = storage.get(message.from_user.id)
    
    # Clear cache và reload
    await order_api.clear_products_cache()
    products = await order_api.list_products(lang=s.lang)
    s.state = "menu_wait_pick"
    s.menu_product_ids = [str(p.get("id")) for p in products if p.get("id") is not None]
    await safe_answer(message, _manual_menu_picker_text(s.lang, products), reply_markup=kb_products(products))

@router.message(lambda m: m.text and m.text in _button_texts["btn_balance"])
async def qa_balance(message: Message, **data):
    """Hiển thị số dư ví"""
    from app.handlers.me import cmd_me
    # Gọi trực tiếp handler me
    await cmd_me(message, **data)

@router.message(lambda m: m.text and m.text in _button_texts["btn_payment"])
async def qa_check_payment(message: Message, **data):
    """Kiểm tra thanh toán"""
    storage: MemoryStorage = data["storage"]
    s = storage.get(message.from_user.id)
    
    await safe_answer(message, t(s.lang, "payment_check"))

@router.message(lambda m: m.text and m.text in _button_texts["btn_help"])
async def qa_help(message: Message, **data):
    """Hiển thị hướng dẫn"""
    from app.handlers.help import cmd_help
    # Gọi trực tiếp handler help
    await cmd_help(message, **data)
