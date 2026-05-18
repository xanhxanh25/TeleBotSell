from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime
import html
from app.i18n import t
from app.keyboards.tickets import kb_error_orders, kb_confirm_warranty
try:
    # một số bản aiogram v3
    from aiogram.exceptions import SkipHandler
except ImportError:
    try:
        # aiogram v2.x
        from aiogram.dispatcher.handler import SkipHandler
    except ImportError:
        # một số bản aiogram v3 khác
        from aiogram.dispatcher.event.bases import SkipHandler
router = Router()

@router.message(Command("warranty"))
async def cmd_warranty(message: Message, **data):
    """
    Lệnh warranty: hiện danh sách đơn hàng để chọn bảo hành.
    """
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(message.from_user.id)
    
    # Lấy danh sách đơn hàng trong tháng hiện tại
    now = datetime.utcnow()
    result = await order_api.history(message.from_user.id, month=now.month, year=now.year, page=1, limit=10)
    orders = result.get("orders", [])
    total = result.get("total", 0)
    
    if not orders:
        await message.answer(t(s.lang, "error_no_orders"))
        return
    
    # Lưu state cho pagination
    s.state = "error_select_order"
    s.history_month = now.month
    s.history_year = now.year
    s.history_page = 1
    
    text = t(s.lang, "error_select_order_title", total=total)
    await message.answer(text, reply_markup=kb_error_orders(orders, 1, total))


@router.message(Command("error"))
async def cmd_error(message: Message, **data):
    """
    Lệnh error: tương tự warranty - hiện danh sách đơn hàng để chọn bảo hành.
    """
    await cmd_warranty(message, **data)


@router.callback_query(lambda c: c.data and c.data.startswith("error:page:"))
async def cb_error_page(cb: CallbackQuery, **data):
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
    
    text = t(s.lang, "error_select_order_title", total=total)
    await cb.message.edit_text(text, reply_markup=kb_error_orders(orders, page, total))
    await cb.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("error:select:"))
async def cb_error_select(cb: CallbackQuery, **data):
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
        
        # Hiển thị thông tin đơn hàng và yêu cầu nhập lý do
        from app.utils import format_amount
        text = t(
            s.lang,
            "error_ask_reason",
            order_code=html.escape(str(order.get("order_code", "N/A")), quote=False),
            product_name=html.escape(str(order.get("product_name", "")), quote=False),
            qty=order.get("qty", 0),
            total=format_amount(order.get("total", "0")),
            currency=order.get("currency", "USD")
        )
        
        s.state = "error_wait_reason"
        s.error_order_id = order_id
        s.error_reason = None
        
        await cb.message.edit_text(text)
        await cb.message.answer(t(s.lang, "error_enter_reason"))
        await cb.answer()
    except Exception as e:
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)


# Bắt tin nhắn khi user nhập lý do
@router.message(lambda m: True)
async def catch_error_reason(message: Message, **data):
    storage = data["storage"]
    s = storage.get(message.from_user.id)
    
    if not s or s.state != "error_wait_reason":
        raise SkipHandler()
    
    # Lưu lý do
    reason = message.text or ""
    if not reason.strip():
        await message.answer(t(s.lang, "error_reason_empty"))
        return
    
    s.error_reason = reason.strip()
    
    # Hiển thị xác nhận với lý do
    try:
        order_api = data["order_api"]
        order = await order_api.get_order_detail(s.error_order_id, message.from_user.id)
        
        from app.utils import format_amount
        text = t(
            s.lang,
            "error_confirm_with_reason",
            order_code=html.escape(str(order.get("order_code", "N/A")), quote=False),
            product_name=html.escape(str(order.get("product_name", "")), quote=False),
            qty=order.get("qty", 0),
            total=format_amount(order.get("total", "0")),
            currency=order.get("currency", "USD"),
            reason=html.escape(reason, quote=False),
        )
        
        s.state = "error_wait_confirm"
        
        await message.answer(text, reply_markup=kb_confirm_warranty(s.error_order_id))
    except Exception as e:
        await message.answer(t(s.lang, "generic_error"))
        storage.reset_flow(message.from_user.id)


@router.callback_query(lambda c: c.data and c.data.startswith("error:confirm:"))
async def cb_error_confirm(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    http = data["order_api"].http
    s = storage.get(cb.from_user.id)
    
    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        await cb.answer(t(s.lang, "generic_error"), show_alert=True)
        return
    order_id = parts[2]
    
    if s.state != "error_wait_confirm" or s.error_order_id != order_id or not s.error_reason:
        await cb.answer("Invalid state", show_alert=False)
        return
    
    # Tạo ticket với order_id và lý do
    telegram_user = cb.from_user.username  # Có thể là None
    payload = {
        "telegram_id": cb.from_user.id,
        "telegram_user": telegram_user,
        "order_id": order_id,
        "text": s.error_reason,
        "photo_file_id": None,
    }
    
    url = f"{order_api.base}/tickets"
    
    try:
        resp = await http.request("POST", url, json=payload)
        ticket_id = resp.get("ticket_id", "N/A") if isinstance(resp, dict) else "N/A"
        
        s.state = "idle"
        s.error_order_id = None
        s.error_reason = None
        
        await cb.message.edit_text(t(s.lang, "error_ticket_created", ticket_id=ticket_id))
        await cb.answer("✅ " + t(s.lang, "error_ticket_created_short"))
    except Exception as e:
        msg = str(e)
        if "USER_BANNED" in msg or "http_error:403" in msg or "403" in msg:
            await cb.message.answer(t(s.lang, "user_banned"))
            await cb.answer(t(s.lang, "user_banned"), show_alert=True)
        else:
            await cb.answer(t(s.lang, "generic_error"), show_alert=True)


@router.callback_query(lambda c: c.data == "error:cancel")
async def cb_error_cancel(cb: CallbackQuery, **data):
    storage = data["storage"]
    s = storage.get(cb.from_user.id)
    
    s.state = "idle"
    s.error_order_id = None
    s.error_reason = None
    
    await cb.message.edit_text(t(s.lang, "error_cancelled"))
    await cb.answer(t(s.lang, "cancelled"))
