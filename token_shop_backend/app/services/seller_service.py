"""
Business logic cho Seller API — don gian hoa.

Seller = User Telegram duoc admin cap API key.
Tat ca dung User.balance, User.id — KHONG tao balance rieng.
Reuse logic checkout hien tai (orders).
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import List

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.product import Product
from app.models.product_stock_item import ProductStockItem
from app.models.user import User
from app.services.idgen import make_order_code

log = logging.getLogger("seller_service")


def _d(x) -> Decimal:
    return Decimal(str(x or "0"))


def _stock_count(db: Session, product_id: int, fallback_stock: int) -> int:
    cnt = db.execute(
        select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == product_id)
    ).scalar_one()
    cnt = int(cnt or 0)
    return cnt if cnt > 0 else int(fallback_stock or 0)


# -- list_products --

def list_products(db: Session) -> list[dict]:
    """List tat ca products dang ban (public)."""
    rows = db.query(Product).filter(Product.is_active == True).order_by(Product.sort_order.asc(), Product.id.asc()).all()
    result = []
    for p in rows:
        stock = _stock_count(db, p.id, int(p.stock or 0))
        result.append({
            "product_id": p.id,
            "code": p.code,
            "name": p.name,
            "price": float(p.price),
            "stock": stock,
            "is_active": True,
        })
    return result


# -- get_product_info --

def get_product_info(db: Session, product_id: int) -> dict | None:
    p = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not p:
        return None
    stock = _stock_count(db, p.id, int(p.stock or 0))
    return {
        "product_id": p.id,
        "code": p.code,
        "name": p.name,
        "description": p.description,
        "price": float(p.price),
        "stock": stock,
        "is_active": True,
    }


# -- checkout (row-lock, tru User.balance, tao Order) --

def checkout(
    db: Session,
    user: User,
    product_id: int,
    qty: int,
    idempotency_key: str,
) -> Order:
    """
    Checkout voi row-lock — giong logic checkout chinh:
    1. Lock product (FOR UPDATE)
    2. Lock stock items (FOR UPDATE SKIP LOCKED)
    3. Lock user balance (FOR UPDATE)
    4. Tru balance, xoa stock items, tao Order
    """
    # idempotency check
    existing = db.query(Order).filter(
        Order.idempotency_key == idempotency_key,
        Order.user_id == user.id,
    ).first()
    if existing:
        return existing

    # 1) lock product
    p_locked = db.execute(
        select(Product)
        .where(Product.id == product_id, Product.is_active == True)
        .with_for_update(nowait=False)
    ).scalar_one_or_none()
    if not p_locked:
        raise ValueError("PRODUCT_NOT_FOUND")

    unit_price = _d(p_locked.price)
    total = unit_price * qty

    # 2) lock stock items
    delivery_lines: list[str] = []
    locked_items: list[ProductStockItem] = []

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
            raise ValueError("OUT_OF_STOCK")
        for it in locked_items:
            v = (it.mota or "").strip()
            if not v:
                v = (it.id_sanpham or "").strip()
            delivery_lines.append(v)
    else:
        if int(p_locked.stock or 0) < qty:
            raise ValueError("OUT_OF_STOCK")
        if p_locked.delivery_payload:
            delivery_lines = [p_locked.delivery_payload]

    # 3) lock user balance
    u_locked = db.execute(
        select(User).where(User.id == user.id).with_for_update()
    ).scalar_one()

    if _d(u_locked.balance) < total:
        raise ValueError("INSUFFICIENT_BALANCE")

    # 4) execute
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

    order_code = make_order_code(u_locked.telegram_id)
    delivery = "\n".join([x for x in delivery_lines if (x or "").strip()]) if delivery_lines else ""
    if not delivery:
        delivery = f"DELIVERY_PLACEHOLDER:{order_code}"

    order = Order(
        order_code=order_code,
        idempotency_key=idempotency_key,
        user_id=u_locked.id,
        telegram_id=u_locked.telegram_id,
        product_id=p_locked.id,
        product_name=p_locked.name,
        qty=qty,
        unit_price=unit_price,
        subtotal=total,
        discount_total=0,
        total=total,
        currency=p_locked.currency or "USD",
        status="PAID",
        delivery_payload=delivery,
    )
    db.add(order)
    db.flush()

    log.info("seller_checkout user=%s product=%s qty=%d total=%s order=%s",
             u_locked.id, p_locked.id, qty, total, order.id)
    return order


# -- get_balance --

def get_balance(user: User) -> dict:
    return {
        "user_id": user.id,
        "balance": float(user.balance or 0),
        "currency": "USD",
    }


# -- list_orders --

def list_orders(db: Session, user: User, page: int = 1, limit: int = 20) -> dict:
    query = (
        db.query(Order)
        .filter(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    total = query.count()
    offset = (page - 1) * limit
    rows = query.offset(offset).limit(limit).all()

    orders = []
    for o in rows:
        orders.append({
            "order_id": o.id,
            "order_code": o.order_code,
            "product_name": o.product_name,
            "qty": o.qty,
            "total": float(o.total),
            "currency": o.currency,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })

    return {
        "orders": orders,
        "total": total,
        "page": page,
        "limit": limit,
    }
