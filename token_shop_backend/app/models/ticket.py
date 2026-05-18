from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func, Index
from app.database import Base

class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_user_created", "user_id", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    
    # Thêm order_id để liên kết với đơn hàng cần bảo hành
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=True, index=True)

    text = Column(Text, nullable=False, default="")
    photo_file_id = Column(String(256), nullable=True)

    status = Column(String(24), nullable=False, default="OPEN")  # OPEN, APPROVED, REJECTED, COMPLETED
    
    # Khi admin duyệt, lưu số item gửi lại cho khách
    replacement_items = Column(Text, nullable=True)  # Lưu danh sách item gửi lại (mỗi dòng 1 item)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
