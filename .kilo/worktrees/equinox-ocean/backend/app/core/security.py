"""Security primitives: password hashing, JWT create/verify, refresh rotation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_token(
    subject: str, token_type: str, minutes: int, extra: dict | None = None
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "jti": bcrypt.gensalt(4).decode()[:16],
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: str, extra: dict | None = None) -> str:
    s = get_settings()
    return create_token(subject, "access", s.access_token_minutes, extra)


def create_refresh_token(subject: str, extra: dict | None = None) -> str:
    s = get_settings()
    return create_token(subject, "refresh", s.refresh_token_minutes, extra)


def decode_token(token: str, expected_type: str | None = None) -> dict:
    s = get_settings()
    payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return payload


def rotate_refresh(subject: str, extra: dict | None = None) -> str:
    """Refresh token rotation: each refresh issues a brand new token (PRD §15.5)."""
    s = get_settings()
    return create_token(subject, "refresh", s.refresh_token_minutes, extra)
