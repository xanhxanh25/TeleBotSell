# app/models/product_stock_item.py
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func, UniqueConstraint
from app.database import Base

class ProductStockItem(Base):
    __tablename__ = "product_stock_items"
    __table_args__ = (
        UniqueConstraint("product_id", "mota", name="uq_product_stock_items_product_mota"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)

    # optional: mã phụ / sku / id_sanpham
    id_sanpham = Column(String(80), nullable=True)

    # mỗi dòng = 1 item để giao cho khách
    mota = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
