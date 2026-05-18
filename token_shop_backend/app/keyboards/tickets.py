from aiogram.utils.keyboard import InlineKeyboardBuilder

def kb_error_orders(orders: list[dict], page: int, total: int, limit: int = 10):
    """
    Tạo keyboard cho danh sách đơn hàng để chọn bảo hành.
    """
    b = InlineKeyboardBuilder()
    
    for order in orders:
        order_code = order.get("order_code", "N/A")
        product_name = order.get("product_name", "")
        # Hiển thị ngắn gọn
        text = f"{order_code} - {product_name[:20]}..."
        b.button(text=text, callback_data=f"error:select:{order.get('order_id')}")
    
    b.adjust(1)
    
    # Pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(("⬅️ Trước", f"error:page:{page-1}"))
    if total > page * limit:
        nav_buttons.append(("Sau ➡️", f"error:page:{page+1}"))
    
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
    b.button(text="✅ Xác nhận", callback_data=f"error:confirm:{order_id}")
    b.button(text="❌ Hủy", callback_data="error:cancel")
    b.adjust(2)
    return b.as_markup()

