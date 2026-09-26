"""Authentication endpoints (PRD §6.1)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.deps import CurrentUser, get_current_user
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    full_name: str = ""
    organization_name: str = "Default Organization"
    platform_role: str | None = None
    module_roles: list[str] | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/register", status_code=201)
def register(
    req: RegisterRequest,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth.register")),
) -> dict:
    try:
        result = auth_service.register_user(
            email=req.email,
            password=req.password,
            full_name=req.full_name,
            organization_name=req.organization_name,
            platform_role=req.platform_role,
            module_roles=req.module_roles,
            db=db,
        )
        tokens = auth_service.login(req.email, req.password, db)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    audit(
        db,
        action="register",
        actor=result["user_id"],
        organization_id=result["organization_id"],
    )
    result.update(tokens)
    return result


@router.post("/login")
def login(
    req: LoginRequest,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth.login")),
) -> dict:
    try:
        tokens = auth_service.login(req.email, req.password, db)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    audit(
        db,
        action="login",
        actor=tokens["user"]["id"],
        organization_id=tokens["user"]["organization_id"],
    )
    return tokens


@router.post("/refresh")
def refresh(
    req: RefreshRequest,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("auth.refresh")),
) -> dict:
    try:
        tokens = auth_service.refresh(req.refresh_token, db)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    audit(
        db,
        action="token_refresh",
        actor=tokens["user"]["id"],
        organization_id=tokens["user"]["organization_id"],
    )
    return tokens


@router.post("/logout")
def logout(req: LogoutRequest, db: Session = Depends(get_db)) -> dict:
    auth_service.logout(req.refresh_token, db)
    return {"ok": True}


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    profile: dict | None = None


@router.get("/me")
def me(
    user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    from app.models import Organization, User

    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    u = db.query(User).filter(User.id == user.id).first()
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name or (u.full_name if u else ""),
        "organization_id": user.organization_id,
        "organization": {
            "id": org.id,
            "name": org.name,
            "subscription_tier": org.subscription_tier,
            "settings": org.settings or {},
        }
        if org
        else None,
        "platform_role": user.platform_role,
        "module_roles": user.module_roles,
        "profile": u.profile if u else {},
        "now": datetime.now(timezone.utc).isoformat(),
    }


@router.patch("/profile")
def update_profile(
    req: ProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    from app.models import User

    u = db.query(User).filter(User.id == user.id).first()
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    if req.full_name is not None:
        u.full_name = req.full_name.strip()
    if req.profile is not None:
        curr = dict(u.profile or {})
        curr.update(req.profile)
        u.profile = curr
    db.commit()
    db.refresh(u)
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "profile": u.profile or {},
    }
