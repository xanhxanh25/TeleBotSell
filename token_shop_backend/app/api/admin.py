from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete
from app.models.coupon_redemption import CouponRedemption
from decimal import Decimal
from typing import Optional
from datetime import datetime
import re
from app.services.stock import sync_product_stock

from app.database import get_db
from app.security.admin_auth import require_admin
from app.models.product import Product
from app.models.coupon import Coupon
from app.models.user import User
from app.models.topup import Topup
from app.models.order import Order
from app.models.product_stock_item import ProductStockItem
from app.services.coupon_service import reverse_redemption_for_order, count_committed_global_ledger
from app.services.product_qty_tiers import validate_tiers_rows, replace_tiers_for_product
router = APIRouter(prefix="/admin", tags=["admin"])
def _parse_lines(lines) -> list[str]:
    """
    Nhận:
      - string nhiều dòng
      - list[str]
    Trả về: list mỗi phần tử = 1 item (strip, bỏ rỗng)
    """
    items: list[str] = []
    if lines is None:
        return items

    if isinstance(lines, str):
        for x in lines.splitlines():
            x = x.strip()
            if x:
                items.append(x)
        return items

    if isinstance(lines, list):
        for v in lines:
            if v is None:
                continue
            s = str(v)
            for x in s.splitlines():
                x = x.strip()
                if x:
                    items.append(x)
        return items

    # fallback
    s = str(lines)
    for x in s.splitlines():
        x = x.strip()
        if x:
            items.append(x)
    return items

@router.get("/users/{telegram_id}/balance", dependencies=[Depends(require_admin)])
def get_balance(telegram_id: int, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.telegram_id == telegram_id).first()
    return {"telegram_id": telegram_id, "balance": str(u.balance if u else 0), "currency": "USD"}

@router.post("/products", dependencies=[Depends(require_admin)])
def upsert_product(payload: dict, db: Session = Depends(get_db)):
    # payload fields: code,name,price,stock,is_active,description,delivery_payload
    code = payload.get("code")
    name = payload.get("name")
    if not code or not name:
        raise HTTPException(400, detail="MISSING_FIELDS")
    price = Decimal(str(payload.get("price") or "0"))
    if price <= 0:
        raise HTTPException(400, detail="INVALID_PRICE")
    stock = int(payload.get("stock") or 0)

    p = db.query(Product).filter(Product.code == code).first()
    if not p:
        p = Product(code=code)
        db.add(p)

    p.name = name
    p.description = payload.get("description")
    p.price = price
    p.currency = "USD"
    p.stock = stock
    p.is_active = bool(payload.get("is_active", True))
    p.delivery_payload = payload.get("delivery_payload")
    # Flush only after required fields are set, tránh NOT NULL violation khi tạo mới.
    db.flush()
    
    # Giảm giá theo số lượng (chỉ set nếu có trong payload và column tồn tại)
    qty_discount_min = payload.get("qty_discount_min")
    qty_discount_percent = payload.get("qty_discount_percent")
    if hasattr(p, 'qty_discount_min'):
        if qty_discount_min is not None:
            p.qty_discount_min = int(qty_discount_min) if qty_discount_min else None
    if hasattr(p, 'qty_discount_percent'):
        if qty_discount_percent is not None:
            p.qty_discount_percent = Decimal(str(qty_discount_percent)) if qty_discount_percent else None
    stock_items = _parse_lines(payload.get("stock_items"))
    if not stock_items:
        stock_items = _parse_lines(payload.get("stock_text"))

    if stock_items:
        id_sanpham = payload.get("id_sanpham")  # optional
        for line in stock_items:
            db.add(ProductStockItem(
                product_id=p.id,
                id_sanpham=id_sanpham,
                mota=line
            ))

        # sync lại products.stock = COUNT(items)
        new_stock = db.query(func.count(ProductStockItem.id)).filter(ProductStockItem.product_id == p.id).scalar() or 0
        p.stock = int(new_stock)

    if "qty_discount_tiers" in payload:
        raw = payload.get("qty_discount_tiers")
        rows: list[tuple[object, object]] = []
        if isinstance(raw, list):
            for t in raw:
                if isinstance(t, dict):
                    rows.append((t.get("min_qty"), t.get("percent")))
        try:
            tiers = validate_tiers_rows(rows)
        except ValueError as ve:
            raise HTTPException(400, detail=str(ve))
        replace_tiers_for_product(db, int(p.id), tiers)

    db.commit()
    return {"ok": True, "product_id": p.id}

@router.post("/coupons", dependencies=[Depends(require_admin)])
def upsert_coupon(payload: dict, db: Session = Depends(get_db)):
    code = (payload.get("code") or "").strip().upper()
    if not code:
        raise HTTPException(400, detail="MISSING_CODE")
    c = db.query(Coupon).filter(Coupon.code == code).first()
    if not c:
        c = Coupon(code=code)
        db.add(c)

    c.discount_type = (payload.get("discount_type") or "PERCENT").upper()
    c.discount_value = Decimal(str(payload.get("discount_value") or "0"))
    c.max_discount_amount = Decimal(str(payload["max_discount_amount"])) if payload.get("max_discount_amount") is not None else None
    c.min_order_amount = Decimal(str(payload["min_order_amount"])) if payload.get("min_order_amount") is not None else None
    
    # Loại 2: Cấp mã riêng cho 1 user (nếu có user_id)
    # Loại 3: Mã giảm giá cho mọi user trên 1 sản phẩm (nếu có product_id, không có user_id)
    product_id = payload.get("product_id")
    user_id = payload.get("user_id")
    c.product_id = int(product_id) if product_id and str(product_id).strip() else None
    c.user_id = int(user_id) if user_id and str(user_id).strip() else None

    # Usage limits (optional)
    max_uses_total = payload.get("max_uses_total")
    max_uses_per_user = payload.get("max_uses_per_user")
    max_qty_per_order = payload.get("max_qty_per_order")
    c.max_uses_total = int(max_uses_total) if max_uses_total is not None and str(max_uses_total).strip() != "" else None
    c.max_uses_per_user = int(max_uses_per_user) if max_uses_per_user is not None and str(max_uses_per_user).strip() != "" else None
    c.max_qty_per_order = int(max_qty_per_order) if max_qty_per_order is not None and str(max_qty_per_order).strip() != "" else None
    
    c.is_active = bool(payload.get("is_active", True))

    db.commit()
    return {"ok": True, "coupon_id": c.id}


@router.post("/coupons/{coupon_id}/add-uses", dependencies=[Depends(require_admin)])
def admin_coupon_add_uses(coupon_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Cộng thêm quota toàn cục (max_uses_total += add). User đã dùng không bị reset;
    chỉ mở thêm slot cho lượt checkout COMMITTED mới.
    """
    add = int(payload.get("add") or 0)
    if add < 1:
        raise HTTPException(400, detail="INVALID_ADD")
    c = db.execute(select(Coupon).where(Coupon.id == coupon_id).with_for_update()).scalar_one_or_none()
    if not c:
        raise HTTPException(404, detail="COUPON_NOT_FOUND")
    used = count_committed_global_ledger(db, coupon_id)
    if c.max_uses_total is None:
        c.max_uses_total = used + add
    else:
        c.max_uses_total = int(c.max_uses_total) + add
    db.commit()
    rem = int(c.max_uses_total) - used
    return {
        "ok": True,
        "max_uses_total": int(c.max_uses_total),
        "committed_uses": used,
        "remaining_uses": max(0, rem),
    }


@router.get("/coupons/{coupon_id}/redemptions", dependencies=[Depends(require_admin)])
def admin_coupon_redemptions(
    coupon_id: int,
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 50,
):
    """Danh sách ledger redemption (COMMITTED/REVERSED) kèm user — phân trang."""
    if not db.query(Coupon).filter(Coupon.id == coupon_id).first():
        raise HTTPException(404, detail="COUPON_NOT_FOUND")
    page = max(1, int(page))
    per_page = min(200, max(1, int(per_page)))
    total = db.execute(
        select(func.count()).select_from(CouponRedemption).where(CouponRedemption.coupon_id == coupon_id)
    ).scalar_one()
    rows = db.execute(
        select(CouponRedemption, User.telegram_id, User.telegram_user)
        .join(User, User.id == CouponRedemption.user_id)
        .where(CouponRedemption.coupon_id == coupon_id)
        .order_by(CouponRedemption.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()
    items = []
    for r, tid, tu in rows:
        items.append(
            {
                "id": int(r.id),
                "user_id": int(r.user_id),
                "order_id": r.order_id,
                "status": r.status,
                "telegram_id": int(tid) if tid is not None else None,
                "telegram_user": tu,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return {
        "total": int(total or 0),
        "page": page,
        "per_page": per_page,
        "items": items,
    }


# ===== Manual approve topup pending (admin) =====
@router.post("/topups/approve", dependencies=[Depends(require_admin)])
def approve_topup(payload: dict, db: Session = Depends(get_db)):
    """
    Manual approve topup (PENDING -> SUCCESS) and credit user's USD balance.
    Body:
      - topup_id (optional) OR out_order_id (optional, recommended)
      - amount (optional): if omitted, use topup.actual_amount
      - note (optional)
    """
    topup_id = payload.get("topup_id")
    out_order_id = payload.get("out_order_id")
    if not topup_id and not out_order_id:
        raise HTTPException(400, detail="MISSING_TOPUP_IDENTIFIER")

    # lock topup + user for safe credit
    with db.begin():
        q = select(Topup).with_for_update()
        if topup_id:
            t = db.execute(q.where(Topup.id == str(topup_id))).scalar_one_or_none()
        else:
            t = db.execute(q.where(Topup.out_order_id == str(out_order_id))).scalar_one_or_none()

        if not t:
            raise HTTPException(404, detail="TOPUP_NOT_FOUND")

        if t.status == "SUCCESS":
            return {"ok": True, "message": "already_success", "out_order_id": t.out_order_id}

        if t.status != "PENDING":
            raise HTTPException(400, detail=f"TOPUP_NOT_PENDING:{t.status}")

        amt = payload.get("amount")
        credit_amount = Decimal(str(amt)) if amt is not None else Decimal(str(t.actual_amount))

        # update topup
        t.status = "SUCCESS"
        t.raw_notify = {
            "manual": True,
            "note": payload.get("note"),
            "credited_amount": str(credit_amount),
        }

        # credit user
        u = db.execute(select(User).where(User.id == t.user_id).with_for_update()).scalar_one()
        u.balance = Decimal(str(u.balance)) + credit_amount

    return {"ok": True, "out_order_id": t.out_order_id, "credited_amount": str(credit_amount)}
from sqlalchemy import func, delete
from app.models.product_stock_item import ProductStockItem

@router.post("/products/{product_id}/stock-items/import", dependencies=[Depends(require_admin)])
def import_stock_items(product_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Body:
      - text: "line1\nline2\nline3"
        hoặc
      - items: ["line1","line2",...]
      - mode: "append" | "replace" (default append)
    Mỗi dòng = 1 item (mota). Mặc định là 1 hàng 1 mota, không hỗ trợ format id|mota.
    """
    mode = (payload.get("mode") or "append").lower()

    raw_items = payload.get("items")
    text = payload.get("text")
    lines_param = payload.get("lines")  # Hỗ trợ cả "lines" key

    lines = []
    if isinstance(raw_items, list):
        lines = [str(x) for x in raw_items]
    elif isinstance(text, str):
        lines = text.splitlines()
    elif isinstance(lines_param, str):
        lines = lines_param.splitlines()
    else:
        raise HTTPException(400, detail="MISSING_ITEMS")

    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, detail="PRODUCT_NOT_FOUND")

    if mode == "replace":
        db.execute(delete(ProductStockItem).where(ProductStockItem.product_id == product_id))

    added = 0
    skipped = 0
    duplicate_lines = []  # Danh sách các dòng trùng
    import secrets, string
    alphabet = string.ascii_uppercase + string.digits
    
    # Lấy danh sách mota đã tồn tại để check trùng
    existing_motas = set(
        db.execute(
            select(ProductStockItem.mota)
            .where(ProductStockItem.product_id == product_id)
            .distinct()
        ).scalars().all()
    )
    
    # Set để check trùng trong cùng batch import
    batch_motas = set()
    
    for line in lines:
        line = (line or "").strip()
        if not line:
            continue

        # Check trùng mota trong cùng product_id hoặc trong cùng batch
        if line in existing_motas or line in batch_motas:
            skipped += 1
            duplicate_lines.append(line)
            continue

        # Mỗi hàng là 1 mota, không hỗ trợ format id|mota
        random_id = "".join(secrets.choice(alphabet) for _ in range(10))
        db.add(ProductStockItem(product_id=product_id, id_sanpham=random_id, mota=line))
        existing_motas.add(line)  # Thêm vào set để tránh trùng trong cùng batch
        batch_motas.add(line)  # Thêm vào batch set
        added += 1

    db.flush()

    # cập nhật stock = count bảng con
    cnt = db.execute(
        select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == product_id)
    ).scalar_one()
    p.stock = int(cnt or 0)

    db.commit()
    return {
        "ok": True, 
        "product_id": product_id, 
        "added": added, 
        "skipped": skipped, 
        "duplicates": duplicate_lines[:100],  # Giới hạn 100 dòng đầu
        "stock": p.stock
    }


# ===== Admin approve ticket và gửi item từ kho =====
@router.post("/tickets/{ticket_id}/approve", dependencies=[Depends(require_admin)])
def approve_ticket(ticket_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Admin duyệt ticket và gửi item từ kho cho khách.
    Body:
      - qty: số lượng item cần lấy từ kho (bắt buộc)
      - note: ghi chú (optional)
    """
    from app.models.ticket import Ticket
    from app.models.product_stock_item import ProductStockItem
    qty = int(payload.get("qty") or 0)
    if qty <= 0:
        raise HTTPException(400, detail="INVALID_QTY")

    # Lock ticket/order/product rows in one transaction to avoid double-approval races.
    with db.begin():
        t = db.execute(
            select(Ticket).where(Ticket.id == ticket_id).with_for_update()
        ).scalar_one_or_none()
        if not t:
            raise HTTPException(404, detail="TICKET_NOT_FOUND")
        if t.status != "OPEN":
            raise HTTPException(400, detail=f"TICKET_NOT_OPEN:{t.status}")
        if not t.order_id:
            raise HTTPException(400, detail="TICKET_HAS_NO_ORDER")

        order = db.execute(
            select(Order).where(Order.id == t.order_id).with_for_update()
        ).scalar_one_or_none()
        if not order:
            raise HTTPException(404, detail="ORDER_NOT_FOUND")

        product = db.execute(
            select(Product).where(Product.id == order.product_id).with_for_update()
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(404, detail="PRODUCT_NOT_FOUND")

        # Kiểm tra số lượng item có sẵn
        item_count = db.execute(
            select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == product.id)
        ).scalar_one()
        item_count = int(item_count or 0)
        
        if item_count < qty:
            raise HTTPException(400, detail=f"INSUFFICIENT_STOCK: available={item_count}, requested={qty}")
        
        # Lock và lấy item
        items = db.execute(
            select(ProductStockItem)
            .where(ProductStockItem.product_id == product.id)
            .order_by(ProductStockItem.id.asc())
            .with_for_update(skip_locked=True)
            .limit(qty)
        ).scalars().all()
        
        if len(items) < qty:
            raise HTTPException(400, detail="OUT_OF_STOCK")
        
        # Lấy danh sách item để gửi cho khách
        delivery_lines = []
        for it in items:
            v = (it.mota or "").strip()
            if not v:
                v = (it.id_sanpham or "").strip()
            delivery_lines.append(v)
        
        # Xóa item đã lấy khỏi kho
        ids = [it.id for it in items]
        db.execute(delete(ProductStockItem).where(ProductStockItem.id.in_(ids)))
        
        # Cập nhật stock cache
        remaining = db.execute(
            select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == product.id)
        ).scalar_one()
        product.stock = int(remaining or 0)
        
        # Cập nhật ticket
        t.status = "APPROVED"
        t.replacement_items = "\n".join(delivery_lines)
    
    return {
        "ok": True,
        "ticket_id": ticket_id,
        "qty": qty,
        "replacement_items": t.replacement_items,
        "message": "Ticket approved and items sent to customer"
    }


@router.get("/products/{product_id}/stock-items", dependencies=[Depends(require_admin)])
def list_stock_items(product_id: int, db: Session = Depends(get_db)):
    """
    Lấy danh sách stock items của một product.
    """
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, detail="PRODUCT_NOT_FOUND")
    
    items = db.query(ProductStockItem).filter(
        ProductStockItem.product_id == product_id
    ).order_by(ProductStockItem.id.asc()).all()
    
    res = []
    for it in items:
        res.append({
            "id": it.id,
            "product_id": it.product_id,
            "id_sanpham": it.id_sanpham,
            "mota": it.mota,
            "created_at": it.created_at.isoformat() if it.created_at else None
        })
    
    return {"items": res, "total": len(res), "product_id": product_id, "product_name": p.name}


@router.delete("/products/{product_id}/stock-items/by-id/{item_id}", dependencies=[Depends(require_admin)])
def delete_stock_item(product_id: int, item_id: int, db: Session = Depends(get_db)):
    """
    Xóa một stock item.
    """
    item = db.query(ProductStockItem).filter(
        ProductStockItem.id == item_id,
        ProductStockItem.product_id == product_id
    ).first()
    
    if not item:
        raise HTTPException(404, detail="ITEM_NOT_FOUND")
    
    db.delete(item)
    db.flush()
    
    # Cập nhật stock cache
    p = db.query(Product).filter(Product.id == product_id).first()
    if p:
        cnt = db.execute(
            select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == product_id)
        ).scalar_one()
        p.stock = int(cnt or 0)
    
    db.commit()
    return {"ok": True, "deleted_id": item_id, "stock": p.stock if p else 0}


@router.delete("/products/{product_id}/stock-items/bulk", dependencies=[Depends(require_admin)])
def delete_stock_items_bulk(product_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Xóa nhiều stock items cùng lúc.
    Body: {"item_ids": [1, 2, 3, ...]}
    """
    item_ids = payload.get("item_ids", [])
    if not item_ids or not isinstance(item_ids, list):
        raise HTTPException(400, detail="MISSING_ITEM_IDS")
    
    # Xóa items
    deleted = db.execute(
        delete(ProductStockItem).where(
            ProductStockItem.id.in_(item_ids),
            ProductStockItem.product_id == product_id
        )
    ).rowcount
    
    db.flush()
    
    # Cập nhật stock cache
    p = db.query(Product).filter(Product.id == product_id).first()
    if p:
        cnt = db.execute(
            select(func.count(ProductStockItem.id)).where(ProductStockItem.product_id == product_id)
        ).scalar_one()
        p.stock = int(cnt or 0)
    
    db.commit()
    return {"ok": True, "deleted_count": deleted, "stock": p.stock if p else 0}


@router.get("/products/{product_id}/stock-items/download", dependencies=[Depends(require_admin)])
def download_stock_items(product_id: int, db: Session = Depends(get_db)):
    """
    Tải về file stock items với format {idproduct}_{ten product}_{ngày}_txt
    """
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, detail="PRODUCT_NOT_FOUND")
    
    items = db.query(ProductStockItem).filter(
        ProductStockItem.product_id == product_id
    ).order_by(ProductStockItem.id.asc()).all()
    
    # Tạo nội dung file: mỗi hàng là 1 mota
    lines = []
    for item in items:
        mota = (item.mota or "").strip()
        if mota:
            lines.append(mota)
    
    content = "\n".join(lines)
    
    # Tạo tên file: {idproduct}_{ten product}_{ngày}_txt
    date_str = datetime.now().strftime("%Y%m%d")
    # Làm sạch tên sản phẩm để dùng trong tên file
    safe_name = re.sub(r'[^\w\s-]', '', p.name)
    safe_name = re.sub(r'[-\s]+', '_', safe_name)
    filename = f"{product_id}_{safe_name}_{date_str}.txt"
    
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.delete("/products/{product_id}/stock-items/all", dependencies=[Depends(require_admin)])
def delete_all_stock_items(product_id: int, db: Session = Depends(get_db)):
    """
    Xóa hết tất cả stock items của một product
    """
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, detail="PRODUCT_NOT_FOUND")
    
    # Xóa tất cả items
    deleted_count = db.execute(
        delete(ProductStockItem).where(ProductStockItem.product_id == product_id)
    ).rowcount
    
    # Cập nhật stock về 0
    p.stock = 0
    db.commit()
    
    return {"ok": True, "deleted_count": deleted_count, "product_id": product_id, "stock": 0}


@router.post("/products/{product_id}/sync-stock", dependencies=[Depends(require_admin)])
def sync_stock(product_id: int, db: Session = Depends(get_db)):
    """
    Đồng bộ lại stock cho một product từ bảng product_stock_items.
    """
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        raise HTTPException(404, detail="PRODUCT_NOT_FOUND")
    new_stock = sync_product_stock(db, product_id)
    db.commit()
    return {"ok": True, "product_id": product_id, "stock": new_stock}


@router.post("/products/sync-stock-all", dependencies=[Depends(require_admin)])
def sync_stock_all(db: Session = Depends(get_db)):
    """
    Đồng bộ lại stock cho tất cả products.
    """
    products = db.query(Product).all()
    total = 0
    for p in products:
        sync_product_stock(db, p.id)
        total += 1
    db.commit()
    return {"ok": True, "synced": total}


@router.post("/orders/{order_id}/reverse_coupon_usage", dependencies=[Depends(require_admin)])
def admin_reverse_coupon_usage(order_id: str, db: Session = Depends(get_db)):
    """
    BUSINESS: Hoàn quota coupon khi order đã PAID nhưng cần cancel/refund thủ công.
    Đặt redemption sang REVERSED; COUNT COMMITTED giảm; committed_usage_count đồng bộ nếu có max_uses_total.
    """
    ok = reverse_redemption_for_order(db, order_id)
    if not ok:
        raise HTTPException(404, detail="NO_COMMITTED_COUPON_REDEMPTION")
    db.commit()
    return {"ok": True, "order_id": order_id}


@router.get("/tickets", dependencies=[Depends(require_admin)])
def list_all_tickets(status: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Admin xem danh sách tất cả tickets.
    """
    from app.models.ticket import Ticket
    
    query = db.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    
    tickets = query.order_by(Ticket.created_at.desc()).limit(100).all()
    
    res = []
    for t in tickets:
        order_code = None
        if t.order_id:
            order = db.query(Order).filter(Order.id == t.order_id).first()
            if order:
                order_code = order.order_code
        
        res.append({
            "ticket_id": t.id,
            "telegram_id": t.telegram_id,
            "order_id": t.order_id,
            "order_code": order_code,
            "status": t.status,
            "text": t.text[:100] + "..." if len(t.text) > 100 else t.text,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    
    return {"tickets": res, "total": len(res)}
