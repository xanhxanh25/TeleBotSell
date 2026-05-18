import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime
import html

from app.i18n import t
from app.keyboards.tickets import kb_error_orders, kb_confirm_warranty, kb_ticket_list, kb_ticket_detail_back
from app.services.flow_runtime import reset_user_flow
from app.services.telegram_utils import safe_answer, safe_answer_callback
from app.utils import format_amount

try:
    from aiogram.exceptions import SkipHandler
except ImportError:
    try:
        from aiogram.dispatcher.handler import SkipHandler
    except ImportError:
        from aiogram.dispatcher.event.bases import SkipHandler

router = Router()
log = logging.getLogger("tickets")


# ═══════════════════════════════════════════════════════════════════════════════
# /tickets — Xem danh sách ticket bảo hành của user
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(Command("tickets"))
async def cmd_tickets(message: Message, **data):
    """Liệt kê tất cả ticket bảo hành của user."""
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(message.from_user.id)

    try:
        url = f"{order_api.base}/tickets?telegram_id={message.from_user.id}"
        result = await order_api.http.request("GET", url)
        tickets = result.get("tickets", []) if isinstance(result, dict) else []
        total = result.get("total", len(tickets)) if isinstance(result, dict) else 0

        if not tickets:
            await safe_answer(message, t(s.lang, "tickets_empty"))
            return

        text = t(s.lang, "tickets_title", total=total)
        await safe_answer(message, text, reply_markup=kb_ticket_list(tickets, page=1, total=total))
    except Exception as e:
        log.exception("Error listing tickets: %s", e)
        await safe_answer(message, t(s.lang, "generic_error"))


@router.callback_query(lambda c: c.data and c.data.startswith("ticket:detail:"))
async def cb_ticket_detail(cb: CallbackQuery, **data):
    """Xem chi tiết một ticket."""
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)

    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)
        return
    ticket_id = parts[2]

    try:
        url = f"{order_api.base}/tickets/{ticket_id}?telegram_id={cb.from_user.id}"
        ticket = await order_api.http.request("GET", url)

        replacement_info = ""
        replacement_items = ticket.get("replacement_items")
        if replacement_items:
            replacement_info = t(s.lang, "tickets_replacement", items=html.escape(str(replacement_items), quote=False))

        text = t(
            s.lang,
            "tickets_detail",
            ticket_id=ticket.get("ticket_id", "N/A"),
            order_code=html.escape(str(ticket.get("order_code") or "N/A"), quote=False),
            status=html.escape(str(ticket.get("status", "")), quote=False),
            text=html.escape(str(ticket.get("text", "")), quote=False),
            created_at=html.escape(
                str(ticket.get("created_at", "")[:19] if ticket.get("created_at") else "N/A"),
                quote=False,
            ),
            replacement_info=replacement_info,
        )

        await cb.message.edit_text(text, reply_markup=kb_ticket_detail_back())
        await safe_answer_callback(cb)
    except Exception as e:
        log.exception("Error getting ticket detail: %s", e)
        await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)


@router.callback_query(lambda c: c.data == "ticket:back")
async def cb_ticket_back(cb: CallbackQuery, **data):
    """Quay lại danh sách ticket."""
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)

    try:
        url = f"{order_api.base}/tickets?telegram_id={cb.from_user.id}"
        result = await order_api.http.request("GET", url)
        tickets = result.get("tickets", []) if isinstance(result, dict) else []
        total = result.get("total", len(tickets)) if isinstance(result, dict) else 0

        if not tickets:
            await cb.message.edit_text(t(s.lang, "tickets_empty"))
        else:
            text = t(s.lang, "tickets_title", total=total)
            await cb.message.edit_text(text, reply_markup=kb_ticket_list(tickets, page=1, total=total))
        await safe_answer_callback(cb)
    except Exception as e:
        log.exception("Error going back to ticket list: %s", e)
        await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)


# ═══════════════════════════════════════════════════════════════════════════════
# /warranty & /error — Tạo ticket bảo hành
# ═══════════════════════════════════════════════════════════════════════════════

@router.message(Command("warranty"))
async def cmd_warranty(message: Message, **data):
    """Lệnh warranty: hiện danh sách đơn hàng để chọn bảo hành."""
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(message.from_user.id)

    try:
        now = datetime.utcnow()
        result = await order_api.history(message.from_user.id, month=now.month, year=now.year, page=1, limit=10)
        orders = result.get("orders", [])
        total = result.get("total", 0)

        if not orders:
            await safe_answer(message, t(s.lang, "error_no_orders"))
            return

        s.state = "error_select_order"
        s.history_month = now.month
        s.history_year = now.year
        s.history_page = 1

        text = t(s.lang, "error_select_order_title", total=total)
        await safe_answer(message, text, reply_markup=kb_error_orders(orders, 1, total))
    except Exception as e:
        log.exception("Error in warranty command: %s", e)
        await safe_answer(message, t(s.lang, "generic_error"))


@router.message(Command("error"))
async def cmd_error(message: Message, **data):
    """Lệnh error: tương tự warranty."""
    await cmd_warranty(message, **data)


@router.callback_query(lambda c: c.data and c.data.startswith("error:page:"))
async def cb_error_page(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)

    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)
        return
    try:
        page = int(parts[2])
    except (TypeError, ValueError):
        await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)
        return
    month = getattr(s, "history_month", None) or datetime.utcnow().month
    year = getattr(s, "history_year", None) or datetime.utcnow().year

    try:
        result = await order_api.history(cb.from_user.id, month=month, year=year, page=page, limit=10)
        orders = result.get("orders", [])
        total = result.get("total", 0)

        s.history_page = page

        text = t(s.lang, "error_select_order_title", total=total)
        await cb.message.edit_text(text, reply_markup=kb_error_orders(orders, page, total))
        await safe_answer_callback(cb)
    except Exception as e:
        log.exception("Error paginating error orders: %s", e)
        await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("error:select:"))
async def cb_error_select(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    s = storage.get(cb.from_user.id)

    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)
        return
    order_id = parts[2]

    try:
        order = await order_api.get_order_detail(order_id, cb.from_user.id)

        text = t(
            s.lang,
            "error_ask_reason",
            order_code=html.escape(str(order.get("order_code", "N/A")), quote=False),
            product_name=html.escape(str(order.get("product_name", "")), quote=False),
            qty=order.get("qty", 0),
            total=format_amount(order.get("total", "0")),
            currency=order.get("currency", "USD"),
        )

        s.state = "error_wait_reason"
        s.error_order_id = order_id
        s.error_reason = None
        s.error_photo_file_id = None

        await cb.message.edit_text(text)
        await safe_answer(cb.message, t(s.lang, "error_enter_reason_with_photo"))
        await safe_answer_callback(cb)
    except Exception as e:
        log.exception("Error selecting order for warranty: %s", e)
        await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)


# ── Photo handler cho warranty ────────────────────────────────────────────────
@router.message(lambda m: m.photo and True)
async def catch_error_photo(message: Message, **data):
    """Bắt ảnh khi user đang ở state error_wait_reason."""
    storage = data["storage"]
    s = storage.get(message.from_user.id)

    if not s or s.state != "error_wait_reason":
        raise SkipHandler()

    # Lấy file_id của ảnh lớn nhất
    photo = message.photo[-1]  # Ảnh resolution cao nhất
    s.error_photo_file_id = photo.file_id

    # Nếu có caption, dùng làm luôn reason
    if message.caption and message.caption.strip():
        s.error_reason = message.caption.strip()
        # Chuyển sang bước confirm
        await _show_warranty_confirm(message, data, s)
        return

    await safe_answer(message, t(s.lang, "error_photo_saved"))


# ── Text handler cho warranty reason ──────────────────────────────────────────
@router.message(lambda m: m.text and not m.text.startswith("/"))
async def catch_error_reason(message: Message, **data):
    """Bắt tin nhắn text khi user đang nhập lý do bảo hành."""
    storage = data["storage"]
    s = storage.get(message.from_user.id)

    if not s or s.state != "error_wait_reason":
        raise SkipHandler()

    reason = message.text.strip()
    if not reason:
        await safe_answer(message, t(s.lang, "error_reason_empty"))
        return

    s.error_reason = reason
    await _show_warranty_confirm(message, data, s)


async def _show_warranty_confirm(message: Message, data: dict, s):
    """Hiển thị xác nhận bảo hành với lý do và ảnh (nếu có)."""
    storage = data["storage"]
    order_api = data["order_api"]

    try:
        order = await order_api.get_order_detail(s.error_order_id, message.from_user.id)

        photo_note = ""
        if s.error_photo_file_id:
            photo_note = "\n📸 <i>Đã đính kèm ảnh</i>"

        text = t(
            s.lang,
            "error_confirm_with_reason",
            order_code=html.escape(str(order.get("order_code", "N/A")), quote=False),
            product_name=html.escape(str(order.get("product_name", "")), quote=False),
            qty=order.get("qty", 0),
            total=format_amount(order.get("total", "0")),
            currency=order.get("currency", "USD"),
            reason=html.escape(s.error_reason, quote=False),
        )
        text += photo_note

        s.state = "error_wait_confirm"

        await safe_answer(message, text, reply_markup=kb_confirm_warranty(s.error_order_id))
    except Exception as e:
        log.exception("Error rendering warranty confirm: %s", e)
        await safe_answer(message, t(s.lang, "generic_error"))
        await reset_user_flow(storage, message.from_user.id, reason="ticket_confirm_render_error")


@router.callback_query(lambda c: c.data and c.data.startswith("error:confirm:"))
async def cb_error_confirm(cb: CallbackQuery, **data):
    storage = data["storage"]
    order_api = data["order_api"]
    http = order_api.http
    s = storage.get(cb.from_user.id)

    parts = (cb.data or "").split(":")
    if len(parts) < 3:
        await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)
        return
    order_id = parts[2]

    if s.state != "error_wait_confirm" or s.error_order_id != order_id or not s.error_reason:
        await safe_answer_callback(cb, "Invalid state", show_alert=False)
        return

    telegram_user = cb.from_user.username
    payload = {
        "telegram_id": cb.from_user.id,
        "telegram_user": telegram_user,
        "order_id": order_id,
        "text": s.error_reason,
        "photo_file_id": s.error_photo_file_id,
    }

    url = f"{order_api.base}/tickets"

    try:
        resp = await http.request("POST", url, json=payload)
        ticket_id = resp.get("ticket_id", "N/A") if isinstance(resp, dict) else "N/A"

        s.state = "idle"
        s.error_order_id = None
        s.error_reason = None
        s.error_photo_file_id = None

        await cb.message.edit_text(t(s.lang, "error_ticket_created", ticket_id=ticket_id))
        await safe_answer_callback(cb, t(s.lang, "error_ticket_created_short"))
    except Exception as e:
        msg = str(e)
        if "USER_BANNED" in msg or "http_error:403" in msg or "403" in msg:
            await safe_answer(cb.message, t(s.lang, "user_banned"))
            await safe_answer_callback(cb, t(s.lang, "user_banned"), show_alert=True)
        else:
            log.exception("Error creating ticket: %s", e)
            await safe_answer_callback(cb, t(s.lang, "generic_error"), show_alert=True)


@router.callback_query(lambda c: c.data == "error:cancel")
async def cb_error_cancel(cb: CallbackQuery, **data):
    storage = data["storage"]
    s = storage.get(cb.from_user.id)

    s.state = "idle"
    s.error_order_id = None
    s.error_reason = None
    s.error_photo_file_id = None

    await cb.message.edit_text(t(s.lang, "error_cancelled"))
    await safe_answer_callback(cb, t(s.lang, "cancelled"))
