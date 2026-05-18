from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


# -- Products --

class SellerProductItem(BaseModel):
    product_id: int
    code: str
    name: str
    price: float
    stock: int
    is_active: bool


class SellerProductListResponse(BaseModel):
    products: List[SellerProductItem]


class SellerProductInfoResponse(BaseModel):
    product_id: int
    code: str
    name: str
    description: str | None = None
    price: float
    stock: int
    is_active: bool


# -- Checkout --

class SellerCheckoutRequest(BaseModel):
    product_id: int
    qty: int = Field(gt=0, le=10000)
    idempotency_key: str = Field(min_length=8, max_length=128)


class SellerCheckoutResponse(BaseModel):
    order_id: str
    order_code: str
    product_name: str
    qty: int
    unit_price: float
    total: float
    currency: str = "USD"
    delivery_payload: str
    status: str


# -- Balance --

class SellerBalanceResponse(BaseModel):
    user_id: int
    balance: float
    currency: str = "USD"


# -- Orders --

class SellerOrderItem(BaseModel):
    order_id: str
    order_code: str
    product_name: str
    qty: int
    total: float
    currency: str
    status: str
    created_at: str | None = None


class SellerOrderListResponse(BaseModel):
    orders: List[SellerOrderItem]
    total: int
    page: int
    limit: int


# -- Coupons --

class SellerCreateCouponRequest(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    telegram_id: int = Field(gt=0, description="Telegram ID of user to assign coupon to")
    discount_type: str = Field(default="PERCENT", pattern="^(PERCENT|FIXED)$")
    discount_value: float = Field(gt=0)
    max_discount_amount: Optional[float] = None
    min_order_amount: Optional[float] = None
    product_id: Optional[int] = None
    max_uses_total: Optional[int] = Field(default=None, ge=1)
    max_uses_per_user: Optional[int] = Field(default=None, ge=1)
    max_qty_per_order: Optional[int] = Field(default=None, ge=1)
    is_active: bool = True


class SellerCouponResponse(BaseModel):
    ok: bool = True
    coupon_id: int
    code: str
    telegram_id: int
    discount_type: str
    discount_value: float


class SellerCouponListItem(BaseModel):
    coupon_id: int
    code: str
    discount_type: str
    discount_value: float
    telegram_id: Optional[int] = None
    product_id: Optional[int] = None
    max_uses_total: Optional[int] = None
    committed_usage_count: int = 0
    is_active: bool


class SellerCouponListResponse(BaseModel):
    coupons: List[SellerCouponListItem]
    total: int
