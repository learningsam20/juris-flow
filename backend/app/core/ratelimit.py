"""Sliding-window rate limiter (per scope + client key) for sensitive endpoints.

In-memory and single-process — appropriate for the default dev deployment.
For multi-worker production, move to a shared store (Redis/limits) at the
edge/proxy layer; the scopes below stay identical.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import get_settings

_limits: dict[str, deque[float]] = defaultdict(deque)
_limit_lock = threading.Lock()

# Scope -> requests allowed per window (default 60s).
# Endpoints read scopes by name so tests can tighten them.
LIMITS: dict[str, int] = {
    "auth.register": 5,
    "auth.login": 10,
    "auth.refresh": 30,
    "documents.upload": 10,
    "knowledge.ask": 20,
    "simulations.start": 20,
    "simulations.hitl": 60,
    "reviews.create": 10,
    "reviews.publish": 10,
    "reviews.qna": 30,
    "exports.get": 30,
}


def reset_limits() -> None:
    with _limit_lock:
        _limits.clear()


def rate_limit(scope: str, window: float = 60.0):
    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        limit = LIMITS.get(scope, 0)
        if limit <= 0:
            return
        key = f"{scope}:{request.client.host if request.client and request.client.host else 'anonymous'}"
        now = time.monotonic()
        with _limit_lock:
            bucket = _limits[key]
            while bucket and bucket[0] <= now - window:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=429, detail=f"rate limit exceeded: {scope}"
                )
            bucket.append(now)

    return dependency
