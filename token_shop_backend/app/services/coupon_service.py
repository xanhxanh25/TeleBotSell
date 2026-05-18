"""
Single source of truth: coupon validation + pricing (quote + checkout).

Global cap: COUNT redemption COMMITTED dưới khóa FOR UPDATE trên row coupon (serialize mọi checkout dùng cùng mã).
committed_usage_count trên bảng coupons = bản sao đếm nhanh, đồng bộ sau mỗi checkout/reverse (sync từ ledger).

Lifecycle:
  - Checkout PAID => redemption COMMITTED; sync counter nếu max_uses_total.
  - Admin reverse_coupon_usage => REVERSED (không tính quota); sync counter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.coupon import Coupon
from app.models.coupon_redemption import CouponRedemption, REDEMPTION_COMMITTED, REDEMPTION_REVERSED
from app.models.product import Product
from app.models.user import User
from app.services import coupon_codes as CC
from app.services.product_qty_tiers import qty_discount_amount as _qty_discount_amount


def _d(x) -> Decimal:
    return Decimal(str(x or "0"))


def normalize_coupon_code(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().upper()
    return s or None


def _count_committed_global_ledger(db: Session, coupon_id: int) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(CouponRedemption)
            .where(
                CouponRedemption.coupon_id == coupon_id,
                CouponRedemption.status == REDEMPTION_COMMITTED,
            )
        ).scalar_one()
        or 0
    )


def count_committed_global_ledger(db: Session, coupon_id: int) -> int:
    """API công khai: số lần dùng coupon (COMMITTED) — dùng cho admin báo cáo / cộng quota."""
    return _count_committed_global_ledger(db, coupon_id)


def _count_committed_user_ledger(db: Session, coupon_id: int, user_id: int) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(CouponRedemption)
            .where(
                CouponRedemption.coupon_id == coupon_id,
                CouponRedemption.user_id == user_id,
                CouponRedemption.status == REDEMPTION_COMMITTED,
            )
        ).scalar_one()
        or 0
    )


@dataclass(frozen=True)
class PricingBreakdown:
    subtotal: Decimal
    qty_discount: Decimal
    coupon_discount: Decimal
    discount: Decimal
    total: Decimal
    applied_coupon_code: Optional[str]
    applied_coupon_id: Optional[int] = None
    coupon_error: Optional[str] = None
    # Quote UX: không có reservation; có thể mất slot trước checkout.
    coupon_not_reserved: bool = False
    coupon_remaining_global: Optional[int] = None
    coupon_remaining_user: Optional[int] = None
    coupon_usage_hint: Optional[str] = None


def _coupon_discount_amount(c: Coupon, subtotal: Decimal) -> Decimal:
    if (c.discount_type or "").upper() == "PERCENT":
        d = (subtotal * _d(c.discount_value) / _d(100)).quantize(Decimal("0.01"))
    else:
        d = _d(c.discount_value).quantize(Decimal("0.01"))
    if c.max_discount_amount is not None:
        md = _d(c.max_discount_amount)
        if d > md:
            d = md
    return d


def _empty_breakdown(
    subtotal: Decimal,
    qty_disc: Decimal,
    base_discount: Decimal,
    *,
    coupon_error: Optional[str],
) -> PricingBreakdown:
    total = (subtotal - base_discount).quantize(Decimal("0.01"))
    if total < 0:
        total = Decimal("0")
    return PricingBreakdown(
        subtotal=subtotal.quantize(Decimal("0.01")),
        qty_discount=qty_disc.quantize(Decimal("0.01")),
        coupon_discount=Decimal("0"),
        discount=base_discount.quantize(Decimal("0.01")),
        total=total,
        applied_coupon_code=None,
        applied_coupon_id=None,
        coupon_error=coupon_error,
        coupon_not_reserved=False,
        coupon_remaining_global=None,
        coupon_remaining_user=None,
        coupon_usage_hint=None,
    )


def _fill_quote_remaining(
    db: Session,
    c: Coupon,
    user: User,
    br: PricingBreakdown,
) -> PricingBreakdown:
    """Gắn remaining_* cho quote (đọc ledger, không lock)."""
    if br.coupon_error is not None:
        return br
    used_g = _count_committed_global_ledger(db, int(c.id))
    used_u = _count_committed_user_ledger(db, int(c.id), int(user.id))
    rem_g = None
    if c.max_uses_total is not None:
        rem_g = max(0, int(c.max_uses_total) - used_g)
    rem_u = None
    if c.max_uses_per_user is not None:
        rem_u = max(0, int(c.max_uses_per_user) - used_u)
    return PricingBreakdown(
        subtotal=br.subtotal,
        qty_discount=br.qty_discount,
        coupon_discount=br.coupon_discount,
        discount=br.discount,
        total=br.total,
        applied_coupon_code=br.applied_coupon_code,
        applied_coupon_id=br.applied_coupon_id,
        coupon_error=br.coupon_error,
        coupon_not_reserved=True,
        coupon_remaining_global=rem_g,
        coupon_remaining_user=rem_u,
        coupon_usage_hint="NOT_RESERVED: slot not held; another buyer may consume remaining uses before you pay.",
    )


def apply_coupon_pricing(
    db: Session,
    product: Product,
    qty: int,
    coupon_raw: Optional[str],
    user: Optional[User],
    *,
    lock_coupon_row: bool,
) -> PricingBreakdown:
    qty = int(qty)
    subtotal = _d(product.price) * _d(qty)
    qty_disc = _qty_discount_amount(db, product, qty, subtotal)
    base_discount = qty_disc

    norm = normalize_coupon_code(coupon_raw)
    if norm and user is None:
        return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_INVALID)

    if not norm:
        return PricingBreakdown(
            subtotal=subtotal.quantize(Decimal("0.01")),
            qty_discount=qty_disc.quantize(Decimal("0.01")),
            coupon_discount=Decimal("0"),
            discount=base_discount.quantize(Decimal("0.01")),
            total=(subtotal - base_discount).quantize(Decimal("0.01")) if (subtotal - base_discount) > 0 else Decimal("0"),
            applied_coupon_code=None,
            applied_coupon_id=None,
            coupon_error=None,
            coupon_not_reserved=False,
            coupon_remaining_global=None,
            coupon_remaining_user=None,
            coupon_usage_hint=None,
        )

    c_row = db.execute(select(Coupon).where(Coupon.code == norm)).scalar_one_or_none()
    if c_row is None:
        return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_INVALID)

    if not c_row.is_active:
        return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_INACTIVE)

    cid = int(c_row.id)
    if lock_coupon_row:
        c = db.execute(select(Coupon).where(Coupon.id == cid).with_for_update()).scalar_one_or_none()
    else:
        c = c_row

    if c is None or not c.is_active:
        return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_INACTIVE)

    now = datetime.now(timezone.utc)
    if c.starts_at is not None:
        sa = c.starts_at
        if sa.tzinfo is None:
            sa = sa.replace(tzinfo=timezone.utc)
        if sa > now:
            return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_NOT_STARTED)

    if c.ends_at is not None:
        ea = c.ends_at
        if ea.tzinfo is None:
            ea = ea.replace(tzinfo=timezone.utc)
        if ea < now:
            return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_EXPIRED)

    if c.product_id is not None and int(c.product_id) != int(product.id):
        return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_WRONG_PRODUCT)

    if c.user_id is not None and int(c.user_id) != int(user.id):
        return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_WRONG_USER)

    max_qty = getattr(c, "max_qty_per_order", None)
    if max_qty is not None and qty > int(max_qty):
        return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_MAX_QTY_EXCEEDED)

    # Per-user: COUNT ledger COMMITTED (checkout path giữ lock coupon + user => không TOCTOU cross-request)
    max_pu = getattr(c, "max_uses_per_user", None)
    if max_pu is not None:
        used_u = _count_committed_user_ledger(db, int(c.id), int(user.id))
        if used_u >= int(max_pu):
            return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_ALREADY_USED_BY_USER)

    # Global: COUNT ledger COMMITTED dưới lock coupon (đúng với thực tế usage)
    mx = getattr(c, "max_uses_total", None)
    if mx is not None:
        used_g = _count_committed_global_ledger(db, int(c.id))
        if used_g >= int(mx):
            return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_MAX_USES_EXCEEDED)

    if c.min_order_amount is not None and subtotal < _d(c.min_order_amount):
        return _empty_breakdown(subtotal, qty_disc, base_discount, coupon_error=CC.COUPON_MIN_ORDER_NOT_MET)

    coupon_disc = _coupon_discount_amount(c, subtotal)
    discount = qty_disc + coupon_disc
    total = (subtotal - discount).quantize(Decimal("0.01"))
    if total < 0:
        total = Decimal("0")

    ok = PricingBreakdown(
        subtotal=subtotal.quantize(Decimal("0.01")),
        qty_discount=qty_disc.quantize(Decimal("0.01")),
        coupon_discount=coupon_disc.quantize(Decimal("0.01")),
        discount=discount.quantize(Decimal("0.01")),
        total=total,
        applied_coupon_code=c.code,
        applied_coupon_id=int(c.id),
        coupon_error=None,
        coupon_not_reserved=not lock_coupon_row,
        coupon_remaining_global=None,
        coupon_remaining_user=None,
        coupon_usage_hint=(
            None
            if lock_coupon_row
            else "NOT_RESERVED: slot not held; another buyer may consume remaining uses before you pay."
        ),
    )
    if not lock_coupon_row:
        return _fill_quote_remaining(db, c, user, ok)
    return ok


def sync_coupon_committed_counter_from_ledger(db: Session, coupon_id: int) -> None:
    """Đặt committed_usage_count = COUNT redemption COMMITTED (sửa drift, báo cáo nhanh)."""
    cnt = _count_committed_global_ledger(db, coupon_id)
    db.execute(
        update(Coupon).where(Coupon.id == coupon_id).values(committed_usage_count=cnt)
    )
    db.flush()


def record_redemption(db: Session, coupon_id: int, user_id: int, order_id: str) -> None:
    row = dict(
        coupon_id=coupon_id,
        user_id=user_id,
        order_id=order_id,
        status=REDEMPTION_COMMITTED,
    )
    if db.get_bind().dialect.name == "sqlite":
        mx = db.execute(select(func.coalesce(func.max(CouponRedemption.id), 0))).scalar_one()
        row["id"] = int(mx) + 1
    db.add(CouponRedemption(**row))
    db.flush()


def reverse_redemption_for_order(db: Session, order_id: str) -> bool:
    """
    Hoàn usage khi order bị cancel/refund (business rule: chỉ REVERSED mới không tính quota).
    Đồng bộ committed_usage_count từ ledger nếu có max_uses_total.
    """
    r = db.execute(
        select(CouponRedemption).where(CouponRedemption.order_id == order_id)
    ).scalar_one_or_none()
    if r is None or r.status != REDEMPTION_COMMITTED:
        return False
    cid = int(r.coupon_id)
    c = db.get(Coupon, cid)
    r.status = REDEMPTION_REVERSED
    db.flush()
    if c is not None and c.max_uses_total is not None:
        sync_coupon_committed_counter_from_ledger(db, cid)
    return True
