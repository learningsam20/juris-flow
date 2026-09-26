"""Simulation lifecycle service: start, drive, pause/resume, inject, complete (PRD §5.1, §6.4)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.casestudy import build_case_study
from app.agents.graph import run_once
from app.agents.state import initial_state
from app.analytics.events import emit
from app.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.core.telemetry import incr
from app.db.session import SessionLocal
from app.llm.factory import get_llm, get_sim_llm
from app.models import CaseStudy, Scenario, ScenarioVersion, Simulation, SimulationTurn
from app.models.simulation import SIM_AGENTS

logger = logging.getLogger(__name__)

MIN_CORE_AGENTS = ["plaintiff", "defendant", "judge"]
_ORG_MESSAGES = {
    "pause": "pause a simulation you do not own",
}


def _calc_sim_metrics(sim: Simulation) -> tuple[float, int]:
    duration_seconds = 0.0
    if sim.started_at and sim.ended_at:
        s_at = (
            sim.started_at
            if sim.started_at.tzinfo
            else sim.started_at.replace(tzinfo=timezone.utc)
        )
        e_at = (
            sim.ended_at
            if sim.ended_at.tzinfo
            else sim.ended_at.replace(tzinfo=timezone.utc)
        )
        duration_seconds = round(max(0.0, (e_at - s_at).total_seconds()), 1)
    elif sim.started_at:
        s_at = (
            sim.started_at
            if sim.started_at.tzinfo
            else sim.started_at.replace(tzinfo=timezone.utc)
        )
        duration_seconds = round(
            max(0.0, (datetime.now(timezone.utc) - s_at).total_seconds()), 1
        )

    total_tokens = 0
    for t in sim.turns:
        p = t.payload or {}
        tok = p.get("tokens") or p.get("estimated_tokens")
        if tok:
            total_tokens += int(tok)
        else:
            text_len = len(t.text or "")
            total_tokens += max(10, int(text_len / 3.8))
    curr_turn = int(getattr(sim, "current_turn", 0) or 0)
    if total_tokens == 0 and curr_turn > 0:
        total_tokens = curr_turn * 350
    return duration_seconds, total_tokens


def list_simulations(
    *, organization_id: str, scenario_id: str | None = None, db: Session
) -> list[dict]:
    query = (
        db.query(Simulation)
        .filter(Simulation.organization_id == organization_id)
        .order_by(Simulation.created_at.desc())
    )
    sims = query.limit(200).all()

    # Pre-fetch scenario versions and scenarios
    version_ids = [s.scenario_version_id for s in sims if s.scenario_version_id]
    versions = (
        db.query(ScenarioVersion).filter(ScenarioVersion.id.in_(version_ids)).all()
        if version_ids
        else []
    )
    version_map = {v.id: v for v in versions}

    scen_ids = [v.scenario_id for v in versions if v.scenario_id]
    scenarios = (
        db.query(Scenario).filter(Scenario.id.in_(scen_ids)).all() if scen_ids else []
    )
    scenario_map = {sc.id: sc for sc in scenarios}

    results = []
    for s in sims:
        v = version_map.get(s.scenario_version_id)
        sc = scenario_map.get(v.scenario_id) if v else None
        if scenario_id and (not sc or sc.id != scenario_id):
            continue

        duration_sec, tokens = _calc_sim_metrics(s)
        verdict = (s.state or {}).get("verdict")
        winner = verdict.get("winner") if verdict else None

        v_params = v.parameters or {} if v else {}
        inc_date = v_params.get("incident_date") or None
        proc_date = (
            v_params.get("proceedings_date")
            or (s.started_at.strftime("%Y-%m-%d") if s.started_at else None)
            or (s.created_at.strftime("%Y-%m-%d") if s.created_at else None)
        )
        sim_turns = s.turns or []
        grounded_count = sum(
            1
            for t in sim_turns
            if bool(getattr(t, "citations", None))
            or bool((getattr(t, "payload", None) or {}).get("is_grounded"))
        )
        total_turns = len(sim_turns) if sim_turns else s.current_turn

        results.append(
            {
                "id": s.id,
                "scenario_id": sc.id if sc else None,
                "scenario_title": sc.title if sc else (v.title if v else None),
                "scenario_version": v.version if v else 1,
                "scenario_jurisdiction": sc.jurisdiction if sc else "",
                "scenario_domain": sc.domain if sc else "",
                "incident_date": inc_date,
                "proceedings_date": proc_date,
                "status": s.status,
                "phase": s.phase,
                "current_turn": s.current_turn,
                "turn_limit": s.turn_limit,
                "active_agents": s.active_agents,
                "winner": winner,
                "duration_seconds": duration_sec,
                "total_tokens": tokens,
                "turns_count": total_turns,
                "grounded_turns_count": grounded_count,
                "is_fully_grounded": grounded_count == total_turns and total_turns > 0,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
        )
    return results


def start_simulation(
    *,
    scenario_id: str,
    scenario_version: int = 0,
    organization_id: str,
    user_id: str,
    active_agents: list[str] | None = None,
    turn_limit: int = 8,
    focus_areas: list[str] | None = None,
    platform_roles: list[str] | None = None,
    judge_effort: str = "",
    judge_max_rounds: int = 0,
    run_async: bool = False,
    db: Session | None = None,
) -> dict:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        _, version = _resolve_scenario(
            db, scenario_id, scenario_version, organization_id
        )
        active = [a for a in (active_agents or MIN_CORE_AGENTS) if a in SIM_AGENTS]
        if not all(a in active for a in MIN_CORE_AGENTS):
            raise ValidationError(
                "A simulation requires at least plaintiff, defendant, and judge agents."
            )
        participants = [
            a
            for a in ("plaintiff", "defendant", "judge", "informer", "witness")
            if a in active
        ]

        sim_id = uuid.uuid4().hex
        sim = Simulation(
            id=sim_id,
            organization_id=organization_id,
            scenario_version_id=version.id,
            status="pending",
            phase="opening",
            active_agents=active,
            participants=participants,
            turn_limit=turn_limit,
            focus_areas=focus_areas or [],
            injected_facts=[],
            state={
                "judge_config": {
                    k: v
                    for k, v in {
                        "judge_effort": judge_effort.strip().lower()
                        if judge_effort
                        and judge_effort.strip().lower() in ("low", "medium", "high")
                        else "",
                        "judge_max_rounds": max(1, judge_max_rounds)
                        if judge_max_rounds
                        else 0,
                    }.items()
                    if v
                }
            },
            started_by=user_id,
            started_at=datetime.now(timezone.utc),
        )
        db.add(sim)
        db.commit()
        if run_async:
            sim.status = "running"
            db.commit()
            from app.queue import ThreadPool

            roles_copy = list(platform_roles or [])
            ThreadPool().executor().submit(_drive, sim_id, platform_roles=roles_copy)
            return get_simulation(
                simulation_id=sim_id, organization_id=organization_id, db=db
            )
        result = _drive(sim_id, platform_roles=platform_roles or [], db=db)
        return result
    finally:
        if own_db:
            db.close()


def advance(
    *,
    simulation_id: str,
    user_input: str,
    organization_id: str,
    db: Session | None = None,
) -> dict:
    """Resume a waiting simulation or inject a new user fact into a running one."""
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        sim = _get_owned(db, simulation_id, organization_id)
        if sim.status in ("paused", "human_input", "failed"):
            sim.status = "running"
            db.commit()
            return _drive(simulation_id, db=db)
        if sim.status in ("completed", "cancelled"):
            raise ValidationError("simulation is finished; start a new one to continue")
        existing_facts = list(getattr(sim, "injected_facts", None) or [])
        sim.injected_facts = existing_facts + [user_input]
        sim.status = "running"
        db.add(
            SimulationTurn(
                id=uuid.uuid4().hex,
                simulation_id=simulation_id,
                turn_number=sim.current_turn + 1,
                phase=sim.phase,
                agent_role="human",
                message_type="human.injection",
                text=user_input,
                citations=[],
            )
        )
        sim.current_turn += 1
        db.commit()
        emit(
            db,
            "simulation.fact_injected",
            organization_id=sim.organization_id,
            user_id=sim.started_by or None,
            module="sim",
            simulation_id=simulation_id,
            payload={"fact": user_input[:200]},
        )
        return _drive(simulation_id, db=db)
    finally:
        if own_db:
            db.close()


def resume_simulation(
    *,
    simulation_id: str,
    organization_id: str,
    platform_roles: list[str] | None = None,
    run_async: bool = True,
    db: Session | None = None,
) -> dict:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        sim = _get_owned(db, simulation_id, organization_id)
        # Orphaned "running" sims (e.g. after uvicorn --reload) are also resumable.
        if sim.status not in ("paused", "human_input", "failed", "running"):
            raise ValidationError(f"simulation is not resumable (status={sim.status})")
        sim.status = "running"
        db.commit()
        if run_async:
            from app.queue import ThreadPool

            roles_copy = list(platform_roles or [])
            ThreadPool().executor().submit(
                _drive, simulation_id, platform_roles=roles_copy
            )
            return get_simulation(
                simulation_id=simulation_id, organization_id=organization_id, db=db
            )
        return _drive(simulation_id, platform_roles=platform_roles or [], db=db)
    finally:
        if own_db:
            db.close()


def pause_simulation(
    *, simulation_id: str, organization_id: str, db: Session | None = None
) -> dict:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        sim = _get_owned(db, simulation_id, organization_id)
        if sim.status in ("completed", "cancelled"):
            raise ValidationError("cannot pause a finished simulation")
        sim.status = "paused"
        db.commit()
        emit(
            db,
            "simulation.paused",
            organization_id=sim.organization_id,
            user_id=sim.started_by or None,
            module="sim",
            simulation_id=simulation_id,
        )
        return {"id": sim.id, "status": sim.status}
    finally:
        if own_db:
            db.close()


def cancel_simulation(
    *, simulation_id: str, organization_id: str, db: Session | None = None
) -> dict:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        sim = _get_owned(db, simulation_id, organization_id)
        sim.status = "cancelled"
        db.commit()
        return {"id": sim.id, "status": sim.status}
    finally:
        if own_db:
            db.close()


def inject_fact(
    *, simulation_id: str, fact: str, organization_id: str, db: Session | None = None
) -> dict:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        sim = _get_owned(db, simulation_id, organization_id)
        if sim.status in ("completed", "cancelled"):
            raise ValidationError("cannot inject into a finished simulation")
        existing_facts = list(getattr(sim, "injected_facts", None) or [])
        sim.injected_facts = existing_facts + [fact]
        if sim.status not in ("running", "pending"):
            sim.status = "running"
        db.add(
            SimulationTurn(
                id=uuid.uuid4().hex,
                simulation_id=simulation_id,
                turn_number=sim.current_turn + 1,
                phase=sim.phase,
                agent_role="human",
                message_type="human.injection",
                text=fact,
                citations=[],
            )
        )
        sim.current_turn += 1
        db.commit()
        emit(
            db,
            "simulation.fact_injected",
            organization_id=sim.organization_id,
            user_id=sim.started_by or None,
            module="sim",
            simulation_id=simulation_id,
            payload={"fact": fact[:200]},
        )
        return _drive(simulation_id, db=db)
    finally:
        if own_db:
            db.close()


def request_clarification(
    *,
    simulation_id: str,
    question: str,
    organization_id: str,
    db: Session | None = None,
) -> dict:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        sim = _get_owned(db, simulation_id, organization_id)
        db.add(
            SimulationTurn(
                id=uuid.uuid4().hex,
                simulation_id=simulation_id,
                turn_number=sim.current_turn + 1,
                phase=sim.phase,
                agent_role="human",
                message_type="human.clarification",
                text=f"Please clarify: {question}",
                citations=[],
            )
        )
        sim.current_turn += 1
        sim.status = "human_input"
        db.commit()
        return {"id": sim.id, "status": sim.status}
    finally:
        if own_db:
            db.close()


def steer_focus(
    *, simulation_id: str, focus: str, organization_id: str, db: Session | None = None
) -> dict:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        sim = _get_owned(db, simulation_id, organization_id)
        existing_focus = list(getattr(sim, "focus_areas", None) or [])
        sim.focus_areas = existing_focus + [focus]
        db.commit()
        return {"id": sim.id, "focus_areas": sim.focus_areas}
    finally:
        if own_db:
            db.close()


def get_simulation(
    *, simulation_id: str, organization_id: str, db: Session | None = None
) -> dict:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        sim = _get_owned(db, simulation_id, organization_id)
        turns = [
            {
                "id": t.id,
                "turn_number": t.turn_number,
                "phase": t.phase,
                "agent_role": t.agent_role,
                "message_type": t.message_type,
                "text": t.text,
                "citations": t.citations or [],
                "payload": t.payload or {},
                "thinking": (t.payload or {}).get("thinking", ""),
                "action": (t.payload or {}).get("action", ""),
                "is_grounded": bool(
                    (t.citations and len(t.citations) > 0)
                    or (t.payload or {}).get("is_grounded")
                ),
                "grounding_status": (t.payload or {}).get("grounding_status")
                or (
                    "grounded"
                    if (t.citations and len(t.citations) > 0)
                    else "not_grounded"
                ),
                "grounding_note": (t.payload or {}).get("grounding_note")
                or (
                    f"Grounded with {len(t.citations or [])} local knowledge source(s)"
                    if (t.citations and len(t.citations) > 0)
                    else "Not grounded with local knowledge"
                ),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in sim.turns
        ]
        case_study = None
        if sim.case_study:
            case_study = {
                "id": sim.case_study.id,
                "markdown": sim.case_study.markdown_content,
                "status": sim.case_study.status,
            }
        sc, v = None, None
        try:
            sc, v = _scenario_context(db, sim.scenario_version_id)
        except Exception:
            logger.debug(
                "scenario context unavailable for sim %s", sim.id, exc_info=True
            )
        duration_sec, tokens = _calc_sim_metrics(sim)

        v_params = v.parameters or {} if v else {}
        inc_date = v_params.get("incident_date") or None
        proc_date = (
            v_params.get("proceedings_date")
            or (sim.started_at.strftime("%Y-%m-%d") if sim.started_at else None)
            or (sim.created_at.strftime("%Y-%m-%d") if sim.created_at else None)
        )

        return {
            "id": sim.id,
            "scenario_id": sc.id if sc else None,
            "scenario_title": sc.title if sc else (v.title if v else None),
            "scenario_version": v.version if v else 1,
            "scenario_jurisdiction": sc.jurisdiction if sc else "",
            "scenario_domain": sc.domain if sc else "",
            "scenario_parameters": v_params,
            "incident_date": inc_date,
            "proceedings_date": proc_date,
            "status": sim.status,
            "phase": sim.phase,
            "current_turn": sim.current_turn,
            "turn_limit": sim.turn_limit,
            "active_agents": sim.active_agents,
            "injected_facts": sim.injected_facts,
            "focus_areas": sim.focus_areas,
            "turns": turns,
            "verdict": (sim.state or {}).get("verdict"),
            "winner": (sim.state or {}).get("verdict", {}).get("winner")
            if (sim.state or {}).get("verdict")
            else None,
            "judge_config": (sim.state or {}).get("judge_config") or {},
            "case_study": case_study,
            "duration_seconds": duration_sec,
            "total_tokens": tokens,
            "disk_path": str(
                (Path(get_settings().data_dir) / "simulations" / sim.id).resolve()
            ),
            "started_by": sim.started_by,
            "started_at": sim.started_at.isoformat() if sim.started_at else None,
            "ended_at": sim.ended_at.isoformat() if sim.ended_at else None,
            "created_at": sim.created_at.isoformat() if sim.created_at else None,
        }
    finally:
        if own_db:
            db.close()


def get_case_study(*, simulation_id: str, organization_id: str, db: Session) -> dict:
    sim = _get_owned(db, simulation_id, organization_id)
    cs = db.query(CaseStudy).filter(CaseStudy.simulation_id == simulation_id).first()
    if cs is None and sim.status == "completed":
        try:
            cs = _generate_case_study(sim, db)
        except Exception as exc:
            logger.warning(
                "on-demand case study generation failed for %s: %s",
                simulation_id,
                exc,
            )
    if cs is None:
        raise NotFoundError("case study not generated yet")
    return {
        "id": cs.id,
        "markdown": cs.markdown_content,
        "status": cs.status,
    }


def simulation_report(*, simulation_id: str, organization_id: str, db: Session) -> str:
    """Generate a full Markdown report for a completed simulation.

    Includes every turn with agent role, phase, text, citations, and the final
    verdict.  If the simulation stored per‑turn timings (via the enhanced
    ``agent_step``) those are surfaced too.
    """
    sim = _get_owned(db, simulation_id, organization_id)
    turns = sim.turns

    _, v = None, None
    try:
        _, v = _scenario_context(db, sim.scenario_version_id)
    except Exception:
        logger.debug(
            "scenario context unavailable for report of sim %s", sim.id, exc_info=True
        )
    v_params = v.parameters or {} if v else {}
    inc_date = v_params.get("incident_date") or "—"
    proc_date = (
        v_params.get("proceedings_date")
        or (sim.started_at.strftime("%Y-%m-%d") if sim.started_at else None)
        or (sim.created_at.strftime("%Y-%m-%d") if sim.created_at else "—")
    )

    lines: list[str] = []
    lines.append(f"# Simulation Report — {sim.id}")
    lines.append("")
    lines.append(f"**Status:** {sim.status}")
    lines.append(f"**Phase:** {sim.phase}")
    lines.append(f"**Date of Incident:** {inc_date}")
    lines.append(f"**Date of Proceedings:** {proc_date}")
    verdict = (sim.state or {}).get("verdict") if isinstance(sim.state, dict) else None
    verdict_winner = verdict.get("winner", "—") if isinstance(verdict, dict) else "—"
    lines.append(f"**Current Turn:** {sim.current_turn}/{sim.turn_limit}")
    lines.append(f"**Judge Verdict:** {verdict_winner}")
    lines.append("")

    # --- Per‑turn ledger ---
    lines.append("## Turn Ledger")
    lines.append("")
    for t in turns:
        agent = t.agent_role or "—"
        phase = t.phase or "—"
        text = (t.text or "").strip()[:200]
        citations = t.citations or []
        payload = t.payload or {}
        duration = payload.get("duration_ms")
        llm_ms = payload.get("llm_ms")
        retrieval_ms = payload.get("retrieval_ms")
        lines.append(f"**Turn {t.turn_number}** — {agent} — Phase: {phase}")
        if text:
            lines.append(f"> {text}")
        if citations:
            lines.append(
                f"*Grounded with Local Knowledge: {len(citations)} cited passage(s)*"
            )
        else:
            lines.append(
                "*⚠️ Note: Response NOT grounded with local knowledge (unreferenced LLM inference)*"
            )
        if duration is not None:
            lines.append(f"*Duration: {round(duration, 1)} ms*")
        if llm_ms is not None:
            lines.append(f"*LLM call: {round(llm_ms, 1)} ms*")
        if retrieval_ms is not None:
            lines.append(f"*Retrieval: {round(retrieval_ms, 1)} ms*")
        lines.append("")

    # --- Final verdict ---
    lines.append("## Final Verdict")
    lines.append("")
    if verdict and isinstance(verdict, dict):
        winner = verdict.get("winner", "—")
        rationale = verdict.get("rationale", "")
        lines.append(f"**Winner:** {winner}")
        if rationale:
            lines.append(f"**Rationale:** {rationale}")
    else:
        lines.append("_No verdict recorded._")
    lines.append("")

    # --- Case study link ---
    cs = db.query(CaseStudy).filter(CaseStudy.simulation_id == simulation_id).first()
    if cs:
        lines.append(f"- Case study: [{cs.id}]({cs.id}) — status: {cs.status}")
    else:
        lines.append("- Case study: not yet generated.")

    md = "\n".join(lines)
    # Ensure the markdown ends with a newline for consistent file output
    return md


def export_case_study(
    *, simulation_id: str, organization_id: str, user, db: Session
) -> dict:
    sim = _get_owned(db, simulation_id, organization_id)
    cs = db.query(CaseStudy).filter(CaseStudy.simulation_id == simulation_id).first()
    if cs is None:
        raise NotFoundError("case study not generated yet")
    from app.core.deps import enforce_export

    enforce_export(
        user, "case_study", {"contains_grounded_citations": bool(cs.citations or [])}
    )
    emit(
        db,
        "case_study.exported",
        organization_id=sim.organization_id,
        user_id=user.id,
        module="sim",
        simulation_id=simulation_id,
        payload={"case_study_id": cs.id},
    )
    return {
        "kind": "case_study",
        "id": cs.id,
        "markdown": cs.markdown_content,
        "citations": cs.citations or [],
        "disclaimer": "Generated by JurisFlow for educational use only; not legal advice.",
    }


# --- Downloadable artifacts (case study + role-play), cached on disk ---------
#
# Every completed simulation ships two markdown artifacts. Both are generated at
# most once per simulation and then served from cache:
#   * case_study.md — LLM-written study, also persisted on the CaseStudy row
#   * role_play.md  — deterministic transcript of the turns, rebuilt only while
#                     the simulation is still running.

ARTIFACT_KEYS = ("case_study", "role_play")

ARTIFACT_TITLES = {
    "case_study": "Case Study",
    "role_play": "Role-Play Transcript",
}

ARTIFACT_DISCLAIMER = (
    "Generated by JurisFlow for educational use only; not legal advice."
)


def _artifact_dir(sim_id: str) -> Path:
    return Path(get_settings().data_dir) / "simulations" / sim_id


def _artifact_filename(sim: Simulation, key: str) -> str:
    return f"{sim.id[:8]}-{key.replace('_', '-')}.md"


def _scenario_title_of(db: Session, sim: Simulation) -> str:
    try:
        scenario, version = _scenario_context(db, sim.scenario_version_id)
        return str(version.title or scenario.title or sim.id)
    except Exception:
        logger.debug("scenario title unavailable for sim %s", sim.id, exc_info=True)
        return str(sim.id)


def _role_play_markdown(sim: Simulation, db: Session) -> str:
    """Transcript of every turn as a script. Deterministic — no LLM call."""
    title = _scenario_title_of(db, sim)
    participants = sim.participants or []
    names = [
        (p.get("name") or p.get("role") or str(p)) if isinstance(p, dict) else str(p)
        for p in participants
    ]
    state = sim.state if isinstance(sim.state, dict) else {}
    verdict = state.get("verdict") if isinstance(state.get("verdict"), dict) else None

    lines: list[str] = [f"# Role-Play Transcript — {title}", ""]
    lines.append(f"**Simulation:** `{sim.id}`")
    lines.append(f"**Status:** {sim.status}")
    lines.append(f"**Phase:** {sim.phase or '—'}")
    lines.append(f"**Turns played:** {sim.current_turn}/{sim.turn_limit}")
    if names:
        lines.append(f"**Cast:** {', '.join(str(n) for n in names)}")
    if verdict:
        lines.append(f"**Verdict:** {verdict.get('winner', '—')}")
        if verdict.get("rationale"):
            lines.append(f"**Rationale:** {verdict['rationale']}")
    lines.append("")
    lines.append("## Scenes")
    lines.append("")

    turns = sim.turns or []
    if not turns:
        lines.append("_No turns have been played yet._")
    last_phase = ""
    for t in turns:
        phase = t.phase or ""
        if phase and phase != last_phase:
            lines.append(f"### {phase.replace('_', ' ').title()}")
            lines.append("")
            last_phase = phase
        speaker = (t.agent_role or "orchestrator").replace("_", " ").title()
        text = (t.text or "").strip()
        lines.append(f"**{speaker}:**")
        lines.append("")
        if text:
            lines.append("> " + text.replace("\n", "\n> "))
            lines.append("")
        citations = t.citations or []
        if citations:
            lines.append(
                f"*Grounded with {len(citations)} local knowledge citation(s).*"
            )
        else:
            lines.append(
                "*Not grounded with local knowledge (general model reasoning).*"
            )
        lines.append("")

    if verdict:
        lines.append("## Ruling")
        lines.append("")
        lines.append(f"**Winner:** {verdict.get('winner', '—')}")
        if verdict.get("rationale"):
            lines.append("")
            lines.append(str(verdict["rationale"]))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*{ARTIFACT_DISCLAIMER}*")
    return "\n".join(lines)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def simulation_artifacts(
    *, simulation_id: str, organization_id: str, db: Session
) -> dict:
    """List both downloadable artifacts and whether each one is already cached."""
    sim = _get_owned(db, simulation_id, organization_id)
    turn_count = len(sim.turns or [])

    cs = db.query(CaseStudy).filter(CaseStudy.simulation_id == simulation_id).first()
    role_play_path = _artifact_dir(sim.id) / "role_play.md"
    role_play_stat = role_play_path.stat() if role_play_path.exists() else None

    entries = [
        {
            "key": "case_study",
            "title": ARTIFACT_TITLES["case_study"],
            "filename": _artifact_filename(sim, "case_study"),
            "available": bool(cs) or sim.status == "completed",
            "cached": bool(cs),
            "generated_at": _iso(cs.generated_at) if cs else None,
            "size_bytes": len((cs.markdown_content or "").encode("utf-8")) if cs else 0,
            "turns": turn_count,
        },
        {
            "key": "role_play",
            "title": ARTIFACT_TITLES["role_play"],
            "filename": _artifact_filename(sim, "role_play"),
            "available": turn_count > 0,
            "cached": bool(role_play_stat) and sim.status == "completed",
            "generated_at": _iso(
                datetime.fromtimestamp(role_play_stat.st_mtime, tz=timezone.utc)
            )
            if role_play_stat
            else None,
            "size_bytes": role_play_stat.st_size if role_play_stat else 0,
            "turns": turn_count,
        },
    ]
    return {
        "simulation_id": sim.id,
        "status": sim.status,
        "artifacts": entries,
        "disclaimer": ARTIFACT_DISCLAIMER,
    }


def get_simulation_artifact(
    *, key: str, simulation_id: str, organization_id: str, db: Session
) -> dict:
    """Return one artifact's markdown, generating it on first request and caching it."""
    if key not in ARTIFACT_KEYS:
        raise NotFoundError(f"unknown artifact '{key}'")
    sim = _get_owned(db, simulation_id, organization_id)
    sim_dir = _artifact_dir(sim.id)
    filename = _artifact_filename(sim, key)

    if key == "case_study":
        cs = (
            db.query(CaseStudy).filter(CaseStudy.simulation_id == simulation_id).first()
        )
        cached = cs is not None
        if cs is None:
            # generates the study when the simulation is completed
            markdown = (
                get_case_study(
                    simulation_id=simulation_id,
                    organization_id=organization_id,
                    db=db,
                )["markdown"]
                or ""
            )
        else:
            markdown = cs.markdown_content or ""
        generated_at = _iso(cs.generated_at) if cs else None
    else:
        path = sim_dir / "role_play.md"
        cached = path.exists() and sim.status == "completed"
        if cached:
            markdown = path.read_text(encoding="utf-8")
            generated_at = _iso(
                datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            )
        else:
            markdown = _role_play_markdown(sim, db)
            generated_at = _iso(datetime.now(timezone.utc))

    # keep a copy next to transcript.json so the disk archive holds both files
    try:
        sim_dir.mkdir(parents=True, exist_ok=True)
        target = sim_dir / f"{key}.md"
        if not target.exists() or target.read_text(encoding="utf-8") != markdown:
            target.write_text(markdown, encoding="utf-8")
    except OSError:
        logger.warning(
            "could not cache artifact %s for sim %s", key, sim.id, exc_info=True
        )

    return {
        "key": key,
        "title": ARTIFACT_TITLES[key],
        "filename": filename,
        "simulation_id": sim.id,
        "markdown": markdown,
        "cached": cached,
        "generated_at": generated_at,
        "disclaimer": ARTIFACT_DISCLAIMER,
    }


def _resolve_scenario(
    db: Session, scenario_id: str, scenario_version: int, organization_id: str
) -> tuple[Scenario, ScenarioVersion]:
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if scenario is None or scenario.organization_id != organization_id:
        raise NotFoundError("scenario not found in this organization")
    if scenario_version <= 0:
        version = (
            db.query(ScenarioVersion)
            .filter(ScenarioVersion.scenario_id == scenario_id)
            .order_by(ScenarioVersion.version.desc())
            .first()
        )
    else:
        version = (
            db.query(ScenarioVersion)
            .filter(
                ScenarioVersion.scenario_id == scenario_id,
                ScenarioVersion.version == scenario_version,
            )
            .one_or_none()
        )
    if version is None:
        raise NotFoundError(
            f"scenario version {scenario_version or 'latest'} not found"
        )
    assert scenario is not None
    return scenario, version


def _get_owned(db: Session, simulation_id: str, organization_id: str) -> Simulation:
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).one_or_none()
    if sim is None:
        raise NotFoundError(f"simulation {simulation_id} not found")
    if sim.organization_id != organization_id:
        raise NotFoundError("simulation not found in this organization")
    return sim


def _save_simulation_to_disk(sim_id: str, organization_id: str, db: Session) -> None:
    try:
        import json
        from pathlib import Path

        data = get_simulation(
            simulation_id=sim_id, organization_id=organization_id, db=db
        )
        sim_dir = Path(get_settings().data_dir) / "simulations" / sim_id
        sim_dir.mkdir(parents=True, exist_ok=True)
        (sim_dir / "transcript.json").write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )
        if data.get("case_study") and data["case_study"].get("markdown"):
            (sim_dir / "case_study.md").write_text(
                data["case_study"]["markdown"], encoding="utf-8"
            )
        logger.info("Saved simulation %s to disk at %s", sim_id, sim_dir)
    except Exception:
        logger.warning("Failed to persist simulation %s to disk", sim_id, exc_info=True)


def _enqueue_audio(sim: Simulation) -> None:
    """Background-synthesize the learning narration + role-play clips for a
    completed simulation (PRD §9 "giving a voice to the case").

    The work is deferred to the in-process job queue so the completion call
    never pays for synthesis latency.  If TTS is disabled the queue is left
    empty and no ``SimulationAudio`` rows are written.
    """
    from app.queue import enqueue
    from app.services.tts import is_enabled as _tts_enabled

    if not _tts_enabled():
        return
    try:
        from app.services import audio as audio_service

        enqueue(audio_service.generate_assets_job, sim.id, sim.organization_id)
    except Exception:
        logger.exception("failed to schedule audio assets for simulation %s", sim.id)


def _drive(
    simulation_id: str,
    *,
    platform_roles: list[str] | None = None,
    db: Session | None = None,
) -> dict:
    own_db = db is None
    db = db or SessionLocal()  # type: ignore[assignment]
    try:
        sim = _get(db, simulation_id)
        scenario, version = _scenario_context(db, sim.scenario_version_id)
        last_agent = (sim.state or {}).get("last_agent")
        if not last_agent and sim.turns:
            last_agent = sim.turns[-1].agent_role
        state = initial_state(
            {
                "id": sim.id,
                "organization_id": sim.organization_id,
                "scenario_id": scenario.id,
                "scenario_parameters": version.parameters or {},
                "scenario_title": version.title or scenario.title,
                "fact_pattern": version.fact_pattern,
                "jurisdiction": scenario.jurisdiction,
                "domain": scenario.domain,
                "phase": sim.phase,
                "turn": sim.current_turn,
                "turn_limit": sim.turn_limit,
                "active_agents": sim.active_agents,
                "participants": sim.participants,
                "focus_areas": sim.focus_areas,
                "injected_facts": sim.injected_facts,
                "prior_messages": [
                    {"agent_role": t.agent_role, "text": t.text, "phase": t.phase}
                    for t in sim.turns
                ],
                "status": sim.status,
                "last_agent": last_agent,
                "rounds": (sim.state or {}).get("rounds", 0),
                "judge_config": (sim.state or {}).get("judge_config") or {},
                "verdict": (sim.state or {}).get("verdict"),
            }
        )
        if (sim.state or {}).get("verdict"):
            state["verdict"] = (sim.state or {}).get("verdict")
        llm = get_sim_llm()
        try:
            result = run_once(state, llm, platform_roles or [], db=db)
        except Exception:
            logger.exception("simulation engine failed")
            sim.status = "failed"
            db.commit()
            raise

        sim.phase = result.get("phase", sim.phase)
        sim.status = result.get("status", "completed")
        # Merge graph result into persisted sim.state (do not look for a nested "state" key).
        merged = dict(sim.state or {})
        for key in (
            "prior_messages",
            "last_agent",
            "phase",
            "rounds",
            "verdict",
            "judge_config",
            "turn_limit",
        ):
            if key in result and result[key] is not None:
                merged[key] = result[key]
        sim.state = merged
        if sim.status in ("paused", "human_input"):
            incr("simulation.paused_outcome")
            db.commit()
            return get_simulation(
                simulation_id=simulation_id, organization_id=sim.organization_id, db=db
            )

        if sim.status == "completed":
            try:
                case_study = _generate_case_study(sim, db)
                emit(
                    db,
                    "simulation.completed",
                    organization_id=sim.organization_id,
                    user_id=sim.started_by or None,
                    module="sim",
                    payload={"case_study_id": case_study.id},
                )
            except Exception:
                logger.exception(
                    "Failed to generate case study for simulation %s", sim.id
                )
            sim.ended_at = datetime.now(timezone.utc)  # type: ignore[assignment]
            db.commit()
            _save_simulation_to_disk(sim.id, sim.organization_id, db)
            _enqueue_audio(sim)
        db.commit()
        return get_simulation(
            simulation_id=simulation_id, organization_id=sim.organization_id, db=db
        )
    finally:
        if own_db:
            db.close()


def _scenario_context(
    db: Session, scenario_version_id: str
) -> tuple[Scenario, ScenarioVersion]:
    version = (
        db.query(ScenarioVersion)
        .filter(ScenarioVersion.id == scenario_version_id)
        .one_or_none()
    )
    if version is None:
        raise NotFoundError(f"scenario version {scenario_version_id} not found")
    scenario = (
        db.query(Scenario).filter(Scenario.id == version.scenario_id).one_or_none()
    )
    if scenario is None:
        raise NotFoundError("scenario not found")
    return scenario, version


def _get(db: Session, simulation_id: str) -> Simulation:
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).one_or_none()
    if sim is None:
        raise NotFoundError(f"simulation {simulation_id} not found")
    return sim


def _generate_case_study(sim: Simulation, db: Session) -> CaseStudy:
    scenario, version = _scenario_context(db, sim.scenario_version_id)
    messages = [
        {
            "agent_role": t.agent_role,
            "text": t.text,
            "phase": t.phase,
            "citations": t.citations or [],
        }
        for t in sim.turns
    ]
    from app.llm.factory import get_llm

    v_params = version.parameters or {} if version else {}
    inc_date = v_params.get("incident_date") or None
    proc_date = (
        v_params.get("proceedings_date")
        or (sim.started_at.strftime("%Y-%m-%d") if sim.started_at else None)
        or (sim.created_at.strftime("%Y-%m-%d") if sim.created_at else None)
    )

    llm = get_llm()
    md = build_case_study(
        scenario_title=version.title or scenario.title or "",
        scenario_facts=version.fact_pattern or "",
        messages=messages,
        jurisdiction=scenario.jurisdiction or "",
        domain=scenario.domain or "",
        incident_date=inc_date,
        proceedings_date=proc_date,
        llm=llm,
    )
    citations = [c for m in messages for c in m.get("citations", [])][:20]
    cs = CaseStudy(
        id=uuid.uuid4().hex,
        simulation_id=sim.id,
        organization_id=sim.organization_id,
        markdown_content=md,
        citations=citations,
        status="draft",
        generated_by=sim.started_by,
    )
    db.add(cs)
    db.commit()
    db.refresh(cs)
    return cs
