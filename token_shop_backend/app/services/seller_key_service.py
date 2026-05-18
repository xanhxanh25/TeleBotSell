"""
Quan ly API key cho Seller (= User Telegram).

api_key  : sk_live_ + 24 hex chars
api_secret: 64 hex chars (dung de ky HMAC-SHA256)
"""
from __future__ import annotations

import secrets
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.seller import SellerApiKey
from app.models.user import User

log = logging.getLogger("seller_key_service")


def _generate_api_key() -> str:
    """sk_live_ + 24 hex chars."""
    return "sk_live_" + secrets.token_hex(12)


def _generate_api_secret() -> str:
    """64 hex chars."""
    return secrets.token_hex(32)


def generate_key_for_user(
    db: Session,
    user_id: int,
    note: str | None = None,
) -> dict:
    """
    Tao API key moi cho user.
    Tra ve dict chua api_key + api_secret (plaintext, chi hien thi 1 lan).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("USER_NOT_FOUND")

    api_key = _generate_api_key()
    api_secret = _generate_api_secret()

    row = SellerApiKey(
        user_id=user_id,
        api_key=api_key,
        api_secret=api_secret,
        is_active=True,
        note=note,
    )
    db.add(row)
    db.flush()

    log.info("generated key id=%s user_id=%s api_key=%s", row.id, user_id, api_key)

    return {
        "key_id": row.id,
        "user_id": user_id,
        "telegram_id": user.telegram_id,
        "api_key": api_key,
        "api_secret": api_secret,  # CHI TRA 1 LAN
    }


def revoke_key(db: Session, key_id: int) -> bool:
    """Set is_active=False, revoked_at=now. Return True neu thanh cong."""
    row = db.query(SellerApiKey).filter(SellerApiKey.id == key_id).first()
    if not row:
        raise ValueError("KEY_NOT_FOUND")
    row.is_active = False
    row.revoked_at = datetime.now(timezone.utc)
    db.flush()
    log.info("revoked key id=%s user_id=%s", key_id, row.user_id)
    return True


def rotate_key(db: Session, key_id: int, note: str | None = None) -> dict:
    """Revoke key cu + generate key moi cho cung user."""
    old = db.query(SellerApiKey).filter(SellerApiKey.id == key_id).first()
    if not old:
        raise ValueError("KEY_NOT_FOUND")

    # revoke old
    old.is_active = False
    old.revoked_at = datetime.now(timezone.utc)
    db.flush()

    # generate new
    return generate_key_for_user(db, old.user_id, note=note or old.note)


def list_keys(db: Session) -> list[dict]:
    """List tat ca active keys + user info."""
    rows = (
        db.query(SellerApiKey, User)
        .join(User, SellerApiKey.user_id == User.id)
        .filter(SellerApiKey.is_active == True)
        .order_by(SellerApiKey.created_at.desc())
        .all()
    )
    result = []
    for key, user in rows:
        result.append({
            "key_id": key.id,
            "user_id": user.id,
            "telegram_id": user.telegram_id,
            "telegram_user": user.telegram_user,
            "api_key": key.api_key,
            "note": key.note,
            "created_at": key.created_at.isoformat() if key.created_at else None,
        })
    return result


def get_key_by_user(db: Session, user_id: int) -> dict | None:
    """Get active key hien tai cua user."""
    row = (
        db.query(SellerApiKey)
        .filter(SellerApiKey.user_id == user_id, SellerApiKey.is_active == True)
        .order_by(SellerApiKey.created_at.desc())
        .first()
    )
    if not row:
        return None
    return {
        "key_id": row.id,
        "user_id": row.user_id,
        "api_key": row.api_key,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
