"""
Seller API Key model.

Seller = 1 User Telegram duoc admin cap API key.
Khi seller goi API mua hang -> tru balance cua User do (bang users, field balance).
KHONG co seller balance rieng, KHONG co SellerProduct/SellerOrder rieng.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, String, UniqueConstraint, func,
)
from app.database import Base


class SellerApiKey(Base):
    __tablename__ = "seller_api_keys"
    __table_args__ = (
        UniqueConstraint("api_key", name="uq_seller_api_keys_api_key"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    api_key = Column(String(64), nullable=False, index=True)       # sk_live_ + 24 hex
    api_secret = Column(String(128), nullable=False)                # plaintext, needed for HMAC verify
    is_active = Column(Boolean, nullable=False, default=True)
    note = Column(String(255), nullable=True)                       # admin ghi chu
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked_at = Column(DateTime(timezone=True), nullable=True)     # thoi diem bi xoa/doi
