"""Authentication service: registration, login, refresh rotation, logout.

Form-based auth (PRD §6.1 P1). Auth providers are pluggable behind a provider
function registry so Keycloak OIDC can replace the form flow without changing
callers.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.errors import UnauthorizedError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    rotate_refresh,
    verify_password,
)
from app.models import Organization, RefreshToken, User, UserRole

logger = logging.getLogger(__name__)


def _refresh_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def register_user(
    *,
    email: str,
    password: str,
    full_name: str,
    organization_name: str,
    platform_role: str | None = None,
    module_roles: list[str] | None = None,
    db: Session,
) -> dict:
    email = email.strip().lower()
    if not email or not password:
        raise ValidationError("email and password are required")
    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing:
        raise ValidationError("a user with this email already exists")

    organization_name = (organization_name or "").strip() or "Default Organization"
    org = (
        db.query(Organization)
        .filter(Organization.name == organization_name)
        .one_or_none()
    )
    if org is None:
        is_new_org = True
        org = Organization(
            id=uuid.uuid4().hex,
            name=organization_name,
            settings={},
            subscription_tier="free",
        )
        db.add(org)
        db.flush()
    else:
        is_new_org = False

    if platform_role is None:
        platform_role = "org_admin" if is_new_org else "member"
    if module_roles is None:
        module_roles = (
            [
                "sim.sim_educator",
                "review.review_lead",
                "hub.knowledge_curator",
                "sim.sim_researcher",
                "hub.knowledge_analyst",
            ]
            if is_new_org
            else []
        )

    user = User(
        id=uuid.uuid4().hex,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        is_active=True,
        profile={"registered": True},
    )
    db.add(user)
    db.flush()
    db.add(
        UserRole(
            id=uuid.uuid4().hex,
            user_id=user.id,
            organization_id=org.id,
            platform_role=platform_role,
            module_roles=module_roles,
            is_default=True,
        )
    )
    db.commit()
    return {"user_id": user.id, "email": user.email, "organization_id": org.id}


def _issue_tokens(user: User, membership: UserRole, db: Session) -> dict:
    access = create_access_token(
        user.id,
        extra={
            "org": membership.organization_id,
            "platform_role": membership.platform_role,
            "module_roles": membership.module_roles,
        },
    )
    refresh = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            id=uuid.uuid4().hex,
            user_id=user.id,
            token_hash=_refresh_hash(refresh),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=_refresh_minutes(db)),
        )
    )
    db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",  # nosec B105 - OAuth2 RFC 6750 scheme literal, not a password
        "user": _user_payload(user, membership),
    }


def _refresh_minutes(db: Session) -> int:
    from app.config import get_settings

    return get_settings().refresh_token_minutes


def login(email: str, password: str, db: Session) -> dict:
    user = db.query(User).filter(User.email == email.strip().lower()).one_or_none()
    if (
        user is None
        or not user.password_hash
        or not verify_password(password, user.password_hash)
    ):
        raise UnauthorizedError("invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("account is disabled")
    membership = (
        db.query(UserRole)
        .filter(UserRole.user_id == user.id, UserRole.is_default == True)
        .first()
    )
    if membership is None:
        membership = db.query(UserRole).filter(UserRole.user_id == user.id).first()
    if membership is None:
        raise UnauthorizedError("user has no organization membership")
    return _issue_tokens(user, membership, db)


def refresh(refresh_token: str, db: Session) -> dict:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except Exception:
        raise UnauthorizedError("invalid refresh token")
    token_hash = _refresh_hash(refresh_token)
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .one_or_none()
    )
    if record is None or record.revoked:
        raise UnauthorizedError("refresh token has been revoked or rotated")
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise UnauthorizedError("refresh token expired")
    user = db.query(User).filter(User.id == payload["sub"]).one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("user not found or disabled")
    membership = (
        db.query(UserRole)
        .filter(UserRole.user_id == user.id, UserRole.is_default == True)
        .first()
    )
    if membership is None:
        membership = db.query(UserRole).filter(UserRole.user_id == user.id).first()
    # rotate: revoke old token and issue a new one
    record.revoked = True
    new_refresh = rotate_refresh(user.id)
    db.add(
        RefreshToken(
            id=uuid.uuid4().hex,
            user_id=user.id,
            token_hash=_refresh_hash(new_refresh),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=_refresh_minutes(db)),
        )
    )
    db.commit()
    return {
        "access_token": create_access_token(
            user.id,
            extra={
                "org": membership.organization_id if membership else "",
                "platform_role": membership.platform_role if membership else "member",
                "module_roles": membership.module_roles if membership else [],
            },
        ),
        "refresh_token": new_refresh,
        "token_type": "bearer",  # nosec B105 - OAuth2 RFC 6750 scheme literal, not a password
        "user": _user_payload(user, membership),
    }


def logout(refresh_token: str, db: Session) -> None:
    record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == _refresh_hash(refresh_token))
        .one_or_none()
    )
    if record:
        record.revoked = True
        db.commit()


def _user_payload(user: User, membership: UserRole | None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "organization_id": membership.organization_id if membership else None,
        "platform_role": membership.platform_role if membership else "member",
        "module_roles": membership.module_roles if membership else [],
    }
