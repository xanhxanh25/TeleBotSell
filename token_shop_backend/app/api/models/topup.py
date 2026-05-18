import uuid
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, Text, func, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base

class Topup(Base):
    __tablename__ = "topups"
    __table_args__ = (
        UniqueConstraint("out_order_id", name="uq_topups_out_order_id"),
        Index("ix_topups_user_created", "user_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    out_order_id = Column(String(80), nullable=False, index=True)  # TokenPay OutOrderId

    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    telegram_id = Column(BigInteger, nullable=False, index=True)

    network = Column(String(32), nullable=False)      # TRON / POLYGON
    currency = Column(String(64), nullable=False)     # TRX / EVM_Polygon_USDT_ERC20
    base_currency = Column(String(16), nullable=False, default="USD")

    actual_amount = Column(Numeric(18, 6), nullable=False)  # số tiền khách chọn (USD)
    amount = Column(Numeric(18, 6), nullable=True)          # TokenPay Amount

    status = Column(String(24), nullable=False, default="PENDING")  # PENDING/SUCCESS/FAILED/EXPIRED

    payment_url = Column(Text, nullable=True)
    to_address = Column(Text, nullable=True)
    qr_code_base64 = Column(Text, nullable=True)  # lưu bản "raw" nếu muốn debug (có thể lớn)
    qr_code_link = Column(Text, nullable=True)
    expire_time = Column(DateTime(timezone=True), nullable=True)

    # notify fields (idempotent)
    tokenpay_id = Column(String(80), nullable=True, index=True)
    txid = Column(Text, nullable=True)
    from_address = Column(Text, nullable=True)
    pay_time = Column(DateTime(timezone=True), nullable=True)

    raw_notify = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
