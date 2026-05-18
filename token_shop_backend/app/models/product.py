from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, Numeric, String, Text, func, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base

class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("code", name="uq_products_code"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Numeric(18, 6), nullable=False)  # USD
    currency = Column(String(10), nullable=False, default="USD")
    stock = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    # payload giao hàng (dễ mở rộng cho sản phẩm số)
    delivery_payload = Column(Text, nullable=True)

    # Giảm giá theo số lượng: mua >= qty_discount_min thì giảm qty_discount_percent %
    qty_discount_min = Column(Integer, nullable=True)  # Số lượng tối thiểu để được giảm giá
    qty_discount_percent = Column(Numeric(5, 2), nullable=True)  # Phần trăm giảm giá (0-100)

    # Thứ tự hiển thị: số nhỏ hơn hiển thị trước, NULL sẽ hiển thị cuối cùng
    sort_order = Column(Integer, nullable=True, default=None)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    qty_discount_tiers = relationship(
        "ProductQtyDiscountTier",
        back_populates="product",
        order_by="ProductQtyDiscountTier.min_qty",
        cascade="all, delete-orphan",
    )
