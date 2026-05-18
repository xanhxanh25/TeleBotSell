from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime


def kb_history_orders(orders: list[dict], page: int, total: int, limit: int = 10):
    b = InlineKeyboardBuilder()

    for order in orders:
        order_code = order.get("order_code", "N/A")
        product_name = order.get("product_name", "")
        status = order.get("status", "")
        status_icon = {"PAID": "✅", "PENDING": "⏳", "CANCELLED": "❌", "REFUNDED": "🔄"}.get(status, "📦")
        text = f"{status_icon}  {order_code} — {product_name[:18]}…"
        b.button(text=text, callback_data=f"history:detail:{order.get('order_id')}")

    b.adjust(1)

    # Pagination
    nav_buttons = []
    if page > 1:
        nav_buttons.append(("⬅️ Prev", f"history:page:{page-1}"))
    if total > page * limit:
        nav_buttons.append(("Next ➡️", f"history:page:{page+1}"))

    if nav_buttons:
        for text, cb in nav_buttons:
            b.button(text=text, callback_data=cb)
        b.adjust(len(nav_buttons))

    return b.as_markup()


def kb_order_detail(order_id: str):
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Back to list", callback_data="history:back")
    return b.as_markup()


def kb_history_months():
    b = InlineKeyboardBuilder()
    now = datetime.utcnow()

    for i in range(3):
        month = now.month - i
        year = now.year
        if month <= 0:
            month += 12
            year -= 1

        month_name = datetime(year, month, 1).strftime("%m/%Y")
        icon = "📅" if i == 0 else "📆"
        b.button(text=f"{icon}  {month_name}", callback_data=f"history:month:{year}:{month}")

    b.adjust(1)
    return b.as_markup()
