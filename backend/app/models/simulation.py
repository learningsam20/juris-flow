"""Simulation, simulation turn, and case study models (PRD §5.1, §9.1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType
from app.models.org import utcnow

SIM_PHASES = ["opening", "arguments", "judge_questions", "outcome"]
SIM_AGENTS = ["orchestrator", "plaintiff", "defendant", "judge", "informer", "witness"]
SIM_STATUSES = [
    "pending",
    "running",
    "paused",
    "human_input",
    "completed",
    "failed",
    "cancelled",
]


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    scenario_version_id: Mapped[str] = mapped_column(
        ForeignKey("scenario_versions.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="pending")
    phase: Mapped[str] = mapped_column(String(32), default="opening")
    active_agents: Mapped[list] = mapped_column(JSONType, default=list)
    participants: Mapped[list] = mapped_column(JSONType, default=list)
    turn_limit: Mapped[int] = mapped_column(Integer, default=8)
    current_turn: Mapped[int] = mapped_column(Integer, default=0)
    focus_areas: Mapped[list] = mapped_column(JSONType, default=list)
    injected_facts: Mapped[list] = mapped_column(JSONType, default=list)
    state: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    started_by: Mapped[str] = mapped_column(String(36), default="")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    turns: Mapped[list[SimulationTurn]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationTurn.turn_number",
    )
    case_study: Mapped[CaseStudy | None] = relationship(
        back_populates="simulation", uselist=False
    )
    audio: Mapped[list[SimulationAudio]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationAudio.turn_number",
    )


class SimulationTurn(Base):
    __tablename__ = "simulation_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    simulation_id: Mapped[str] = mapped_column(
        ForeignKey("simulations.id"), index=True, nullable=False
    )
    turn_number: Mapped[int] = mapped_column(Integer, default=0)
    phase: Mapped[str] = mapped_column(String(32), default="opening")
    agent_role: Mapped[str] = mapped_column(String(32), default="")
    message_type: Mapped[str] = mapped_column(String(64), default="simulation.turn")
    text: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(JSONType, default=list)
    payload: Mapped[dict | None] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    simulation: Mapped[Simulation] = relationship(back_populates="turns")


class CaseStudy(Base):
    __tablename__ = "case_studies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    simulation_id: Mapped[str] = mapped_column(
        ForeignKey("simulations.id"), index=True, nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    markdown_content: Mapped[str] = mapped_column(Text, default="")
    citations: Mapped[list] = mapped_column(JSONType, default=list)
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft|published
    generated_by: Mapped[str] = mapped_column(String(36), default="")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    simulation: Mapped[Simulation] = relationship(back_populates="case_study")


# Audio asset kinds persisted post-run. kind is one of:
#   "learning"  – narrated pedagogical overview of the whole outcome
#   "roleplay"  – full concatenated role-play of all spoken turns
#   "turn"      – a single spoken agent turn (distinct voice per role)
AUDIO_KINDS = ["learning", "roleplay", "turn", "run"]
AUDIO_STATUSES = ["pending", "ready", "error"]


class SimulationAudio(Base):
    __tablename__ = "simulation_audio"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    simulation_id: Mapped[str] = mapped_column(
        ForeignKey("simulations.id"), index=True, nullable=False
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), default="turn")
    agent_role: Mapped[str] = mapped_column(String(32), default="")
    turn_number: Mapped[int] = mapped_column(Integer, default=0)
    file_name: Mapped[str] = mapped_column(String(255), default="")
    format: Mapped[str] = mapped_column(String(16), default="mp3")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    estimated_tokens: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    simulation: Mapped[Simulation] = relationship(back_populates="audio")
