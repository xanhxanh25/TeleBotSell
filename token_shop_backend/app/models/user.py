from sqlalchemy import BigInteger, Column, DateTime, Numeric, String, Boolean, func, UniqueConstraint
from app.database import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("telegram_id", name="uq_users_telegram_id"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    telegram_user = Column(String(255), nullable=True)  # Telegram username (ví dụ: @username)
    # Số dư USD
    balance = Column(Numeric(18, 6), nullable=False, default=0)
    # Ban user: nếu True thì không cho mua / nạp / tạo ticket
    is_banned = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
