from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

def kb_history_orders(orders: list[dict], page: int, total: int, limit: int = 10):
    """
    Tạo keyboard cho danh sách đơn hàng với pagination.
    """
    b = InlineKeyboardBuilder()
    
    for order in orders:
        order_code = order.get("order_code", "N/A")
        product_name = order.get("product_name", "")
        # Hiển thị ngắn gọn
        text = f"{order_code} - {product_name[:20]}..."
        b.button(text=text, callback_data=f"history:detail:{order.get('order_id')}")
    
    b.adjust(1)
    
    # Pagination buttons
    nav_buttons = []
    if page > 1:
        nav_buttons.append(("⬅️ Trước", f"history:page:{page-1}"))
    if total > page * limit:
        nav_buttons.append(("Sau ➡️", f"history:page:{page+1}"))
    
    if nav_buttons:
        for text, cb in nav_buttons:
            b.button(text=text, callback_data=cb)
        b.adjust(len(nav_buttons))
    
    return b.as_markup()


def kb_order_detail(order_id: str):
    """
    Tạo keyboard cho chi tiết đơn hàng.
    """
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Quay lại", callback_data="history:back")
    return b.as_markup()


def kb_history_months():
    """
    Tạo keyboard để chọn tháng.
    """
    b = InlineKeyboardBuilder()
    now = datetime.utcnow()
    
    # Hiển thị 3 tháng gần nhất
    for i in range(3):
        month = now.month - i
        year = now.year
        if month <= 0:
            month += 12
            year -= 1
        
        month_name = datetime(year, month, 1).strftime("%m/%Y")
        b.button(text=month_name, callback_data=f"history:month:{year}:{month}")
    
    b.adjust(1)
    return b.as_markup()

