from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint, func, Index
from app.database import Base


# Ledger: nhiều dòng / (coupon_id, user_id) khi max_uses_per_user > 1.
# Chỉ status=COMMITTED được tính vào quota; REVERSED = hoàn usage (cancel/refund).
REDEMPTION_COMMITTED = "COMMITTED"
REDEMPTION_REVERSED = "REVERSED"


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_coupon_redemptions_order"),
        Index("ix_cr_coupon_status", "coupon_id", "status"),
        Index("ix_cr_coupon_user_status", "coupon_id", "user_id", "status"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    coupon_id = Column(BigInteger, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(24), nullable=False, default=REDEMPTION_COMMITTED)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
