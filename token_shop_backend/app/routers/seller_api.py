"""
Seller public API — prefix /seller/v1

Seller = User Telegram duoc admin cap API key.
Auth = HMAC-SHA256, tra ve User object.
Tat ca dung User.balance, User.id.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.firewall import check_firewall
from app.middleware.seller_auth import verify_seller_hmac
from app.models.user import User
from decimal import Decimal

from app.models.coupon import Coupon
from app.models.user import User as UserModel
from app.schemas.seller import (
    SellerBalanceResponse,
    SellerCheckoutRequest,
    SellerCheckoutResponse,
    SellerCouponListResponse,
    SellerCouponListItem,
    SellerCouponResponse,
    SellerCreateCouponRequest,
    SellerOrderListResponse,
    SellerProductInfoResponse,
    SellerProductListResponse,
)
from app.services.seller_service import (
    checkout as do_checkout,
    get_balance,
    get_product_info,
    list_orders,
    list_products,
)

log = logging.getLogger("seller_api")

router = APIRouter(
    prefix="/seller/v1",
    tags=["seller"],
    dependencies=[Depends(check_firewall)],
)


# -- GET /seller/v1/products --

@router.get("/products", response_model=SellerProductListResponse)
async def seller_list_products(
    request: Request,
    user: User = Depends(verify_seller_hmac),
    db: Session = Depends(get_db),
):
    products = list_products(db)
    return SellerProductListResponse(products=products)


# -- GET /seller/v1/products/{product_id} --

@router.get("/products/{product_id}", response_model=SellerProductInfoResponse)
async def seller_product_info(
    product_id: int,
    request: Request,
    user: User = Depends(verify_seller_hmac),
    db: Session = Depends(get_db),
):
    info = get_product_info(db, product_id)
    if not info:
        raise HTTPException(404, detail="PRODUCT_NOT_FOUND")
    return SellerProductInfoResponse(**info)


# -- POST /seller/v1/checkout --

@router.post("/checkout", response_model=SellerCheckoutResponse)
async def seller_checkout(
    req: SellerCheckoutRequest,
    request: Request,
    user: User = Depends(verify_seller_hmac),
    db: Session = Depends(get_db),
):
    try:
        with db.begin_nested():
            order = do_checkout(
                db,
                user,
                req.product_id,
                req.qty,
                req.idempotency_key,
            )
        db.commit()
        return SellerCheckoutResponse(
            order_id=order.id,
            order_code=order.order_code,
            product_name=order.product_name,
            qty=order.qty,
            unit_price=float(order.unit_price),
            total=float(order.total),
            currency=order.currency,
            delivery_payload=order.delivery_payload or "",
            status=order.status,
        )
    except ValueError as e:
        code = str(e)
        status = 400
        if code == "PRODUCT_NOT_FOUND":
            status = 404
        raise HTTPException(status, detail=code)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("seller_checkout error")
        raise HTTPException(500, detail="CHECKOUT_FAILED")


# -- GET /seller/v1/balance --

@router.get("/balance", response_model=SellerBalanceResponse)
async def seller_balance(
    request: Request,
    user: User = Depends(verify_seller_hmac),
    db: Session = Depends(get_db),
):
    data = get_balance(user)
    return SellerBalanceResponse(**data)


# -- GET /seller/v1/orders --

@router.get("/orders", response_model=SellerOrderListResponse)
async def seller_orders(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(verify_seller_hmac),
    db: Session = Depends(get_db),
):
    data = list_orders(db, user, page=page, limit=limit)
    return SellerOrderListResponse(**data)


# -- POST /seller/v1/coupons --

@router.post("/coupons", response_model=SellerCouponResponse)
async def seller_create_coupon(
    req: SellerCreateCouponRequest,
    request: Request,
    user: User = Depends(verify_seller_hmac),
    db: Session = Depends(get_db),
):
    """
    Seller tạo mã giảm giá cho 1 user cụ thể (theo telegram_id).
    Coupon sẽ gắn với user_id trong DB.
    """
    code = req.code.strip().upper()
    if not code:
        raise HTTPException(400, detail="MISSING_CODE")

    # Tìm user theo telegram_id
    target_user = db.query(UserModel).filter(UserModel.telegram_id == req.telegram_id).first()
    if not target_user:
        raise HTTPException(404, detail="USER_NOT_FOUND")

    # Check duplicate code
    existing = db.query(Coupon).filter(Coupon.code == code).first()
    if existing:
        raise HTTPException(409, detail="COUPON_CODE_EXISTS")

    coupon = Coupon(
        code=code,
        discount_type=req.discount_type.upper(),
        discount_value=Decimal(str(req.discount_value)),
        max_discount_amount=Decimal(str(req.max_discount_amount)) if req.max_discount_amount is not None else None,
        min_order_amount=Decimal(str(req.min_order_amount)) if req.min_order_amount is not None else None,
        product_id=req.product_id,
        user_id=target_user.id,
        max_uses_total=req.max_uses_total,
        max_uses_per_user=req.max_uses_per_user,
        max_qty_per_order=req.max_qty_per_order,
        is_active=req.is_active,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)

    log.info("seller=%s created coupon=%s for telegram_id=%s user_id=%s",
             user.id, code, req.telegram_id, target_user.id)

    return SellerCouponResponse(
        coupon_id=coupon.id,
        code=code,
        telegram_id=req.telegram_id,
        discount_type=coupon.discount_type,
        discount_value=float(coupon.discount_value),
    )


# -- GET /seller/v1/coupons --

@router.get("/coupons", response_model=SellerCouponListResponse)
async def seller_list_coupons(
    request: Request,
    user: User = Depends(verify_seller_hmac),
    db: Session = Depends(get_db),
):
    """
    Liệt kê tất cả coupons (seller xem được toàn bộ).
    """
    coupons = db.query(Coupon).order_by(Coupon.created_at.desc()).limit(200).all()
    items = []
    for c in coupons:
        # Lấy telegram_id nếu coupon gắn user
        tid = None
        if c.user_id:
            u = db.query(UserModel).filter(UserModel.id == c.user_id).first()
            tid = u.telegram_id if u else None
        items.append(SellerCouponListItem(
            coupon_id=c.id,
            code=c.code,
            discount_type=c.discount_type,
            discount_value=float(c.discount_value),
            telegram_id=tid,
            product_id=c.product_id,
            max_uses_total=c.max_uses_total,
            committed_usage_count=c.committed_usage_count,
            is_active=c.is_active,
        ))
    return SellerCouponListResponse(coupons=items, total=len(items))


# -- DELETE /seller/v1/coupons/{coupon_id} --

@router.delete("/coupons/{coupon_id}")
async def seller_deactivate_coupon(
    coupon_id: int,
    request: Request,
    user: User = Depends(verify_seller_hmac),
    db: Session = Depends(get_db),
):
    """
    Vô hiệu hóa coupon (set is_active=False).
    """
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, detail="COUPON_NOT_FOUND")

    coupon.is_active = False
    db.commit()

    log.info("seller=%s deactivated coupon=%s code=%s", user.id, coupon_id, coupon.code)
    return {"ok": True, "coupon_id": coupon_id}
