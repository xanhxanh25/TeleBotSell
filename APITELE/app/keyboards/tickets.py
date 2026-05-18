from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_error_orders(orders: list[dict], page: int, total: int, limit: int = 10):
    """
    Tạo keyboard cho danh sách đơn hàng để chọn bảo hành.
    """
    b = InlineKeyboardBuilder()

    for order in orders:
        order_code = order.get("order_code", "N/A")
        product_name = order.get("product_name", "")
        text = f"{order_code} - {product_name[:20]}..."
        b.button(text=text, callback_data=f"error:select:{order.get('order_id')}")

    b.adjust(1)

    # Pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(("⬅️ Prev", f"error:page:{page-1}"))
    if total > page * limit:
        nav_buttons.append(("Next ➡️", f"error:page:{page+1}"))

    if nav_buttons:
        for text, cb in nav_buttons:
            b.button(text=text, callback_data=cb)
        b.adjust(len(nav_buttons))

    return b.as_markup()


def kb_confirm_warranty(order_id: str):
    """
    Tạo keyboard xác nhận bảo hành.
    """
    b = InlineKeyboardBuilder()
    b.button(text="✅ Confirm", callback_data=f"error:confirm:{order_id}")
    b.button(text="❌ Cancel", callback_data="error:cancel")
    b.adjust(2)
    return b.as_markup()


def kb_ticket_list(tickets: list[dict], page: int = 1, total: int = 0, limit: int = 10):
    """
    Tạo keyboard cho danh sách ticket bảo hành.
    """
    b = InlineKeyboardBuilder()

    for tk in tickets:
        ticket_id = tk.get("ticket_id", "N/A")
        status = tk.get("status", "")
        text_preview = tk.get("text", "")[:20]
        status_icon = {"OPEN": "🟡", "APPROVED": "✅", "REJECTED": "❌", "COMPLETED": "🟢"}.get(status, "⚪")
        b.button(text=f"{status_icon} #{ticket_id} - {text_preview}...", callback_data=f"ticket:detail:{ticket_id}")

    b.adjust(1)

    # Pagination
    nav_buttons = []
    if page > 1:
        nav_buttons.append(("⬅️ Prev", f"ticket:page:{page-1}"))
    if total > page * limit:
        nav_buttons.append(("Next ➡️", f"ticket:page:{page+1}"))

    if nav_buttons:
        for text, cb in nav_buttons:
            b.button(text=text, callback_data=cb)
        b.adjust(len(nav_buttons))

    return b.as_markup()


def kb_ticket_detail_back():
    """
    Tạo keyboard quay lại danh sách ticket.
    """
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Back", callback_data="ticket:back")
    return b.as_markup()
