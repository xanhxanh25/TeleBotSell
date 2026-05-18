from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.security.bot_auth import require_bot_api_key
from app.models.user import User
from app.schemas.users import MeResponse

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_bot_api_key)])

def _get_or_create_user(db: Session, telegram_id: int, telegram_user: str | None = None) -> User:
    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    if u:
        # Cập nhật username nếu có và (hiện tại là None/empty hoặc khác với giá trị hiện tại)
        if telegram_user and telegram_user.strip():
            telegram_user = telegram_user.strip()
            # Update nếu: chưa có username hoặc username khác
            old_username = u.telegram_user
            if not u.telegram_user or u.telegram_user != telegram_user:
                print(f"🔄 [DEBUG] Updating username for telegram_id={telegram_id}: '{old_username}' -> '{telegram_user}'")
                u.telegram_user = telegram_user
                db.commit()
                db.refresh(u)
                print(f"✅ [DEBUG] Username updated successfully. Current value: '{u.telegram_user}'")
            else:
                print(f"ℹ️ [DEBUG] Username unchanged for telegram_id={telegram_id}: '{telegram_user}'")
        else:
            print(f"⚠️ [DEBUG] No telegram_user provided for telegram_id={telegram_id} (current: '{u.telegram_user}')")
        return u
    # Tạo user mới
    telegram_user_clean = telegram_user.strip() if telegram_user else None
    print(f"🆕 [DEBUG] Creating new user: telegram_id={telegram_id}, telegram_user='{telegram_user_clean}'")
    u = User(telegram_id=telegram_id, balance=0, telegram_user=telegram_user_clean)
    db.add(u)
    db.commit()
    db.refresh(u)
    print(f"✅ [DEBUG] New user created. telegram_user='{u.telegram_user}'")
    return u

@router.get("/me", response_model=MeResponse)
def me(telegram_id: int, telegram_user: str | None = None, db: Session = Depends(get_db)):
    """
    Lấy thông tin user. Nếu có telegram_user thì cập nhật vào database.
    """
    u = _get_or_create_user(db, telegram_id, telegram_user)
    is_banned = getattr(u, "is_banned", False)
    return MeResponse(
        telegram_id=u.telegram_id,
        balance=float(u.balance),
        currency="USD",
        created_at=u.created_at.isoformat() if u.created_at else None,
        is_banned=is_banned,
    )
