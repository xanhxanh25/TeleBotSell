"""
Input sanitisation middleware.

Inspects incoming request bodies and query parameters for common
injection patterns:
  - SQL injection fragments
  - XSS / script injection
  - Path traversal (../)
  - Command injection metacharacters
  - Null-byte injection

If a suspicious pattern is detected the request is rejected with 400
*before* it reaches any route handler.

Design notes:
  - Pattern matching uses simple string checks (no regex engine overhead
    on every request).  This is a defense-in-depth layer, NOT a WAF
    replacement.  Application-level validation (Pydantic schemas,
    parameterised queries) remains the primary defense.
  - Only JSON bodies and query strings are inspected.
  - Binary uploads (multipart/form-data) are skipped.
"""
from __future__ import annotations

import logging
import re
from typing import Pattern

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

log = logging.getLogger("input_sanitizer")

# ── Pattern definitions ────────────────────────────────────

# SQL injection indicators (case-insensitive)
_SQL_PATTERNS: list[Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(\b(UNION\s+(ALL\s+)?SELECT)\b)",
        r"(\b(SELECT\s+.+\s+FROM)\b)",
        r"(\b(INSERT\s+INTO)\b)",
        r"(\b(UPDATE\s+\w+\s+SET)\b)",
        r"(\b(DELETE\s+FROM)\b)",
        r"(\b(DROP\s+(TABLE|DATABASE))\b)",
        r"(\b(ALTER\s+TABLE)\b)",
        r"(--\s)",                              # SQL comment
        r"(;\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC))",
        r"('\s*(OR|AND)\s+'?\d*'?\s*=\s*'?\d*)",  # ' OR '1'='1
        r"('\s*(OR|AND)\s+\d+\s*=\s*\d+)",
    ]
]

# XSS / script injection
_XSS_PATTERNS: list[Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"<script[\s>]",
        r"javascript\s*:",
        r"on(error|load|click|mouseover|focus|blur)\s*=",
        r"<iframe[\s>]",
        r"<object[\s>]",
        r"<embed[\s>]",
        r"<svg[\s/].*?on\w+\s*=",
        r"expression\s*\(",
        r"url\s*\(\s*['\"]?\s*javascript:",
    ]
]

# Path traversal
_PATH_TRAVERSAL = re.compile(r"(\.\.[\\/])")

# Command injection meta-characters in a suspicious context
_CMD_INJECTION = re.compile(r"[;|`$]|\$\(|\b(&&|\|\|)\b")

# Null-byte
_NULL_BYTE = re.compile(r"%00|\x00")


def _check_value(value: str) -> str | None:
    """
    Return the name of the first matched threat category, or None if clean.
    """
    for pat in _SQL_PATTERNS:
        if pat.search(value):
            return "SQL_INJECTION"

    for pat in _XSS_PATTERNS:
        if pat.search(value):
            return "XSS_INJECTION"

    if _PATH_TRAVERSAL.search(value):
        return "PATH_TRAVERSAL"

    if _NULL_BYTE.search(value):
        return "NULL_BYTE_INJECTION"

    # Command injection — only flag on longer strings to reduce false positives
    if len(value) > 3 and _CMD_INJECTION.search(value):
        return "CMD_INJECTION"

    return None


def _scan_dict(data: dict | list | str, depth: int = 0) -> str | None:
    """Recursively scan a parsed JSON structure."""
    if depth > 10:
        return None
    if isinstance(data, str):
        return _check_value(data)
    if isinstance(data, dict):
        for k, v in data.items():
            threat = _check_value(str(k))
            if threat:
                return threat
            threat = _scan_dict(v, depth + 1)
            if threat:
                return threat
    if isinstance(data, list):
        for item in data:
            threat = _scan_dict(item, depth + 1)
            if threat:
                return threat
    return None


class InputSanitizerMiddleware(BaseHTTPMiddleware):
    """
    Reject requests whose body or query string contains injection patterns.
    """

    # Skip binary uploads
    _SKIP_CONTENT_TYPES = frozenset({"multipart/form-data"})

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        ip = request.client.host if request.client else "0.0.0.0"

        # ── Check query parameters ──────────────────────
        for key, value in request.query_params.items():
            threat = _check_value(key)
            if not threat:
                threat = _check_value(value)
            if threat:
                log.warning(
                    "Blocked %s in query: ip=%s path=%s param=%s",
                    threat, ip, request.url.path, key,
                )
                return JSONResponse(
                    status_code=400,
                    content={"detail": "INVALID_INPUT", "reason": threat},
                )

        # ── Check JSON body ─────────────────────────────
        content_type = (request.headers.get("content-type") or "").lower()
        if any(ct in content_type for ct in self._SKIP_CONTENT_TYPES):
            return await call_next(request)

        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                if body and (b"{" in body or b"[" in body):
                    import json as _json
                    data = _json.loads(body)
                    threat = _scan_dict(data)
                    if threat:
                        log.warning(
                            "Blocked %s in body: ip=%s path=%s",
                            threat, ip, request.url.path,
                        )
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "INVALID_INPUT", "reason": threat},
                        )
            except (ValueError, UnicodeDecodeError):
                # Not valid JSON — let downstream handle it
                pass

        return await call_next(request)
