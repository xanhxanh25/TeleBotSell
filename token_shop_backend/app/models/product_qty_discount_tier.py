"""Bậc giảm giá theo số lượng mua (mỗi product nhiều mốc)."""
from sqlalchemy import BigInteger, Column, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ProductQtyDiscountTier(Base):
    __tablename__ = "product_qty_discount_tiers"
    __table_args__ = (
        UniqueConstraint("product_id", "min_qty", name="uq_pqdt_product_min_qty"),
    )

    # Integer: SQLite autoincrement ổn định hơn BigInteger
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Mua >= min_qty sản phẩm thì áp dụng percent% cho subtotal (một tier duy nhất: mốc cao nhất đạt được)
    min_qty = Column(Integer, nullable=False)
    percent = Column(Numeric(5, 2), nullable=False)

    product = relationship("Product", back_populates="qty_discount_tiers")
