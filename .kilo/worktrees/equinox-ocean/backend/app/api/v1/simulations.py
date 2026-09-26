"""Simulation lifecycle endpoints (PRD §4.2, §6.4, §8.1)."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.deps import CurrentUser, require_module
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.services import simulation as sim_service

router = APIRouter(prefix="/simulations", tags=["simulations"])


class SimulationCreate(BaseModel):
    scenario_id: str
    scenario_version: int = 0  # 0 = latest
    active_agents: list[str] | None = None
    debug: bool = False
    judge_effort: str = ""  # "low" | "medium" | "high" — per-run LLM-as-judge rigor
    judge_max_rounds: int = (
        0  # 0 = use config default; else max exchanges before ruling
    )
    async_run: bool = False


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)


class FactCreate(BaseModel):
    fact: str = Field(min_length=1)


class SteerCreate(BaseModel):
    focus: str = Field(min_length=1)


@router.post("", status_code=201)
def start_simulation(
    body: SimulationCreate,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.start")),
) -> dict:
    try:
        sim = sim_service.start_simulation(
            scenario_id=body.scenario_id,
            scenario_version=body.scenario_version,
            organization_id=user.organization_id,
            user_id=user.id,
            db=db,
            active_agents=body.active_agents,
            judge_effort=body.judge_effort,
            judge_max_rounds=body.judge_max_rounds,
            run_async=body.async_run,
            platform_roles=user.platform_roles or ["platform.member"],
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit(
        db,
        action="simulation_started",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="simulation",
        resource_id=sim["id"],
    )
    return sim


@router.get("")
def list_simulations(
    scenario_id: str | None = None,
    user: CurrentUser = Depends(require_module("sim", "simulation.observe")),
    db: Session = Depends(get_db),
) -> dict:
    return {
        "simulations": sim_service.list_simulations(
            organization_id=user.organization_id, scenario_id=scenario_id, db=db
        )
    }


@router.get("/{simulation_id}")
def get_simulation(
    simulation_id: str,
    user: CurrentUser = Depends(require_module("sim", "simulation.observe")),
    db: Session = Depends(get_db),
) -> dict:
    return sim_service.get_simulation(
        simulation_id=simulation_id, organization_id=user.organization_id, db=db
    )


@router.post("/{simulation_id}/advance")
def advance(
    simulation_id: str,
    body: MessageCreate | None = None,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.hitl")),
) -> dict:
    try:
        return sim_service.advance(
            simulation_id=simulation_id,
            user_input=body.content if body else "",
            organization_id=user.organization_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{simulation_id}/advance/stream")
def advance_stream(
    simulation_id: str,
    body: MessageCreate | None = None,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.hitl")),
):
    """SSE -- drive the tribunal one turn at a time, emitting each turn as it
    is produced so the UI can narrate/step through the case live (PRD §9).

    Event shape (per turn):
        event: turn\ndata: {<full simulation dict incl. latest turn>}\n\n
    Terminal event (after the last turn):
        event: done\ndata: {<final simulation dict>}\n\n
    """
    import json

    from fastapi.responses import StreamingResponse

    def _generate() -> Iterator[str]:
        cur = sim_service.get_simulation(
            simulation_id=simulation_id,
            organization_id=user.organization_id,
            db=db,
        )
        guard = 0
        while cur["status"] in (
            "running",
            "opening",
            "arguments",
            "judge_questions",
            "outcome",
            "pending",
        ):
            guard += 1
            if guard > 64:
                break
            try:
                cur = sim_service.advance(
                    simulation_id=simulation_id,
                    user_input=body.content if body else "",
                    organization_id=user.organization_id,
                    db=db,
                )
            except Exception as exc:
                yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"
                break
            yield f"event: turn\ndata: {json.dumps(cur)}\n\n"
        yield f"event: done\ndata: {json.dumps(cur)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{simulation_id}/pause")
def pause(
    simulation_id: str,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.hitl")),
) -> dict:
    try:
        sim_service.pause_simulation(
            simulation_id=simulation_id, organization_id=user.organization_id, db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit(
        db,
        action="simulation_paused",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="simulation",
        resource_id=simulation_id,
    )
    return {"ok": True}


@router.post("/{simulation_id}/resume")
def resume(
    simulation_id: str,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.hitl")),
) -> dict:
    try:
        sim_service.resume_simulation(
            simulation_id=simulation_id,
            organization_id=user.organization_id,
            db=db,
            platform_roles=user.platform_roles or ["platform.member"],
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit(
        db,
        action="simulation_resumed",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="simulation",
        resource_id=simulation_id,
    )
    return {"ok": True}


@router.post("/{simulation_id}/cancel")
def cancel(
    simulation_id: str,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.hitl")),
) -> dict:
    sim_service.cancel_simulation(
        simulation_id=simulation_id, organization_id=user.organization_id, db=db
    )
    audit(
        db,
        action="simulation_cancelled",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="simulation",
        resource_id=simulation_id,
    )
    return {"ok": True}


@router.post("/{simulation_id}/inject_fact")
def inject_fact(
    simulation_id: str,
    body: FactCreate,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.hitl")),
) -> dict:
    try:
        result = sim_service.inject_fact(
            simulation_id=simulation_id,
            fact=body.fact,
            organization_id=user.organization_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit(
        db,
        action="fact_injected",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="simulation",
        resource_id=simulation_id,
    )
    return result


@router.post("/{simulation_id}/clarify")
def clarify(
    simulation_id: str,
    body: MessageCreate,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.hitl")),
) -> dict:
    try:
        result = sim_service.request_clarification(
            simulation_id=simulation_id,
            question=body.content,
            organization_id=user.organization_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.post("/{simulation_id}/steer")
def steer(
    simulation_id: str,
    body: SteerCreate,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.hitl")),
) -> dict:
    try:
        result = sim_service.steer_focus(
            simulation_id=simulation_id,
            focus=body.focus,
            organization_id=user.organization_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


@router.get("/{simulation_id}/case_study")
def case_study(
    simulation_id: str,
    user: CurrentUser = Depends(require_module("sim", "simulation.observe")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        study = sim_service.get_case_study(
            simulation_id=simulation_id,
            organization_id=user.organization_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return study


@router.get("/{simulation_id}/report")
def simulation_report(
    simulation_id: str,
    user: CurrentUser = Depends(require_module("sim", "simulation.observe")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        report = sim_service.simulation_report(
            simulation_id=simulation_id,
            organization_id=user.organization_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "report_md": report,
        "download_name": f"simulation-{simulation_id}-report.md",
    }


@router.post("/{simulation_id}/export")
def export_case_study(
    simulation_id: str,
    user: CurrentUser = Depends(require_module("sim", "simulation.observe")),
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit("simulations.hitl")),
) -> dict:
    try:
        exported = sim_service.export_case_study(
            simulation_id=simulation_id,
            organization_id=user.organization_id,
            user=user,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit(
        db,
        action="case_study_exported",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="simulation",
        resource_id=simulation_id,
    )
    return exported
