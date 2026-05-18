"""
HMAC-SHA256 authentication cho Seller API.

Client gui 4 header:
  X-Seller-Key:       api_key (sk_live_...)
  X-Seller-Timestamp: unix timestamp (seconds) — chong replay +-300s
  X-Seller-Nonce:     random string — chong replay
  X-Seller-Signature: HMAC-SHA256(api_secret, method+path+timestamp+nonce+body)

Tra ve User object (tu user_id FK) de dung trong endpoint.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.seller import SellerApiKey
from app.models.user import User

log = logging.getLogger("seller_auth")

MAX_TIMESTAMP_DRIFT = 300


async def verify_seller_hmac(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    api_key = request.headers.get("x-seller-key")
    timestamp = request.headers.get("x-seller-timestamp")
    nonce = request.headers.get("x-seller-nonce")
    signature = request.headers.get("x-seller-signature")

    if not api_key or not timestamp or not nonce or not signature:
        raise HTTPException(401, detail="MISSING_AUTH_HEADERS")

    # timestamp check
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        raise HTTPException(401, detail="INVALID_TIMESTAMP")

    now = int(time.time())
    if abs(now - ts) > MAX_TIMESTAMP_DRIFT:
        raise HTTPException(401, detail="TIMESTAMP_EXPIRED")

    # lookup key
    key_row = (
        db.query(SellerApiKey)
        .filter(SellerApiKey.api_key == api_key, SellerApiKey.is_active == True)
        .first()
    )
    if not key_row:
        raise HTTPException(401, detail="INVALID_API_KEY")

    # read body
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8") if body_bytes else ""

    # build payload: method\npath\ntimestamp\nnonce\nbody
    method = request.method.upper()
    path = request.url.path
    nonce_str = nonce or ""
    payload = f"{method}\n{path}\n{timestamp}\n{nonce_str}\n{body_str}"

    # compute HMAC-SHA256
    expected = hmac.new(
        key_row.api_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        log.warning("HMAC mismatch key=%s path=%s", api_key, path)
        raise HTTPException(401, detail="INVALID_SIGNATURE")

    # return the User linked to this key
    user = db.query(User).filter(User.id == key_row.user_id).first()
    if not user:
        raise HTTPException(401, detail="USER_NOT_FOUND")

    return user
