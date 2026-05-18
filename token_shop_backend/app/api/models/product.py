from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, Numeric, String, Text, func, UniqueConstraint
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

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
