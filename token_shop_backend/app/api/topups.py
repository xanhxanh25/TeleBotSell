# app/api/topups.py
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models.user import User
from app.models.topup import Topup
from app.services.idgen import make_topup_out_order_id
from app.services.tokenpay_client import TokenPayClient
from app.schemas.topups import TopupCreateRequest, TopupCreateResponse, TopupStatusResponse

try:
    from zoneinfo import ZoneInfo
    TOKENPAY_EXPIRE_LOCAL_TZ = ZoneInfo(os.getenv("TOKENPAY_EXPIRE_TZ", "Asia/Ho_Chi_Minh"))
except Exception:
    # Windows chưa có tzdata -> dùng timezone hệ thống (đủ dùng cho hạn 30 phút)
    TOKENPAY_EXPIRE_LOCAL_TZ = datetime.now().astimezone().tzinfo
router = APIRouter(prefix="/topups", tags=["topups"])

# fallback nếu topup cũ thiếu expire_time trong DB
EXPIRE_MINUTES_FALLBACK = 30
DT_FMT = "%Y-%m-%d %H:%M:%S"

# ✅ TokenPay trả ExpireTime dạng "naive" (không timezone).
# Từ ảnh bạn gửi: Expiration hiển thị GMT+00 nhưng API trả ExpireTime = giờ Pacific.
  # Pacific (có DST)
DEBUG_TOPUP_TIME = os.getenv("DEBUG_TOPUP_TIME", "0") == "1"

# Timezone Việt Nam để hiển thị expire_time cho user
_VN_TZ = timezone(timedelta(hours=7))

def _to_vn_str(dt: datetime | None) -> str | None:
    """Convert UTC datetime sang chuỗi giờ Việt Nam."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_VN_TZ).strftime(DT_FMT)


def _dbg_print(now_utc: datetime, expire_utc: datetime | None):
    if not DEBUG_TOPUP_TIME:
        return
    print("NOW_UTC:", now_utc)
    print("EXPIRE_UTC:", expire_utc)


def _get_or_create_user(db: Session, telegram_id: int, telegram_user: str | None = None) -> User:
    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    if u:
        # Cập nhật username nếu có và khác với giá trị hiện tại
        if telegram_user and telegram_user != u.telegram_user:
            u.telegram_user = telegram_user
        # Nếu user bị ban thì không cho nạp thêm
        if getattr(u, "is_banned", False):
            raise HTTPException(403, detail="USER_BANNED")
        return u
    u = User(telegram_id=telegram_id, balance=0, telegram_user=telegram_user)
    db.add(u)
    db.flush()
    return u


def _map_currency(network: str, coin: str) -> str:
    n = (network or "").upper().strip()
    c = (coin or "").upper().strip()

    # TRON: USDT_TRC20 → USDT_TRC20, TRX → TRX (backward compatibility)
    if n in ("TRON", "TRX", "TRC20"):
        if c in ("USDT_TRC20", "USDT-TRC20"):
            return "USDT_TRC20"
        if c in ("TRX",):
            return "TRX"
    # BSC / BEP20: USDT_BEP20
    if n in ("BSC", "BNB", "BEP20"):
        if c in ("USDT_BEP20", "USDT-BEP20", "USDT", "BEP20"):
            return "EVM_BSC_USDT_BEP20"
        if c in ("USDC_BEP20", "USDC-BEP20", "USDC"):
            return "EVM_BSC_USDC_BEP20"
    # Binance Exchange deposit (nạp qua tài khoản Binance, không phải on-chain trực tiếp)
    # currency = BINANCE_USDT_BSC (khớp với config Binance:Coin=USDT, Binance:Network=BSC)
    if n in ("BINANCE", "BINANCE_EXCHANGE"):
        if c in ("USDT", "USDT_BSC", "USDT-BSC"):
            return "BINANCE_USDT_BSC"
        if c in ("USDT_TRC20", "USDT-TRC20"):
            return "BINANCE_USDT_TRC20"
    # Ethereum: hỗ trợ USDT_ERC20
    if n in ("ETH", "ETHEREUM", "EVM") and c in ("USDT_ERC20", "USDT-ERC20", "USDT", "ERC20"):
        return "EVM_ETH_USDT_ERC20"
    # Polygon: hỗ trợ USDT-ERC20
    if n in ("POLYGON", "MATIC") and c in ("USDT-ERC20", "USDT_ERC20", "USDT", "ERC20"):
        return "EVM_Polygon_USDT_ERC20"

    raise HTTPException(400, detail="UNSUPPORTED_TOPUP_METHOD")


def _parse_expire_time(exp_str: str | None) -> datetime | None:
    """
    TokenPay ExpireTime format: 'YYYY-mm-dd HH:MM:SS' (không kèm timezone).
    ✅ Theo thực tế (ảnh bạn gửi): exp_str đang là giờ local Pacific.
    => Gắn TZ Pacific, rồi convert về UTC để lưu DB và so sánh nhất quán.
    """
    if not exp_str:
        return None
    try:
        naive = datetime.strptime(exp_str, DT_FMT)  # naive local time
        local_dt = naive.replace(tzinfo=TOKENPAY_EXPIRE_LOCAL_TZ)
        return local_dt.astimezone(timezone.utc)
    except Exception:
        return None


@router.post("/create", response_model=TopupCreateResponse)
def create_topup(req: TopupCreateRequest, db: Session = Depends(get_db)):
    currency = _map_currency(req.network, req.coin)
    now = datetime.now(timezone.utc)

    # 1) LOCK user + check pending (không gọi external trong lúc lock)
    with db.begin():
        u = _get_or_create_user(db, req.telegram_id, req.telegram_user)

        # lock user row để tránh 2 request create song song
        db.execute(select(User).where(User.id == u.id).with_for_update()).scalar_one()

        pending = db.execute(
            select(Topup)
            .where(Topup.user_id == u.id, Topup.status == "PENDING")
            .order_by(Topup.created_at.desc())
            .with_for_update()
        ).scalar_one_or_none()

        if pending:
            # Thống nhất: luôn dùng created_at + 30 phút, không phụ thuộc expire_time từ TokenPay
            created_at = pending.created_at
            if created_at is not None and created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            expire_at = (created_at or now) + timedelta(minutes=EXPIRE_MINUTES_FALLBACK)

            # ✅ debug: xem NOW vs EXPIRE khi check pending
            _dbg_print(now, expire_at)

            # còn hạn => CHẶN, bắt buộc Cancel
            if expire_at > now:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "PENDING_EXISTS",
                        "topup_id": str(pending.id),
                        "out_order_id": pending.out_order_id,
                        "expire_time": _to_vn_str(expire_at),
                    },
                )

            # quá hạn => chuyển CANCELED rồi cho tạo mới
            pending.status = "CANCELED"

    # 2) Gọi TokenPay create_order (không giữ lock DB)
    out_order_id = make_topup_out_order_id(req.telegram_id)
    client = TokenPayClient()

    try:
        tp = client.create_order(
            out_order_id=out_order_id,
            order_user_key=str(req.telegram_id),
            actual_amount=float(req.amount),
            currency=currency,
        )
    except Exception as e:
        raise HTTPException(502, detail=f"TOKENPAY_CREATE_FAILED:{e}")

    info = tp.get("info") or {}

    # 3) Lưu topup dựa theo ExpireTime của TokenPay
    expire_str = info.get("ExpireTime")
    expire_dt = _parse_expire_time(expire_str)

    actual_amount = Decimal(str(req.amount))
    pay_amount = Decimal(str(info.get("Amount") or req.amount))

    # insert topup (có thể bị unique index chặn nếu race)
    try:
        u = _get_or_create_user(db, req.telegram_id, req.telegram_user)  # load lại user
        topup = Topup(
            out_order_id=out_order_id,
            user_id=u.id,
            telegram_id=req.telegram_id,
            network=req.network.upper(),
            currency=currency,
            base_currency=str(info.get("BaseCurrency") or "USD"),

            actual_amount=actual_amount,
            amount=pay_amount,

            status="PENDING",
            payment_url=tp.get("payment_url"),
            to_address=info.get("ToAddress"),
            qr_code_base64=info.get("QrCodeBase64"),
            qr_code_link=info.get("QrCodeLink"),

            expire_time=expire_dt,  # ✅ lưu UTC
            tokenpay_id=info.get("Id"),
        )
        db.add(topup)
        db.commit()

        # ✅ debug: kiểm tra expire_time đã lưu (UTC) có đúng chưa
        _dbg_print(datetime.now(timezone.utc), topup.expire_time)

    except IntegrityError:
        db.rollback()
        # bị uq_topups_one_pending_per_user chặn => trả 409
        raise HTTPException(status_code=409, detail={"code": "PENDING_EXISTS"})

    # Binance Pay: TokenPay trả về BinanceId trong ToAddress và NoteToPayee trong PassThroughInfo
    is_binance_pay = topup.currency.upper().startswith("BINANCE_")
    binance_id_val  = info.get("BinanceId")    or (topup.to_address if is_binance_pay else None)
    note_to_payee   = info.get("NoteToPayee") or (info.get("PassThroughInfo") if is_binance_pay else None)

    return TopupCreateResponse(
        topup_id=str(topup.id),
        out_order_id=topup.out_order_id,

        # amount = pay_amount để bot hiện đúng số cần chuyển
        amount=str(topup.amount or topup.actual_amount),
        actual_amount=str(topup.actual_amount),
        pay_amount=str(topup.amount or topup.actual_amount),

        address=topup.to_address,
        qr_base64=topup.qr_code_base64,
        payment_url=topup.payment_url,

        expire_time=_to_vn_str(expire_dt),

        currency=topup.currency,
        base_currency=topup.base_currency,
        status=topup.status,

        # Binance Pay exclusive fields
        binance_id=str(binance_id_val) if binance_id_val else None,
        note_to_payee=str(note_to_payee) if note_to_payee else None,
    )


@router.get("/{topup_id}", response_model=TopupStatusResponse)
def get_topup(topup_id: str, db: Session = Depends(get_db)):
    t = db.query(Topup).filter(Topup.id == topup_id).first()
    if not t:
        raise HTTPException(404, detail="TOPUP_NOT_FOUND")

    actual_amount_str = str(t.actual_amount)
    pay_amount_str = str(t.amount or t.actual_amount)

    is_binance_pay = t.currency and t.currency.upper().startswith("BINANCE_")
    binance_id = t.to_address if is_binance_pay else None
    note_prefix = os.getenv("BINANCE_NOTE_PREFIX", "SHOP")
    note_to_payee = f"{note_prefix}{t.telegram_id}" if is_binance_pay else None

    return TopupStatusResponse(
        topup_id=str(t.id),
        status=t.status,
        out_order_id=t.out_order_id,
        amount=pay_amount_str,
        actual_amount=actual_amount_str,
        pay_amount=pay_amount_str,
        network=t.network,
        address=t.to_address,
        qr_base64=t.qr_code_base64,
        payment_url=t.payment_url,
        expire_time=_to_vn_str(t.expire_time),
        currency=t.currency,
        base_currency=t.base_currency,
        binance_id=binance_id,
        note_to_payee=note_to_payee,
    )


@router.post("/{topup_id}/cancel")
def cancel_topup(topup_id: str, telegram_id: int, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not u:
        raise HTTPException(404, detail="USER_NOT_FOUND")

    t = db.query(Topup).filter(Topup.id == topup_id, Topup.user_id == u.id).first()
    if not t:
        raise HTTPException(404, detail="TOPUP_NOT_FOUND")

    if t.status != "PENDING":
        # idempotent
        return {"ok": True, "status": t.status}

    t.status = "CANCELED"
    db.commit()
    return {"ok": True, "status": t.status}
