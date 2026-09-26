"""Audit logging of key actions (PRD §7.2 P1)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.logging import get_correlation_id
from app.models import AnalyticsEvent

logger = logging.getLogger("audit")


def audit(
    db: Session,
    *,
    action: str,
    actor: str | None,
    organization_id: str | None = None,
    resource_type: str = "",
    resource_id: str | None = None,
    outcome: str = "success",
    detail: dict | None = None,
) -> None:
    logger.info(
        "audit",
        extra={
            "action": action,
            "actor": actor,
            "organization_id": organization_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "outcome": outcome,
            "detail": detail or {},
        },
    )
    db.add(
        AnalyticsEvent(
            id=__import__("uuid").uuid4().hex,
            event_type=f"audit.{action}",
            user_id=actor,
            organization_id=organization_id,
            correlation_id=get_correlation_id(),
            payload={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "outcome": outcome,
                "detail": detail or {},
            },
        )
    )
    db.commit()
