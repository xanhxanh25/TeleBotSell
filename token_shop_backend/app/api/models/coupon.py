from sqlalchemy import BigInteger, Boolean, Column, DateTime, Numeric, String, func, UniqueConstraint
from app.database import Base

class Coupon(Base):
    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("code", name="uq_coupons_code"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(64), nullable=False)
    discount_type = Column(String(16), nullable=False)  # PERCENT | FIXED
    discount_value = Column(Numeric(18, 6), nullable=False, default=0)
    max_discount_amount = Column(Numeric(18, 6), nullable=True)
    min_order_amount = Column(Numeric(18, 6), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
