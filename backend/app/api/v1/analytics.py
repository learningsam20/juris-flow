"""Analytics and dashboards endpoints (PRD §6.8, §7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Text, cast, or_
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_module
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import AnalyticsEvent
from app.services import insights as insights_service
from app.services.hub import insights as hub_insights
from app.services.kpis import compute_kpis
from app.services.telemetry import telemetry_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard(
    user: CurrentUser = Depends(require_module("dashboard", "dashboard.view")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return {
            "kpis": compute_kpis(organization_id=user.organization_id, db=db),
            "insights": hub_insights(organization_id=user.organization_id, db=db),
            "telemetry": telemetry_summary(organization_id=user.organization_id, db=db),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"dashboard generation failed: {exc}"
        )


@router.get("/insights-report")
def insights_report(
    user: CurrentUser = Depends(require_module("dashboard", "dashboard.view")),
    db: Session = Depends(get_db),
) -> dict:
    """Latest cached insights report for this organization (``report`` is null if none)."""
    row = insights_service.get_latest_report(
        organization_id=user.organization_id, db=db
    )
    return {
        "report": insights_service.report_payload(row, cached=True) if row else None
    }


@router.post("/insights-report/generate")
def generate_insights_report(
    force: bool = False,
    user: CurrentUser = Depends(require_module("dashboard", "dashboard.view")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("analytics.insights", 120.0)),
) -> dict:
    """Run the LLM recommender agent over the current metric pack.

    Cached report is reused while the underlying metrics are unchanged unless
    ``force=true``. Falls back to a deterministic rule-based report (flagged as
    ``generated_by: "rules"``) when the LLM provider is unavailable.
    """
    try:
        report = insights_service.generate_report(
            organization_id=user.organization_id,
            user_id=user.id,
            db=db,
            force=force,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"insights report generation failed: {exc}"
        )
    return {"report": report}


@router.get("/events")
def events(
    module: str = "",
    q: str = "",
    limit: int = 200,
    user: CurrentUser = Depends(require_module("dashboard", "dashboard.view")),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(AnalyticsEvent).filter(
        AnalyticsEvent.organization_id == user.organization_id
    )
    if module:
        query = query.filter(AnalyticsEvent.module == module)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                AnalyticsEvent.event_type.ilike(term),
                AnalyticsEvent.module.ilike(term),
                AnalyticsEvent.correlation_id.ilike(term),
                cast(AnalyticsEvent.payload, Text).ilike(term),
            )
        )
    rows = query.order_by(AnalyticsEvent.timestamp.desc()).limit(min(limit, 500)).all()
    return {
        "events": [
            {
                "id": e.id,
                "type": e.event_type,
                "module": e.module,
                "user_id": e.user_id,
                "correlation_id": e.correlation_id,
                "created_at": e.timestamp.isoformat() if e.timestamp else None,
                "payload": e.payload,
            }
            for e in rows
        ]
    }
