"""User and organization administration endpoints (PRD §6.5)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.deps import CurrentUser, get_current_user, require_role_any
from app.db.session import get_db
from app.models import Organization, User, UserRole

router = APIRouter(prefix="/users", tags=["users"])


class RoleAssign(BaseModel):
    organization_id: str
    platform_role: str = "member"
    module_roles: list[str] = []


@router.get("")
def list_users(
    user: CurrentUser = Depends(require_role_any("org_admin", "platform_admin")),
    db: Session = Depends(get_db),
) -> dict:
    roles = (
        db.query(UserRole)
        .filter(UserRole.organization_id == user.organization_id)
        .all()
    )
    result = []
    for r in roles:
        u = db.query(User).filter(User.id == r.user_id).one_or_none()
        if u:
            result.append(
                {
                    "id": u.id,
                    "email": u.email,
                    "full_name": u.full_name,
                    "is_active": u.is_active,
                    "platform_role": r.platform_role,
                    "module_roles": r.module_roles,
                }
            )
    return {"users": result}


class OrgUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None


@router.get("/organization")
def get_organization(
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="organization not found")
    return {
        "id": org.id,
        "name": org.name,
        "subscription_tier": org.subscription_tier,
        "settings": org.settings or {},
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


@router.patch("/organization")
def update_organization(
    req: OrgUpdate,
    user: CurrentUser = Depends(require_role_any("org_admin", "platform_admin")),
    db: Session = Depends(get_db),
) -> dict:
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="organization not found")
    if req.name is not None and req.name.strip():
        org.name = req.name.strip()
    if req.settings is not None:
        curr = dict(org.settings or {})
        curr.update(req.settings)
        org.settings = curr
    db.commit()
    db.refresh(org)
    audit(
        db,
        action="organization_updated",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="organization",
        resource_id=org.id,
    )
    return {
        "id": org.id,
        "name": org.name,
        "subscription_tier": org.subscription_tier,
        "settings": org.settings or {},
    }


@router.get("/{user_id}")
def get_user(
    user_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    role = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == user_id,
            UserRole.organization_id == user.organization_id,
        )
        .one_or_none()
    )
    if role is None:
        raise HTTPException(
            status_code=404, detail="user not found in your organization"
        )
    u = db.query(User).filter(User.id == user_id).one_or_none()
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "is_active": u.is_active,
        "platform_role": role.platform_role,
        "module_roles": role.module_roles,
    }


@router.put("/{user_id}/roles")
def assign_roles(
    user_id: str,
    req: RoleAssign,
    user: CurrentUser = Depends(require_role_any("org_admin", "platform_admin")),
    db: Session = Depends(get_db),
) -> dict:
    if (
        req.organization_id != user.organization_id
        and "platform_admin" not in user.platform_roles
    ):
        raise HTTPException(
            status_code=403, detail="cannot assign roles outside your organization"
        )
    role = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == user_id, UserRole.organization_id == req.organization_id
        )
        .one_or_none()
    )
    if role is None:
        raise HTTPException(
            status_code=404, detail="user has no membership in this organization"
        )
    role.platform_role = req.platform_role
    role.module_roles = req.module_roles
    db.commit()
    audit(
        db,
        action="roles_updated",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="user",
        resource_id=user_id,
        detail={"platform_role": req.platform_role, "module_roles": req.module_roles},
    )
    return {"ok": True}


@router.post("/invite")
def invite_user(
    email: str,
    user: CurrentUser = Depends(require_role_any("org_admin", "platform_admin")),
    db: Session = Depends(get_db),
) -> dict:
    existing = db.query(User).filter(User.email == email.strip().lower()).one_or_none()
    if existing:
        raise HTTPException(
            status_code=409, detail="user already has an account; assign roles instead"
        )
    # invite record is persisted as a disabled placeholder until registration
    org = db.query(Organization).filter(Organization.id == user.organization_id).one()
    invited = User(
        id=uuid.uuid4().hex,
        email=email.strip().lower(),
        is_active=False,
        profile={"invited_by": user.id, "pending": True},
    )
    db.add(invited)
    db.flush()
    db.add(
        UserRole(
            id=uuid.uuid4().hex,
            user_id=invited.id,
            organization_id=org.id,
            platform_role="member",
            module_roles=[],
            is_default=True,
        )
    )
    db.commit()
    audit(
        db,
        action="user_invited",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="user",
        resource_id=invited.id,
    )
    return {"user_id": invited.id, "status": "invited"}
