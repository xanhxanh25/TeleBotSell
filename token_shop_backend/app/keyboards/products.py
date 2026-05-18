from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.utils import format_amount

def kb_products(products: list[dict]):
    b = InlineKeyboardBuilder()
    for p in products:
        name = p.get("name", "Item")
        price = p.get("price", "0")
        stock = p.get("stock", 0)
        currency = p.get("currency", "USD")
        
        # Format: "Tên sản phẩm | Giá | Còn: X"
        # Telegram button text có giới hạn ~64 ký tự
        price_str = format_amount(price)
        
        # Tạo text button với thông tin đầy đủ (dùng tiếng Anh)
        button_text = f"{name} | {price_str} {currency} | Stock: {stock}"
        
        # Nếu quá dài thì rút gọn tên
        if len(button_text) > 60:
            max_name_len = 60 - len(f" | {price_str} {currency} | Stock: {stock}")
            if max_name_len > 0:
                button_text = f"{name[:max_name_len-3]}... | {price_str} {currency} | Stock: {stock}"
        
        pid = str(p.get("id"))
        b.button(text=button_text, callback_data=f"p:open:{pid}")
    b.adjust(1)
    return b.as_markup()

def kb_product_actions(product_id: str):
    b = InlineKeyboardBuilder()
    b.button(text="🛒 Mua / Buy", callback_data=f"p:buy:{product_id}")
    b.button(text="⬅️ Back", callback_data="menu:back")
    b.adjust(2)
    return b.as_markup()

def kb_confirm_buy(has_coupon: bool = False):
    b = InlineKeyboardBuilder()
    if not has_coupon:
        b.button(text="🎫 Enter coupon", callback_data="buy:apply_coupon")
    b.button(text="✅ Confirm", callback_data="buy:confirm")
    b.button(text="❌ Cancel", callback_data="buy:cancel")
    if not has_coupon:
        b.adjust(1, 2)
    else:
        b.adjust(2)
    return b.as_markup()
