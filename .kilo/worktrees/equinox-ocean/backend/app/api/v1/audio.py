"""Simulation audio (TTS) endpoints: list + regenerate (PRD §9 "a voice for the case")."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.deps import CurrentUser, require_module
from app.db.session import get_db
from app.queue import enqueue
from app.services import audio as audio_service
from app.services.simulation import get_simulation

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/simulations/{simulation_id}/audio", tags=["audio"])


@router.get("")
def list_simulation_audio(
    simulation_id: str,
    user: CurrentUser = Depends(require_module("sim", "simulation.observe")),
    db: Session = Depends(get_db),
):
    """List synthesized narration + role-play clips for a simulation."""
    get_simulation(
        simulation_id=simulation_id, organization_id=user.organization_id, db=db
    )
    return [
        audio_service.asset_dict(a)
        for a in audio_service.list_assets(
            simulation_id=simulation_id, organization_id=user.organization_id, db=db
        )
    ]


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def regenerate_simulation_audio(
    simulation_id: str,
    user: CurrentUser = Depends(require_module("sim", "simulation.run")),
    db: Session = Depends(get_db),
):
    """Kick off narration + clip synthesis in the background job queue."""
    get_simulation(
        simulation_id=simulation_id, organization_id=user.organization_id, db=db
    )
    enqueue(audio_service.generate_assets_job, simulation_id, user.organization_id)
    audit(
        db,
        action="simulation.audio.generate",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="simulation",
        resource_id=simulation_id,
    )
    return {"status": "queued", "simulation_id": simulation_id}
