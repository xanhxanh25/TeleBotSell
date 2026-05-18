from pydantic import BaseModel, Field
from decimal import Decimal

class TopupCreateRequest(BaseModel):
    telegram_id: int
    telegram_user: str | None = None  # Telegram username (optional)
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

    address: str | None = None       # ví BSC/TRON hoặc Binance ID nếu là Binance Pay
    qr_base64: str | None = None
    payment_url: str | None = None
    expire_time: str | None = None
    currency: str
    base_currency: str = "USD"
    status: str = "PENDING"

    # ── Binance Pay fields (chỉ có khi currency bắt đầu bằng BINANCE_) ──
    binance_id: str | None = None        # Binance ID của merchant (vd: "711662011")
    note_to_payee: str | None = None     # Note bắt buộc điền (vd: "SHOP5147388757")

class TopupStatusResponse(BaseModel):
    topup_id: str
    status: str
    out_order_id: str
    amount: str
    actual_amount: str
    pay_amount: str
    network: str | None = None
    address: str | None = None
    qr_base64: str | None = None
    payment_url: str | None = None
    expire_time: str | None = None
    currency: str
    base_currency: str = "USD"
    binance_id: str | None = None
    note_to_payee: str | None = None
