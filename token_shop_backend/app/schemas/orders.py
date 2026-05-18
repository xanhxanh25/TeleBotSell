from pydantic import BaseModel, Field
from typing import Optional

class QuoteRequest(BaseModel):
    telegram_id: int
    telegram_user: str | None = None  # Telegram username (optional)
    product_id: int
    # Bỏ giới hạn tối đa 999, chỉ yêu cầu > 0
    qty: int = Field(gt=0)
    coupon: str | None = None

class QuoteResponse(BaseModel):
    subtotal: float
    discount: float
    qty_discount: float = 0.0  # Giảm giá theo số lượng
    coupon: str | None
    """Machine-readable reason when client sent coupon but it was not applied (same codes as checkout)."""
    coupon_error: Optional[str] = None
    """True on quote: usage limits are not reserved; checkout can still fail if slots run out."""
    coupon_not_reserved: bool = False
    coupon_remaining_global: Optional[int] = None
    coupon_remaining_user: Optional[int] = None
    coupon_usage_hint: Optional[str] = None
    total: float
    currency: str = "USD"

class CheckoutRequest(BaseModel):
    telegram_id: int
    telegram_user: str | None = None  # Telegram username (optional)
    product_id: int
    # Bỏ giới hạn tối đa 999, chỉ yêu cầu > 0
    qty: int = Field(gt=0)
    coupon: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)

class CheckoutResponse(BaseModel):
    order_id: str
    order_code: str
    total: float
    currency: str = "USD"
    delivery_payload: str
