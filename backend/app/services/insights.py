"""Insights report: metric pack + LLM recommender agent (PRD §6.8).

The report answers three management questions from the dashboard/analytics
surface: what is working (best practices), what needs improvement, and what to
do next — phased across immediate / 30 / 90 / 180-day horizons.

Reports are cached per organization and keyed by a hash of the metric pack, so
an unchanged dashboard never re-runs the agent.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.agents.recommender import (
    RECOMMENDER_SYSTEM,
    TIMELINE_LABELS,
    TIMELINES,
    build_user_prompt,
    normalize_report,
    parse_recommender_json,
)
from app.models import (
    AnalyticsEvent,
    DocumentReview,
    InsightsReport,
    LegalDocument,
    ReviewFinding,
)
from app.models.org import utcnow

logger = logging.getLogger(__name__)

REPORT_TTL = timedelta(hours=24)

CONTRACT_DOC_TYPES = ("contract", "agreement", "nda", "lease", "contract_review")


def collect_metrics(*, organization_id: str, db: Session) -> dict:
    """Aggregate the dashboard/analytics signals the recommender reasons over."""
    from app.services.hub import insights as hub_insights
    from app.services.kpis import compute_kpis
    from app.services.telemetry import telemetry_summary

    telemetry = telemetry_summary(organization_id=organization_id, db=db)
    latency = telemetry.get("latency_stats", {})
    return {
        "kpis": compute_kpis(organization_id=organization_id, db=db),
        "risk_signals": risk_signals(organization_id=organization_id, db=db),
        "coverage": hub_insights(organization_id=organization_id, db=db),
        "activity": activity_signals(organization_id=organization_id, db=db),
        "telemetry": {
            "total_events": telemetry.get("total_events", 0),
            "by_module": telemetry.get("by_module", {}),
            "p95_duration_ms": latency.get("p95_duration_ms", 0),
            "avg_duration_ms": latency.get("avg_duration_ms", 0),
            "total_timed_events": latency.get("total_timed_events", 0),
        },
    }


def risk_signals(*, organization_id: str, db: Session) -> dict:
    """Audit coverage, risk distribution, and the clause types driving risk."""
    total_docs = (
        db.query(LegalDocument)
        .filter(LegalDocument.organization_id == organization_id)
        .count()
    )
    contract_docs = (
        db.query(LegalDocument)
        .filter(
            LegalDocument.organization_id == organization_id,
            LegalDocument.doc_type.in_(CONTRACT_DOC_TYPES),
        )
        .count()
    )

    review_rows = (
        db.query(DocumentReview)
        .filter(DocumentReview.organization_id == organization_id)
        .all()
    )
    audited = len(review_rows)
    published = sum(1 for r in review_rows if r.status == "published")
    risk_distribution = {"high": 0, "medium": 0, "low": 0}
    balances: list[float] = []
    obligations = 0
    for r in review_rows:
        level = (r.risk_level or "medium").lower()
        risk_distribution[level] = risk_distribution.get(level, 0) + 1
        if r.balance_score is not None:
            balances.append(float(r.balance_score))
        obligations += int(r.obligation_load or 0)

    finding_levels = dict(
        db.query(ReviewFinding.risk_level, func.count(ReviewFinding.id))
        .join(DocumentReview, DocumentReview.id == ReviewFinding.review_id)
        .filter(DocumentReview.organization_id == organization_id)
        .group_by(ReviewFinding.risk_level)
        .all()
    )
    top_high_clause_types = [
        {"clause_type": ct, "count": c}
        for ct, c in (
            db.query(ReviewFinding.clause_type, func.count(ReviewFinding.id))
            .join(DocumentReview, DocumentReview.id == ReviewFinding.review_id)
            .filter(
                DocumentReview.organization_id == organization_id,
                ReviewFinding.risk_level == "high",
            )
            .group_by(ReviewFinding.clause_type)
            .order_by(desc(func.count(ReviewFinding.id)))
            .limit(5)
            .all()
        )
    ]

    return {
        "total_documents": total_docs,
        "contract_documents": contract_docs,
        "audited_documents": audited,
        "published_audits": published,
        "coverage_percentage": round(audited / total_docs * 100, 1)
        if total_docs
        else 0.0,
        "publish_rate_percentage": round(published / audited * 100, 1)
        if audited
        else 0.0,
        "review_risk_distribution": risk_distribution,
        "finding_risk_distribution": {
            "high": int(finding_levels.get("high", 0)),
            "medium": int(finding_levels.get("medium", 0)),
            "low": int(finding_levels.get("low", 0)),
        },
        "top_high_risk_clause_types": top_high_clause_types,
        "total_obligations": obligations,
        "avg_balance_score": round(sum(balances) / len(balances), 3)
        if balances
        else 0.0,
    }


def activity_signals(*, organization_id: str, db: Session) -> dict:
    """Recent event volume — adoption and whether the workflow is actually used."""
    now = utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    base = db.query(AnalyticsEvent).filter(
        AnalyticsEvent.organization_id == organization_id
    )
    last_7 = base.filter(AnalyticsEvent.timestamp >= week_ago).count()
    last_30 = base.filter(AnalyticsEvent.timestamp >= month_ago).count()
    by_module = dict(
        db.query(AnalyticsEvent.module, func.count(AnalyticsEvent.id))
        .filter(
            AnalyticsEvent.organization_id == organization_id,
            AnalyticsEvent.timestamp >= month_ago,
        )
        .group_by(AnalyticsEvent.module)
        .all()
    )
    return {
        "events_last_7_days": last_7,
        "events_last_30_days": last_30,
        "by_module_last_30_days": by_module,
    }


def _metrics_hash(metrics: dict) -> str:
    payload = json.dumps(metrics, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_fresh(generated_at: datetime | None) -> bool:
    """True when the cached report is younger than REPORT_TTL.

    SQLite returns naive datetimes; normalize to UTC before comparing.
    """
    if generated_at is None:
        return False
    stamp = (
        generated_at
        if generated_at.tzinfo is not None
        else generated_at.replace(tzinfo=timezone.utc)
    )
    return (datetime.now(timezone.utc) - stamp) <= REPORT_TTL


def get_latest_report(*, organization_id: str, db: Session) -> InsightsReport | None:
    return (
        db.query(InsightsReport)
        .filter(InsightsReport.organization_id == organization_id)
        .order_by(InsightsReport.generated_at.desc())
        .first()
    )


def generate_report(
    *,
    organization_id: str,
    db: Session,
    user_id: str | None = None,
    force: bool = False,
) -> dict:
    """Return the cached report while metrics are unchanged; otherwise run the agent."""
    metrics = collect_metrics(organization_id=organization_id, db=db)
    metrics_hash = _metrics_hash(metrics)

    latest = get_latest_report(organization_id=organization_id, db=db)
    if (
        latest is not None
        and not force
        and latest.metrics_hash == metrics_hash
        and _is_fresh(latest.generated_at)
    ):
        return report_payload(latest, cached=True)

    content, generated_by, model, llm_error = _run_agent(metrics)
    row = InsightsReport(
        id=uuid.uuid4().hex,
        organization_id=organization_id,
        metrics_hash=metrics_hash,
        source_metrics=metrics,
        content=content,
        markdown="",
        generated_by=generated_by,
        model=model,
        llm_error=llm_error,
    )
    row.markdown = render_markdown(content, metrics, generated_by=generated_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        "insights report %s generated by %s for org %s (actor %s)",
        row.id,
        generated_by,
        organization_id,
        user_id,
    )
    return report_payload(row, cached=False)


def report_payload(row: InsightsReport, *, cached: bool) -> dict:
    content = row.content or {}
    return {
        "id": row.id,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "generated_by": row.generated_by,
        "model": row.model,
        "llm_error": row.llm_error or None,
        "cached": cached,
        "executive_summary": content.get("executive_summary", ""),
        "recommendations": content.get("recommendations", []),
        "best_practices": content.get("best_practices", []),
        "needs_improvement": content.get("needs_improvement", []),
        "timeline_labels": content.get("timeline_labels", dict(TIMELINE_LABELS)),
        "source_metrics": row.source_metrics or {},
        "markdown": row.markdown or "",
    }


def _run_agent(metrics: dict) -> tuple[dict, str, str, str]:
    """Run the recommender LLM; fall back to deterministic rules when it fails.

    The fallback is never silent: ``generated_by``/``llm_error`` are surfaced on
    the report payload so the UI can flag it.
    """
    try:
        from app.llm.factory import get_llm

        llm = get_llm()
        raw = llm.chat(
            RECOMMENDER_SYSTEM,
            [{"role": "user", "content": build_user_prompt(metrics)}],
            max_tokens=2200,
        )
        parsed = parse_recommender_json(raw or "")
        if parsed is None:
            raise ValueError("recommender agent returned unparseable output")
        content = normalize_report(parsed)
        content["timeline_labels"] = dict(TIMELINE_LABELS)
        return content, "llm", str(getattr(llm, "name", "") or ""), ""
    except Exception as exc:
        logger.warning("recommender agent failed, using rule-based report: %s", exc)
        content = normalize_report(rule_based_report(metrics))
        content["timeline_labels"] = dict(TIMELINE_LABELS)
        return content, "rules", "", str(exc)[:500]


def rule_based_report(metrics: dict) -> dict:
    """Deterministic baseline so the report still renders without an LLM."""
    kpis = metrics.get("kpis", {}) or {}
    risk = metrics.get("risk_signals", {}) or {}
    activity = metrics.get("activity", {}) or {}
    telemetry = metrics.get("telemetry", {}) or {}

    recommendations: list[dict] = []
    best_practices: list[dict] = []
    gaps: list[dict] = []

    def rec(title, detail, category, priority, timeline):
        recommendations.append(
            {
                "title": title,
                "detail": detail,
                "category": category,
                "priority": priority,
                "timeline": timeline,
            }
        )

    def good(title, evidence, timeline="immediate"):
        best_practices.append(
            {"title": title, "evidence": evidence, "timeline": timeline}
        )

    def gap(title, problem, fix, timeline):
        gaps.append(
            {
                "title": title,
                "gap": problem,
                "recommendation": fix,
                "timeline": timeline,
            }
        )

    reviews = int(kpis.get("reviews", 0))
    documents = int(kpis.get("documents", 0))
    publish_rate = float(kpis.get("reviews_published_rate", 0) or 0)
    completion = float(kpis.get("simulation_completion_rate", 0) or 0)
    coverage = float(risk.get("coverage_percentage", 0) or 0)
    searches = int(kpis.get("knowledge_searches", 0) or 0)
    events_7 = int(activity.get("events_last_7_days", 0) or 0)
    p95 = float(telemetry.get("p95_duration_ms", 0) or 0)
    balance = float(risk.get("avg_balance_score", 0) or 0)
    high_findings = int(
        (risk.get("finding_risk_distribution") or {}).get("high", 0) or 0
    )

    # --- Recommendations (timeline phased) ---
    if reviews and publish_rate < 100:
        rec(
            "Publish outstanding audit reports",
            f"{publish_rate:.0f}% of {reviews} audits are published. Draft reports "
            "never reach reviewers, so flagged risks stay invisible to the business.",
            "governance",
            "high",
            "immediate",
        )
    if p95 and p95 > 5000:
        rec(
            "Investigate slow request paths",
            f"p95 latency is {p95:.0f} ms across telemetry events; users will perceive "
            "audits and searches as stalled above ~5 s.",
            "operations",
            "high" if p95 > 10000 else "medium",
            "immediate",
        )
    if reviews and balance < -0.2:
        rec(
            "Rebalance one-sided clauses",
            f"Average balance score is {balance:+.2f} (negative = obligations skew to one "
            "party). Target remediation at indemnity, liability and termination clauses.",
            "risk",
            "high",
            "30_days",
        )
    if documents and coverage < 60:
        rec(
            "Raise audit coverage across the contract portfolio",
            f"Only {coverage:.0f}% of ingested documents have been audited. Schedule "
            "batch audits by risk domain to close the gap.",
            "quality",
            "high",
            "30_days",
        )
    if not searches:
        rec(
            "Drive adoption of grounded knowledge search",
            "No knowledge searches recorded. Train reviewers to ground answers in the "
            "indexed corpus instead of raw model reasoning.",
            "adoption",
            "medium",
            "30_days",
        )
    if completion and completion < 80:
        rec(
            "Review aborted simulations",
            f"Simulation completion is {completion:.0f}%. Check turn limits, model "
            "availability, and scenario difficulty.",
            "operations",
            "medium",
            "90_days",
        )
    if documents and documents < 25:
        rec(
            "Expand the precedent and clause library",
            f"Only {documents} documents indexed; retrieval quality and grounded answers "
            "improve with a broader, tagged corpus.",
            "content",
            "medium",
            "90_days",
        )
    rec(
        "Codify a remediation review cadence",
        "Set a monthly contract-governance review where high-risk findings, applied "
        "suggestions, and residual risks are signed off by counsel.",
        "governance",
        "medium",
        "180_days",
    )

    # --- Best practices already followed ---
    if reviews:
        good(
            "Every contract audit carries structured findings and a risk grade",
            f"{reviews} audits stored with findings, obligations and balance scoring.",
        )
    if completion >= 80:
        good(
            "Simulation workflow completes reliably",
            f"Completion rate {completion:.0f}% — learners reach the verdict and case study.",
        )
    if publish_rate >= 80:
        good(
            "Audit reports are published, not left in draft",
            f"Publish rate {publish_rate:.0f}%.",
        )
    if searches:
        good(
            "Answers are grounded in indexed knowledge",
            f"{searches} knowledge searches recorded against the local corpus.",
            "30_days",
        )
    if events_7:
        good(
            "Active weekly usage across modules",
            f"{events_7} events in the last 7 days.",
        )
    if int(kpis.get("knowledge_collections", 0) or 0):
        good(
            "Knowledge is curated into collections",
            f"{kpis.get('knowledge_collections')} collections organise source material.",
            "30_days",
        )
    if not best_practices:
        good(
            "Baseline instrumentation is in place",
            "Dashboard, analytics events, and telemetry are being captured.",
        )

    # --- Needs improvement ---
    if reviews and publish_rate < 100:
        gap(
            "Audit reports stuck in draft",
            f"{reviews - round(publish_rate / 100 * reviews)} reports are unpublished.",
            "Add a publish gate to the review workflow and alert review leads on ageing drafts.",
            "immediate",
        )
    if high_findings:
        gap(
            "Open high-risk clauses without tracked remediation",
            f"{high_findings} high-risk findings exist across audits.",
            "Apply suggested redlines to the source contract and record them as remediated.",
            "30_days",
        )
    if not searches:
        gap(
            "Knowledge hub under-used",
            "No retrieval activity — grounded Q&A is effectively dormant.",
            "Add an entry point from the audit screen and run a reviewer enablement session.",
            "30_days",
        )
    if coverage < 60:
        gap(
            "Uneven audit coverage",
            f"{coverage:.0f}% of documents audited.",
            "Prioritise contracts by spend and clause risk for the next audit batch.",
            "90_days",
        )
    if events_7 == 0:
        gap(
            "No recent platform activity",
            "Zero events in the last 7 days.",
            "Confirm the rollout, owners, and training schedule with each module's leads.",
            "immediate",
        )
    if completion and completion < 80:
        gap(
            "Simulations not reaching completion",
            f"Completion rate {completion:.0f}%.",
            "Shorten default turn limits for classroom sessions and add retry handling.",
            "90_days",
        )
    gap(
        "Remediation tracking not yet systematic",
        "Applied suggestions are not yet reconciled against a contract version history.",
        "Version contracts on remediation and diff risk scores before/after.",
        "180_days",
    )

    return {
        "executive_summary": (
            f"{documents} documents indexed, {reviews} audits run "
            f"({coverage:.0f}% coverage), {int(kpis.get('simulations', 0) or 0)} "
            f"simulations executed. "
            + (
                f"Publish rate is {publish_rate:.0f}% and average balance score is "
                f"{balance:+.2f}. "
                if reviews
                else ""
            )
            + "Recommendations below are phased across immediate, 30, 90 and 180-day "
            "horizons."
        ),
        "recommendations": recommendations,
        "best_practices": best_practices,
        "needs_improvement": gaps,
    }


def render_markdown(content: dict, metrics: dict, *, generated_by: str) -> str:
    """Render the report as Markdown for download/annotation."""
    labels = content.get("timeline_labels") or TIMELINE_LABELS
    risk = metrics.get("risk_signals", {}) or {}
    kpis = metrics.get("kpis", {}) or {}

    lines: list[str] = ["# Contract Operations Insights Report", ""]
    lines.append(
        f"*Generated by {'the LLM recommender agent' if generated_by == 'llm' else 'the rule-based fallback'} "
        f"on {utcnow().strftime('%Y-%m-%d %H:%M UTC')}.*"
    )
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(content.get("executive_summary", ""))
    lines.append("")

    lines.append("## Source Metrics")
    lines.append(
        f"- Documents indexed: **{kpis.get('documents', 0)}** · Audits: "
        f"**{kpis.get('reviews', 0)}** · Simulations: **{kpis.get('simulations', 0)}**"
    )
    lines.append(
        f"- Audit coverage: **{risk.get('coverage_percentage', 0)}%** · Publish rate: "
        f"**{risk.get('publish_rate_percentage', 0)}%** · Avg balance: "
        f"**{risk.get('avg_balance_score', 0)}**"
    )
    lines.append("")

    lines.append("## Recommendations by Timeline")
    for timeline in TIMELINES:
        items = [
            r
            for r in content.get("recommendations", [])
            if r.get("timeline") == timeline
        ]
        if not items:
            continue
        lines.append("")
        lines.append(f"### {labels.get(timeline, timeline)}")
        for r in items:
            lines.append(
                f"- **{r.get('title', '')}** ({r.get('priority', 'medium')} · "
                f"{r.get('category', 'operations')}) — {r.get('detail', '')}"
            )
    lines.append("")

    lines.append("## Best Practices Followed")
    for b in content.get("best_practices", []):
        lines.append(f"- **{b.get('title', '')}** — {b.get('evidence', '')}")
    lines.append("")

    lines.append("## Needs Improvement")
    for g in content.get("needs_improvement", []):
        lines.append(
            f"- **{g.get('title', '')}** — {g.get('gap', '')} "
            f"_Recommended fix:_ {g.get('recommendation', '')}"
        )
    lines.append("")

    lines.append(
        "---\n\n*This report is generated for educational and informational purposes "
        "and is not legal advice.*"
    )
    return "\n".join(lines)
