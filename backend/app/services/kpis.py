"""KPI aggregation for the dashboard (PRD §7.1)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    AnalyticsEvent,
    CaseStudy,
    DocumentReview,
    KnowledgeCollection,
    LegalDocument,
    ReviewFinding,
    Scenario,
    Simulation,
    SimulationTurn,
)
from app.review.extractor import ABSTAINED_PREFIX


def compute_kpis(*, organization_id: str, db: Session) -> dict:
    docs = (
        db.query(LegalDocument)
        .filter(LegalDocument.organization_id == organization_id)
        .all()
    )
    documents = len(docs)
    knowledge_artefacts = sum(
        1 for d in docs if d.document_category == "knowledge_artefact"
    )
    contract_documents = sum(
        1 for d in docs if d.document_category == "contract_review"
    )
    scenarios = (
        db.query(Scenario).filter(Scenario.organization_id == organization_id).count()
    )
    simulations = (
        db.query(Simulation)
        .filter(Simulation.organization_id == organization_id)
        .count()
    )
    completed = (
        db.query(Simulation)
        .filter(
            Simulation.organization_id == organization_id,
            Simulation.status == "completed",
        )
        .count()
    )
    reviews = (
        db.query(DocumentReview)
        .filter(DocumentReview.organization_id == organization_id)
        .count()
    )
    published_reviews = (
        db.query(DocumentReview)
        .filter(
            DocumentReview.organization_id == organization_id,
            DocumentReview.status == "published",
        )
        .count()
    )
    turns = (
        db.query(SimulationTurn)
        .join(Simulation, Simulation.id == SimulationTurn.simulation_id)
        .filter(Simulation.organization_id == organization_id)
        .count()
    )
    case_studies = (
        db.query(CaseStudy).filter(CaseStudy.organization_id == organization_id).count()
    )
    collections = (
        db.query(KnowledgeCollection)
        .filter(KnowledgeCollection.organization_id == organization_id)
        .count()
    )
    searches = (
        db.query(AnalyticsEvent)
        .filter(
            AnalyticsEvent.organization_id == organization_id,
            AnalyticsEvent.event_type == "knowledge.search",
        )
        .count()
    )
    avg_turns = round(turns / simulations, 1) if simulations else 0.0
    remediation = _remediation_metrics(organization_id, db)
    return {
        "documents": documents,
        "knowledge_artefacts": knowledge_artefacts,
        "contract_documents": contract_documents,
        "scenarios": scenarios,
        "simulations": simulations,
        "simulation_completion_rate": round(completed / simulations * 100, 1)
        if simulations
        else 0.0,
        "reviews": reviews,
        "reviews_published_rate": round(published_reviews / reviews * 100, 1)
        if reviews
        else 0.0,
        "simulation_turns": turns,
        "avg_turns_per_simulation": avg_turns,
        "case_studies": case_studies,
        "knowledge_collections": collections,
        "knowledge_searches": searches,
        "contract_remediation": remediation,
    }


def _remediation_metrics(organization_id: str, db: Session) -> dict:
    """Contract-management metrics: risk load, remediation progress, grounding."""
    rows = (
        db.query(
            ReviewFinding.review_id,
            ReviewFinding.risk_level,
            ReviewFinding.implementation_status,
            ReviewFinding.proposed_change,
            ReviewFinding.text,
            ReviewFinding.support_status,
        )
        .join(DocumentReview, DocumentReview.id == ReviewFinding.review_id)
        .filter(DocumentReview.organization_id == organization_id)
        .all()
    )

    risk_counts = {"high": 0, "medium": 0, "low": 0}
    implementation = {"not_started": 0, "in_progress": 0, "applied": 0}
    non_grounded = 0
    actionable = 0
    open_high = 0
    km_confirmed = 0
    manual_review = 0
    for row in rows:
        level = row.risk_level if row.risk_level in risk_counts else "low"
        support = str(getattr(row, "support_status", "") or "")
        if support == "manual_review":
            manual_review += 1
        elif support == "km_confirmed" or (
            support == "" and not str(row.text or "").startswith(ABSTAINED_PREFIX)
        ):
            # Legacy rows without support_status count as confirmed when document-grounded.
            km_confirmed += 1
        risk_counts[level] += 1
        status = (
            row.implementation_status
            if row.implementation_status in implementation
            else "not_started"
        )
        implementation[status] += 1
        if level == "high" and status != "applied" and support != "manual_review":
            open_high += 1
        if str(row.text or "").startswith(ABSTAINED_PREFIX) or support == "doc_ungrounded":
            non_grounded += 1
        if (row.proposed_change or "").strip():
            actionable += 1

    # Reviews that still carry at least one high-risk finding left un-applied.
    pending_reviews = (
        db.query(DocumentReview.id)
        .join(ReviewFinding, ReviewFinding.review_id == DocumentReview.id)
        .filter(
            DocumentReview.organization_id == organization_id,
            ReviewFinding.risk_level == "high",
            ReviewFinding.implementation_status != "applied",
            ReviewFinding.support_status != "manual_review",
        )
        .distinct()
        .count()
    )
    total = len(rows)
    return {
        "findings": total,
        "risk_distribution": risk_counts,
        "implementation": implementation,
        "actionable": actionable,
        "in_progress": implementation["in_progress"],
        "open_high_risk": open_high,
        "non_grounded": non_grounded,
        "non_grounded_pct": round(non_grounded / total * 100, 1) if total else 0.0,
        "km_confirmed": km_confirmed,
        "manual_review": manual_review,
        "manual_review_pct": round(manual_review / total * 100, 1) if total else 0.0,
        "remediation_progress_pct": round(
            implementation["applied"] / actionable * 100, 1
        )
        if actionable
        else 0.0,
        "pending_high_risk_reviews": pending_reviews,
    }
