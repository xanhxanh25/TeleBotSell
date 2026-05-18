from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.security.bot_auth import require_bot_api_key
from app.models.user import User
from app.models.ticket import Ticket
from app.models.order import Order
from app.schemas.tickets import TicketCreateRequest, TicketCreateResponse, TicketListResponse, TicketDetailResponse

router = APIRouter(prefix="/tickets", tags=["tickets"], dependencies=[Depends(require_bot_api_key)])

def _get_or_create_user(db: Session, telegram_id: int, telegram_user: str | None = None) -> User:
    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    if u:
        # Cập nhật username nếu có và khác với giá trị hiện tại
        if telegram_user and telegram_user != u.telegram_user:
            u.telegram_user = telegram_user
        # Nếu user bị ban vẫn cho xem lịch sử nhưng không cho tạo ticket mới
        if getattr(u, "is_banned", False):
            raise HTTPException(403, detail="USER_BANNED")
        return u
    u = User(telegram_id=telegram_id, balance=0, telegram_user=telegram_user)
    db.add(u)
    db.flush()
    return u

@router.post("", response_model=TicketCreateResponse)
def create_ticket(req: TicketCreateRequest, db: Session = Depends(get_db)):
    u = _get_or_create_user(db, req.telegram_id, req.telegram_user)
    
    # Commit username update nếu có (nếu user đã tồn tại và username thay đổi)
    if req.telegram_user and u.telegram_user != req.telegram_user:
        db.commit()
    
    # Nếu có order_id, kiểm tra đơn hàng có thuộc về user này không
    order_id = None
    if req.order_id:
        order = db.query(Order).filter(Order.id == req.order_id, Order.user_id == u.id).first()
        if not order:
            raise HTTPException(404, detail="ORDER_NOT_FOUND_OR_NOT_OWNED")
        order_id = req.order_id
    
    t = Ticket(
        user_id=u.id,
        telegram_id=req.telegram_id,
        order_id=order_id,
        text=req.text or "",
        photo_file_id=req.photo_file_id,
        status="OPEN"
    )
    db.add(t)
    db.commit()
    return TicketCreateResponse(ticket_id=t.id)


@router.get("")
def list_tickets(telegram_id: int, db: Session = Depends(get_db)):
    """
    Lấy danh sách tickets của user.
    """
    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not u:
        return {"tickets": [], "total": 0}
    
    tickets = db.query(Ticket).filter(Ticket.user_id == u.id).order_by(Ticket.created_at.desc()).all()
    
    res = []
    for t in tickets:
        order_code = None
        if t.order_id:
            order = db.query(Order).filter(Order.id == t.order_id).first()
            if order:
                order_code = order.order_code
        
        res.append({
            "ticket_id": t.id,
            "order_id": t.order_id,
            "order_code": order_code,
            "status": t.status,
            "text": t.text[:50] + "..." if len(t.text) > 50 else t.text,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    
    return {"tickets": res, "total": len(res)}


@router.get("/{ticket_id}")
def get_ticket_detail(ticket_id: int, telegram_id: int, db: Session = Depends(get_db)):
    """
    Lấy chi tiết ticket.
    """
    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not u:
        raise HTTPException(404, detail="USER_NOT_FOUND")
    
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.user_id == u.id).first()
    if not t:
        raise HTTPException(404, detail="TICKET_NOT_FOUND")
    
    order_code = None
    if t.order_id:
        order = db.query(Order).filter(Order.id == t.order_id).first()
        if order:
            order_code = order.order_code
    
    return {
        "ticket_id": t.id,
        "order_id": t.order_id,
        "order_code": order_code,
        "status": t.status,
        "text": t.text,
        "photo_file_id": t.photo_file_id,
        "replacement_items": t.replacement_items,
        "created_at": t.created_at.isoformat() if t.created_at else None
    }
