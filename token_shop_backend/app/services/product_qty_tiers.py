"""Giảm giá theo số lượng: nhiều bậc / sản phẩm (admin cấu hình), fallback cột legacy."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_qty_discount_tier import ProductQtyDiscountTier


def _d(x) -> Decimal:
    return Decimal(str(x or "0"))


def validate_tiers_rows(rows: Iterable[tuple[object, object]]) -> list[tuple[int, Decimal]]:
    """
    rows: (min_qty, percent) từ form/API.
    Trả về đã sort theo min_qty tăng dần, không trùng min_qty.
    """
    seen: set[int] = set()
    out: list[tuple[int, Decimal]] = []
    for mq_raw, pct_raw in rows:
        if mq_raw is None and pct_raw is None:
            continue
        s_mq = str(mq_raw).strip() if mq_raw is not None else ""
        s_pc = str(pct_raw).strip() if pct_raw is not None else ""
        if not s_mq and not s_pc:
            continue
        if not s_mq or not s_pc:
            raise ValueError("TIER_INCOMPLETE_ROW")
        try:
            mq = int(s_mq)
        except ValueError as e:
            raise ValueError("TIER_INVALID_MIN_QTY") from e
        if mq < 1:
            raise ValueError("TIER_MIN_QTY_TOO_SMALL")
        try:
            pct = Decimal(s_pc)
        except Exception as e:
            raise ValueError("TIER_INVALID_PERCENT") from e
        if pct < 0 or pct > 100:
            raise ValueError("TIER_PERCENT_RANGE")
        if mq in seen:
            raise ValueError("TIER_DUPLICATE_MIN_QTY")
        seen.add(mq)
        out.append((mq, pct))
    out.sort(key=lambda x: x[0])
    return out


def load_tiers_for_product(db: Session, product_id: int) -> list[tuple[int, Decimal]]:
    rows = (
        db.execute(
            select(ProductQtyDiscountTier.min_qty, ProductQtyDiscountTier.percent)
            .where(ProductQtyDiscountTier.product_id == product_id)
            .order_by(ProductQtyDiscountTier.min_qty.asc())
        )
        .all()
    )
    return [(int(r[0]), _d(r[1])) for r in rows]


def replace_tiers_for_product(db: Session, product_id: int, tiers: list[tuple[int, Decimal]]) -> None:
    db.execute(delete(ProductQtyDiscountTier).where(ProductQtyDiscountTier.product_id == product_id))
    for mq, pct in tiers:
        db.add(ProductQtyDiscountTier(product_id=product_id, min_qty=mq, percent=pct))
    db.flush()


def tiers_map_by_product_ids(db: Session, product_ids: list[int]) -> dict[int, list[dict]]:
    if not product_ids:
        return {}
    rows = (
        db.execute(
            select(ProductQtyDiscountTier)
            .where(ProductQtyDiscountTier.product_id.in_(product_ids))
            .order_by(ProductQtyDiscountTier.product_id, ProductQtyDiscountTier.min_qty)
        )
        .scalars()
        .all()
    )
    m: dict[int, list[dict]] = {}
    for r in rows:
        pid = int(r.product_id)
        m.setdefault(pid, []).append({"min_qty": r.min_qty, "percent": str(r.percent)})
    return m


def qty_discount_amount(db: Session, product: Product, qty: int, subtotal: Decimal) -> Decimal:
    """Áp dụng mốc cao nhất có min_qty <= qty; nếu không có tier trong DB thì fallback legacy."""
    qty = int(qty)
    subtotal = _d(subtotal)
    tiers = load_tiers_for_product(db, int(product.id))
    if tiers:
        best_pct: Optional[Decimal] = None
        for min_q, pct in tiers:
            if qty >= min_q:
                best_pct = pct
        if best_pct is not None:
            return (subtotal * (best_pct / Decimal("100"))).quantize(Decimal("0.000001"))
        return Decimal("0")

    qty_discount_min = getattr(product, "qty_discount_min", None)
    qty_discount_percent = getattr(product, "qty_discount_percent", None)
    if qty_discount_min and qty_discount_percent and qty >= int(qty_discount_min):
        return (subtotal * (_d(qty_discount_percent) / Decimal("100"))).quantize(Decimal("0.000001"))
    return Decimal("0")
