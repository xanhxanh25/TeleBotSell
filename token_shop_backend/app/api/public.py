import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy import select, column, text, func
from app.database import get_db
from app.models.product import Product
from app.models.product_stock_item import ProductStockItem
import json

router = APIRouter(prefix="/public", tags=["public"])
log = logging.getLogger("backend.public")

# Cache để kiểm tra xem columns đã tồn tại chưa
_columns_exist_cache = None
_sort_order_exists_cache = None

def _check_columns_exist(db: Session) -> bool:
    """Kiểm tra xem các cột discount đã tồn tại trong database chưa"""
    global _columns_exist_cache
    if _columns_exist_cache is not None:
        return _columns_exist_cache
    
    try:
        # Query từ information_schema để check columns
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'products' 
              AND column_name IN ('qty_discount_min', 'qty_discount_percent')
        """)).fetchall()
        _columns_exist_cache = len(result) >= 2
        return _columns_exist_cache
    except Exception as e:
        # Nếu không query được, giả sử columns chưa tồn tại
        db.rollback()
        _columns_exist_cache = False
        return False

def _check_sort_order_exists(db: Session) -> bool:
    """Kiểm tra xem cột sort_order đã tồn tại trong database chưa"""
    global _sort_order_exists_cache
    if _sort_order_exists_cache is not None:
        return _sort_order_exists_cache
    
    try:
        # Query từ information_schema để check column
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'products' 
              AND column_name = 'sort_order'
        """)).fetchall()
        _sort_order_exists_cache = len(result) > 0
        return _sort_order_exists_cache
    except Exception as e:
        # Nếu không query được, giả sử column chưa tồn tại
        db.rollback()
        _sort_order_exists_cache = False
        return False

def _parse_description(description: str, lang: str = "en") -> str:
    """Parse description từ JSON hoặc trả về text thuần. Mặc định lang='en'"""
    if not description:
        return None
    
    # Thử parse JSON
    try:
        desc_dict = json.loads(description)
        if isinstance(desc_dict, dict):
            # Trả về description theo lang, fallback về 'en' nếu không có
            # Lưu ý: empty string "" là giá trị hợp lệ, chỉ None mới là không có
            if lang in desc_dict:
                return desc_dict[lang]  # Trả về kể cả nếu là ""
            # Fallback về 'en'
            if "en" in desc_dict:
                return desc_dict["en"]  # Trả về kể cả nếu là ""
            # Nếu không có cả lang và 'en', trả về None
            return None
    except (json.JSONDecodeError, TypeError):
        # Không phải JSON, trả về text thuần (backward compatibility)
        pass
    
    # Nếu không phải JSON, trả về text thuần
    return description


def _stock_item_counts_by_product_ids(db: Session, product_ids: list[int]) -> dict[int, int]:
    """
    Một query GROUP BY thay cho N lần COUNT — /public/products là điểm nóng khi nhiều SP.
    Index: product_stock_items.product_id (FK) được dùng cho filter + group.
    """
    if not product_ids:
        return {}
    rows = db.execute(
        select(ProductStockItem.product_id, func.count(ProductStockItem.id))
        .where(ProductStockItem.product_id.in_(product_ids))
        .group_by(ProductStockItem.product_id)
    ).all()
    return {int(r[0]): int(r[1]) for r in rows}


def _stock_display(count_from_items: int, product_row_stock: int) -> int:
    """Giữ đúng semantics cũ: có dòng stock_items thì dùng count; không thì fallback cột products.stock."""
    cnt = int(count_from_items or 0)
    return cnt if cnt > 0 else int(product_row_stock or 0)


def _attach_qty_discount_tiers(db: Session, items: list[dict]) -> None:
    """Gắn qty_discount_tiers[] vào mỗi item; nếu bảng chưa có (DB cũ) thì bỏ qua."""
    if not items:
        return
    ids = [int(it["id"]) for it in items]
    try:
        from app.services.product_qty_tiers import tiers_map_by_product_ids

        tm = tiers_map_by_product_ids(db, ids)
    except (ProgrammingError, OperationalError):
        db.rollback()
        tm = {}
    for it in items:
        it["qty_discount_tiers"] = tm.get(int(it["id"]), [])


@router.get("/products")
def list_products(lang: str = Query("en", description="Ngôn ngữ (vi, en, zh, ru). Mặc định: en"), db: Session = Depends(get_db)):
    try:
        columns_exist = _check_columns_exist(db)
        sort_order_exists = _check_sort_order_exists(db)
        
        if columns_exist and sort_order_exists:
            # Tất cả columns đã tồn tại - query bình thường với sort_order
            # Sắp xếp theo sort_order ASC (NULL cuối), sau đó theo id ASC
            # Dùng text() để đảm bảo tương thích với PostgreSQL
            q = db.query(Product).filter(Product.is_active == True).order_by(
                text("sort_order ASC NULLS LAST"),
                Product.id.asc()
            )
            products = q.all()
            cmap = _stock_item_counts_by_product_ids(db, [p.id for p in products])
            items = []
            for p in products:
                stock_val = _stock_display(cmap.get(p.id, 0), int(p.stock or 0))
                description = _parse_description(p.description, lang)
                items.append({
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "description": description,
                    "price": str(p.price),
                    "currency": p.currency,
                    "stock": stock_val,
                    "qty_discount_min": p.qty_discount_min,
                    "qty_discount_percent": str(p.qty_discount_percent) if p.qty_discount_percent else None,
                })
        elif columns_exist:
            # Discount columns có nhưng sort_order chưa có
            q = db.query(Product).filter(Product.is_active == True).order_by(Product.id.asc())
            products = q.all()
            cmap = _stock_item_counts_by_product_ids(db, [p.id for p in products])
            items = []
            for p in products:
                stock_val = _stock_display(cmap.get(p.id, 0), int(p.stock or 0))
                description = _parse_description(p.description, lang)
                items.append({
                    "id": p.id,
                    "code": p.code,
                    "name": p.name,
                    "description": description,
                    "price": str(p.price),
                    "currency": p.currency,
                    "stock": stock_val,
                    "qty_discount_min": p.qty_discount_min,
                    "qty_discount_percent": str(p.qty_discount_percent) if p.qty_discount_percent else None,
                })
        else:
            # Columns chưa tồn tại - query chỉ các columns cơ bản
            # Kiểm tra sort_order riêng
            if sort_order_exists:
                result = db.execute(text("""
                    SELECT id, code, name, description, price, currency, stock, is_active, sort_order
                    FROM products
                    WHERE is_active = true
                    ORDER BY sort_order ASC NULLS LAST, id ASC
                """))
            else:
                result = db.execute(text("""
                    SELECT id, code, name, description, price, currency, stock, is_active
                    FROM products
                    WHERE is_active = true
                    ORDER BY id ASC
                """))
            rows = result.fetchall()
            cmap = _stock_item_counts_by_product_ids(db, [r.id for r in rows])
            items = []
            for row in rows:
                stock_val = _stock_display(cmap.get(row.id, 0), int(row.stock or 0))
                description = _parse_description(row.description, lang)
                items.append({
                    "id": row.id,
                    "code": row.code,
                    "name": row.name,
                    "description": description,
                    "price": str(row.price),
                    "currency": row.currency,
                    "stock": stock_val,
                    "qty_discount_min": None,
                    "qty_discount_percent": None,
                })
        _attach_qty_discount_tiers(db, items)
        return items
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        log.exception("list_products failed")
        raise HTTPException(status_code=500, detail="INTERNAL_SERVER_ERROR")

@router.get("/products/{product_id}")
def product_detail(product_id: int, lang: str = Query("en", description="Ngôn ngữ (vi, en, zh, ru). Mặc định: en"), db: Session = Depends(get_db)):
    try:
        columns_exist = _check_columns_exist(db)
        
        if columns_exist:
            # Columns đã tồn tại - query bình thường
            p = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
            if not p:
                raise HTTPException(status_code=404, detail="PRODUCT_NOT_FOUND")
            cmap = _stock_item_counts_by_product_ids(db, [p.id])
            stock_val = _stock_display(cmap.get(p.id, 0), int(p.stock or 0))
            # Parse description theo ngôn ngữ
            description = _parse_description(p.description, lang)
            out = {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "description": description,
                "price": str(p.price),
                "currency": p.currency,
                "stock": stock_val,
                "qty_discount_min": p.qty_discount_min,
                "qty_discount_percent": str(p.qty_discount_percent) if p.qty_discount_percent else None,
            }
            _attach_qty_discount_tiers(db, [out])
            return out
        else:
            # Columns chưa tồn tại - query chỉ các columns cơ bản
            # Nhưng vẫn đếm stock từ bảng con để đảm bảo chính xác
            result = db.execute(text("""
                SELECT id, code, name, description, price, currency, stock
                FROM products
                WHERE id = :product_id AND is_active = true
            """), {"product_id": product_id}).first()
            
            if not result:
                raise HTTPException(status_code=404, detail="PRODUCT_NOT_FOUND")
            
            cmap = _stock_item_counts_by_product_ids(db, [result.id])
            stock_val = _stock_display(cmap.get(result.id, 0), int(result.stock or 0))
            # Parse description theo ngôn ngữ
            description = _parse_description(result.description, lang)
            out = {
                "id": result.id,
                "code": result.code,
                "name": result.name,
                "description": description,
                "price": str(result.price),
                "currency": result.currency,
                "stock": stock_val,
                "qty_discount_min": None,
                "qty_discount_percent": None,
            }
            _attach_qty_discount_tiers(db, [out])
            return out
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        log.exception("product_detail failed product_id=%s", product_id)
        raise HTTPException(status_code=500, detail="INTERNAL_SERVER_ERROR")
