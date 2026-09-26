"""LangGraph simulation state (PRD §8)."""

from __future__ import annotations

from typing import Any, TypedDict


class SimulationState(TypedDict, total=False):
    simulation_id: str
    organization_id: str
    scenario_id: str
    scenario_parameters: dict[str, Any]
    scenario_title: str
    scenario_facts: str
    jurisdiction: str
    domain: str
    phase: str
    turn: int
    next_agent: str | None
    last_agent: str | None
    active_agents: list[str]
    participants: list[str]
    focus_areas: list[str]
    injected_facts: list[str]
    prior_messages: list[dict]
    citations: list[dict]
    message: dict[str, Any]
    outcome: str
    reasoning: str
    issues: list[str]
    status: str
    rounds: int
    judge_verdict: bool
    verdict: dict[str, Any]
    judge_config: dict[str, Any]
    timings: dict[str, Any]
    turn_limit: int


def phase_order() -> dict[str, int]:
    return {"opening": 0, "arguments": 1, "judge_questions": 2, "outcome": 3}


def initial_state(simulation: dict) -> SimulationState:
    state: SimulationState = {
        "simulation_id": simulation["id"],
        "organization_id": simulation["organization_id"],
        "scenario_id": simulation.get("scenario_id", ""),
        "scenario_parameters": simulation.get("scenario_parameters") or {},
        "scenario_title": simulation.get("scenario_title", ""),
        "scenario_facts": simulation.get("fact_pattern", ""),
        "jurisdiction": simulation.get("jurisdiction", ""),
        "domain": simulation.get("domain", ""),
        "phase": simulation.get("phase", "opening"),
        "turn": simulation.get("turn", 0),
        "turn_limit": int(simulation.get("turn_limit") or 8),
        "active_agents": simulation.get(
            "active_agents", ["plaintiff", "defendant", "judge"]
        ),
        "participants": simulation.get("participants", []),
        "focus_areas": simulation.get("focus_areas", []),
        "injected_facts": simulation.get("injected_facts", []),
        "prior_messages": simulation.get("prior_messages", []),
        "citations": [],
        "message": {},
        "last_agent": simulation.get("last_agent"),
        "next_agent": simulation.get("next_agent"),
        "status": simulation.get("status", "running"),
        "rounds": simulation.get("rounds", 0),
        "judge_config": simulation.get("judge_config") or {},
    }
    if simulation.get("verdict"):
        state["verdict"] = simulation["verdict"]
    return state
