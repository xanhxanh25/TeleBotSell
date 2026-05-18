from pydantic import BaseModel

class MeResponse(BaseModel):
    telegram_id: int
    balance: float
    currency: str = "USD"
    created_at: str | None = None
    is_banned: bool = False  # Thêm field is_banned
