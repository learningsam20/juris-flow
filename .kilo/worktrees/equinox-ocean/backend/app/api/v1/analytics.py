"""Analytics and dashboards endpoints (PRD §6.8, §7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Text, cast, or_
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require_module
from app.db.session import get_db
from app.models import AnalyticsEvent
from app.services.hub import insights as hub_insights
from app.services.kpis import compute_kpis

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _telemetry(db: Session, organization_id: str) -> dict:
    rows = (
        db.query(AnalyticsEvent)
        .filter(AnalyticsEvent.organization_id == organization_id)
        .all()
    )
    by_type: dict[str, int] = {}
    by_module: dict[str, int] = {}
    durations: list[float] = []
    durations_by_type: dict[str, list[float]] = {}
    durations_by_module: dict[str, list[float]] = {}

    for e in rows:
        event_type = str(getattr(e, "event_type", "") or "")
        by_type[event_type] = by_type.get(event_type, 0) + 1
        mod = str(getattr(e, "module", "") or "system")
        by_module[mod] = by_module.get(mod, 0) + 1

        payload = getattr(e, "payload", None) or {}
        duration = payload.get("duration_ms")
        if duration is not None:
            try:
                d_val = float(duration)
                if d_val >= 0:
                    durations.append(d_val)
                    durations_by_type.setdefault(event_type, []).append(d_val)
                    durations_by_module.setdefault(mod, []).append(d_val)
            except (ValueError, TypeError):
                pass

    durations.sort()
    total_timed = len(durations)
    avg_dur = round(sum(durations) / total_timed, 1) if total_timed > 0 else 0.0
    p95_dur = round(durations[int(total_timed * 0.95)], 1) if total_timed > 0 else 0.0
    min_dur = round(durations[0], 1) if total_timed > 0 else 0.0
    max_dur = round(durations[-1], 1) if total_timed > 0 else 0.0

    avg_by_type = {
        k: round(sum(v) / len(v), 1) for k, v in durations_by_type.items() if v
    }
    avg_by_module = {
        k: round(sum(v) / len(v), 1) for k, v in durations_by_module.items() if v
    }

    return {
        "total_events": len(rows),
        "by_event_type": dict(
            sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)
        ),
        "by_module": dict(
            sorted(by_module.items(), key=lambda kv: kv[1], reverse=True)
        ),
        "latency_stats": {
            "total_timed_events": total_timed,
            "avg_duration_ms": avg_dur,
            "p95_duration_ms": p95_dur,
            "min_duration_ms": min_dur,
            "max_duration_ms": max_dur,
            "avg_by_type": dict(
                sorted(avg_by_type.items(), key=lambda kv: kv[1], reverse=True)
            ),
            "avg_by_module": dict(
                sorted(avg_by_module.items(), key=lambda kv: kv[1], reverse=True)
            ),
        },
    }


@router.get("/dashboard")
def dashboard(
    user: CurrentUser = Depends(require_module("dashboard", "dashboard.view")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return {
            "kpis": compute_kpis(organization_id=user.organization_id, db=db),
            "insights": hub_insights(organization_id=user.organization_id, db=db),
            "telemetry": _telemetry(db, user.organization_id),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"dashboard generation failed: {exc}"
        )


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
