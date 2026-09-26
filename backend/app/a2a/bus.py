"""A2A message bus: validate schema, authorize via OPA, route, and audit (PRD §8, §15.4)."""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.a2a.schema import A2AEnvelope, A2AMessage
from app.core.errors import PolicyDeniedError, ValidationError
from app.core.telemetry import incr
from app.opa.engine import get_engine

logger = logging.getLogger(__name__)

# in-memory route table for agent-to-agent delivery
_hooks: dict[str, Callable[[A2AEnvelope], None]] = {}


def register_handler(agent_role: str, handler: Callable[[A2AEnvelope], None]) -> None:
    _hooks[agent_role] = handler


def send(
    message: A2AMessage,
    *,
    sender_role: str,
    sender_platform_roles: list[str],
    participants: list[str],
    phases: list[str],
    phase: str,
    actor_organization: str,
) -> A2AEnvelope:
    if message.from_agent == message.to_agent:
        raise ValidationError("agents cannot message themselves")
    envelope = A2AEnvelope(
        message=message,
        sender_role=sender_role,
        sender_platform_roles=sender_platform_roles,
        participants=participants,
        phases=phases,
        phase=phase,
    )
    decision_input = {
        "organization": {
            "organization_id": actor_organization,
            "participants": participants,
            "phases": phases,
            "phase": phase,
        },
        "message": message.model_dump(),
        "user": {
            "organization_id": actor_organization,
            "platform_roles": sender_platform_roles,
        },
    }
    decision = get_engine().decide("a2a", decision_input)
    if not decision.allow:
        incr("a2a.denied")
        raise PolicyDeniedError(f"A2A message denied: {decision.reason}")
    incr("a2a.sent")

    handler = _hooks.get(message.to_agent)
    if handler:
        handler(envelope)
    return envelope
