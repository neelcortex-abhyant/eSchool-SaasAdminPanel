"""In-process sliding-window rate limits for sensitive auth endpoints.

Counts live in this process only (same approach as school registration). With
several workers each counts separately, so the effective limit is higher; move
to a shared store (Redis) before relying on exact numbers.

The client IP is request.client.host. Behind a proxy that is the proxy's address
unless the server is started with trusted forwarded headers (uvicorn
--proxy-headers --forwarded-allow-ips=...). X-Forwarded-For is never read here,
because clients can set it.
"""

from __future__ import annotations

import math
import threading
import time

from fastapi import HTTPException, Request, status

TOO_MANY = "Too many attempts. Try again later."


class SlidingWindowLimiter:
    def __init__(self, name: str, limit: int, window_seconds: int):
        self.name = name
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        _LIMITERS.append(self)

    def _recent(self, key: str, now: float) -> list[float]:
        recent = [stamp for stamp in self._hits.get(key, []) if now - stamp < self.window]
        if recent:
            self._hits[key] = recent
        else:
            self._hits.pop(key, None)
        return recent

    def check(self, key: str) -> None:
        """Raise 429 when `key` already used up its limit. Does not count."""
        now = time.monotonic()
        with self._lock:
            recent = self._recent(key, now)
            if len(recent) >= self.limit:
                retry = max(1, math.ceil(self.window - (now - recent[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=TOO_MANY,
                    headers={"Retry-After": str(retry)},
                )

    def record(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._recent(key, now)
            self._hits.setdefault(key, []).append(now)

    def hit(self, key: str) -> None:
        """Check, then count this attempt."""
        self.check(key)
        self.record(key)

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


_LIMITERS: list[SlidingWindowLimiter] = []

# Failed logins (v1 shared login and Super Admin login), per email and per IP.
LOGIN_PER_EMAIL = SlidingWindowLimiter("login_email", limit=10, window_seconds=15 * 60)
LOGIN_PER_IP = SlidingWindowLimiter("login_ip", limit=50, window_seconds=15 * 60)
# Every forgot-password request, per email and per IP.
FORGOT_PER_EMAIL = SlidingWindowLimiter("forgot_email", limit=5, window_seconds=60 * 60)
FORGOT_PER_IP = SlidingWindowLimiter("forgot_ip", limit=20, window_seconds=60 * 60)
# Every reset-password attempt, per IP (tokens are unguessable; this stops scanning).
RESET_PER_IP = SlidingWindowLimiter("reset_ip", limit=10, window_seconds=15 * 60)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def reset_limits() -> None:
    """Clear every counter. For tests."""
    for limiter in _LIMITERS:
        limiter.reset()
