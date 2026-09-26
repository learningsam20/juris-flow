"""LangGraph graph for the multi-agent simulation engine (PRD §8.1).

Cyclic StateGraph: orchestrator sequences the phase state machine and routes to
the appropriate agent node; agents speak via the MCP-gated tool pipeline and
persist each turn to the database before control returns to the orchestrator.
The active DB session is threaded as ``config["configurable"]["db_session"]``.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents.nodes import _next_speaker, _verdict_due, agent_step
from app.agents.state import SimulationState
from app.analytics.events import emit
from app.llm.base import LLMProvider
from app.models import Simulation, SimulationTurn

logger = logging.getLogger(__name__)

AGENT_NODES = ["plaintiff", "defendant", "judge", "informer", "witness"]


def _db_from_config(config: RunnableConfig | None):
    if config is None:
        return None
    return config.get("configurable", {}).get("db_session")


def persist_step(sim_id: str, state: SimulationState, *, phase: str, db) -> None:
    if db is None:
        return
    message = state.get("message") or {}
    sim = db.query(Simulation).filter(Simulation.id == sim_id).first()
    if sim is None:
        return
    # Hard ceiling: never persist more turns than the proposed turn_limit.
    limit = max(1, int(getattr(sim, "turn_limit", 0) or state.get("turn_limit") or 8))
    if int(sim.current_turn or 0) >= limit:
        logger.warning(
            "refusing to persist turn beyond limit sim=%s current=%s limit=%s",
            sim_id,
            sim.current_turn,
            limit,
        )
        state["status"] = "completed"
        state["next_agent"] = None
        sim.status = "completed"
        db.commit()
        return

    turn_payload = dict(message.get("payload") or {})
    if "thinking" not in turn_payload and message.get("thinking"):
        turn_payload["thinking"] = message.get("thinking")
    if "action" not in turn_payload and message.get("action"):
        turn_payload["action"] = message.get("action")
    if "is_grounded" not in turn_payload and "is_grounded" in message:
        turn_payload["is_grounded"] = message["is_grounded"]
    if "grounding_status" not in turn_payload and "grounding_status" in message:
        turn_payload["grounding_status"] = message["grounding_status"]
    if "grounding_note" not in turn_payload and "grounding_note" in message:
        turn_payload["grounding_note"] = message["grounding_note"]
    if "knowledge_citations" not in turn_payload:
        turn_payload["knowledge_citations"] = message.get(
            "knowledge_citations", message.get("citations", [])
        )
    if "scenario_citations" not in turn_payload:
        turn_payload["scenario_citations"] = message.get("scenario_citations", [])
    if "has_scenario_dossier" not in turn_payload:
        turn_payload["has_scenario_dossier"] = message.get(
            "has_scenario_dossier", False
        )
    turn_payload["status"] = state.get("status", "running")
    turn_payload["turn_limit"] = limit
    verdict = state.get("verdict")
    if verdict:
        turn_payload["winner"] = verdict.get("winner")

    turn = SimulationTurn(
        id=uuid.uuid4().hex,
        simulation_id=sim_id,
        turn_number=sim.current_turn + 1,
        phase=phase,
        agent_role=message.get("agent_role", ""),
        message_type="simulation.turn",
        text=message.get("text", ""),
        citations=message.get("citations", []),
        payload=turn_payload,
    )
    db.add(turn)
    sim.current_turn += 1
    sim.phase = phase
    sim.status = state.get("status", sim.status)
    sim.state = {
        "prior_messages": state.get("prior_messages", [])[-20:],
        "last_agent": state.get("last_agent"),
        "phase": phase,
        "rounds": state.get("rounds") or 0,
        "verdict": state.get("verdict"),
        "judge_config": state.get("judge_config") or {},
        "turn_limit": limit,
    }
    if sim.current_turn >= limit:
        # Cap reached after this turn — mark complete unless a verdict still needs
        # to be recorded on this same turn (already persisted above).
        if state.get("verdict") or message.get("agent_role") == "judge":
            sim.status = "completed"
            state["status"] = "completed"
            state["next_agent"] = None
    db.commit()
    timings = state.get("timings") or {}
    emit(
        db,
        "agent.turn",
        organization_id=sim.organization_id,
        user_id=sim.started_by,
        module="sim",
        simulation_id=sim_id,
        payload={
            "agent_role": message.get("agent_role"),
            "phase": phase,
            "turn": sim.current_turn,
            "turn_limit": limit,
            "duration_ms": timings.get("duration_ms"),
            "llm_ms": timings.get("llm_ms"),
            "retrieval_ms": timings.get("retrieval_ms"),
            "retrieval_hits": timings.get("retrieval_hits"),
            "tool_calls": timings.get("tool_calls"),
        },
    )


def orchestrator_node(
    state: SimulationState, config: RunnableConfig
) -> SimulationState:
    sim_id = state.get("simulation_id", "")
    db = _db_from_config(config)
    limit = _turn_limit(state, config)
    state["turn_limit"] = limit

    if db is not None:
        sim = db.query(Simulation).filter(Simulation.id == sim_id).first()
        if sim is not None and sim.status not in ("running", "pending"):
            state["status"] = sim.status
            state["next_agent"] = None
            return state
        # Prefer DB current_turn as source of truth for the hard ceiling.
        if sim is not None and int(sim.current_turn or 0) >= limit:
            state["status"] = "completed"
            state["next_agent"] = None
            if sim.status != "completed":
                sim.status = "completed"
                db.commit()
            return state

    turn = int(state.get("turn", 0) or 0)
    if turn == 0:
        state["rounds"] = state.get("rounds") or 0
        state["judge_verdict"] = False
        agents = state.get("active_agents", [])
        first = next((a for a in ("plaintiff", "defendant") if a in agents), None)
        state["next_agent"] = first or None
        state["phase"] = "opening"
        state["turn"] = 1
        state["status"] = "running"
        if not first:
            state["status"] = "failed"
        return state

    last_agent = state.get("last_agent")
    if last_agent is None:
        state["status"] = "failed"
        state["next_agent"] = None
        return state

    # Each judge close completes one litigant exchange ("conversation").
    if last_agent == "judge":
        state["rounds"] = (state.get("rounds") or 0) + 1

    # Hard stop: proposed turn budget already consumed.
    if turn >= limit:
        state["status"] = "completed"
        state["next_agent"] = None
        state["phase"] = "outcome"
        return state

    nxt, phase = _next_speaker(last_agent, state)
    remaining_slots = limit - turn  # how many turns can still be scheduled
    agents = state.get("active_agents", [])

    # Accelerate wrap-up: when the budget is tight, skip lingering argument
    # phases and pull the judge forward so a ruling lands inside the limit.
    if (
        remaining_slots <= 3
        and "judge" in agents
        and not state.get("verdict")
        and phase in ("opening", "arguments")
        and last_agent in ("plaintiff", "defendant", "witness")
    ):
        phase = "judge_questions"
        if remaining_slots <= 2 or _verdict_due(state):
            nxt = "judge"

    # On the final remaining slot, force a judge verdict when a judge is active
    # and no winner has been recorded yet — never overrun the proposed limit.
    if (
        remaining_slots <= 1
        and "judge" in agents
        and not state.get("verdict")
        and last_agent != "judge"
    ):
        nxt = "judge"
        phase = "judge_questions" if phase not in ("outcome", "judge_questions") else phase
        state["judge_verdict"] = True
    else:
        # Also force verdict when ≤2 slots remain and judge is about to speak.
        force_late_verdict = (
            remaining_slots <= 2
            and nxt == "judge"
            and not state.get("verdict")
        )
        verdict_due = nxt == "judge" and (_verdict_due(state) or force_late_verdict)
        state["judge_verdict"] = bool(verdict_due)

    # Scheduling another turn would exceed the hard limit.
    if turn + 1 > limit:
        state["status"] = "completed"
        state["next_agent"] = None
        state["phase"] = "outcome"
        return state

    state["phase"] = phase
    state["next_agent"] = nxt
    state["turn"] = turn + 1
    if nxt is None:
        state["status"] = "completed"
    return state


def _turn_limit(state: SimulationState, config: RunnableConfig) -> int:
    configured = int(state.get("turn_limit") or 0)
    db = _db_from_config(config)
    if db is not None:
        sim = (
            db.query(Simulation)
            .filter(Simulation.id == state.get("simulation_id", ""))
            .first()
        )
        if sim is not None and sim.turn_limit:
            configured = int(sim.turn_limit)
    return max(1, configured or 8)


def _router(state: SimulationState) -> str:
    nxt = state.get("next_agent")
    if nxt in AGENT_NODES:
        return nxt
    return END


def _make_agent_node(role: str, llm: LLMProvider, platform_roles: list[str]):
    def node(state: SimulationState, config: RunnableConfig) -> SimulationState:
        phase_before = state.get("phase", "opening")
        agent_step(
            state,
            role,
            llm,
            platform_roles=platform_roles,
            db=_db_from_config(config),
        )
        state["last_agent"] = role
        state["prior_messages"] = state.get("prior_messages", []) + [
            {
                "agent_role": role,
                "text": state.get("message", {}).get("text", ""),
                "phase": phase_before,
            }
        ]
        persist_step(
            state.get("simulation_id", ""),
            state,
            phase=phase_before,
            db=_db_from_config(config),
        )
        state["next_agent"] = None
        return state

    return node


def build_simulation_graph(llm: LLMProvider, platform_roles: list[str]) -> Any:
    graph = StateGraph(SimulationState)  # type: ignore[arg-type]
    graph.add_node("orchestrator", orchestrator_node)
    for role in AGENT_NODES:
        graph.add_node(role, _make_agent_node(role, llm, platform_roles))

    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges("orchestrator", _router)
    for role in AGENT_NODES:
        graph.add_edge(role, "orchestrator")
    return graph.compile()


def run_once(
    state: SimulationState, llm: LLMProvider, platform_roles: list[str], *, db=None
):
    compiled = build_simulation_graph(llm, platform_roles)
    return compiled.invoke(
        state, config={"recursion_limit": 40, "configurable": {"db_session": db}}
    )
