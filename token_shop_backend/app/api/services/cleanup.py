from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# Import model
from app.models.topup import Topup


def cleanup_old_records(db) -> Dict[str, Any]:
    """
    Bạn đang có hàm này rồi.
    Giữ nguyên logic hiện tại của bạn.
    Đây là placeholder để file FULL không lỗi.
    """
    # TODO: thay bằng code cleanup hiện tại của bạn
    return {"ok": True, "deleted": 0}


def expire_pending_topups(db, minutes: int = 30) -> Dict[str, Any]:
    """
    Pending topup quá `minutes` phút => chuyển status sang CANCELED.
    Thống nhất: TẤT CẢ giao dịch (on-chain + Binance Pay) đều dùng created_at + minutes.
    Không phụ thuộc expire_time từ TokenPay (có thể lệch timezone).
    """
    now = datetime.now(timezone.utc)
    canceled = 0

    pending_list = db.query(Topup).filter(Topup.status == "PENDING").all()

    for t in pending_list:
        created_at = getattr(t, "created_at", None)
        if created_at is None:
            continue

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if created_at + timedelta(minutes=minutes) <= now:
            t.status = "CANCELED"
            canceled += 1

    return {
        "ok": True,
        "canceled": canceled,
        "checked": len(pending_list),
        "cutoff_minutes": minutes,
    }
