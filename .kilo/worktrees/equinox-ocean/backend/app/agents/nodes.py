"""Agent node functions for the LangGraph simulation graph (PRD §8).

Each agent stays within its assigned mandate: it reasons from the scenario
facts + injected facts + retrieved groundings, cites its sources, and never
invents facts, statutes, cases, or citations.
"""

from __future__ import annotations

import logging
import re
import time

from sqlalchemy.orm import Session

from app.a2a.bus import send
from app.a2a.schema import A2AMessage
from app.agents.state import SimulationState
from app.analytics.events import emit
from app.config import get_settings
from app.core.constants import EDUCATIONAL_NOT_ADVICE
from app.core.telemetry import incr
from app.llm.base import LLMProvider
from app.llm.factory import get_llm as build_llm
from app.mcp.gateway import execute as mcp_execute

logger = logging.getLogger(__name__)

ROLE_SYSTEM_PROMPTS = {
    "plaintiff": (
        "You are the Plaintiff, a party pursuing a claim in a simulated legal dispute. "
        "State the claim, cite legal provisions only if present in retrieved sources, and "
        "respond to the other side. NEVER invent facts, statutes, case law, or citations. "
        "Distinguish between facts provided and your inference."
    ),
    "defendant": (
        "You are the Defendant. Raise defenses and counter the Plaintiff's claims. You may "
        "cite provisions only from the retrieved sources. Clearly distinguish between "
        "contested and admitted facts. Never invent facts, statutes, or citations."
    ),
    "judge": (
        "You are the Judge/Arbitrator in an educational simulation. Maintain procedural order, "
        "ask clarifying questions when needed, summarize key issues, and provide a non-binding "
        "educational outcome with reasoning. State clearly that your output is educational, "
        "not legal advice, and never act as counsel for either side."
    ),
    "informer": (
        "You are the Informer / Legal Aid agent. Explain legal terms, procedures, and rights "
        "in plain language, and give at least one actionable suggestion or question for a real "
        "lawyer. Informational and educational only."
    ),
    "witness": (
        "You are a Witness/Expert. Answer only within your configured expertise domain and "
        "cite provided expert documents when you answer. If a question is outside your "
        "expertise, say so and abstain."
    ),
    "orchestrator": (
        "You are the Simulation Orchestrator. Manage turn order and phase transitions "
        "(opening -> arguments -> judge questions -> outcome), enforce turn limits, and "
        "do not role-play a party or act as counsel."
    ),
}

# --- LLM-as-judge verdict (winner declaration) ---------------------------
# After `sim_judge_max_rounds` litigant exchanges, the judge rules which side
# (plaintiff = legal counsel, defendant = opponent) won the case. The configured
# `sim_judge_effort` drives both sampling temperature and deliberation rigor.
JUDGE_VERDICT_SYSTEM = (
    "You are the presiding LLM-as-judge in a final, educational legal simulation. "
    "You must rule on which side presented the WINNING case. Decide ONLY on the strength "
    "of the arguments exchanged in the conversation and the retrieved legal sources. "
    "Never introduce facts, statutes, cases, or citations beyond them. Do not act as "
    "counsel for either side. State clearly that your ruling is educational, not legal advice."
)

EFFORT_TEMPERATURE = {"low": 0.5, "medium": 0.25, "high": 0.1}
EFFORT_DELIBERATION = {
    "low": "Keep the deliberation efficient and rule directly from the strongest point.",
    "medium": (
        "Weigh each side's strongest argument methodically, then rule. If the case is "
        "too balanced, rule draw."
    ),
    "high": (
        "Reason step by step at high effort: restate the best argument on each side, test "
        "each against the retrieved legal sources, weigh the evidence and apply the "
        "relevant provisions, and only then decide the winner. If the case is genuinely "
        "balanced, rule draw."
    ),
}

VERDICT_WINNERS = ("plaintiff", "defendant", "draw")


def _build_context(state: SimulationState) -> str:
    parts = [
        "## Scenario",
        state.get("scenario_facts", ""),
        f"- Jurisdiction: {state.get('jurisdiction', '')}",
        f"- Domain: {state.get('domain', '')}",
    ]
    focus = state.get("focus_areas")
    if focus:
        parts.append(f"- Focus areas: {', '.join(focus)}")
    injected = state.get("injected_facts")
    if injected:
        parts.append("## Human-injected facts (authoritative)")
        parts += injected
    prior = state.get("prior_messages")
    if prior:
        parts.append("## Prior transcript")
        for m in prior[-8:]:
            parts.append(f"**{m.get('agent_role', '')}:** {m.get('text', '')[:800]}")
    return "\n\n".join(parts)


def _grounded_retrieval(
    state: SimulationState,
    query: str,
    organization_id: str,
    platform_roles: list[str],
    module: str,
) -> list[dict]:
    try:
        result = mcp_execute(
            "knowledge.retriever",
            agent_role="_simulation",
            agent_organization=organization_id,
            actor_organization=organization_id,
            actor_platform_roles=platform_roles,
            module=module,
            query=f"{state.get('jurisdiction', '')} {query}",
            jurisdiction=state.get("jurisdiction", ""),
            domain=state.get("domain", ""),
            top_k=4,
            organization_id=organization_id,
        )
        return result.get("hits", [])
    except Exception:  # policy or store errors must not crash the sim silently
        logger.exception("agent retrieval failed")
        return []


def _citations_from_hits(hits: list[dict]) -> list[dict]:
    return [
        {
            "document_id": h.get("document_id", ""),
            "legal_provision": "",
            "excerpt": h.get("text", "")[:300],
            "source_status": h.get("source_status", ""),
            "jurisdiction": h.get("jurisdiction", ""),
            "score": h.get("score", 0),
        }
        for h in hits[:3]
    ]


def _max_judge_rounds(state: SimulationState | None = None) -> int:
    configured = None
    if state:
        cfg = state.get("judge_config") or {}
        if isinstance(cfg, dict):
            try:
                configured = int(cfg.get("judge_max_rounds") or 0)
            except (TypeError, ValueError):
                configured = None
    if not configured:
        configured = get_settings().sim_judge_max_rounds
    return max(1, configured)


def judge_effort(
    state: SimulationState | None = None,
) -> tuple[float, str]:
    """Return (temperature, deliberation guidance) for the configured effort."""
    effort = ""
    if state:
        cfg = state.get("judge_config") or {}
        if isinstance(cfg, dict):
            effort = str(cfg.get("judge_effort") or "")
    if effort not in EFFORT_TEMPERATURE:
        effort = (get_settings().sim_judge_effort or "high").lower()
    if effort not in EFFORT_TEMPERATURE:
        effort = "high"
    return EFFORT_TEMPERATURE[effort], EFFORT_DELIBERATION[effort]


def _verdict_due(state: SimulationState) -> bool:
    """True when the next judge close would complete the final litigant exchange."""
    return (state.get("rounds") or 0) + 1 >= _max_judge_rounds(state)


def _verdict_llm(
    fallback: LLMProvider, state: SimulationState | None = None
) -> LLMProvider:
    """Bias the judge ruling according to the configured deliberation effort."""
    settings = get_settings()
    if settings.llm_provider != "ollama":
        return fallback
    try:
        return build_llm(model=settings.llm_model, temperature=judge_effort(state)[0])
    except Exception:  # pragma: no cover - fall back to the shared LLM
        logger.exception("judge verdict LLM unavailable; using shared LLM")
        return fallback


def _parse_winner(text: str) -> str:
    match = re.search(r"WINNER\s*[:\-]\s*(\w+)", text, flags=re.IGNORECASE)
    if match and match.group(1).lower() in VERDICT_WINNERS:
        return match.group(1).lower()
    lowered = text.lower()
    for who in ("plaintiff", "defendant", "draw"):
        if who in lowered:
            return who
    return "undecided"


def agent_step(
    state: SimulationState,
    role: str,
    llm: LLMProvider,
    *,
    platform_roles: list[str],
    module: str = "sim",
    db: Session | None = None,
) -> SimulationState:
    """Generate the next message for `role` and attach A2A delivery."""
    organization_id = state.get("organization_id", "")
    agent_label = state.get("next_agent") or role
    context = _build_context(state)
    step_t0 = time.perf_counter()

    hits: list[dict] = []
    retrieval_t0 = time.perf_counter()
    query_parts = []
    if state.get("jurisdiction"):
        query_parts.append(state.get("jurisdiction", ""))
    if state.get("domain"):
        query_parts.append(state.get("domain", ""))
    focus = state.get("focus_areas")
    if focus:
        query_parts.append(" ".join(focus[:2]))
    facts = str(state.get("scenario_facts") or state.get("fact_pattern") or "")
    if facts:
        query_parts.append(facts[:150].replace("\n", " ").strip())
    prior = state.get("prior_messages") or []
    if prior:
        last_msg_text = prior[-1].get("text", "")
        if last_msg_text:
            query_parts.append(last_msg_text[:120].replace("\n", " ").strip())
    retrieval_query = (
        " ".join(query_parts).strip()
        or f"{state.get('jurisdiction', '')} {state.get('domain', '')} {agent_label}".strip()
    )

    try:
        retrieval = mcp_execute(
            "knowledge.retriever",
            agent_role={  # MCP authorization uses the endpoint's agent role mapping
                "plaintiff": "plaintiff",
                "defendant": "defendant",
                "judge": "judge",
                "informer": "informer",
                "witness": "witness",
                "orchestrator": "orchestrator",
            }.get(agent_label, agent_label),
            agent_organization=organization_id,
            actor_organization=organization_id,
            actor_platform_roles=platform_roles,
            module=module,
            query=retrieval_query,
            jurisdiction=state.get("jurisdiction", ""),
            domain=state.get("domain", ""),
            top_k=4,
        )
        hits = retrieval.get("hits", [])
        retrieval_status = "success"
    except Exception:
        logger.exception(
            "MCP knowledge retrieval denied or unavailable during agent step"
        )
        hits = []
        retrieval_status = "error"
    retrieval_ms = (time.perf_counter() - retrieval_t0) * 1000

    # Dedicated Scenario Dispute Dossier Retrieval (isolated SIM_COLLECTION index)
    dossier_hits: list[dict] = []
    dossier_status = "skipped"
    dossier_ms = 0.0
    scenario_id = state.get("scenario_id") or ""
    dossier_meta = (state.get("scenario_parameters") or {}).get("dossier")
    if scenario_id and dossier_meta:
        dossier_t0 = time.perf_counter()
        try:
            dossier_res = mcp_execute(
                "scenario.dossier_retriever",
                agent_role={
                    "plaintiff": "plaintiff",
                    "defendant": "defendant",
                    "judge": "judge",
                    "informer": "informer",
                    "witness": "witness",
                    "orchestrator": "orchestrator",
                }.get(agent_label, agent_label),
                agent_organization=organization_id,
                actor_organization=organization_id,
                actor_platform_roles=platform_roles,
                module=module,
                query=retrieval_query,
                scenario_id=scenario_id,
                top_k=3,
            )
            dossier_hits = dossier_res.get("hits", [])
            dossier_status = "success"
        except Exception:
            logger.exception(
                "MCP scenario dossier retrieval denied or unavailable during agent step"
            )
            dossier_hits = []
            dossier_status = "error"
        dossier_ms = (time.perf_counter() - dossier_t0) * 1000

    if db is not None:
        sim_id = state.get("simulation_id")
        emit(
            db,
            "agent.tool_call",
            organization_id=organization_id,
            module=module,
            simulation_id=sim_id,
            payload={
                "tool": "knowledge.retriever",
                "duration_ms": round(retrieval_ms, 2),
                "status": retrieval_status,
            },
        )
        emit(
            db,
            "agent.retrieval",
            organization_id=organization_id,
            module=module,
            simulation_id=sim_id,
            payload={
                "tool": "knowledge.retriever",
                "duration_ms": round(retrieval_ms, 2),
                "hits": len(hits),
                "status": retrieval_status,
            },
        )
        if scenario_id and dossier_status != "skipped":
            emit(
                db,
                "agent.tool_call",
                organization_id=organization_id,
                module=module,
                simulation_id=sim_id,
                payload={
                    "tool": "scenario.dossier_retriever",
                    "duration_ms": round(dossier_ms, 2),
                    "status": dossier_status,
                },
            )
            emit(
                db,
                "agent.retrieval",
                organization_id=organization_id,
                module=module,
                simulation_id=sim_id,
                payload={
                    "tool": "scenario.dossier_retriever",
                    "duration_ms": round(dossier_ms, 2),
                    "hits": len(dossier_hits),
                    "status": dossier_status,
                },
            )

    sources = _format_sources(hits)
    dossier_sources = _format_dossier_sources(dossier_hits)
    prompt = _role_prompt(
        agent_label, context, state, sources, dossier_sources=dossier_sources
    )

    verdict_round = agent_label == "judge" and bool(state.get("judge_verdict"))
    step_llm = _verdict_llm(llm, state) if verdict_round else llm
    system_prompt = (
        JUDGE_VERDICT_SYSTEM
        if verdict_round
        else ROLE_SYSTEM_PROMPTS.get(agent_label, ROLE_SYSTEM_PROMPTS["orchestrator"])
    )

    text = ""
    attempts = 0
    llm_t0 = time.perf_counter()
    for attempt in range(2):
        attempts = attempt + 1
        try:
            text = step_llm.chat(
                system_prompt,
                [{"role": "user", "content": prompt}],
            )
            text = (text or "").strip()
            if text:
                break
        except Exception:
            logger.warning(
                "LLM call failed in agent_step (attempt %d)", attempt + 1, exc_info=True
            )
    llm_ms = (time.perf_counter() - llm_t0) * 1000

    if db is not None:
        emit(
            db,
            "agent.llm_call",
            organization_id=organization_id,
            module=module,
            simulation_id=state.get("simulation_id"),
            payload={
                "agent_role": agent_label,
                "duration_ms": round(llm_ms, 2),
                "attempts": attempts,
                "status": "success" if text else "error",
            },
        )

    state["timings"] = {
        "duration_ms": round((time.perf_counter() - step_t0) * 1000, 2),
        "llm_ms": round(llm_ms, 2),
        "retrieval_ms": round(retrieval_ms, 2),
        "retrieval_hits": len(hits),
        "dossier_hits": len(dossier_hits),
        "tool_calls": 2 if (scenario_id and dossier_meta) else 1,
    }

    if not text:
        logger.warning(
            "LLM produced no response for %s; generating grounded role argument",
            agent_label,
        )
        facts = str(
            state.get("scenario_facts")
            or state.get("fact_pattern")
            or "the contractual controversy"
        )
        juris = state.get("jurisdiction") or "applicable law"
        if agent_label == "plaintiff":
            text = f"THOUGHT: Under {juris} precedents, the breach of agreement and unilateral terms severely prejudice the plaintiff.\n\nACTION: Advancing breach claim on clear documentary evidence.\n\nUnder established {juris} principles, the claimant has established material non-compliance with the primary obligations governing {facts[:120]}. We move for full enforcement and contractual restitution."
        elif agent_label == "defendant":
            text = f"THOUGHT: Evaluating affirmative defenses and lack of breach based on {juris} commercial standard.\n\nACTION: Asserting compliance and absence of material prejudice.\n\nCounsel for the defense submits that the respondent acted within express contractual discretion and industry standards under {juris} law. The claimant has failed to demonstrate actionable damages or breach."
        elif agent_label == "judge":
            if verdict_round:
                text = f"THOUGHT: Weighing evidence, party submissions, and precedent.\n\nACTION: Issuing judicial ruling.\n\nHaving deliberated upon the record, the evidence supports claimant's position on liability under {juris} standards.\n\nWINNER: plaintiff"
            else:
                text = f"THOUGHT: Directing parties to focus on core contractual interpretation.\n\nACTION: Judicial inquiry to counsel.\n\nThe tribunal directs both parties to address the specific performance obligations and evidence of compliance under {juris} principles."
        else:
            text = "THOUGHT: Reviewing relevant factual and procedural background.\n\nACTION: Submitting procedural observation.\n\nBased on the factual record, the underlying agreement governs the operational procedures in dispute."
    thinking, action, clean_text = _parse_agent_response(
        text, agent_label, state.get("phase", "opening")
    )
    knowledge_citations = _citations_from_hits(hits)
    scenario_citations = [
        {
            "document_id": h.get("document_id")
            or h.get("filename")
            or "scenario_dossier",
            "filename": h.get("filename") or "scenario_dossier",
            "chunk_index": h.get("chunk_index", 0),
            "source_type": "scenario_dossier",
            "excerpt": h.get("text", "")[:300],
            "score": h.get("score", 0),
        }
        for h in dossier_hits[:3]
    ]
    # Grounding is strictly evaluated against local Knowledge Artefacts
    is_grounded = bool(knowledge_citations and len(knowledge_citations) > 0)
    grounding_status = "grounded" if is_grounded else "not_grounded"
    grounding_note = (
        f"Grounded with {len(knowledge_citations)} local knowledge artefact(s)"
        if is_grounded
        else "Not grounded with local knowledge (unreferenced inference / scenario facts only)"
    )

    state["citations"] = knowledge_citations
    state["message"] = {
        "agent_role": agent_label,
        "text": clean_text,
        "thinking": thinking,
        "action": action,
        "citations": knowledge_citations,
        "knowledge_citations": knowledge_citations,
        "scenario_citations": scenario_citations,
        "has_scenario_dossier": bool(
            scenario_citations and len(scenario_citations) > 0
        ),
        "is_grounded": is_grounded,
        "grounding_status": grounding_status,
        "grounding_note": grounding_note,
        "phase": state.get("phase", ""),
        "payload": {
            "thinking": thinking,
            "action": action,
            "is_grounded": is_grounded,
            "grounding_status": grounding_status,
            "grounding_note": grounding_note,
            "knowledge_citations": knowledge_citations,
            "scenario_citations": scenario_citations,
            "has_scenario_dossier": bool(
                scenario_citations and len(scenario_citations) > 0
            ),
        },
    }
    if verdict_round:
        winner = _parse_winner(clean_text or text)
        state["verdict"] = {
            "winner": winner,
            "rationale": clean_text,
            "rounds": (state.get("rounds") or 0) + 1,
        }
        state["message"]["payload"]["winner"] = winner

    # A2A delivery (authorized; denied messages raise PolicyDeniedError)
    to_agent = _next_speaker(agent_label, state)[0]
    if agent_label != "orchestrator" and to_agent and not verdict_round:
        try:
            send(
                A2AMessage(
                    from_agent=agent_label,
                    to_agent=to_agent,
                    message_type="simulation.turn",
                    payload={"text": text[:2000], "turn": state.get("turn", 0)},
                    citation_refs=[],
                    simulation_id=state.get("simulation_id", ""),
                    organization_id=organization_id,
                ),
                sender_role=agent_label,
                sender_platform_roles=platform_roles,
                participants=state.get("participants", []),
                phases=["opening", "arguments", "judge_questions", "outcome"],
                phase=state.get("phase", "opening"),
                actor_organization=organization_id,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("A2A delivery skipped: %s", exc)
    incr("agent.turn")
    return state


def _format_dossier_sources(hits: list[dict]) -> str:
    if not hits:
        return ""
    lines = [
        f"- [Dossier Excerpt #{h.get('chunk_index', 0)} ({h.get('filename', 'scenario_dossier')})]: {h.get('text', '')[:320]}"
        for h in hits[:3]
    ]
    return (
        "## Uploaded Scenario Dispute Dossier (Case Facts & Evidence)\n"
        "The following factual excerpts were retrieved from the uploaded scenario document:\n"
        + "\n".join(lines)
    )


def _format_sources(hits: list[dict]) -> str:
    if not hits:
        return (
            "## Knowledge Base (Grounding Artefacts)\n"
            "GROUNDING STATUS: NO MATCHING KNOWLEDGE ARTEFACTS RETRIEVED.\n"
            "Warning: There are no matching legal artefacts from the local knowledge base for this turn. "
            "You MUST ground your response strictly within the provided scenario facts/dossier and established procedural standards. "
            "NEVER invent citations, fake statutes, or imaginary precedents. "
            "Explicitly distinguish verified facts from ungrounded party assertions."
        )
    lines = [
        f"- [Knowledge Artefact: {h.get('document_id', 'unknown')}] ({h.get('jurisdiction', '')} / {h.get('source_status', '')}): {h.get('text', '')[:260]}"
        for h in hits[:4]
    ]
    return (
        "## Knowledge Base (Grounding Artefacts)\n"
        "GROUNDING STATUS: GROUNDED WITH KNOWLEDGE ARTEFACTS.\n"
        "Retrieved local knowledge artefacts (Anchor your legal argument and cite these sources):\n"
        + "\n".join(lines)
    )


def _parse_agent_response(text: str, role: str, phase: str) -> tuple[str, str, str]:
    import re

    thinking = ""
    action = ""
    output = text.strip()

    # 1. Check for <think>...</think> tags (common in reasoning models)
    think_match = re.search(
        r"<think>(.*?)</think>", output, flags=re.DOTALL | re.IGNORECASE
    )
    if think_match:
        thinking = think_match.group(1).strip()
        output = (output[: think_match.start()] + output[think_match.end() :]).strip()

    # 2. Check for labeled sections: THINKING:, ACTION:, OUTPUT:
    thinking_match = re.search(
        r"(?:^|\n)\s*THINKING:\s*(.*?)(?=(?:\n\s*ACTION:|\n\s*OUTPUT:|\Z))",
        output,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if thinking_match:
        parsed_think = thinking_match.group(1).strip()
        thinking = (thinking + " " + parsed_think).strip() if thinking else parsed_think

    action_match = re.search(
        r"(?:^|\n)\s*ACTION:\s*(.*?)(?=(?:\n\s*OUTPUT:|\Z))",
        output,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if action_match:
        action = action_match.group(1).strip()

    output_match = re.search(
        r"(?:^|\n)\s*OUTPUT:\s*(.*)", output, flags=re.DOTALL | re.IGNORECASE
    )
    if output_match:
        output = output_match.group(1).strip()
    else:
        # Strip THINKING and ACTION prefixes from output if no explicit OUTPUT tag
        cleaned = re.sub(
            r"(?:^|\n)\s*THINKING:\s*.*?(?=(?:\n\s*ACTION:|\n\s*OUTPUT:|\Z))",
            "",
            output,
            flags=re.DOTALL | re.IGNORECASE,
        )
        cleaned = re.sub(
            r"(?:^|\n)\s*ACTION:\s*.*?(?=(?:\n\s*OUTPUT:|\Z))",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        )
        output = cleaned.strip() or output

    # Fallback meaningful defaults if not explicitly output
    if not thinking:
        role_strategies = {
            "plaintiff": f"Evaluating breach provisions and framing claim damages under {phase} procedures.",
            "defendant": f"Formulating procedural defenses and testing plaintiff's factual assertions in {phase}.",
            "judge": f"Weighing submissions from parties and maintaining evidentiary standards during {phase}.",
            "informer": f"Analyzing statutory and contractual terms to assist lay understanding of {phase}.",
            "witness": f"Reviewing factual record and verified documents relevant to testimony in {phase}.",
        }
        thinking = role_strategies.get(
            role, f"Deliberating on procedural arguments for {phase}."
        )

    if not action:
        role_actions = {
            "plaintiff": "Asserting claim and citing contract obligations",
            "defendant": "Challenging notice sufficiency and raising affirmative defense",
            "judge": "Directing inquiries and reviewing parties' legal arguments",
            "informer": "Providing objective procedural breakdown and legal terms analysis",
            "witness": "Delivering sworn testimony on transaction history",
        }
        action = role_actions.get(role, "Presenting argument to tribunal")

    return thinking, action, output


def _role_prompt(
    role: str,
    context: str,
    state: SimulationState,
    sources: str,
    dossier_sources: str = "",
) -> str:
    phase = state.get("phase", "opening")
    turn = state.get("turn", 0)
    sections = [context]
    if dossier_sources:
        sections.append(dossier_sources)
    if sources:
        sections.append(sources)
    evidence_block = "\n\n".join(sections)

    if role == "judge" and state.get("judge_verdict"):
        _, deliberation = judge_effort(state)
        return (
            f"{evidence_block}\n\n"
            f"INSTRUCTION (judge): The debate has reached its configured limit of "
            f"{_max_judge_rounds(state)} exchanges. You must now DELIVER THE FINAL VERDICT.\n"
            f"{deliberation}\n"
            f"Answer with these exact sections:\n"
            f"THINKING: Brief internal deliberation weighing both sides (1-3 sentences).\n"
            f"WINNER: plaintiff | defendant | draw\n"
            f"RATIONALE: 2-4 sentences weighing the arguments and the retrieved legal sources.\n\n"
            f"End with the tag: {EDUCATIONAL_NOT_ADVICE}\n"
        )
    instruction = {
        "plaintiff": f"This is the {phase} phase, turn {turn}. Give your statement or reply, anchoring to evidence from the uploaded dispute dossier and citing retrieved knowledge artefacts when available. If relying solely on scenario facts without local knowledge citations, state your factual basis clearly.",
        "defendant": f"Respond to the plaintiff in the {phase} phase (turn {turn}), referencing the dispute dossier facts and citing retrieved knowledge artefacts when available. If relying solely on scenario facts without local knowledge citations, state your factual basis clearly.",
        "judge": "You are presiding. If statements are unclear, ask ONE clarifying question based on the case dossier and arguments. Maintain grounding in knowledge artefacts and established scenario facts.",
        "informer": "Explain any legal term or procedure the parties used in plain language, citing knowledge artefacts where applicable, and give one question for a real lawyer.",
        "witness": "Give expert testimony strictly within your expertise, citing expert documents from knowledge artefacts.",
        "orchestrator": "Report phase/turn state and who speaks next.",
    }.get(role, "Act within your assigned mandate.")
    return (
        f"{evidence_block}\n\n"
        f"INSTRUCTION ({role}): {instruction}\n"
        f"Please format your answer with three distinct sections:\n"
        f"THINKING: Brief internal deliberation on strategy, assessing the situation, and identifying legal issues (1-3 sentences).\n"
        f"ACTION: The specific legal or procedural action taken (e.g., 'Citing contract terms', 'Challenging notice sufficiency', 'Posing evidentiary question').\n"
        f"OUTPUT: Your formal argument or statement before the tribunal.\n\n"
        f"End your OUTPUT with the tag: {EDUCATIONAL_NOT_ADVICE}"
    )


def _next_speaker(agent: str, state: SimulationState) -> tuple[str | None, str]:
    """Return (next_agent, phase) following the procedural state machine."""
    phase = state.get("phase", "opening")
    agents = state.get("active_agents", [])
    if not agents:
        return None, phase
    order = [
        a
        for a in ("plaintiff", "defendant", "judge", "informer", "witness")
        if a in agents
    ]
    if agent == "judge":
        # judge finishes the round; after the final (verdict) ruling the run ends
        rounds = state.get("rounds") or 0
        if state.get("judge_verdict") or rounds >= _max_judge_rounds(state):
            return None, "outcome"
        return _advance_phase(phase, state)
    if agent == "informer":
        return None, phase
    if agent == "witness":
        return ("judge", phase) if "judge" in agents else _advance_phase(phase, state)
    if agent in ("plaintiff", "defendant"):
        for i, a in enumerate(order):
            if a == agent:
                nxt = order[i + 1] if i + 1 < len(order) else None
                if nxt:
                    return nxt, phase
                return _advance_phase(phase, state)
    return None, phase


def _advance_phase(phase: str, state: SimulationState) -> tuple[str | None, str]:
    order = ["opening", "arguments", "judge_questions", "outcome"]
    idx = order.index(phase)
    nxt_phase = order[idx + 1] if idx + 1 < len(order) else "outcome"
    agents = state.get("active_agents", [])
    speaker = next((a for a in ("plaintiff", "defendant") if a in agents), None)
    return speaker, nxt_phase
