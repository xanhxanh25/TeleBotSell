"""
Log request latency; giúp tìm endpoint chậm trên production (LOG_LEVEL=INFO).
"""
from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

log = logging.getLogger("request_timing")

# Chỉ log khi chậm hơn ngưỡng (ms) để không spam
SLOW_MS = 400


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
            return response
        finally:
            ms = (time.perf_counter() - t0) * 1000.0
            if ms >= SLOW_MS:
                log.info(
                    "%s %s %.1fms",
                    request.method,
                    request.url.path,
                    ms,
                )
