"""FastAPI dependencies: auth principal resolution and OPA-backed authorization."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User, UserRole
from app.opa.engine import get_engine

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    email: str
    full_name: str
    organization_id: str
    platform_role: str = "member"
    module_roles: list[str] = field(default_factory=list)

    @property
    def platform_roles(self) -> list[str]:
        """Flat platform roles consumed by OPA policies (org_admin/platform_admin)."""
        if self.platform_role in ("platform_admin", "org_admin", "billing_admin"):
            return [self.platform_role]
        return []


def _decision(engine, policy: str, input_data: dict) -> bool:
    return bool(engine.decide(policy, input_data).allow)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid or expired access token")
    user = db.query(User).filter(User.id == payload.get("sub")).one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="user not found or disabled")
    membership = (
        db.query(UserRole)
        .filter(UserRole.user_id == user.id, UserRole.is_default == True)
        .first()
    )
    if membership is None:
        membership = db.query(UserRole).filter(UserRole.user_id == user.id).first()
    return CurrentUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=(
            membership.organization_id if membership else payload.get("org", "")
        ),
        platform_role=(membership.platform_role if membership else "member"),
        module_roles=list(membership.module_roles)
        if membership and membership.module_roles
        else [],
    )


def require_any(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Any authenticated user (used for reading your own org's data broadly)."""
    return user


def require_role_any(*roles: str):
    """Require one of the given platform roles (org_admin / platform_admin)."""
    roles_set = set(roles)

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        decision = get_engine().decide(
            "rbac",
            {
                "action": "role",
                "user": {
                    "platform_roles": [r for r in user.platform_roles if r in roles_set]
                },
                "resource": {},
            },
        )
        if not decision.allow:
            raise HTTPException(status_code=403, detail="insufficient role")
        return user

    return dependency


def require_module(module: str, permission: str):
    """Dependency factory enforcing the rbac OPA policy for a module permission."""

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        decision = get_engine().decide(
            "rbac",
            {
                "action": "module",
                "user": {
                    "platform_roles": user.platform_roles,
                    "module_roles": user.module_roles,
                },
                "resource": {"module": module, "permission": permission},
            },
        )
        if not decision.allow:
            raise HTTPException(
                status_code=403,
                detail=f"permission denied: needed {module}.{permission} ({decision.reason})",
            )
        return user

    return dependency


def require_tenant(resource_organization_id: str, user: CurrentUser) -> None:
    """Enforce tenant isolation on an already-loaded resource."""
    decision = get_engine().decide(
        "tenant",
        {
            "user": {
                "organization_id": user.organization_id,
                "platform_roles": user.platform_roles,
            },
            "resource": {"organization_id": resource_organization_id},
        },
    )
    if not decision.allow:
        raise HTTPException(
            status_code=403, detail=f"tenant isolation denied: {decision.reason}"
        )


def enforce_export(user: CurrentUser, artifact_type: str, checks: dict) -> None:
    # Normalize caller-provided provenance checks into the policy schema
    # (export.rego reads checks.disclaimers and checks.citations).
    policy_checks = {
        "disclaimers": bool(checks.get("disclaimers", True)),
        "citations": bool(
            checks.get("citations")
            or checks.get("contains_grounded_citations")
            or checks.get("contains_plain_language")
        ),
    }
    decision = get_engine().decide(
        "export",
        {
            "user": {
                "platform_roles": user.platform_roles,
                "module_roles": user.module_roles,
            },
            "artifact": {"type": artifact_type},
            "checks": policy_checks,
        },
    )
    if not decision.allow:
        raise HTTPException(status_code=403, detail=f"export denied: {decision.reason}")
