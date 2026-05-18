from __future__ import annotations

import os
import asyncio
import time
import json
import io
import base64
import logging
from typing import Annotated, Optional
from collections import defaultdict

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from sqlalchemy import or_, cast, String
from starlette.requests import Request as StarletteRequest
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, inspect, text, delete, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, ProgrammingError
import hashlib
import secrets
from urllib.parse import quote_plus
import bcrypt
import pyotp
import qrcode

# Đảm bảo có thể import được token_shop_backend khi chạy từ thư mục AdminWeb
import sys
base_dir_fs = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(base_dir_fs)

# Thêm project_root vào sys.path để import token_shop_backend
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Thêm token_shop_backend vào sys.path để các module bên trong có thể import app.*
backend_path = os.path.join(project_root, "token_shop_backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Load .env từ backend TRƯỚC khi import database (để config có DATABASE_URL)
backend_env_path = os.path.join(project_root, "token_shop_backend", ".env")
if os.path.exists(backend_env_path):
    from dotenv import load_dotenv
    # Prioritize container runtime environment; file env is local fallback.
    load_dotenv(backend_env_path, override=False)

# Log chẩn đoán khi chạy dưới nohup/supervisor (service.log) — biết kẹt ở bước import nào
def _boot_log(msg: str) -> None:
    print(f"[adminweb] {msg}", flush=True)


_boot_log(f"project_root={project_root!r}")
_boot_log("import database + models...")

from app.database import SessionLocal
from app.models.product import Product
from app.models.product_qty_discount_tier import ProductQtyDiscountTier
from app.models.product_stock_item import ProductStockItem
from app.models.user import User
from app.models.coupon import Coupon
from app.models.coupon_redemption import CouponRedemption
from app.models.order import Order
from app.models.topup import Topup
from app.models.ticket import Ticket
from app.services.product_qty_tiers import validate_tiers_rows, replace_tiers_for_product
from app.services.coupon_service import count_committed_global_ledger
from app.models.seller import SellerApiKey
from app.services.seller_key_service import (
    generate_key_for_user,
    revoke_key,
    rotate_key,
    list_keys,
)

_boot_log("imports OK")


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = FastAPI(title="Admin Web")
_boot_log("FastAPI app created")


@app.get("/health", include_in_schema=False)
def health():
    return {"ok": True}

# Thư mục static dùng cho mount + favicon (đăng ký TRƯỚC mount để /favicon.ico luôn khớp route)
base_dir = base_dir_fs
static_dir = os.path.join(base_dir, "static")
os.makedirs(static_dir, exist_ok=True)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """File thật trong static/ → log 200; không có file thì 204 (không 404)."""
    png = os.path.join(static_dir, "favicon.png")
    if os.path.isfile(png):
        return FileResponse(png, media_type="image/png")
    return Response(status_code=204)


# ── Security logger ──────────────────────────────────────────────────────
_security_log = logging.getLogger("adminweb.security")
_security_log.setLevel(logging.INFO)
_sec_handler = logging.StreamHandler()
_sec_handler.setFormatter(logging.Formatter("[%(asctime)s] SECURITY %(message)s"))
_security_log.addHandler(_sec_handler)

# ── Rate limiting (brute-force protection) ───────────────────────────────
_MAX_FAILED = 5          # max failed attempts
_WINDOW_SEC = 600        # 10 phút window
_BLOCK_SEC = 900         # block 15 phút

# {ip: [(timestamp, username), ...]}
_failed_attempts: dict[str, list[tuple[float, str]]] = defaultdict(list)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _cleanup_old_attempts(ip: str) -> None:
    now = time.time()
    _failed_attempts[ip] = [
        (ts, u) for ts, u in _failed_attempts[ip] if now - ts < _WINDOW_SEC
    ]
    if not _failed_attempts[ip]:
        _failed_attempts.pop(ip, None)


def _is_blocked(ip: str) -> tuple[bool, int]:
    """Return (blocked, remaining_seconds)."""
    _cleanup_old_attempts(ip)
    attempts = _failed_attempts.get(ip, [])
    if len(attempts) >= _MAX_FAILED:
        last_ts = attempts[-1][0]
        elapsed = time.time() - last_ts
        if elapsed < _BLOCK_SEC:
            return True, int((_BLOCK_SEC - elapsed) / 60) + 1
    return False, 0


def _record_failed(ip: str, username: str) -> None:
    _failed_attempts[ip].append((time.time(), username))
    _security_log.warning("FAILED LOGIN ip=%s username=%s", ip, username)


def _clear_attempts(ip: str) -> None:
    _failed_attempts.pop(ip, None)


# ── Admin credentials from env ───────────────────────────────────────────
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
# bcrypt hash — generate via scripts/setup_admin.py
# Fallback: bcrypt hash of "cuocdoima@8386"
_DEFAULT_BCRYPT_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
if not _DEFAULT_BCRYPT_HASH:
    # Auto-generate from old default for backwards compat on first run
    _DEFAULT_BCRYPT_HASH = bcrypt.hashpw(b"cuocdoima@8386", bcrypt.gensalt()).decode()

ADMIN_PASSWORD_BCRYPT = _DEFAULT_BCRYPT_HASH

# TOTP secret for 2FA (empty = 2FA disabled)
ADMIN_TOTP_SECRET = os.getenv("ADMIN_TOTP_SECRET", "")

# Session timeout (2 hours)
SESSION_MAX_AGE = int(os.getenv("ADMIN_SESSION_MAX_AGE", "7200"))


# ── Security headers middleware ──────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


# Middleware để check authentication (mỗi browser / máy một session riêng)
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Cho phép các routes công khai (không cần đăng nhập)
        public_prefixes = ["/login", "/static", "/favicon.ico", "/health", "/setup-2fa"]
        if any(path.startswith(p) for p in public_prefixes):
            return await call_next(request)

        # Check session timeout
        session = request.scope.get("session")
        if isinstance(session, dict) and session.get("admin_authenticated"):
            last_active = session.get("last_active", 0)
            if time.time() - last_active > SESSION_MAX_AGE:
                session.clear()
                return RedirectResponse(url="/login", status_code=303)
            # Update last active time
            session["last_active"] = time.time()

        # Các route còn lại: yêu cầu đã đăng nhập
        if not _check_auth(request):
            return RedirectResponse(url="/login", status_code=303)

        return await call_next(request)


# Thêm middleware theo đúng thứ tự: Security headers → Auth → Session
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuthMiddleware)

# Session middleware — HttpOnly + SameSite=Strict
SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", secrets.token_urlsafe(32))
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="admin_session",
    same_site="strict",
    https_only=os.getenv("ADMIN_HTTPS_ONLY", "false").lower() == "true",
    max_age=SESSION_MAX_AGE,
)

templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))
# Jinja2 không luôn có sẵn filter urlencode cho chuỗi — cần cho /users phân trang
templates.env.filters["urlencode"] = lambda s: quote_plus(str(s or ""))

# ── Filter hiển thị giờ Việt Nam (UTC+7) ─────────────────────────────────
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
_VN_TZ_OFFSET = _td(hours=7)
_VN_TZ = _tz(_VN_TZ_OFFSET, name="ICT")

def _to_vn(value, fmt: str = "%Y-%m-%d %H:%M:%S"):
    """Convert datetime sang giờ Việt Nam (UTC+7)."""
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    try:
        if value.tzinfo is None:
            value = value.replace(tzinfo=_tz.utc)
        vn_dt = value.astimezone(_VN_TZ)
        return vn_dt.strftime(fmt)
    except Exception:
        return str(value)

templates.env.filters["vn"] = _to_vn

app.mount("/static", StaticFiles(directory=static_dir), name="static")


DbDep = Annotated[Session, Depends(get_db)]


def _verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def _check_auth(request: Request) -> bool:
    """Kiểm tra user đã đăng nhập chưa (an toàn kể cả khi chưa có SessionMiddleware)"""
    session = request.scope.get("session")
    if not isinstance(session, dict):
        return False
    return session.get("admin_authenticated", False) is True


def require_auth(request: Request):
    """Dependency để check authentication"""
    if not _check_auth(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Trang đăng nhập"""
    ip = _get_client_ip(request)
    blocked, minutes_left = _is_blocked(ip)
    ctx: dict = {"request": request, "totp_enabled": bool(ADMIN_TOTP_SECRET)}
    if blocked:
        ctx["error"] = f"Quá nhiều lần đăng nhập sai. Vui lòng đợi {minutes_left} phút."
        ctx["locked"] = True
    return templates.TemplateResponse("login.html", ctx)


@app.post("/login")
def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    totp_code: str = Form(""),
):
    """Xử lý đăng nhập với username + password + TOTP"""
    ip = _get_client_ip(request)
    ctx: dict = {"request": request, "totp_enabled": bool(ADMIN_TOTP_SECRET)}

    # Check rate limit
    blocked, minutes_left = _is_blocked(ip)
    if blocked:
        ctx["error"] = f"Quá nhiều lần đăng nhập sai. Vui lòng đợi {minutes_left} phút."
        ctx["locked"] = True
        return templates.TemplateResponse("login.html", ctx, status_code=429)

    # Verify username + password
    username_ok = secrets.compare_digest(username.strip(), ADMIN_USERNAME)
    password_ok = _verify_password(password, ADMIN_PASSWORD_BCRYPT)

    if not (username_ok and password_ok):
        _record_failed(ip, username.strip())
        # Check if now blocked after recording
        blocked, minutes_left = _is_blocked(ip)
        if blocked:
            ctx["error"] = f"Quá nhiều lần đăng nhập sai. Vui lòng đợi {minutes_left} phút."
            ctx["locked"] = True
        else:
            remaining = _MAX_FAILED - len(_failed_attempts.get(ip, []))
            ctx["error"] = f"Sai tên đăng nhập hoặc mật khẩu! Còn {remaining} lần thử."
        return templates.TemplateResponse("login.html", ctx, status_code=401)

    # Verify TOTP (if enabled)
    if ADMIN_TOTP_SECRET:
        totp = pyotp.TOTP(ADMIN_TOTP_SECRET)
        if not totp.verify(totp_code.strip(), valid_window=1):
            _record_failed(ip, username.strip())
            ctx["error"] = "Mã xác thực 2FA không đúng hoặc đã hết hạn!"
            return templates.TemplateResponse("login.html", ctx, status_code=401)

    # Login success — regenerate session
    request.session.clear()
    request.session["admin_authenticated"] = True
    request.session["admin_user"] = username.strip()
    request.session["last_active"] = time.time()
    request.session["login_time"] = time.time()

    _clear_attempts(ip)
    _security_log.info("LOGIN SUCCESS ip=%s username=%s", ip, username.strip())

    return RedirectResponse(url="/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    """Đăng xuất"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# ── 2FA Setup route ──────────────────────────────────────────────────────
@app.get("/setup-2fa", response_class=HTMLResponse)
def setup_2fa_page(request: Request):
    """Hiện QR code để admin quét bằng Google Authenticator.
    Chỉ hoạt động khi ADMIN_TOTP_SECRET đã được set trong env."""
    if not ADMIN_TOTP_SECRET:
        return HTMLResponse(
            "<h3>TOTP chưa được cấu hình.</h3>"
            "<p>Chạy <code>python scripts/setup_admin.py</code> để tạo TOTP secret, "
            "sau đó set <code>ADMIN_TOTP_SECRET</code> trong .env và restart.</p>",
            status_code=400,
        )

    totp = pyotp.TOTP(ADMIN_TOTP_SECRET)
    uri = totp.provisioning_uri(name=ADMIN_USERNAME, issuer_name="AdminWeb")

    # Generate QR code as base64 image
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    html = f"""<!DOCTYPE html>
<html><head><title>Setup 2FA</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head><body class="bg-dark text-light">
<div class="container mt-5">
<div class="row justify-content-center"><div class="col-md-6 text-center">
<h2>Setup Google Authenticator</h2>
<p>Quét mã QR bằng Google Authenticator hoặc app tương tự:</p>
<img src="data:image/png;base64,{qr_b64}" class="img-fluid border rounded" style="max-width:300px;">
<p class="mt-3"><small class="text-muted">Hoặc nhập thủ công: <code>{ADMIN_TOTP_SECRET}</code></small></p>
<p class="mt-2"><a href="/login" class="btn btn-primary">Quay lại đăng nhập</a></p>
</div></div></div></body></html>"""
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: DbDep):
    """Dashboard"""
    products_cnt = db.query(Product).count()
    users_cnt = db.query(User).count()
    orders_cnt = db.query(Order).count()
    topups_cnt = db.query(Topup).count()
    open_tickets = db.query(Ticket).filter(Ticket.status == "OPEN").count()
    # Tổng doanh thu (chỉ tính PAID)
    total_revenue = (
        db.query(func.coalesce(func.sum(Order.total), 0))
        .filter(Order.status == "PAID")
        .scalar()
    )
    # Doanh thu hôm nay
    from datetime import date

    today = date.today()
    today_revenue = (
        db.query(func.coalesce(func.sum(Order.total), 0))
        .filter(
            Order.status == "PAID",
            func.date(Order.created_at) == today,
        )
        .scalar()
    )
    # Thống kê ticket
    error_open = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.status.in_(["OPEN", "APPROVED"]))
        .scalar()
    )
    error_done = (
        db.query(func.count(Ticket.id))
        .filter(Ticket.status.in_(["REJECTED", "COMPLETED"]))
        .scalar()
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "products_cnt": products_cnt,
            "users_cnt": users_cnt,
            "orders_cnt": orders_cnt,
            "topups_cnt": topups_cnt,
            "open_tickets": open_tickets,
            "total_revenue": total_revenue,
            "today_revenue": today_revenue,
            "error_open": error_open,
            "error_done": error_done,
        },
    )


# ==== STATS ====


@app.get("/stats", response_class=HTMLResponse)
def stats_page(request: Request, db: DbDep):
    """Top 10 người nạp nhiều nhất & Top 10 sản phẩm bán chạy nhất"""
    # A. Top 10 người nạp nhiều nhất
    top_topups = (
        db.query(
            User.id,
            User.telegram_id,
            User.telegram_user,
            func.coalesce(func.sum(Topup.amount), 0).label("total_topup"),
            func.count(Topup.id).label("topup_count"),
        )
        .join(Topup, Topup.user_id == User.id)
        .filter(Topup.status == "SUCCESS")
        .group_by(User.id, User.telegram_id, User.telegram_user)
        .order_by(func.sum(Topup.amount).desc())
        .limit(10)
        .all()
    )

    # B. Top 10 sản phẩm bán chạy nhất
    top_products = (
        db.query(
            Product.id,
            Product.name,
            Product.code,
            Product.price,
            func.coalesce(func.sum(Order.qty), 0).label("total_sold"),
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total), 0).label("total_revenue"),
        )
        .join(Order, Order.product_id == Product.id)
        .filter(Order.status == "PAID")
        .group_by(Product.id, Product.name, Product.code, Product.price)
        .order_by(func.sum(Order.qty).desc())
        .limit(10)
        .all()
    )

    # Tính max để làm progress bar
    max_sold = int(top_products[0].total_sold) if top_products else 1

    return templates.TemplateResponse(
        "stats.html",
        {
            "request": request,
            "top_topups": top_topups,
            "top_products": top_products,
            "max_sold": max_sold,
        },
    )


# ==== PRODUCTS ====


@app.get("/products", response_class=HTMLResponse)
def products_list(
    request: Request,
    db: DbDep,
    q: Optional[str] = None,
    notice: Optional[str] = None,
    error: Optional[str] = None,
):
    notice_map = {
        "product_deleted": "Da xoa san pham va du lieu lien quan thanh cong.",
        # Backward compatibility cho link notice cũ.
        "product_deactivated": "San pham da duoc xu ly. Vui long tai lai danh sach.",
    }
    error_map = {
        "product_not_found": "Khong tim thay san pham.",
        "delete_failed": "Khong the xoa san pham. Vui long thu lai.",
    }
    # Sắp xếp theo sort_order ASC (NULL cuối), sau đó theo id ASC
    # Dùng text() để đảm bảo tương thích với PostgreSQL
    from sqlalchemy import text
    query = db.query(Product)
    # Kiểm tra xem column sort_order có tồn tại không
    try:
        # Thử query với sort_order
        query = query.order_by(
            text("sort_order ASC NULLS LAST"),
            Product.id.asc()
        )
    except Exception:
        # Nếu column chưa tồn tại, sắp xếp theo id
        query = query.order_by(Product.id.asc())
    
    if q:
        like = f"%{q}%"
        query = query.filter(Product.name.ilike(like) | Product.code.ilike(like))
    products = query.limit(100).all()
    return templates.TemplateResponse(
        "products_list.html",
        {
            "request": request,
            "products": products,
            "q": q or "",
            "notice": notice_map.get(notice or "", notice or ""),
            "error": error_map.get(error or "", error or ""),
        },
    )


@app.get("/products/new", response_class=HTMLResponse)
def product_form_new(request: Request, db: DbDep):
    # Form tạo sản phẩm mới
    descriptions = {"vi": "", "en": "", "zh": "", "ru": ""}
    return templates.TemplateResponse(
        "product_form.html",
        {"request": request, "product": None, "descriptions": descriptions, "qty_tiers": []},
    )


@app.get("/products/{product_id:int}", response_class=HTMLResponse)
def product_form_edit(request: Request, product_id: int, db: DbDep):
    # Form sửa sản phẩm existing
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Parse descriptions từ JSON
    descriptions = {"vi": "", "en": "", "zh": "", "ru": ""}
    if product.description:
        try:
            desc_dict = json.loads(product.description)
            if isinstance(desc_dict, dict):
                descriptions.update(desc_dict)
        except (json.JSONDecodeError, TypeError):
            # Không phải JSON, giữ nguyên text thuần (backward compatibility)
            descriptions["en"] = product.description
    
    try:
        qty_tiers = (
            db.query(ProductQtyDiscountTier)
            .filter(ProductQtyDiscountTier.product_id == product_id)
            .order_by(ProductQtyDiscountTier.min_qty.asc())
            .all()
        )
    except ProgrammingError:
        db.rollback()
        qty_tiers = []
    return templates.TemplateResponse(
        "product_form.html",
        {
            "request": request,
            "product": product,
            "descriptions": descriptions,
            "qty_tiers": qty_tiers,
        },
    )


def _form_optional_int(raw) -> Optional[int]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return int(s)


def _form_optional_float(raw) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return float(s)


@app.post("/products/save")
async def product_save(request: Request, db: DbDep):
    form = await request.form()
    product_id_raw = form.get("product_id")
    product_id = int(product_id_raw) if product_id_raw and str(product_id_raw).strip() else None
    code = (form.get("code") or "").strip()
    name = (form.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="Code and name are required")

    price = float(form.get("price") or 0)
    stock = int(form.get("stock") or 0)
    is_active = form.get("is_active") in ("on", "true", "1", True)
    description_vi = str(form.get("description_vi") or "")
    description_en = str(form.get("description_en") or "")
    description_zh = str(form.get("description_zh") or "")
    description_ru = str(form.get("description_ru") or "")
    delivery_payload = str(form.get("delivery_payload") or "")
    qty_discount_min = _form_optional_int(form.get("qty_discount_min"))
    qty_discount_percent = _form_optional_float(form.get("qty_discount_percent"))
    sort_order = _form_optional_int(form.get("sort_order"))

    tier_mins = form.getlist("tier_min")
    tier_pcts = form.getlist("tier_pct")
    tier_rows = list(zip(tier_mins, tier_pcts))
    try:
        tiers = validate_tiers_rows(tier_rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if product_id:
        product = db.query(Product).get(int(product_id))
        if not product:
            raise HTTPException(404, "Product not found")
    else:
        product = Product(code=code)
        db.add(product)

    product.code = code
    product.name = name
    product.price = price
    product.stock = stock
    product.is_active = bool(is_active)

    descriptions = {
        "vi": description_vi.strip(),
        "en": description_en.strip(),
        "zh": description_zh.strip(),
        "ru": description_ru.strip(),
    }
    descriptions_filtered = {k: v for k, v in descriptions.items() if v}
    if descriptions_filtered:
        product.description = json.dumps(descriptions_filtered, ensure_ascii=False)
    else:
        product.description = None

    product.delivery_payload = delivery_payload
    product.qty_discount_min = qty_discount_min
    product.qty_discount_percent = qty_discount_percent
    product.sort_order = sort_order if sort_order is not None else None

    db.flush()
    replace_tiers_for_product(db, int(product.id), tiers)
    db.commit()
    return RedirectResponse(url="/products", status_code=303)


@app.post("/products/{product_id}/delete")
def product_delete(product_id: int, db: DbDep):
    product = db.query(Product).get(product_id)
    if not product:
        return RedirectResponse(url="/products?error=product_not_found", status_code=303)

    try:
        # Xóa các dữ liệu liên quan theo thứ tự phụ thuộc khóa ngoại:
        # Ticket -> Order -> Coupon/Stock -> Product
        order_ids = [
            row[0]
            for row in db.query(Order.id).filter(Order.product_id == product_id).all()
        ]
        if order_ids:
            db.execute(delete(Ticket).where(Ticket.order_id.in_(order_ids)))
            db.execute(delete(Order).where(Order.id.in_(order_ids)))

        db.execute(delete(Coupon).where(Coupon.product_id == product_id))
        db.execute(delete(ProductStockItem).where(ProductStockItem.product_id == product_id))
        db.flush()
        db.delete(product)
        db.commit()
        return RedirectResponse(url="/products?notice=product_deleted", status_code=303)
    except IntegrityError:
        db.rollback()
        return RedirectResponse(url="/products?error=delete_failed", status_code=303)
    except Exception:
        db.rollback()
        return RedirectResponse(url="/products?error=delete_failed", status_code=303)


@app.get("/products/{product_id}/stock", response_class=HTMLResponse)
def product_stock(request: Request, product_id: int, db: DbDep):
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    items = (
        db.query(ProductStockItem)
        .filter(ProductStockItem.product_id == product_id)
        .order_by(ProductStockItem.id.desc())
        .limit(100)
        .all()
    )
    total = (
        db.query(ProductStockItem)
        .filter(ProductStockItem.product_id == product_id)
        .count()
    )
    
    # Lấy thông tin từ query params nếu có (sau khi import)
    added = request.query_params.get("added")
    skipped = request.query_params.get("skipped")
    duplicates_str = request.query_params.get("duplicates")
    duplicates = duplicates_str.split(",") if duplicates_str else []
    
    return templates.TemplateResponse(
        "stock_items.html",
        {
            "request": request,
            "product": product,
            "items": items,
            "total": total,
            "added": added,
            "skipped": skipped,
            "duplicates": duplicates,
        },
    )


@app.post("/products/{product_id}/stock/import")
def product_stock_import(
    product_id: int,
    db: DbDep,
    mode: str = Form("append"),
    lines: str = Form(""),
):
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")

    text = (lines or "").strip()
    if not text:
        raise HTTPException(400, "Lines is empty")

    from sqlalchemy import delete

    if mode == "replace":
        db.execute(
            delete(ProductStockItem).where(
                ProductStockItem.product_id == product_id
            )
        )

    added = 0
    skipped = 0
    duplicate_lines = []  # Danh sách các dòng trùng
    # Lấy danh sách mota đã tồn tại để check trùng
    existing_motas_result = (
        db.query(ProductStockItem.mota)
        .filter(ProductStockItem.product_id == product_id)
        .distinct()
        .all()
    )
    existing_motas = {m[0] for m in existing_motas_result if m[0]}
    
    # Set để check trùng trong cùng batch import
    batch_motas = set()
    
    for raw in text.splitlines():
        line = (raw or "").strip()
        if not line:
            continue
        
        # Check trùng mota trong cùng product_id hoặc trong cùng batch
        if line in existing_motas or line in batch_motas:
            skipped += 1
            duplicate_lines.append(line)
            continue
        
        # Mỗi hàng là 1 mota, không có format id|mota
        # Sinh id_sanpham ngẫu nhiên để dễ truy vết nếu cần
        import secrets, string
        alphabet = string.ascii_uppercase + string.digits
        random_id = "".join(secrets.choice(alphabet) for _ in range(10))
        item = ProductStockItem(
            product_id=product_id, id_sanpham=random_id, mota=line
        )
        db.add(item)
        existing_motas.add(line)  # Thêm vào set để tránh trùng trong cùng batch
        batch_motas.add(line)  # Thêm vào batch set
        added += 1

    # sync stock
    from sqlalchemy import func

    # Flush để đảm bảo tất cả items đã được lưu vào DB trước khi đếm
    db.flush()
    
    new_stock = (
        db.query(func.count(ProductStockItem.id))
        .filter(ProductStockItem.product_id == product_id)
        .scalar()
        or 0
    )
    product.stock = int(new_stock)
    db.flush()  # Flush lại sau khi update stock
    
    # Lấy product name trước khi commit (để tránh detached instance error)
    product_name = product.name
    product_id_for_broadcast = product.id
    
    db.commit()

    # Gửi thông báo broadcast cho tất cả users (chạy background, không block request)
    if added > 0:
        # Chạy broadcast trong background thread để không block response
        import threading
        def run_broadcast():
            try:
                asyncio.run(_broadcast_stock_update(product_id_for_broadcast, product_name, added, int(new_stock)))
            except Exception as e:
                print(f"❌ Error in broadcast thread: {e}")
        
        thread = threading.Thread(target=run_broadcast, daemon=True)
        thread.start()

    # Nếu có dòng trùng, hiển thị thông báo
    if duplicate_lines:
        from urllib.parse import urlencode
        params = {
            "added": added,
            "skipped": skipped,
            "duplicates": ",".join(duplicate_lines[:50])  # Giới hạn 50 dòng đầu
        }
        return RedirectResponse(
            url=f"/products/{product_id}/stock?{urlencode(params)}", status_code=303
        )
    
    return RedirectResponse(
        url=f"/products/{product_id}/stock", status_code=303
    )


@app.get("/products/{product_id}/stock/download")
def product_stock_download(product_id: int, db: DbDep):
    """Tải về file stock items với format {idproduct}_{ten product}_{ngày}_txt"""
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    
    items = (
        db.query(ProductStockItem)
        .filter(ProductStockItem.product_id == product_id)
        .order_by(ProductStockItem.id.asc())
        .all()
    )
    
    # Tạo nội dung file: mỗi hàng là 1 mota
    lines = []
    for item in items:
        mota = (item.mota or "").strip()
        if mota:
            lines.append(mota)
    
    content = "\n".join(lines)
    
    # Tạo tên file: {idproduct}_{ten product}_{ngày}_txt
    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")
    # Làm sạch tên sản phẩm để dùng trong tên file
    import re
    safe_name = re.sub(r'[^\w\s-]', '', product.name)
    safe_name = re.sub(r'[-\s]+', '_', safe_name)
    filename = f"{product_id}_{safe_name}_{date_str}.txt"
    
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.post("/products/{product_id}/stock/delete-all")
def product_stock_delete_all(product_id: int, db: DbDep):
    """Xóa hết tất cả stock items của một product"""
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    
    from sqlalchemy import delete, func
    
    # Xóa tất cả items
    deleted_count = db.execute(
        delete(ProductStockItem).where(
            ProductStockItem.product_id == product_id
        )
    ).rowcount
    
    # Cập nhật stock về 0
    product.stock = 0
    db.commit()
    
    return RedirectResponse(
        url=f"/products/{product_id}/stock", status_code=303
    )


@app.post("/products/{product_id}/stock/delete-selected")
async def product_stock_delete_selected(product_id: int, request: Request, db: DbDep):
    """Xóa các stock items được chọn"""
    product = db.query(Product).get(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    
    # Lấy danh sách item_ids từ form (có thể có nhiều checkbox cùng name)
    form_data = await request.form()
    item_ids_str = form_data.getlist("item_ids")
    
    if not item_ids_str:
        raise HTTPException(400, "Không có mục nào được chọn")
    
    # Convert sang int
    try:
        item_ids = [int(id_str) for id_str in item_ids_str]
    except ValueError:
        raise HTTPException(400, "ID không hợp lệ")
    
    from sqlalchemy import delete, func
    
    # Xóa các items được chọn
    deleted_count = db.execute(
        delete(ProductStockItem).where(
            ProductStockItem.product_id == product_id,
            ProductStockItem.id.in_(item_ids)
        )
    ).rowcount
    
    # Cập nhật stock
    new_stock = (
        db.query(func.count(ProductStockItem.id))
        .filter(ProductStockItem.product_id == product_id)
        .scalar()
        or 0
    )
    product.stock = int(new_stock)
    db.commit()
    
    return RedirectResponse(
        url=f"/products/{product_id}/stock", status_code=303
    )


# ==== COUPONS ====


@app.get("/coupons", response_class=HTMLResponse)
def coupons_list(request: Request, db: DbDep):
    try:
        coupons = db.query(Coupon).order_by(Coupon.id.desc()).limit(200).all()
    except Exception as e:
        # Nếu lỗi do thiếu cột product_id/user_id, hiển thị thông báo migration
        if "product_id" in str(e) or "user_id" in str(e):
            error_msg = """
            <div class="alert alert-danger">
                <h4>⚠️ Database chưa được cập nhật!</h4>
                <p>Các cột <code>product_id</code> và <code>user_id</code> chưa tồn tại trong bảng <code>coupons</code>.</p>
                <p><strong>Vui lòng chạy migration:</strong></p>
                <ol>
                    <li>Chạy SQL script: <code>token_shop_backend/migrations/add_coupon_product_user_columns.sql</code></li>
                    <li>Hoặc chạy Python script: <code>python token_shop_backend/migrations/add_coupon_product_user_columns.py</code></li>
                </ol>
                <p>Sau đó reload lại trang này.</p>
            </div>
            """
            return HTMLResponse(content=error_msg, status_code=500)
        raise
    
    # Lấy danh sách products và users để hiển thị tên
    products = {p.id: p for p in db.query(Product).all()}
    users = {u.id: u for u in db.query(User).limit(1000).all()}
    usage_by_cid = {}
    for c in coupons:
        used = int(count_committed_global_ledger(db, int(c.id)))
        cap = int(c.max_uses_total) if c.max_uses_total is not None else None
        rem = (cap - used) if cap is not None else None
        usage_by_cid[c.id] = {"used": used, "remaining": rem}
    return templates.TemplateResponse(
        "coupons_list.html", {
            "request": request,
            "coupons": coupons,
            "products": products,
            "users": users,
            "usage_by_cid": usage_by_cid,
        }
    )


@app.post("/coupons/save")
def coupon_save(
    db: DbDep,
    coupon_id: str = Form(""),
    code: str = Form(...),
    discount_type: str = Form("PERCENT"),
    discount_value: float = Form(0),
    max_discount_amount: Optional[float] = Form(None),
    min_order_amount: Optional[float] = Form(None),
    product_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
    max_uses_total: Optional[int] = Form(None),
    max_uses_per_user: Optional[int] = Form(None),
    max_qty_per_order: Optional[int] = Form(None),
    is_active: bool = Form(False),
):
    """
    Tạo / cập nhật mã giảm giá.
    - Để tạo mới: để trống trường ID.
    - Để sửa: nhập đúng ID đã có.
    """
    code = (code or "").strip().upper()
    if not code:
        raise HTTPException(400, "Mã coupon là bắt buộc")

    coupon_obj: Optional[Coupon] = None
    cid = (coupon_id or "").strip()
    if cid:
        try:
            cid_int = int(cid)
        except ValueError:
            raise HTTPException(400, "ID coupon phải là số")
        coupon_obj = db.query(Coupon).get(cid_int)
        if not coupon_obj:
            raise HTTPException(404, "Không tìm thấy coupon")
        
        # Kiểm tra code có bị trùng với coupon khác không (khi edit)
        if coupon_obj.code != code:
            existing = db.query(Coupon).filter(Coupon.code == code, Coupon.id != cid_int).first()
            if existing:
                raise HTTPException(400, f"Mã coupon '{code}' đã tồn tại (coupon ID: {existing.id})")
    else:
        # Kiểm tra code đã tồn tại chưa (khi tạo mới)
        existing = db.query(Coupon).filter(Coupon.code == code).first()
        if existing:
            raise HTTPException(400, f"Mã coupon '{code}' đã tồn tại (coupon ID: {existing.id})")
        coupon_obj = Coupon(code=code)
        db.add(coupon_obj)

    coupon_obj.code = code
    coupon_obj.discount_type = (discount_type or "PERCENT").upper()
    coupon_obj.discount_value = discount_value
    coupon_obj.max_discount_amount = max_discount_amount
    coupon_obj.min_order_amount = min_order_amount

    # Usage limits (optional) — form rỗng => None, không phải 0
    coupon_obj.max_uses_total = _form_optional_int(max_uses_total)
    coupon_obj.max_uses_per_user = _form_optional_int(max_uses_per_user)
    coupon_obj.max_qty_per_order = _form_optional_int(max_qty_per_order)
    
    # Loại 2: Cấp mã riêng cho 1 user (nếu có user_id)
    # Loại 3: Mã giảm giá cho mọi user trên 1 sản phẩm (nếu có product_id, không có user_id)
    # Xử lý product_id
    if product_id and str(product_id).strip():
        try:
            product_id_int = int(str(product_id).strip())
            # Kiểm tra product có tồn tại không
            product_exists = db.query(Product).filter(Product.id == product_id_int).first()
            if not product_exists:
                raise HTTPException(400, f"Product với ID {product_id_int} không tồn tại")
            coupon_obj.product_id = product_id_int
        except ValueError:
            raise HTTPException(400, f"Product ID phải là số hợp lệ, nhận được: '{product_id}'")
    else:
        coupon_obj.product_id = None
    
    # Xử lý user_id - hỗ trợ cả ID database và telegram_id
    if user_id and str(user_id).strip():
        try:
            user_id_int = int(str(user_id).strip())
            # Tìm user theo ID database trước
            user_exists = db.query(User).filter(User.id == user_id_int).first()
            if not user_exists:
                # Nếu không tìm thấy theo ID, thử tìm theo telegram_id
                user_by_telegram = db.query(User).filter(User.telegram_id == user_id_int).first()
                if user_by_telegram:
                    # Tìm thấy theo telegram_id, dùng id database
                    coupon_obj.user_id = user_by_telegram.id
                else:
                    raise HTTPException(
                        400, 
                        f"Không tìm thấy user với ID database hoặc telegram_id = {user_id_int}. "
                        f"Vui lòng kiểm tra lại ID user trong trang Users."
                    )
            else:
                coupon_obj.user_id = user_id_int
        except ValueError:
            raise HTTPException(400, f"User ID phải là số hợp lệ, nhận được: '{user_id}'")
    else:
        coupon_obj.user_id = None
    
    coupon_obj.is_active = bool(is_active)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Lỗi khi lưu coupon: {str(e)}")
    
    return RedirectResponse(url="/coupons", status_code=303)


@app.post("/coupons/{coupon_id}/delete")
def coupon_delete(coupon_id: int, db: DbDep):
    coupon = db.query(Coupon).get(coupon_id)
    if coupon:
        db.delete(coupon)
        db.commit()
    return RedirectResponse(url="/coupons", status_code=303)


@app.post("/coupons/{coupon_id}/add-uses")
def coupon_add_uses(coupon_id: int, db: DbDep, add: int = Form(...)):
    if int(add) < 1:
        raise HTTPException(400, "Số lượt cộng phải >= 1")
    c = db.execute(select(Coupon).where(Coupon.id == coupon_id).with_for_update()).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Không tìm thấy coupon")
    used = int(count_committed_global_ledger(db, coupon_id))
    n = int(add)
    if c.max_uses_total is None:
        c.max_uses_total = used + n
    else:
        c.max_uses_total = int(c.max_uses_total) + n
    db.commit()
    return RedirectResponse(url="/coupons", status_code=303)


@app.get("/coupons/{coupon_id}/usage", response_class=HTMLResponse)
def coupon_redemptions_page(
    request: Request,
    coupon_id: int,
    db: DbDep,
    page: int = 1,
    per_page: int = 50,
):
    c = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not c:
        raise HTTPException(404, "Không tìm thấy coupon")
    page = max(1, int(page))
    per_page = min(200, max(10, int(per_page)))
    total = (
        db.query(func.count(CouponRedemption.id))
        .filter(CouponRedemption.coupon_id == coupon_id)
        .scalar()
        or 0
    )
    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1
    if page > total_pages:
        page = total_pages
    rows = (
        db.query(CouponRedemption, User)
        .join(User, User.id == CouponRedemption.user_id)
        .filter(CouponRedemption.coupon_id == coupon_id)
        .order_by(CouponRedemption.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    used = int(count_committed_global_ledger(db, coupon_id))
    cap = int(c.max_uses_total) if c.max_uses_total is not None else None
    remaining = (cap - used) if cap is not None else None
    return templates.TemplateResponse(
        "coupon_usage.html",
        {
            "request": request,
            "coupon": c,
            "rows": rows,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "used": used,
            "remaining": remaining,
        },
    )


# ==== USERS ====


@app.get("/users", response_class=HTMLResponse)
def users_list(
    request: Request,
    db: DbDep,
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
):
    db.expire_all()

    page = max(1, int(page))
    per_page = min(100, max(5, int(per_page)))

    query = db.query(User).order_by(User.id.desc())
    q_clean = (q or "").strip()
    if q_clean:
        like = f"%{q_clean}%"
        parts = [
            User.telegram_user.ilike(like),
            cast(User.telegram_id, String).like(like),
            cast(User.id, String).like(like),
        ]
        if q_clean.isdigit():
            try:
                n = int(q_clean)
                parts.append(User.id == n)
                parts.append(User.telegram_id == n)
            except ValueError:
                pass
        query = query.filter(or_(*parts))

    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()

    if users:
        user_ids = [u.id for u in users]
        banned_rows = db.query(User.id, User.is_banned).filter(User.id.in_(user_ids)).all()
        banned_dict = {row[0]: (row[1] if row[1] is not None else False) for row in banned_rows}
        for user in users:
            setattr(user, "is_banned", banned_dict.get(user.id, getattr(user, "is_banned", False)))

    return templates.TemplateResponse(
        "users_list.html",
        {
            "request": request,
            "users": users,
            "q": q_clean,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    )


@app.get("/users/{user_id:int}", response_class=HTMLResponse)
def user_detail(request: Request, user_id: int, db: DbDep):
    # Query lại từ đầu để đảm bảo lấy data mới nhất
    # Expire tất cả để force reload từ DB
    db.expire_all()
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    # Debug: Log telegram_user để kiểm tra
    print(f"[USER_DETAIL] User {user_id} - telegram_id: {user.telegram_id}, telegram_user: '{user.telegram_user}'")
    
    # Tự động fetch username từ Telegram API nếu không có
    if user.telegram_id and (not user.telegram_user or not user.telegram_user.strip()):
        try:
            username = asyncio.run(_get_telegram_username(user.telegram_id))
            if username:
                user.telegram_user = username
                db.commit()
                db.refresh(user)
                print(f"✅ [USER_DETAIL] Fetched and updated username for user {user_id}: @{username}")
        except Exception as e:
            print(f"⚠️ [USER_DETAIL] Failed to fetch username: {e}")
    
    # Query is_banned trực tiếp từ DB nếu attribute không có
    is_banned = False
    if hasattr(user, 'is_banned'):
        is_banned = getattr(user, 'is_banned', False)
    else:
        # Query trực tiếp từ DB bằng raw SQL
        result = db.execute(
            text("SELECT is_banned FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        ).fetchone()
        if result:
            is_banned = result[0] if result[0] is not None else False
        # Gán vào user object để template có thể dùng
        setattr(user, 'is_banned', is_banned)
    
    # Log để debug
    print(f"[USER_DETAIL] User {user_id} - is_banned: {is_banned}, telegram_id: {user.telegram_id}, telegram_user: '{user.telegram_user}'")
    # Lịch sử đơn và topup của user
    orders = (
        db.query(Order)
        .filter(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(50)
        .all()
    )
    topups = (
        db.query(Topup)
        .filter(Topup.user_id == user_id)
        .order_by(Topup.created_at.desc())
        .limit(50)
        .all()
    )
    tickets = (
        db.query(Ticket)
        .filter(Ticket.user_id == user_id)
        .order_by(Ticket.created_at.desc())
        .limit(50)
        .all()
    )
    
    return templates.TemplateResponse(
        "user_detail.html",
        {
            "request": request,
            "user": user,
            "orders": orders,
            "topups": topups,
            "tickets": tickets,
        },
    )


@app.get("/users/{user_id:int}/ban")
def user_ban_get(user_id: int):
    """Redirect GET request về user detail"""
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)


@app.post("/users/{user_id:int}/ban")
def user_ban(user_id: int, db: DbDep):
    """Ban user"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")
        
        # Kiểm tra xem column is_banned có tồn tại không
        if not hasattr(user, 'is_banned'):
            # Nếu không có attribute, update bằng raw SQL
            db.execute(
                text("UPDATE users SET is_banned = TRUE WHERE id = :user_id"),
                {"user_id": user_id}
            )
            db.commit()
            print(f"[BAN] Updated via raw SQL - User {user_id}")
        else:
            # Log trạng thái ban đầu
            print(f"[BAN] User {user_id} (telegram_id={user.telegram_id}) - Current is_banned: {getattr(user, 'is_banned', False)}")
            
            # Cập nhật is_banned
            user.is_banned = True
            db.flush()  # Flush để đảm bảo thay đổi được gửi đến DB
            print(f"[BAN] After set is_banned=True, before commit: {getattr(user, 'is_banned', False)}")
            
            db.commit()
            print(f"[BAN] After commit, is_banned: {getattr(user, 'is_banned', False)}")
            
            # Query lại từ DB để verify
            db.expire_all()  # Expire tất cả objects trong session
            user_after = db.query(User).filter(User.id == user_id).first()
            if user_after:
                print(f"[BAN] After expire_all and re-query, is_banned: {getattr(user_after, 'is_banned', False)}")
        
        import time
        return RedirectResponse(url=f"/users/{user_id}?t={int(time.time())}", status_code=303)
    except Exception as e:
        import traceback
        print(f"[BAN] Error banning user {user_id}: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(500, f"Error banning user: {str(e)}")


@app.get("/users/{user_id:int}/unban")
def user_unban_get(user_id: int):
    """Redirect GET request về user detail"""
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)


@app.post("/users/{user_id:int}/unban")
def user_unban(user_id: int, db: DbDep):
    """Unban user"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")
        
        # Kiểm tra xem column is_banned có tồn tại không
        if not hasattr(user, 'is_banned'):
            # Nếu không có attribute, update bằng raw SQL
            db.execute(
                text("UPDATE users SET is_banned = FALSE WHERE id = :user_id"),
                {"user_id": user_id}
            )
            db.commit()
            print(f"[UNBAN] Updated via raw SQL - User {user_id}")
        else:
            # Log trạng thái ban đầu
            print(f"[UNBAN] User {user_id} (telegram_id={user.telegram_id}) - Current is_banned: {getattr(user, 'is_banned', False)}")
            
            # Cập nhật is_banned
            user.is_banned = False
            db.flush()  # Flush để đảm bảo thay đổi được gửi đến DB
            print(f"[UNBAN] After set is_banned=False, before commit: {getattr(user, 'is_banned', False)}")
            
            db.commit()
            print(f"[UNBAN] After commit, is_banned: {getattr(user, 'is_banned', False)}")
            
            # Query lại từ DB để verify
            db.expire_all()  # Expire tất cả objects trong session
            user_after = db.query(User).filter(User.id == user_id).first()
            if user_after:
                print(f"[UNBAN] After expire_all and re-query, is_banned: {getattr(user_after, 'is_banned', False)}")
        
        import time
        return RedirectResponse(url=f"/users/{user_id}?t={int(time.time())}", status_code=303)
    except Exception as e:
        import traceback
        print(f"[UNBAN] Error unbanning user {user_id}: {e}")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(500, f"Error unbanning user: {str(e)}")


@app.post("/users/{user_id:int}/adjust_balance")
def user_adjust_balance(
    user_id: int,
    db: DbDep,
    amount: float = Form(...),
    note: str = Form(""),
):
    """
    Cộng / trừ tiền thủ công cho user.
    - amount > 0: cộng
    - amount < 0: trừ
    """
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    from decimal import Decimal
    import uuid
    from datetime import datetime

    delta = Decimal(str(amount))
    # Cập nhật balance ngay
    user.balance = Decimal(str(user.balance)) + delta

    # Ghi lại 1 topup manual để dễ trace
    # Thêm timestamp vào out_order_id để tránh trùng khi điều chỉnh nhiều lần
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    topup = Topup(
        id=str(uuid.uuid4()),
        out_order_id=f"ADMIN_ADJUST_{user.telegram_id}_{timestamp}",
        user_id=user.id,
        telegram_id=user.telegram_id,
        network="MANUAL",
        currency="MANUAL",
        base_currency="USD",
        actual_amount=delta,
        amount=delta,
        status="SUCCESS",
        raw_notify={"admin_adjust": True, "note": note},
    )
    db.add(topup)
    db.commit()
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)


@app.post("/users/{user_id:int}/reset_balance")
def user_reset_balance(user_id: int, db: DbDep):
    """
    Đặt lại số dư user về 0 và ghi lại topup record để trace số tiền đã trừ.
    """
    from decimal import Decimal
    import uuid
    from datetime import datetime

    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    current_balance = Decimal(str(user.balance))
    
    # Nếu có số dư > 0, ghi lại topup record với số âm để trace
    if current_balance > 0:
        # Thêm timestamp vào out_order_id để tránh trùng khi reset nhiều lần
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        topup = Topup(
            id=str(uuid.uuid4()),
            out_order_id=f"ADMIN_RESET_{user.telegram_id}_{timestamp}",
            user_id=user.id,
            telegram_id=user.telegram_id,
            network="MANUAL",
            currency="MANUAL",
            base_currency="USD",
            actual_amount=-current_balance,  # Số âm để trừ
            amount=-current_balance,
            status="SUCCESS",
            raw_notify={"admin_reset": True, "previous_balance": str(current_balance)},
        )
        db.add(topup)
    
    # Đặt balance về 0
    user.balance = Decimal("0")
    db.commit()
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)


# ==== ORDERS & TOPUPS (read only) ====


@app.get("/orders", response_class=HTMLResponse)
def orders_list(request: Request, db: DbDep):
    orders = (
        db.query(Order)
        .order_by(Order.created_at.desc())
        .limit(100)
        .all()
    )
    # Lấy thông tin users để hiển thị telegram_user
    user_ids = list(set([o.user_id for o in orders if o.user_id]))
    users = {}
    if user_ids:
        users_list = db.query(User).filter(User.id.in_(user_ids)).all()
        users = {u.id: u for u in users_list}
    
    return templates.TemplateResponse(
        "orders_list.html", {"request": request, "orders": orders, "users": users}
    )


@app.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail(request: Request, order_id: str, db: DbDep):
    """Xem chi tiết đơn hàng"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    
    # Lấy thông tin user
    user = db.query(User).filter(User.id == order.user_id).first()
    
    return templates.TemplateResponse(
        "order_detail.html",
        {
            "request": request,
            "order": order,
            "user": user,
        },
    )


@app.get("/topups", response_class=HTMLResponse)
def topups_list(request: Request, db: DbDep):
    topups = (
        db.query(Topup)
        .order_by(Topup.created_at.desc())
        .limit(100)
        .all()
    )
    # Lấy thông tin users để hiển thị telegram_user
    user_ids = list(set([t.user_id for t in topups if t.user_id]))
    users = {}
    if user_ids:
        users_list = db.query(User).filter(User.id.in_(user_ids)).all()
        users = {u.id: u for u in users_list}
    
    return templates.TemplateResponse(
        "topups_list.html", {"request": request, "topups": topups, "users": users}
    )


# ==== TICKETS ====


@app.get("/tickets", response_class=HTMLResponse)
def tickets_list(
    request: Request, db: DbDep, status: Optional[str] = None
):
    query = db.query(Ticket).order_by(Ticket.created_at.desc())
    if status and status != "ALL":
        query = query.filter(Ticket.status == status)
    tickets = query.limit(200).all()
    
    # Lấy thông tin users để hiển thị telegram_user
    user_ids = list(set([t.user_id for t in tickets if t.user_id]))
    users = {}
    if user_ids:
        users_list = db.query(User).filter(User.id.in_(user_ids)).all()
        users = {u.id: u for u in users_list}
    
    return templates.TemplateResponse(
        "tickets_list.html",
        {
            "request": request,
            "tickets": tickets,
            "status": status or "ALL",
            "users": users,
        },
    )


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
def ticket_detail(request: Request, ticket_id: int, db: DbDep):
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    order = (
        db.query(Order).filter(Order.id == ticket.order_id).first()
        if ticket.order_id
        else None
    )
    user = db.query(User).filter(User.id == ticket.user_id).first()
    
    return templates.TemplateResponse(
        "ticket_detail.html",
        {
            "request": request,
            "ticket": ticket,
            "order": order,
            "user": user,
        },
    )


@app.post("/tickets/{ticket_id}/approve")
def ticket_approve(
    ticket_id: int,
    db: DbDep,
    replacement_items: str = Form(""),
):
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    # Lấy thông tin order và user
    order = None
    if ticket.order_id:
        order = db.query(Order).filter(Order.id == ticket.order_id).first()
    
    replacement_items_str = (replacement_items or "").strip()
    ticket.status = "APPROVED"
    ticket.replacement_items = replacement_items_str or None
    db.commit()
    
    # Gửi thông báo cho user qua Telegram
    message = f"✅ <b>Ticket Approved</b>\n\n"
    if order:
        message += f"Order <code>{order.order_code}</code> has been processed.\n\n"
    
    if replacement_items_str:
        # Có replacement items -> gửi message và file txt
        message += "Replacement items:\n\n"
        message += "Thank you for your patience!"
        
        # Gửi message trước
        success, error = asyncio.run(_send_telegram_message(ticket.telegram_id, message))
        if not success:
            print(f"Warning: Failed to send Telegram message to {ticket.telegram_id}: {error}")
        
        # Gửi file txt với replacement items
        success_file, error_file = asyncio.run(_send_telegram_file(
            ticket.telegram_id, 
            replacement_items_str,
            f"replacement_{ticket.id}_{order.order_code if order else 'items'}.txt"
        ))
        if not success_file:
            print(f"Warning: Failed to send Telegram file to {ticket.telegram_id}: {error_file}")
    else:
        # Không có items -> chỉ thông báo đã fix
        message += "Your account has been fixed. Thank you for your patience!"
        
        # Gửi message async
        success, error = asyncio.run(_send_telegram_message(ticket.telegram_id, message))
        if not success:
            # Log error nhưng không fail request
            print(f"Warning: Failed to send Telegram message to {ticket.telegram_id}: {error}")
    
    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=303)


@app.post("/tickets/{ticket_id}/reject")
def ticket_reject(ticket_id: int, db: DbDep, reason: str = Form("")):
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    # Lấy thông tin order
    order = None
    if ticket.order_id:
        order = db.query(Order).filter(Order.id == ticket.order_id).first()
    
    ticket.status = "REJECTED"
    db.commit()
    
    # Gửi thông báo từ chối cho user qua Telegram
    message = "❌ <b>Ticket Rejected</b>\n\n"
    if order:
        message += f"Order <code>{order.order_code}</code> has been rejected.\n\n"
    else:
        message += "Your ticket has been rejected.\n\n"
    
    # Thêm lý do nếu có
    if reason and reason.strip():
        message += f"<b>Reason:</b>\n{reason.strip()}\n\n"
    
    message += "If you have any questions, please contact support."
    
    # Gửi message async
    success, error = asyncio.run(_send_telegram_message(ticket.telegram_id, message))
    if not success:
        # Log error nhưng không fail request
        print(f"Warning: Failed to send Telegram message to {ticket.telegram_id}: {error}")
    
    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=303)


# ==== HELPER: Get Telegram username ====


async def _get_telegram_username(telegram_id: int) -> Optional[str]:
    """
    Lấy username của user từ Telegram API.
    Returns: username hoặc None nếu không có hoặc lỗi
    """
    try:
        apitele_dir = os.path.join(project_root, "APITELE")
        if apitele_dir not in sys.path:
            sys.path.insert(0, apitele_dir)
        
        from aiogram import Bot
        from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramForbiddenError
        
        from dotenv import load_dotenv
        apitele_env = os.path.join(apitele_dir, ".env")
        if os.path.exists(apitele_env):
            load_dotenv(apitele_env, override=False)
        
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            return None
        
        bot = Bot(token=bot_token)
        try:
            user_info = await bot.get_chat(chat_id=telegram_id)
            username = getattr(user_info, "username", None)
            return username
        except (TelegramBadRequest, TelegramAPIError, TelegramForbiddenError):
            return None
        finally:
            await bot.session.close()
    except Exception:
        return None


# ==== HELPER: Send Telegram message ====


async def _send_telegram_message(telegram_id: int, message: str) -> tuple[bool, str]:
    """
    Gửi message đến user qua Telegram bot.
    Returns: (success: bool, error_message: str)
    """
    try:
        # Import aiogram và config từ APITELE
        apitele_dir = os.path.join(project_root, "APITELE")
        if apitele_dir not in sys.path:
            sys.path.insert(0, apitele_dir)
        
        from aiogram import Bot
        from aiogram.enums import ParseMode
        from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramForbiddenError
        
        # Load BOT_TOKEN từ APITELE/.env
        from dotenv import load_dotenv
        apitele_env = os.path.join(apitele_dir, ".env")
        if os.path.exists(apitele_env):
            load_dotenv(apitele_env, override=False)
        
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            return False, "BOT_TOKEN not found"
        
        bot = Bot(token=bot_token)
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            return True, ""
        except TelegramForbiddenError:
            return False, "Forbidden (blocked/unavailable)"
        except (TelegramBadRequest, TelegramAPIError) as e:
            return False, str(e)
        finally:
            await bot.session.close()
    except Exception as e:
        return False, f"Error: {str(e)}"


async def _send_telegram_file(telegram_id: int, content: str, filename: str) -> tuple[bool, str]:
    """
    Gửi file txt đến user qua Telegram bot.
    Returns: (success: bool, error_message: str)
    """
    import tempfile
    try:
        # Import aiogram và config từ APITELE
        apitele_dir = os.path.join(project_root, "APITELE")
        if apitele_dir not in sys.path:
            sys.path.insert(0, apitele_dir)
        
        from aiogram import Bot
        from aiogram.types import FSInputFile
        from aiogram.exceptions import TelegramBadRequest, TelegramAPIError, TelegramForbiddenError
        
        # Load BOT_TOKEN từ APITELE/.env
        from dotenv import load_dotenv
        apitele_env = os.path.join(apitele_dir, ".env")
        if os.path.exists(apitele_env):
            load_dotenv(apitele_env, override=False)
        
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            return False, "BOT_TOKEN not found"
        
        # Tạo file tạm
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            tmp_path = f.name
        
        bot = Bot(token=bot_token)
        try:
            await bot.send_document(
                chat_id=telegram_id,
                document=FSInputFile(tmp_path, filename=filename),
                caption="📄 Replacement items"
            )
            return True, ""
        except TelegramForbiddenError:
            return False, "Forbidden (blocked/unavailable)"
        except (TelegramBadRequest, TelegramAPIError) as e:
            return False, str(e)
        finally:
            await bot.session.close()
            # Xóa file tạm
            try:
                os.unlink(tmp_path)
            except:
                pass
    except Exception as e:
        return False, f"Error: {str(e)}"


# ==== BROADCAST ====


async def _broadcast_message(chat_ids: list[int], message: str) -> dict:
    """
    Gửi broadcast message đến danh sách users.
    Tối ưu với batch processing và rate limiting để tránh nghẽn.
    Returns: dict với success_count, failed_count, blocked_count
    """
    try:
        # Import aiogram và config từ APITELE
        apitele_dir = os.path.join(project_root, "APITELE")
        if apitele_dir not in sys.path:
            sys.path.insert(0, apitele_dir)
        
        from aiogram import Bot
        from aiogram.enums import ParseMode
        from aiogram.exceptions import (
            TelegramBadRequest,
            TelegramAPIError,
            TelegramForbiddenError,
            TelegramUnauthorizedError,
        )
        
        # Load BOT_TOKEN từ APITELE/.env
        from dotenv import load_dotenv
        apitele_env = os.path.join(apitele_dir, ".env")
        if os.path.exists(apitele_env):
            load_dotenv(apitele_env, override=False)
        
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            raise Exception("BOT_TOKEN not found")
        
        if not chat_ids:
            return {"success_count": 0, "failed_count": 0, "blocked_count": 0}
        
        print(f"📢 Broadcasting to {len(chat_ids)} users...")
        
        bot = Bot(token=bot_token)
        success_count = 0
        failed_count = 0
        blocked_count = 0
        
        # Batch size: gửi 20 messages cùng lúc (an toàn với rate limit 30 msg/s)
        batch_size = 20
        delay_between_batches = 1.0  # Delay 1 giây giữa các batch
        
        try:
            # Kiểm tra bot token
            await bot.get_me()
            
            # Chia thành các batch
            for batch_start in range(0, len(chat_ids), batch_size):
                batch_end = min(batch_start + batch_size, len(chat_ids))
                batch = chat_ids[batch_start:batch_end]
                
                # Tạo tasks cho batch này
                tasks = []
                for chat_id in batch:
                    task = bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True,
                    )
                    tasks.append((chat_id, task))
                
                # Gửi batch song song
                results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
                
                # Đếm kết quả
                for (chat_id, _), result in zip(tasks, results):
                    if isinstance(result, Exception):
                        failed_count += 1
                        if isinstance(result, TelegramForbiddenError):
                            blocked_count += 1
                        # Chỉ log lỗi quan trọng, bỏ qua lỗi thông thường (blocked, not found)
                        if not isinstance(result, (TelegramForbiddenError, TelegramBadRequest)):
                            print(f"⚠️ Failed to send to {chat_id}: {type(result).__name__}")
                    else:
                        success_count += 1
                
                # Delay giữa các batch (trừ batch cuối)
                if batch_end < len(chat_ids):
                    await asyncio.sleep(delay_between_batches)
            
            print(f"✅ Broadcast completed: {success_count} success, {failed_count} failed")
            return {
                "success_count": success_count,
                "failed_count": failed_count,
                "blocked_count": blocked_count,
            }
        finally:
            await bot.session.close()
    except Exception as e:
        # Log lỗi và raise để caller xử lý
        print(f"❌ Error in broadcast_message: {e}")
        import traceback
        traceback.print_exc()
        raise


async def _broadcast_stock_update(product_id: int, product_name: str, added_stock: int, total_stock: int):
    """
    Gửi thông báo cập nhật stock cho tất cả users.
    Tối ưu với batch processing và rate limiting để tránh nghẽn.
    """
    try:
        # Tạo message theo format trong ảnh (tiếng Anh)
        message = (
            "📦 <b>UPDATE STOCK</b>\n\n"
            f"🏷️ Product: {product_name}\n"
            f"➕ Added: {added_stock} stock\n"
            f"📊 Total stock: {total_stock}"
        )
        
        # Lấy danh sách tất cả users có telegram_id
        db_session = SessionLocal()
        try:
            users = db_session.query(User).filter(User.telegram_id.isnot(None)).all()
            chat_ids = [u.telegram_id for u in users if u.telegram_id]
        finally:
            db_session.close()
        
        if not chat_ids:
            print("⚠️ No users to broadcast")
            return
        
        await _broadcast_message(chat_ids, message)
    except Exception as e:
        # Log lỗi nhưng không throw để không block request
        print(f"❌ Error in broadcast_stock_update: {e}")


def _get_users_by_target(db: Session, target: str):
    """Lấy danh sách users theo filter target"""
    if target == "positive_balance":
        query = db.query(User).filter(User.balance > 0)
    elif target == "has_orders":
        query = (
            db.query(User)
            .join(Order, Order.user_id == User.id)
            .group_by(User.id)
        )
    elif target == "no_orders":
        has_order_ids = db.query(Order.user_id).distinct()
        query = db.query(User).filter(~User.id.in_(has_order_ids))
    else:  # "all" hoặc bất kỳ giá trị nào khác
        query = db.query(User)
    return query.order_by(User.id.asc()).all()


@app.get("/broadcast", response_class=HTMLResponse)
def broadcast_form(request: Request):
    return templates.TemplateResponse(
        "broadcast.html",
        {"request": request, "result": None, "send_result": None},
    )


@app.post("/broadcast", response_class=HTMLResponse)
def broadcast_generate(
    request: Request,
    db: DbDep,
    message: str = Form(...),
    target: str = Form("all"),
    action: str = Form("generate"),  # "generate" hoặc "send"
):
    """
    Tạo file danh sách user hoặc gửi broadcast trực tiếp.
    - action="generate": tạo file (như cũ)
    - action="send": gửi trực tiếp qua bot
    """
    users = _get_users_by_target(db, target)
    ids = [u.telegram_id for u in users if u.telegram_id]  # Lọc None/NULL telegram_id
    
    # Debug: Log số lượng users
    print(f"📊 Broadcast target: {target}, Found {len(ids)} users")
    
    if action == "send":
        # Gửi trực tiếp qua bot với batch processing (giống như update stocks)
        try:
            # Chạy async broadcast với batch processing
            async def send_broadcast():
                start_time = time.time()
                try:
                    result = await _broadcast_message(ids, message)
                    elapsed = time.time() - start_time
                    return {
                        "success": True,
                        "total": len(ids),
                        "success_count": result["success_count"],
                        "failed_count": result["failed_count"],
                        "blocked_count": result["blocked_count"],
                        "elapsed": elapsed,
                    }
                except Exception as e:
                    error_msg = str(e)
                    # Kiểm tra nếu là lỗi BOT_TOKEN
                    if "BOT_TOKEN" in error_msg or "Unauthorized" in error_msg:
                        apitele_env = os.path.join(project_root, "APITELE", ".env")
                        raise Exception(
                            "❌ BOT_TOKEN không hợp lệ hoặc đã hết hạn!\n\n"
                            "Nguyên nhân có thể:\n"
                            "1. Token bị sai/không đúng format\n"
                            "2. Bot đã bị xóa/vô hiệu hóa trên @BotFather\n"
                            "3. Token đã bị reset và cần lấy lại\n\n"
                            f"Kiểm tra file: {apitele_env}\n"
                            "Và lấy token mới từ @BotFather trên Telegram"
                        )
                    raise
            
            send_result = asyncio.run(send_broadcast())
            
            return templates.TemplateResponse(
                "broadcast.html",
                {
                    "request": request,
                    "result": None,
                    "send_result": send_result,
                },
            )
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            return templates.TemplateResponse(
                "broadcast.html",
                {
                    "request": request,
                    "result": None,
                    "send_result": {"success": False, "error": error_msg},
                },
            )
    else:
        # Generate file (như cũ)
        ids_str = [str(tid) for tid in ids]
        out_path = os.path.join(base_dir, "broadcast_recipients.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ids_str))

        result = {
            "count": len(ids),
            "file": out_path,
            "message": message,
        }
        return templates.TemplateResponse(
            "broadcast.html",
            {"request": request, "result": result, "send_result": None},
        )


# ── Seller API Key Management ────────────────────────────────────────────


def _mask_api_key(key: str) -> str:
    """sk_live_****xxxx — chi hien 4 ky tu cuoi."""
    if len(key) > 12:
        return key[:8] + "****" + key[-4:]
    return key[:4] + "****"


@app.get("/sellers", response_class=HTMLResponse)
def sellers_list(request: Request, db: DbDep):
    keys = list_keys(db)
    # Them balance tu user
    user_ids = [k["user_id"] for k in keys]
    users_map = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u for u in users}
    for k in keys:
        u = users_map.get(k["user_id"])
        k["balance"] = float(u.balance) if u else 0
        k["masked_key"] = _mask_api_key(k["api_key"])
    return templates.TemplateResponse(
        "sellers_list.html",
        {"request": request, "keys": keys},
    )


@app.post("/sellers/create")
def sellers_create(
    request: Request,
    db: DbDep,
    telegram_id: int = Form(...),
    note: str = Form(""),
):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        db.rollback()
        keys = list_keys(db)
        for k in keys:
            k["masked_key"] = _mask_api_key(k["api_key"])
            k["balance"] = 0
        return templates.TemplateResponse(
            "sellers_list.html",
            {
                "request": request,
                "keys": keys,
                "error": f"Khong tim thay user voi Telegram ID: {telegram_id}",
            },
        )
    try:
        result = generate_key_for_user(db, user.id, note=note or None)
        db.commit()
    except Exception as e:
        db.rollback()
        keys = list_keys(db)
        for k in keys:
            k["masked_key"] = _mask_api_key(k["api_key"])
            k["balance"] = 0
        return templates.TemplateResponse(
            "sellers_list.html",
            {"request": request, "keys": keys, "error": str(e)},
        )
    # Luu secret vao session (chi hien 1 lan)
    request.session["seller_secret"] = result["api_secret"]
    request.session["seller_key_id"] = result["key_id"]
    return RedirectResponse(
        url=f"/sellers/{result['key_id']}/credentials", status_code=303
    )


@app.get("/sellers/{key_id}/credentials", response_class=HTMLResponse)
def seller_credentials(request: Request, key_id: int, db: DbDep):
    row = db.query(SellerApiKey, User).join(User, SellerApiKey.user_id == User.id).filter(SellerApiKey.id == key_id).first()
    if not row:
        return RedirectResponse(url="/sellers", status_code=303)
    key, user = row

    # Lay secret tu session (chi co sau create/rotate)
    api_secret = request.session.pop("seller_secret", None)
    session_key_id = request.session.pop("seller_key_id", None)

    return templates.TemplateResponse(
        "seller_credentials.html",
        {
            "request": request,
            "key": key,
            "user": user,
            "api_secret": api_secret if session_key_id == key_id else None,
        },
    )


@app.post("/sellers/{key_id}/rotate")
def seller_rotate(request: Request, key_id: int, db: DbDep):
    try:
        result = rotate_key(db, key_id)
        db.commit()
    except ValueError as e:
        db.rollback()
        return RedirectResponse(url="/sellers", status_code=303)
    request.session["seller_secret"] = result["api_secret"]
    request.session["seller_key_id"] = result["key_id"]
    return RedirectResponse(
        url=f"/sellers/{result['key_id']}/credentials", status_code=303
    )


@app.post("/sellers/{key_id}/revoke")
def seller_revoke(request: Request, key_id: int, db: DbDep):
    try:
        revoke_key(db, key_id)
        db.commit()
    except ValueError:
        db.rollback()
    return RedirectResponse(url="/sellers", status_code=303)


@app.get("/sellers/api-doc", response_class=HTMLResponse)
def seller_api_doc(request: Request):
    return templates.TemplateResponse(
        "seller_api_doc.html",
        {"request": request},
    )


@app.get("/sellers/api-doc/download")
def seller_api_doc_download(request: Request):
    """Tải file API Documentation standalone HTML cho seller."""
    html_path = os.path.join(base_dir, "templates", "seller_api_doc_standalone.html")
    return FileResponse(
        html_path,
        media_type="text/html",
        filename="Seller_API_Documentation.html",
    )


@app.get("/sellers/sdk-download")
def seller_sdk_download(
    request: Request,
    api_key: str = "",
    api_secret: str = "",
):
    """Tải file seller_sdk.py với api_key và api_secret đã điền sẵn."""
    sdk_path = os.path.join(os.path.dirname(base_dir), "seller_sdk.py")
    with open(sdk_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Thay placeholder bằng key/secret thật nếu có
    if api_key:
        content = content.replace('api_key="sk_live_xxx"', f'api_key="{api_key}"')
        content = content.replace("api_key='sk_live_xxx'", f"api_key='{api_key}'")
    if api_secret:
        content = content.replace('api_secret="xxx"', f'api_secret="{api_secret}"')
        content = content.replace("api_secret='xxx'", f"api_secret='{api_secret}'")

    return Response(
        content=content,
        media_type="text/x-python",
        headers={"Content-Disposition": 'attachment; filename="seller_sdk.py"'},
    )


if __name__ == "__main__":
    import uvicorn

    # reload=True dễ gây process/reloader thoát sạch (exit 0) khi chạy qua setsid/nohup/supervisor → mất cổng 8001.
    # Chỉ bật khi dev: ADMINWEB_RELOAD=1
    _reload = os.getenv("ADMINWEB_RELOAD", "").strip().lower() in ("1", "true", "yes")
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=_reload)


