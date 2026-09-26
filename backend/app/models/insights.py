"""Persisted insights reports produced by the LLM recommender agent (PRD §6.8)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONType
from app.models.org import utcnow


class InsightsReport(Base):
    __tablename__ = "insights_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    # Hash of the metric pack the report was derived from; unchanged metrics reuse
    # the cached report instead of re-running the recommender agent.
    metrics_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    content: Mapped[dict] = mapped_column(JSONType, default=dict)
    markdown: Mapped[str] = mapped_column(Text, default="")
    generated_by: Mapped[str] = mapped_column(String(16), default="llm")  # llm | rules
    model: Mapped[str] = mapped_column(String(64), default="")
    llm_error: Mapped[str] = mapped_column(String(512), default="")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
