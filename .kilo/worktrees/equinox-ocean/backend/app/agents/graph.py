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
    }
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
    if db is not None:
        sim = db.query(Simulation).filter(Simulation.id == sim_id).first()
        if sim is not None and sim.status not in ("running", "pending"):
            state["status"] = sim.status
            state["next_agent"] = None
            return state

    turn = state.get("turn", 0)
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

    nxt, phase = _next_speaker(last_agent, state)

    # The pending judge verdict (LLM-as-judge winner ruling) takes precedence over
    # the generic turn limit so the ruling is always rendered.
    verdict_due = nxt == "judge" and _verdict_due(state)
    state["judge_verdict"] = verdict_due

    if turn > _turn_limit(state, config) and not verdict_due:
        state["status"] = "completed"
        state["next_agent"] = None
        return state
    state["phase"] = phase
    state["next_agent"] = nxt
    state["turn"] = turn + 1
    if nxt is None:
        state["status"] = "completed"
    return state


def _turn_limit(state: SimulationState, config: RunnableConfig) -> int:
    db = _db_from_config(config)
    if db is None:
        return 8
    sim = (
        db.query(Simulation)
        .filter(Simulation.id == state.get("simulation_id", ""))
        .first()
    )
    return sim.turn_limit if sim else 8


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
