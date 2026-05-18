from sqlalchemy import BigInteger, Boolean, Column, DateTime, Numeric, String, func, UniqueConstraint, ForeignKey
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

    # Loại 2: Cấp mã riêng cho 1 user (nếu có user_id)
    # Loại 3: Mã giảm giá cho mọi user trên 1 sản phẩm (nếu có product_id, không có user_id)
    # Để trống cả 2 = mã giảm giá cho mọi user, mọi sản phẩm
    product_id = Column(BigInteger, ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    # Usage limits:
    # - max_uses_total: tổng số lần coupon được dùng (vd 10 => 10 user dùng xong là hết)
    # - max_uses_per_user: mỗi user dùng tối đa bao nhiêu lần (vd 1)
    # - max_qty_per_order: giới hạn số lượng sản phẩm trong 1 lần mua khi dùng coupon (vd 1)
    max_uses_total = Column(BigInteger, nullable=True)
    # NULL = không giới hạn số lần / user (chỉ còn max_uses_total + rule sản phẩm).
    max_uses_per_user = Column(BigInteger, nullable=True)
    max_qty_per_order = Column(BigInteger, nullable=True)

    # Bộ đếm global atomic (chỉ khi max_uses_total IS NOT NULL): checkout UPDATE ... WHERE count < max.
    # Đồng bộ với COUNT(*) redemption COMMITTED sau migration / reverse.
    committed_usage_count = Column(BigInteger, nullable=False, default=0)

    is_active = Column(Boolean, nullable=False, default=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
