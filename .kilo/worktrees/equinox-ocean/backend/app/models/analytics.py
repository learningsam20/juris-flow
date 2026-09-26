"""Analytics, knowledge collection, and annotation models (PRD §6.8, §9.1, §6.7 P2)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType
from app.models.org import utcnow


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    organization_id: Mapped[str | None] = mapped_column(
        String(36), index=True, nullable=True
    )
    module: Mapped[str] = mapped_column(String(32), default="")
    simulation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    review_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict | None] = mapped_column(JSONType, default=dict)


class KnowledgeCollection(Base):
    __tablename__ = "knowledge_collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    items: Mapped[list[CollectionItem]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class CollectionItem(Base):
    __tablename__ = "collection_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_collections.id"), index=True, nullable=False
    )
    item_type: Mapped[str] = mapped_column(
        String(32), default="document"
    )  # document|scenario|simulation|review
    item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")

    collection: Mapped[KnowledgeCollection] = relationship(back_populates="items")


class Annotation(Base):
    """Collaborative annotations on reports/case studies (P2)."""

    __tablename__ = "annotations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    author_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # case_study|review_report|document
    target_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    resolution: Mapped[str] = mapped_column(String(32), default="")  # open|resolved
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
