from __future__ import annotations

import asyncio
import logging
from fastapi import FastAPI

from app.database import Base, engine, SessionLocal
from app.api import public, orders, topups, tokenpay_webhooks, tickets, admin, users
from app.routers import seller_api
from app.services.cleanup import cleanup_old_records, expire_pending_topups
from app.middlewares.request_timing import RequestTimingMiddleware
from app.middleware.firewall import FirewallMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.middleware.input_sanitizer import InputSanitizerMiddleware

log = logging.getLogger("backend")


def create_app() -> FastAPI:
    app = FastAPI(title="TeleShop Backend API", version="1.0.0")

    # Middleware stack (outermost first):
    # 1. Request timing (measures total)
    app.add_middleware(RequestTimingMiddleware)
    # 2. Request logger (structured logging)
    app.add_middleware(RequestLoggerMiddleware)
    # 3. Input sanitizer (block SQLi/XSS before hitting routes)
    app.add_middleware(InputSanitizerMiddleware)
    # 4. Firewall (rate limit, IP block, DDoS, brute-force)
    app.add_middleware(FirewallMiddleware)

    # routers
    app.include_router(public.router)
    app.include_router(orders.router)
    app.include_router(topups.router)
    app.include_router(tokenpay_webhooks.router)
    app.include_router(tickets.router)
    app.include_router(admin.router)
    app.include_router(users.router)
    app.include_router(seller_api.router)

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.on_event("startup")
    async def startup():
        # create tables (MVP). Khi làm webadmin lớn, bạn chuyển sang Alembic migration.
        Base.metadata.create_all(bind=engine)

        # background cleanup mỗi 24h
        async def _loop_cleanup():
            while True:
                db = SessionLocal()
                try:
                    with db.begin():
                        res = cleanup_old_records(db)
                    log.info("cleanup: %s", res)
                except Exception as e:
                    log.warning("cleanup_error: %s", e)
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass
                await asyncio.sleep(24 * 3600)

        # ✅ background expire pending topups mỗi 60s (pending quá 30 phút => EXPIRED)
        async def _loop_expire_pending_topups():
            while True:
                db = SessionLocal()
                try:
                    with db.begin():
                        res = expire_pending_topups(db, minutes=30)
                    # chỉ log khi có thay đổi để đỡ spam
                    if res.get("canceled", 0) > 0:
                        log.info("expire_pending_topups: %s", res)
                except Exception as e:
                    log.warning("expire_pending_topups_error: %s", e)
                finally:
                    try:
                        db.close()
                    except Exception:
                        pass
                await asyncio.sleep(60)

        asyncio.create_task(_loop_cleanup())
        asyncio.create_task(_loop_expire_pending_topups())

    return app


app = create_app()
