"""Parse backend API errors from HttpClient RuntimeError strings."""
from __future__ import annotations

import ast
import json
import re
from typing import Any


def extract_error_code_from_http_runtime(msg: str) -> str | None:
    """
    HttpClient raises: http_error:<status>:<payload>
    FastAPI JSON body often: {"detail": {"code": "COUPON_WRONG_PRODUCT"}}
    or {"detail": "OUT_OF_STOCK"}.
    """
    if not msg.startswith("http_error:"):
        return None
    parts = msg.split(":", 2)
    if len(parts) < 3:
        return None
    raw = parts[2].strip()
    data: Any = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return None
    if not isinstance(data, dict):
        return None
    detail = data.get("detail")
    if isinstance(detail, dict) and "code" in detail:
        c = detail.get("code")
        return str(c) if c is not None else None
    if isinstance(detail, str):
        m = re.match(r"^([A-Z][A-Z0-9_]+)$", detail.strip())
        if m:
            return m.group(1)
    return None
