from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.utils import format_amount


def kb_products(products: list[dict]):
    b = InlineKeyboardBuilder()
    for p in products:
        name = p.get("name", "Item")
        price = p.get("price", "0")
        stock = p.get("stock", 0)

        price_str = format_amount(price)

        if stock > 0:
            button_text = f"📦 {name} · ${price_str} · ✅ {stock}"
        else:
            button_text = f"⛔ {name} · ${price_str} · Sold out"

        # Truncate name if button text too long
        if len(button_text) > 62:
            if stock > 0:
                suffix = f" · ${price_str} · ✅ {stock}"
            else:
                suffix = f" · ${price_str} · Sold out"
            icon = "📦 " if stock > 0 else "⛔ "
            max_name = 62 - len(icon) - len(suffix)
            if max_name > 3:
                button_text = f"{icon}{name[:max_name-1]}…{suffix}"

        pid = str(p.get("id"))
        b.button(text=button_text, callback_data=f"p:open:{pid}")
    b.adjust(1)
    return b.as_markup()


def kb_product_actions(product_id: str):
    b = InlineKeyboardBuilder()
    b.button(text="🛒 Buy Now", callback_data=f"p:buy:{product_id}")
    b.button(text="← Back", callback_data="menu:back")
    b.adjust(2)
    return b.as_markup()


def kb_confirm_buy(has_coupon: bool = False):
    b = InlineKeyboardBuilder()
    if not has_coupon:
        b.button(text="🏷 Coupon", callback_data="buy:apply_coupon")
    b.button(text="✅ Confirm", callback_data="buy:confirm")
    b.button(text="✕ Cancel", callback_data="buy:cancel")
    if not has_coupon:
        b.adjust(1, 2)
    else:
        b.adjust(2)
    return b.as_markup()
