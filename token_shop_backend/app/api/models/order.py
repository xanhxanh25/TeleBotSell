import uuid
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, Text, func, UniqueConstraint, Index
from app.database import Base

class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_orders_idem"),
        Index("ix_orders_user_created", "user_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_code = Column(String(64), nullable=False, index=True)  # hiển thị cho khách
    idempotency_key = Column(String(128), nullable=False)

    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    telegram_id = Column(BigInteger, nullable=False, index=True)

    product_id = Column(BigInteger, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(255), nullable=False)

    qty = Column(BigInteger, nullable=False)
    unit_price = Column(Numeric(18, 6), nullable=False)
    subtotal = Column(Numeric(18, 6), nullable=False)
    discount_total = Column(Numeric(18, 6), nullable=False, default=0)
    total = Column(Numeric(18, 6), nullable=False)
    currency = Column(String(10), nullable=False, default="USD")

    coupon_code = Column(String(64), nullable=True)

    status = Column(String(24), nullable=False, default="PAID")  # PAID (bằng balance)
    delivery_payload = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
