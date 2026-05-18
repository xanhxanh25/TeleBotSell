from fastapi import Header, HTTPException
from app.config import settings


def require_bot_api_key(x_bot_api_key: str | None = Header(default=None)):
    # Reject requests from clients that are not trusted bot services.
    if not x_bot_api_key or x_bot_api_key != settings.BOT_API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")
    return True
