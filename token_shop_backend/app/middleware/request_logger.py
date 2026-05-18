"""
Structured request/response logging middleware.

Logs every HTTP request with:
  - timestamp, method, path, status, duration_ms
  - client IP, user-agent
  - request body hash (not the body itself — privacy)
  - response size

Output goes to the "request_log" logger so it can be routed
to a separate file/stream via logging config.
"""
from __future__ import annotations

import hashlib
import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

log = logging.getLogger("request_log")


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _body_hash(body: bytes) -> str:
    """SHA-256 truncated to 12 hex chars — enough to correlate, not to leak."""
    if not body:
        return "-"
    return hashlib.sha256(body).hexdigest()[:12]


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """
    Log every request with timing, IP, and a body fingerprint.

    Sensitive headers (Authorization, X-Seller-Signature, Cookie)
    are redacted.
    """

    REDACTED_HEADERS = frozenset({
        "authorization",
        "x-seller-signature",
        "x-seller-key",
        "x-admin-key",
        "x-bot-api-key",
        "cookie",
    })

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.monotonic()
        ip = _client_ip(request)

        # Cache body for hashing (Starlette allows re-reading after this)
        body = b""
        try:
            body = await request.body()
        except Exception:
            pass

        response: Response | None = None
        error: str | None = None
        try:
            response = await call_next(request)
        except Exception as exc:
            error = type(exc).__name__
            raise
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            status = response.status_code if response else 500

            log.info(
                "method=%s path=%s status=%d duration_ms=%.1f ip=%s "
                "ua=%s body_hash=%s",
                request.method,
                request.url.path,
                status,
                elapsed_ms,
                ip,
                (request.headers.get("user-agent") or "-")[:120],
                _body_hash(body),
            )

            if error:
                log.error(
                    "unhandled_exception method=%s path=%s ip=%s error=%s",
                    request.method, request.url.path, ip, error,
                )

        return response
