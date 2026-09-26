"""Model registry: imports all models so metadata.create_all sees every table."""

from app.models.analytics import (
    AnalyticsEvent,
    Annotation,
    CollectionItem,
    KnowledgeCollection,
)
from app.models.document import DocumentChunk, LegalDocument
from app.models.job import BackgroundJob
from app.models.org import Organization, User, UserRole
from app.models.review import DocumentReview, ReviewFinding, ReviewTemplate
from app.models.scenario import Scenario, ScenarioVersion
from app.models.simulation import (
    CaseStudy,
    Simulation,
    SimulationAudio,
    SimulationTurn,
)
from app.models.token import RefreshToken

__all__ = [
    "AnalyticsEvent",
    "Annotation",
    "BackgroundJob",
    "CaseStudy",
    "CollectionItem",
    "DocumentChunk",
    "DocumentReview",
    "KnowledgeCollection",
    "LegalDocument",
    "Organization",
    "RefreshToken",
    "ReviewFinding",
    "ReviewTemplate",
    "Scenario",
    "ScenarioVersion",
    "Simulation",
    "SimulationAudio",
    "SimulationTurn",
    "User",
    "UserRole",
]
