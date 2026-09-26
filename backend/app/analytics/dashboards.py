"""Analytics event capture and dashboards aggregation (PRD §6.8)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging import get_correlation_id
from app.models import AnalyticsEvent
from app.models.review import DocumentReview
from app.models.simulation import Simulation

logger = logging.getLogger(__name__)


def emit(
    db: Session,
    event_type: str,
    *,
    organization_id: str,
    user_id: str | None = None,
    module: str = "",
    simulation_id: str | None = None,
    review_id: str | None = None,
    document_id: str | None = None,
    payload: dict | None = None,
    duration_ms: float | None = None,
    status: str = "",
) -> AnalyticsEvent:
    event_payload = dict(payload or {})
    if duration_ms is not None:
        event_payload["duration_ms"] = round(float(duration_ms), 2)
    if status:
        event_payload["status"] = status
    event = AnalyticsEvent(
        id=uuid.uuid4().hex,
        event_type=event_type,
        organization_id=organization_id,
        user_id=user_id,
        module=module,
        simulation_id=simulation_id,
        review_id=review_id,
        document_id=document_id,
        correlation_id=get_correlation_id(),
        payload=event_payload,
    )
    db.add(event)
    db.commit()
    return event


def dashboard(organization_id: str, db: Session) -> dict:
    """Basic usage dashboard (PRD §6.8 P1)."""

    def count_events(event_type: str) -> int:
        return (
            db.query(func.count(AnalyticsEvent.id))
            .filter(AnalyticsEvent.organization_id == organization_id)
            .filter(AnalyticsEvent.event_type == event_type)
            .scalar()
            or 0
        )

    simulations = (
        db.query(Simulation)
        .filter(Simulation.organization_id == organization_id)
        .order_by(Simulation.created_at.desc())
        .all()
    )
    reviews = (
        db.query(DocumentReview)
        .filter(DocumentReview.organization_id == organization_id)
        .order_by(DocumentReview.generated_at.desc())
        .all()
    )

    sims_by_scenario: dict[str, int] = {}
    sims_by_role: dict[str, int] = {}
    for sim in simulations:
        sims_by_scenario[sim.scenario_version_id] = (
            sims_by_scenario.get(sim.scenario_version_id, 0) + 1
        )
        for agent in sim.active_agents:
            sims_by_role[agent] = sims_by_role.get(agent, 0) + 1

    reviews_by_type: dict[str, int] = {}
    for rev in reviews:
        rtype = rev.document.doc_type if rev.document else "unknown"
        reviews_by_type[rtype] = reviews_by_type.get(rtype, 0) + 1

    return {
        "simulations_run": len(simulations),
        "simulations_by_scenario": sims_by_scenario,
        "simulations_by_role": sims_by_role,
        "simulations_by_status": {
            status: count
            for status, count in (
                db.query(Simulation.status, func.count(Simulation.id))
                .filter(Simulation.organization_id == organization_id)
                .group_by(Simulation.status)
                .all()
            )
        },
        "reviews_performed": len(reviews),
        "reviews_by_document_type": reviews_by_type,
        "top_searches": _top_payloads(db, organization_id, "knowledge.search"),
        "case_studies_exported": count_events("case_study.exported"),
        "reports_exported": count_events("review_report.exported"),
        "document_uploads": count_events("document.uploaded"),
        "search_latency_ms": _latency_summary(db, organization_id, "knowledge.search"),
        "ask_latency_ms": _latency_summary(db, organization_id, "knowledge.ask"),
    }


def _accumulate(stats: dict[str, dict[str, float]], key: str, ms: float) -> None:
    bucket = stats.setdefault(key, {"count": 0, "avg": 0.0, "max": 0.0})
    bucket["count"] += 1
    bucket["max"] = max(bucket["max"], ms)
    bucket["avg"] += (ms - bucket["avg"]) / bucket["count"]


def agent_telemetry(organization_id: str, db: Session) -> dict:
    """Agent telemetry: turns, tool calls, retrieval hits, and call latencies."""
    events = (
        db.query(AnalyticsEvent)
        .filter(AnalyticsEvent.organization_id == organization_id)
        .filter(AnalyticsEvent.module == "sim")
        .order_by(AnalyticsEvent.timestamp.desc())
        .limit(2000)
        .all()
    )
    turns: dict[str, int] = {}
    tool_calls: dict[str, int] = {}
    retrieval_hits: dict[str, int] = {}
    latency: dict[str, dict[str, float]] = {}
    tool_latency: dict[str, dict[str, float]] = {}
    for ev in events:
        p = ev.payload or {}
        if ev.event_type == "agent.turn":
            role = p.get("agent_role", "unknown")
            turns[role] = turns.get(role, 0) + 1
        elif ev.event_type == "agent.tool_call":
            tool = p.get("tool", "unknown")
            tool_calls[tool] = tool_calls.get(tool, 0) + 1
            dur = p.get("duration_ms")
            if dur is not None:
                _accumulate(tool_latency, tool, float(dur))
        elif ev.event_type == "agent.retrieval":
            hit = p.get("hits", 0)
            retrieval_hits["total"] = retrieval_hits.get("total", 0) + hit
        dur = p.get("duration_ms")
        if dur is not None:
            _accumulate(latency, ev.event_type, float(dur))
    return {
        "turns_by_agent": turns,
        "tool_calls": tool_calls,
        "retrieval_hits": retrieval_hits,
        "latency_ms": latency,
        "tool_latency_ms": tool_latency,
    }


def _latency_summary(db: Session, organization_id: str, event_type: str) -> dict:
    rows = (
        db.query(AnalyticsEvent.payload)
        .filter(AnalyticsEvent.organization_id == organization_id)
        .filter(AnalyticsEvent.event_type == event_type)
        .all()
    )
    durations = []
    for (p,) in rows:
        dur = (p or {}).get("duration_ms")
        if dur is not None:
            durations.append(float(dur))
    if not durations:
        return {"count": 0}
    return {
        "count": len(durations),
        "avg_ms": round(sum(durations) / len(durations), 2),
        "max_ms": round(max(durations), 2),
    }


def _top_payloads(db: Session, organization_id: str, event_type: str) -> list[dict]:
    """Top payloads by query, aggregated in Python since payloads now carry
    per-event timings that would otherwise fragment a SQL GROUP BY."""
    rows = (
        db.query(AnalyticsEvent.payload)
        .filter(AnalyticsEvent.organization_id == organization_id)
        .filter(AnalyticsEvent.event_type == event_type)
        .all()
    )
    counts: dict[str, int] = {}
    for (p,) in rows:
        q = (p or {}).get("query", "")
        counts[q] = counts.get(q, 0) + 1
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    return [{"query": q, "count": n} for q, n in top]
