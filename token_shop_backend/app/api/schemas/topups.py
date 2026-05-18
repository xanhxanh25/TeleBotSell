from pydantic import BaseModel, Field
from decimal import Decimal

class TopupCreateRequest(BaseModel):
    telegram_id: int
    network: str
    coin: str
    amount: Decimal = Field(gt=0)

class TopupCreateResponse(BaseModel):
    topup_id: str
    out_order_id: str

    # amount = pay_amount để bot đang dùng invoice["amount"] vẫn chạy
    amount: str

    actual_amount: str      # số USD khách nhập
    pay_amount: str         # số TokenPay bắt chuyển (có thể 10.0002)

    address: str | None = None
    qr_base64: str | None = None
    payment_url: str | None = None
    expire_time: str | None = None
    currency: str
    base_currency: str = "USD"
    status: str = "PENDING"

class TopupStatusResponse(BaseModel):
    topup_id: str
    status: str
    out_order_id: str
    amount: str
    actual_amount: str
    pay_amount: str
    currency: str
    base_currency: str = "USD"
