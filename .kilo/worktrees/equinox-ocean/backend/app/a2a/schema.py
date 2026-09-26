"""A2A structured agent-to-agent message schema (PRD §8, §14).

Every agent communicates using messages with ``from_agent``, ``to_agent``,
``message_type``, ``payload`` and ``citation_refs``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class A2ACitation(BaseModel):
    document_id: str = ""
    chunk_id: str | None = None
    legal_provision: str = ""
    excerpt: str = ""


class A2AMessage(BaseModel):
    from_agent: str
    to_agent: str
    message_type: str = Field(default="simulation.turn")
    payload: dict[str, Any] = Field(default_factory=dict)
    citation_refs: list[A2ACitation] = Field(default_factory=list)
    simulation_id: str = ""
    organization_id: str = ""


class A2AEnvelope(BaseModel):
    """Message plus authorization context (filled by the bus)."""

    message: A2AMessage
    sender_role: str = ""
    sender_platform_roles: list[str] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)
    phase: str = "opening"
