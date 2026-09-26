"""KPI aggregation for the dashboard (PRD §7.1)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    AnalyticsEvent,
    CaseStudy,
    DocumentReview,
    KnowledgeCollection,
    LegalDocument,
    Scenario,
    Simulation,
    SimulationTurn,
)


def compute_kpis(*, organization_id: str, db: Session) -> dict:
    documents = (
        db.query(LegalDocument)
        .filter(LegalDocument.organization_id == organization_id)
        .count()
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
    return {
        "documents": documents,
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
    }
