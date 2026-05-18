"""
HTTP-level security middleware for the Seller API and general backend.

Components:
  - RateLimiter:          sliding-window per-IP rate limiting
  - IPFirewall:           allowlist / blocklist by IP or CIDR
  - DDoSDetector:         detect abnormal request bursts (global)
  - BruteForceProtector:  lock out IPs after N consecutive auth failures

All state is in-memory (dict/deque) — suitable for single-process deploys.
For multi-process / multi-node, swap with Redis-backed stores.
"""
from __future__ import annotations

import ipaddress
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Callable, Sequence

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

log = logging.getLogger("firewall")


# ═══════════════════════════════════════════════════════════
#  RateLimiter — sliding-window per-IP
# ═══════════════════════════════════════════════════════════

class RateLimiter:
    """
    Track request timestamps per IP in a sliding window.
    Thread-safe via a global lock (lightweight — no per-IP lock needed
    because critical section is O(1) amortised).
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, ip: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[ip]
            while q and (now - q[0]) > self.window:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            return True

    def remaining(self, ip: str) -> int:
        now = time.monotonic()
        with self._lock:
            q = self._hits[ip]
            while q and (now - q[0]) > self.window:
                q.popleft()
            return max(0, self.max_requests - len(q))

    def reset(self, ip: str) -> None:
        with self._lock:
            self._hits.pop(ip, None)

    def cleanup_stale(self, max_age: float = 300.0) -> int:
        """Remove IPs with no hits in the last *max_age* seconds."""
        now = time.monotonic()
        removed = 0
        with self._lock:
            stale = [
                ip for ip, q in self._hits.items()
                if not q or (now - q[-1]) > max_age
            ]
            for ip in stale:
                del self._hits[ip]
                removed += 1
        return removed


# ═══════════════════════════════════════════════════════════
#  IPFirewall — allowlist / blocklist
# ═══════════════════════════════════════════════════════════

class IPFirewall:
    """
    Block or allow requests based on IP address.

    - If *allowlist* is non-empty, only those IPs/CIDRs are permitted.
    - *blocklist* is always checked; blocked IPs are rejected even if
      they match the allowlist.
    - Dynamic blocking via `block()` / `unblock()`.
    """

    def __init__(
        self,
        allowlist: Sequence[str] | None = None,
        blocklist: Sequence[str] | None = None,
    ):
        self._static_allow: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        self._static_block: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        self._dynamic_block: set[str] = set()
        self._lock = threading.Lock()

        for cidr in (allowlist or []):
            self._static_allow.append(ipaddress.ip_network(cidr, strict=False))
        for cidr in (blocklist or []):
            self._static_block.append(ipaddress.ip_network(cidr, strict=False))

    def _match(self, ip_str: str, nets: list) -> bool:
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        return any(addr in net for net in nets)

    def is_blocked(self, ip: str) -> bool:
        with self._lock:
            if ip in self._dynamic_block:
                return True
        if self._match(ip, self._static_block):
            return True
        if self._static_allow and not self._match(ip, self._static_allow):
            return True
        return False

    def block(self, ip: str) -> None:
        with self._lock:
            self._dynamic_block.add(ip)
        log.warning("IP dynamically blocked: %s", ip)

    def unblock(self, ip: str) -> None:
        with self._lock:
            self._dynamic_block.discard(ip)
        log.info("IP unblocked: %s", ip)

    def blocked_ips(self) -> list[str]:
        with self._lock:
            return list(self._dynamic_block)


# ═══════════════════════════════════════════════════════════
#  DDoSDetector — global burst detection
# ═══════════════════════════════════════════════════════════

class DDoSDetector:
    """
    Track total requests across all IPs in a short window.
    If the global rate exceeds *threshold* in *window_seconds*, flag alert.
    Useful to trigger protective measures (e.g. enable stricter rate limits).
    """

    def __init__(self, threshold: int = 500, window_seconds: int = 10):
        self.threshold = threshold
        self.window = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()
        self._alert_active = False

    def record(self) -> bool:
        """Record a request. Returns True if under DDoS alert."""
        now = time.monotonic()
        with self._lock:
            self._timestamps.append(now)
            while self._timestamps and (now - self._timestamps[0]) > self.window:
                self._timestamps.popleft()
            count = len(self._timestamps)
            if count >= self.threshold:
                if not self._alert_active:
                    log.critical(
                        "DDoS alert: %d requests in %ds (threshold=%d)",
                        count, self.window, self.threshold,
                    )
                self._alert_active = True
                return True
            self._alert_active = False
            return False

    @property
    def is_alert(self) -> bool:
        return self._alert_active

    @property
    def current_count(self) -> int:
        now = time.monotonic()
        with self._lock:
            while self._timestamps and (now - self._timestamps[0]) > self.window:
                self._timestamps.popleft()
            return len(self._timestamps)


# ═══════════════════════════════════════════════════════════
#  BruteForceProtector — lock out after N auth failures
# ═══════════════════════════════════════════════════════════

class BruteForceProtector:
    """
    Track consecutive authentication failures per IP.
    After *max_failures* within *window_seconds*, block the IP
    for *lockout_seconds*.
    """

    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: int = 300,
        lockout_seconds: int = 900,
    ):
        self.max_failures = max_failures
        self.window = window_seconds
        self.lockout = lockout_seconds
        # ip -> deque of failure timestamps
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        # ip -> lockout expiry (monotonic)
        self._locked: dict[str, float] = {}
        self._lock = threading.Lock()

    def record_failure(self, ip: str) -> bool:
        """Record an auth failure. Returns True if IP is now locked out."""
        now = time.monotonic()
        with self._lock:
            q = self._failures[ip]
            q.append(now)
            while q and (now - q[0]) > self.window:
                q.popleft()
            if len(q) >= self.max_failures:
                self._locked[ip] = now + self.lockout
                self._failures.pop(ip, None)
                log.warning(
                    "Brute-force lockout: ip=%s failures=%d lockout=%ds",
                    ip, self.max_failures, self.lockout,
                )
                return True
            return False

    def record_success(self, ip: str) -> None:
        """Clear failure counter on successful auth."""
        with self._lock:
            self._failures.pop(ip, None)

    def is_locked(self, ip: str) -> bool:
        now = time.monotonic()
        with self._lock:
            expiry = self._locked.get(ip)
            if expiry is None:
                return False
            if now >= expiry:
                del self._locked[ip]
                return False
            return True

    def lockout_remaining(self, ip: str) -> float:
        now = time.monotonic()
        with self._lock:
            expiry = self._locked.get(ip, 0)
            return max(0.0, expiry - now)

    def unlock(self, ip: str) -> None:
        with self._lock:
            self._locked.pop(ip, None)
            self._failures.pop(ip, None)

    def cleanup_expired(self) -> int:
        now = time.monotonic()
        removed = 0
        with self._lock:
            expired = [ip for ip, exp in self._locked.items() if now >= exp]
            for ip in expired:
                del self._locked[ip]
                removed += 1
        return removed


# ═══════════════════════════════════════════════════════════
#  Combined ASGI Middleware
# ═══════════════════════════════════════════════════════════

def _client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a trusted proxy."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


# Singleton instances — import these to share state across the app
rate_limiter = RateLimiter(max_requests=60, window_seconds=60)
ip_firewall = IPFirewall()
ddos_detector = DDoSDetector(threshold=500, window_seconds=10)
brute_force = BruteForceProtector(max_failures=5, window_seconds=300, lockout_seconds=900)


# ═══════════════════════════════════════════════════════════
#  FastAPI dependency — route-level firewall check
# ═══════════════════════════════════════════════════════════

def check_firewall(request: Request) -> None:
    """
    FastAPI dependency that enforces firewall rules at the route level.
    Defense-in-depth: works even if the middleware is not mounted.
    Raises HTTPException on violation.
    """
    from fastapi import HTTPException

    ip = _client_ip(request)

    if ip_firewall.is_blocked(ip):
        log.warning("Blocked IP rejected (dep): %s %s", ip, request.url.path)
        raise HTTPException(
            status_code=403,
            detail="IP_BLOCKED",
        )

    if brute_force.is_locked(ip):
        remaining = int(brute_force.lockout_remaining(ip))
        raise HTTPException(
            status_code=429,
            detail="LOCKED_OUT",
            headers={"Retry-After": str(remaining)},
        )

    if not rate_limiter.is_allowed(ip):
        raise HTTPException(
            status_code=429,
            detail="RATE_LIMITED",
            headers={"Retry-After": str(rate_limiter.window)},
        )


class FirewallMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that chains all four protections:
      1. IP blocklist check
      2. Brute-force lockout check
      3. DDoS global burst detection
      4. Per-IP rate limit
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        ip = _client_ip(request)

        # 1) IP firewall
        if ip_firewall.is_blocked(ip):
            log.warning("Blocked IP rejected: %s %s", ip, request.url.path)
            return JSONResponse(
                status_code=403,
                content={"detail": "IP_BLOCKED"},
            )

        # 2) Brute-force lockout
        if brute_force.is_locked(ip):
            remaining = int(brute_force.lockout_remaining(ip))
            return JSONResponse(
                status_code=429,
                content={"detail": "LOCKED_OUT", "retry_after": remaining},
                headers={"Retry-After": str(remaining)},
            )

        # 3) DDoS detection (record + check)
        if ddos_detector.record():
            # Under DDoS alert — tighten rate limit to 10 req/min
            if rate_limiter.remaining(ip) < (rate_limiter.max_requests - 10):
                return JSONResponse(
                    status_code=503,
                    content={"detail": "SERVICE_OVERLOADED"},
                    headers={"Retry-After": "30"},
                )

        # 4) Per-IP rate limit
        if not rate_limiter.is_allowed(ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "RATE_LIMITED"},
                headers={"Retry-After": str(rate_limiter.window)},
            )

        response = await call_next(request)

        # Track auth failures for brute-force detection on seller auth endpoints
        if request.url.path.startswith("/seller/") and response.status_code == 401:
            brute_force.record_failure(ip)
        elif request.url.path.startswith("/seller/") and response.status_code == 200:
            brute_force.record_success(ip)

        return response
