from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime
import html
from app.i18n import t
from app.keyboards.history import kb_history_orders, kb_order_detail, kb_history_months

router = Router()

@router.message(Command("history"))
async def cmd_history(message: Message, **data):
    storage = data["storage"]
    s = storage.get(message.from_user.id)
    
    # Hiển thị menu chọn tháng
    await message.answer(
        t(s.lang, "history_choose_month"),
        reply_markup=kb_history_months()
    )


@router.callback_query(lambda c: c.data and c.data.startswith("history:month:"))
async def cb_history_month(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)
    
    # Parse year và month từ callback_data: "history:month:2024:1"
    parts = (cb.data or "").split(":")
    if len(parts) < 4:
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)
        return
    try:
        year = int(parts[2])
        month = int(parts[3])
    except (TypeError, ValueError):
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)
        return
    
    # Lấy danh sách đơn hàng tháng đó
    result = await order_api.history(cb.from_user.id, month=month, year=year, page=1, limit=10)
    orders = result.get("orders", [])
    total = result.get("total", 0)
    
    if not orders:
        await cb.message.edit_text(t(s.lang, "history_no_orders"))
        await cb.answer()
        return
    
    # Lưu tháng/năm vào storage để dùng cho pagination
    s.history_month = month
    s.history_year = year
    s.history_page = 1
    
    # Format danh sách
    text = t(s.lang, "history_list_title", month=month, year=year, total=total)
    await cb.message.edit_text(text, reply_markup=kb_history_orders(orders, 1, total))
    await cb.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("history:page:"))
async def cb_history_page(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)
    
    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)
        return
    try:
        page = int(parts[2])
    except (TypeError, ValueError):
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)
        return
    month = getattr(s, "history_month", None) or datetime.utcnow().month
    year = getattr(s, "history_year", None) or datetime.utcnow().year
    
    result = await order_api.history(cb.from_user.id, month=month, year=year, page=page, limit=10)
    orders = result.get("orders", [])
    total = result.get("total", 0)
    
    s.history_page = page
    
    text = t(s.lang, "history_list_title", month=month, year=year, total=total)
    await cb.message.edit_text(text, reply_markup=kb_history_orders(orders, page, total))
    await cb.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("history:detail:"))
async def cb_history_detail(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)
    
    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)
        return
    order_id = parts[2]
    
    try:
        order = await order_api.get_order_detail(order_id, cb.from_user.id)
        
        # Format chi tiết đơn hàng
        from app.utils import format_amount
        text = t(
            s.lang,
            "history_order_detail",
            order_code=html.escape(str(order.get("order_code", "N/A")), quote=False),
            product_name=html.escape(str(order.get("product_name", "")), quote=False),
            qty=order.get("qty", 0),
            unit_price=format_amount(order.get("unit_price", "0")),
            subtotal=format_amount(order.get("subtotal", "0")),
            discount_total=format_amount(order.get("discount_total", "0")),
            total=format_amount(order.get("total", "0")),
            currency=order.get("currency", "USD"),
            status=html.escape(str(order.get("status", "")), quote=False),
            coupon_code=html.escape(str(order.get("coupon_code") or "None"), quote=False),
            created_at=html.escape(
                str(order.get("created_at", "")[:19] if order.get("created_at") else "N/A"),
                quote=False,
            ),
        )
        
        await cb.message.edit_text(text, reply_markup=kb_order_detail(order_id))
        await cb.answer()
    except Exception as e:
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)


@router.callback_query(lambda c: c.data == "history:back")
async def cb_history_back(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)
    
    month = getattr(s, "history_month", None) or datetime.utcnow().month
    year = getattr(s, "history_year", None) or datetime.utcnow().year
    page = getattr(s, "history_page", 1)
    
    result = await order_api.history(cb.from_user.id, month=month, year=year, page=page, limit=10)
    orders = result.get("orders", [])
    total = result.get("total", 0)
    
    text = t(s.lang, "history_list_title", month=month, year=year, total=total)
    await cb.message.edit_text(text, reply_markup=kb_history_orders(orders, page, total))
    await cb.answer()
