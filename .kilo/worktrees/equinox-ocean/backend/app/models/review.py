"""Document review and review findings models (PRD §5.2, §9.1)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType
from app.models.org import utcnow

if TYPE_CHECKING:
    from app.models.document import LegalDocument


class ReviewTemplate(Base):
    """Customizable review template by document type (PRD §7.2, P2)."""

    __tablename__ = "review_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    document_types: Mapped[list] = mapped_column(
        JSONType, default=list
    )  # e.g. ["contract", "lease"]
    focus_clause_types: Mapped[list] = mapped_column(
        JSONType, default=list
    )  # restrict extraction to these clause types
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class DocumentReview(Base):
    __tablename__ = "document_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        ForeignKey("legal_documents.id"), index=True, nullable=False
    )
    reviewer_id: Mapped[str] = mapped_column(String(36), default="")
    template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    template_name: Mapped[str] = mapped_column(String(128), default="")
    markdown_report: Mapped[str] = mapped_column(Text, default="")
    executive_summary: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str] = mapped_column(
        String(16), default="medium"
    )  # low|medium|high
    obligation_load: Mapped[int] = mapped_column(Integer, default=0)
    balance_score: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|published
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    document: Mapped[LegalDocument] = relationship(back_populates="reviews")
    findings: Mapped[list[ReviewFinding]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class ReviewFinding(Base):
    __tablename__ = "review_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_id: Mapped[str] = mapped_column(
        ForeignKey("document_reviews.id"), index=True, nullable=False
    )
    clause_type: Mapped[str] = mapped_column(
        String(64), default="general"
    )  # termination|payment|indemnity|...
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    span_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    span_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    plain_language: Mapped[str] = mapped_column(Text, default="")
    obligation: Mapped[bool] = mapped_column(default=False)
    suggested_question: Mapped[str] = mapped_column(Text, default="")
    proposed_change: Mapped[str] = mapped_column(Text, default="")
    change_rationale: Mapped[str] = mapped_column(Text, default="")

    review: Mapped[DocumentReview] = relationship(back_populates="findings")
