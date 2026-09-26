"""Scenario and scenario-version models (PRD §5.1, §6.3, §9.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType
from app.models.org import utcnow


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    jurisdiction: Mapped[str] = mapped_column(String(128), default="")
    domain: Mapped[str] = mapped_column(String(128), default="")
    tags: Mapped[list] = mapped_column(JSONType, default=list)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|published
    created_by: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    versions: Mapped[list[ScenarioVersion]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        order_by="ScenarioVersion.version",
    )


class ScenarioVersion(Base):
    __tablename__ = "scenario_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("scenarios.id"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255), default="")
    fact_pattern: Mapped[str] = mapped_column(Text, default="")
    parameters: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    document_ids: Mapped[list] = mapped_column(JSONType, default=list)
    created_by: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    scenario: Mapped[Scenario] = relationship(back_populates="versions")
