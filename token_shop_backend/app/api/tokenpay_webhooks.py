from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from decimal import Decimal
from datetime import datetime, timezone

from app.database import get_db
from app.models.topup import Topup
from app.models.user import User
from app.config import settings
from app.services.tokenpay_signature import verify_signature

router = APIRouter(prefix="/pay/tokenpay", tags=["tokenpay"])

@router.post("/notify_url")
async def notify_url(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()

    # 1) verify signature
    if not verify_signature(payload, settings.TOKENPAY_API_TOKEN):
        raise HTTPException(400, detail="INVALID_SIGNATURE")

    out_order_id = payload.get("OutOrderId")
    if not out_order_id:
        raise HTTPException(400, detail="MISSING_OUTORDERID")

    status = int(payload.get("Status") or 0)  # 1=success theo sample
    amount = Decimal(str(payload.get("ActualAmount") or payload.get("Amount") or "0"))

    # 2) idempotent update + credit
    with db.begin():
        t = db.execute(
            select(Topup).where(Topup.out_order_id == out_order_id).with_for_update()
        ).scalar_one_or_none()

        if not t:
            # Nếu backend chưa tạo topup record nhưng TokenPay bắn notify: vẫn có thể tạo record "orphan"
            # Tuy nhiên để an toàn, ta từ chối để tránh credit nhầm.
            raise HTTPException(404, detail="TOPUP_NOT_FOUND")

        if t.status == "SUCCESS":
            return {"ok": True, "message": "already_processed"}

        # cập nhật fields
        t.raw_notify = payload
        t.tokenpay_id = payload.get("Id") or t.tokenpay_id
        t.txid = payload.get("BlockTransactionId")
        t.from_address = payload.get("FromAddress")
        if payload.get("PayTime"):
            try:
                # TokenPay gửi PayTime dạng local time (VN = UTC+7)
                from datetime import timedelta
                _VN = timezone(timedelta(hours=7))
                naive = datetime.strptime(payload["PayTime"], "%Y-%m-%d %H:%M:%S")
                t.pay_time = naive.replace(tzinfo=_VN).astimezone(timezone.utc)
            except Exception:
                pass

        if status == 1:
            t.status = "SUCCESS"
            # credit user (lock user)
            u = db.execute(select(User).where(User.id == t.user_id).with_for_update()).scalar_one()
            u.balance = Decimal(str(u.balance)) + amount
        else:
            t.status = "FAILED"

    return {"ok": True}

@router.get("/return_url")
def return_url(order_id: str):
    # chỉ là trang redirect - bạn có thể thay bằng HTML trong webadmin sau
    return {"ok": True, "order_id": order_id}
