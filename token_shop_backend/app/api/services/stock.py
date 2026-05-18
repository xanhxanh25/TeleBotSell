# app/services/stock.py
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.product import Product
from app.models.product_stock_item import ProductStockItem

def sync_product_stock(db: Session, product_id: int) -> int:
    """
    Đồng bộ products.stock = COUNT(product_stock_items)
    Trả về stock mới.
    """
    cnt = db.execute(
        select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == product_id)
    ).scalar_one()

    p = db.execute(select(Product).where(Product.id == product_id).with_for_update()).scalar_one_or_none()
    if p:
        p.stock = int(cnt)
    return int(cnt)
