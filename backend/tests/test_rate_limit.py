"""Rate limiting on sensitive endpoints (plan Phase 3)."""

from __future__ import annotations

from app.config import get_settings
from app.core.ratelimit import LIMITS, reset_limits


def test_login_rate_limited_after_threshold(client):
    reset_limits()
    original = LIMITS["auth.login"]
    LIMITS["auth.login"] = 2
    try:
        get_settings().rate_limit_enabled = True
        for _ in range(2):
            resp = client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "wrong-password"},
            )
            assert resp.status_code in (401, 429)
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 429
        assert "rate limit exceeded" in resp.json()["detail"]
    finally:
        LIMITS["auth.login"] = original
        get_settings().rate_limit_enabled = False
        reset_limits()


def test_rate_limit_scopes_registered():
    for scope in (
        "auth.register",
        "auth.login",
        "auth.refresh",
        "documents.upload",
        "simulations.start",
        "simulations.hitl",
        "reviews.create",
        "reviews.publish",
        "reviews.qna",
        "exports.get",
    ):
        assert scope in LIMITS, scope
        assert LIMITS[scope] > 0, scope
