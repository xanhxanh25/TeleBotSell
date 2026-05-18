from fastapi import Header, HTTPException
from app.config import settings

def require_admin(x_admin_key: str | None = Header(default=None)):
    if not x_admin_key or x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")
    return True
