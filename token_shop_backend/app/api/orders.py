from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
from decimal import Decimal
from typing import Optional, List

from app.database import get_db
from app.security.bot_auth import require_bot_api_key
from app.models.user import User
from app.models.product import Product
from app.models.order import Order
from app.models.product_stock_item import ProductStockItem
from app.schemas.orders import QuoteRequest, QuoteResponse, CheckoutRequest, CheckoutResponse
from app.services.idgen import make_order_code as build_order_code
from app.models.coupon import Coupon
from app.services.coupon_service import apply_coupon_pricing, record_redemption, sync_coupon_committed_counter_from_ledger


router = APIRouter(prefix="/orders", tags=["orders"], dependencies=[Depends(require_bot_api_key)])


def _d(x) -> Decimal:
    return Decimal(str(x or "0"))


def _get_or_create_user(db: Session, telegram_id: int, telegram_user: str | None = None) -> User:
    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    if u:
        if telegram_user and telegram_user != u.telegram_user:
            u.telegram_user = telegram_user
        if getattr(u, "is_banned", False):
            raise HTTPException(403, detail="USER_BANNED")
        return u
    u = User(telegram_id=telegram_id, balance=0, telegram_user=telegram_user)
    db.add(u)
    db.flush()
    return u


def make_order_code(telegram_id: int) -> str:
    return build_order_code(telegram_id)


def _coupon_http_exception(code: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": code})


def _available_stock(db: Session, product_id: int, fallback_stock: int) -> int:
    cnt = db.execute(
        select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == product_id)
    ).scalar_one()
    cnt = int(cnt or 0)
    return cnt if cnt > 0 else int(fallback_stock or 0)


@router.post("/quote", response_model=QuoteResponse)
def quote(req: QuoteRequest, db: Session = Depends(get_db)):
    """
    Read-heavy: không commit giữa chừng (giảm round-trip DB). Một commit cuối nếu có thay đổi user.
    """
    try:
        if req.telegram_user:
            u_check = db.query(User).filter(User.telegram_id == req.telegram_id).first()
            if u_check and u_check.telegram_user != req.telegram_user:
                u_check.telegram_user = req.telegram_user

        u = db.query(User).filter(User.telegram_id == req.telegram_id).first()
        if u and getattr(u, "is_banned", False):
            raise HTTPException(403, detail="USER_BANNED")

        u = None
        if req.coupon and str(req.coupon).strip():
            u = _get_or_create_user(db, req.telegram_id, req.telegram_user)
            db.flush()
        else:
            u = db.query(User).filter(User.telegram_id == req.telegram_id).first()

        p = db.query(Product).filter(Product.id == req.product_id, Product.is_active == True).first()
        if not p:
            raise HTTPException(404, detail="PRODUCT_NOT_FOUND")

        stock = _available_stock(db, p.id, int(p.stock or 0))
        if stock < int(req.qty):
            raise HTTPException(
                status_code=400,
                detail=f"OUT_OF_STOCK:Requested {req.qty} but only {stock} available",
            )

        br = apply_coupon_pricing(
            db,
            p,
            int(req.qty),
            req.coupon,
            u,
            lock_coupon_row=False,
        )

        out = QuoteResponse(
            subtotal=float(br.subtotal),
            discount=float(br.discount),
            qty_discount=float(br.qty_discount),
            coupon=br.applied_coupon_code,
            coupon_error=br.coupon_error,
            coupon_not_reserved=bool(br.coupon_not_reserved),
            coupon_remaining_global=br.coupon_remaining_global,
            coupon_remaining_user=br.coupon_remaining_user,
            coupon_usage_hint=br.coupon_usage_hint,
            total=float(br.total),
            currency=p.currency or "USD",
        )
        db.commit()
        return out
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(req: CheckoutRequest, db: Session = Depends(get_db)):
    try:
        with db.begin():
            existing = db.query(Order).filter(Order.idempotency_key == req.idempotency_key).first()
            if existing:
                return CheckoutResponse(
                    order_id=existing.id,
                    order_code=existing.order_code,
                    total=float(existing.total),
                    currency=existing.currency,
                    delivery_payload=existing.delivery_payload or "",
                )

            p_locked = db.execute(
                select(Product)
                .where(Product.id == req.product_id, Product.is_active == True)
                .with_for_update(nowait=False)
            ).scalar_one_or_none()

            if not p_locked:
                raise HTTPException(404, detail="PRODUCT_NOT_FOUND")

            qty = int(req.qty)
            delivery_lines: List[str] = []
            locked_items: List[ProductStockItem] = []

            item_count = db.execute(
                select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == p_locked.id)
            ).scalar_one()
            item_count = int(item_count or 0)

            if item_count > 0:
                locked_items = list(
                    db.execute(
                        select(ProductStockItem)
                        .where(ProductStockItem.product_id == p_locked.id)
                        .order_by(ProductStockItem.id.asc())
                        .with_for_update(skip_locked=True)
                        .limit(qty)
                    ).scalars().all()
                )
                if len(locked_items) < qty:
                    raise HTTPException(400, detail="OUT_OF_STOCK")
                for it in locked_items:
                    v = (it.mota or "").strip()
                    if not v:
                        v = (it.id_sanpham or "").strip()
                    delivery_lines.append(v)
            else:
                if int(p_locked.stock or 0) < qty:
                    raise HTTPException(400, detail="OUT_OF_STOCK")
                if p_locked.delivery_payload:
                    delivery_lines = [p_locked.delivery_payload]

            u = _get_or_create_user(db, req.telegram_id, req.telegram_user)
            u_locked = db.execute(select(User).where(User.id == u.id).with_for_update()).scalar_one()

            br = apply_coupon_pricing(
                db,
                p_locked,
                qty,
                req.coupon,
                u_locked,
                lock_coupon_row=bool(req.coupon and str(req.coupon).strip()),
            )
            if br.coupon_error:
                raise _coupon_http_exception(br.coupon_error)

            total = br.total
            if _d(u_locked.balance) < total:
                raise HTTPException(400, detail="INSUFFICIENT_BALANCE")

            if locked_items:
                ids = [it.id for it in locked_items]
                db.execute(delete(ProductStockItem).where(ProductStockItem.id.in_(ids)))
                remaining = db.execute(
                    select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == p_locked.id)
                ).scalar_one()
                p_locked.stock = int(remaining or 0)
            else:
                p_locked.stock = int(p_locked.stock) - qty

            u_locked.balance = _d(u_locked.balance) - total

            order_code = make_order_code(req.telegram_id)
            delivery = "\n".join([x for x in delivery_lines if (x or "").strip()]) if delivery_lines else ""
            if not delivery:
                delivery = f"DELIVERY_PLACEHOLDER:{order_code}"

            o = Order(
                order_code=order_code,
                idempotency_key=req.idempotency_key,
                user_id=u_locked.id,
                telegram_id=req.telegram_id,
                product_id=p_locked.id,
                product_name=p_locked.name,
                qty=qty,
                unit_price=p_locked.price,
                subtotal=br.subtotal,
                discount_total=br.discount,
                total=total,
                currency=p_locked.currency or "USD",
                coupon_code=br.applied_coupon_code,
                status="PAID",
                delivery_payload=delivery,
            )
            db.add(o)
            db.flush()

            if br.applied_coupon_id is not None:
                c_row = db.get(Coupon, br.applied_coupon_id)
                if c_row is None:
                    raise _coupon_http_exception("COUPON_INVALID")
                try:
                    record_redemption(db, br.applied_coupon_id, u_locked.id, o.id)
                except IntegrityError as ie:
                    raise _coupon_http_exception("COUPON_ALREADY_USED_BY_USER") from ie
                if c_row.max_uses_total is not None:
                    sync_coupon_committed_counter_from_ledger(db, int(c_row.id))

        return CheckoutResponse(
            order_id=o.id,
            order_code=o.order_code,
            total=float(o.total),
            currency=o.currency,
            delivery_payload=o.delivery_payload or "",
        )

    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        o = db.query(Order).filter(Order.idempotency_key == req.idempotency_key).first()
        if o:
            return CheckoutResponse(
                order_id=o.id,
                order_code=o.order_code,
                total=float(o.total),
                currency=o.currency,
                delivery_payload=o.delivery_payload or "",
            )
        raise HTTPException(500, detail="CHECKOUT_FAILED")


@router.get("/history")
def history(telegram_id: int, month: Optional[int] = None, year: Optional[int] = None, page: int = 1, limit: int = 10, db: Session = Depends(get_db)):
    from datetime import datetime
    from sqlalchemy import and_

    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not u:
        return {"orders": [], "total": 0, "page": page, "limit": limit}

    now = datetime.utcnow()
    if month is None:
        month = now.month
    if year is None:
        year = now.year

    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    query = (
        db.query(Order)
        .filter(
            and_(
                Order.user_id == u.id,
                Order.created_at >= start_date,
                Order.created_at < end_date,
            )
        )
        .order_by(Order.created_at.desc())
    )

    total = query.count()
    offset = (page - 1) * limit
    rows = query.offset(offset).limit(limit).all()

    res = []
    for o in rows:
        res.append({
            "order_id": o.id,
            "order_code": o.order_code,
            "product_name": o.product_name,
            "qty": o.qty,
            "total": str(o.total),
            "currency": o.currency,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })

    return {
        "orders": res,
        "total": total,
        "page": page,
        "limit": limit,
        "month": month,
        "year": year,
    }


@router.get("/{order_id}")
def get_order_detail(order_id: str, telegram_id: int, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not u:
        raise HTTPException(404, detail="USER_NOT_FOUND")

    o = db.query(Order).filter(Order.id == order_id, Order.user_id == u.id).first()
    if not o:
        raise HTTPException(404, detail="ORDER_NOT_FOUND")

    return {
        "order_id": o.id,
        "order_code": o.order_code,
        "product_id": o.product_id,
        "product_name": o.product_name,
        "qty": o.qty,
        "unit_price": str(o.unit_price),
        "subtotal": str(o.subtotal),
        "discount_total": str(o.discount_total),
        "total": str(o.total),
        "currency": o.currency,
        "coupon_code": o.coupon_code,
        "status": o.status,
        "delivery_payload": o.delivery_payload,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }
