from pydantic import BaseModel
from typing import Optional

class TicketCreateRequest(BaseModel):
    telegram_id: int
    order_id: Optional[str] = None  # ID đơn hàng cần bảo hành
    text: str = ""
    photo_file_id: str | None = None

class TicketCreateResponse(BaseModel):
    ticket_id: int

class TicketListResponse(BaseModel):
    tickets: list[dict]
    total: int

class TicketDetailResponse(BaseModel):
    ticket_id: int
    order_id: Optional[str]
    order_code: Optional[str]
    status: str
    text: str
    photo_file_id: Optional[str]
    replacement_items: Optional[str]
    created_at: str
