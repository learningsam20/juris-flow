"""Scenario management and versioning endpoints (PRD §5.1, §6.3)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.deps import CurrentUser, require_module, require_tenant
from app.db.session import get_db
from app.services import scenario as scenario_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scenarios", tags=["scenarios"])


class ScenarioCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    jurisdiction: str = ""
    domain: str = ""
    tags: list[str] = []
    fact_pattern: str = ""
    parameters: dict = {}
    document_ids: list[str] = []
    incident_date: str | None = None
    proceedings_date: str | None = None


class ScenarioUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    jurisdiction: str | None = None
    domain: str | None = None
    tags: list[str] | None = None
    status: str | None = None
    fact_pattern: str | None = None
    parameters: dict | None = None
    document_ids: list[str] | None = None
    incident_date: str | None = None
    proceedings_date: str | None = None


@router.get("")
def list_scenarios(
    user: CurrentUser = Depends(require_module("sim", "scenario.view")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return {
            "scenarios": scenario_service.list_scenarios(
                organization_id=user.organization_id, db=db
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to list scenarios: {exc}")


@router.post("", status_code=201)
def create_scenario(
    body: ScenarioCreate,
    user: CurrentUser = Depends(require_module("sim", "scenario.create")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        params = dict(body.parameters or {})
        if body.incident_date:
            params["incident_date"] = body.incident_date
        if body.proceedings_date:
            params["proceedings_date"] = body.proceedings_date

        scenario = scenario_service.create_scenario(
            organization_id=user.organization_id,
            user_id=user.id,
            title=body.title,
            description=body.description,
            jurisdiction=body.jurisdiction,
            domain=body.domain,
            tags=body.tags,
            fact_pattern=body.fact_pattern,
            parameters=params,
            document_ids=body.document_ids,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit(
        db,
        action="scenario_created",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="scenario",
        resource_id=scenario["id"],
    )
    return scenario


@router.post("/upload", status_code=201)
async def create_scenario_with_file(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    jurisdiction: str = Form(""),
    domain: str = Form(""),
    tags: str = Form(""),
    fact_pattern: str = Form(""),
    incident_date: str | None = Form(None),
    proceedings_date: str | None = Form(None),
    document_ids: str = Form(""),
    parameters: str = Form("{}"),
    user: CurrentUser = Depends(require_module("sim", "scenario.create")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        tag_list: list[str] = []
        if tags:
            try:
                parsed_tags = json.loads(tags)
                tag_list = (
                    parsed_tags
                    if isinstance(parsed_tags, list)
                    else [t.strip() for t in tags.split(",") if t.strip()]
                )
            except Exception:
                tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        doc_id_list: list[str] = []
        if document_ids:
            try:
                parsed_docs = json.loads(document_ids)
                doc_id_list = (
                    parsed_docs
                    if isinstance(parsed_docs, list)
                    else [d.strip() for d in document_ids.split(",") if d.strip()]
                )
            except Exception:
                doc_id_list = [d.strip() for d in document_ids.split(",") if d.strip()]

        params = {}
        if parameters:
            try:
                parsed_params = json.loads(parameters)
                if isinstance(parsed_params, dict):
                    params = parsed_params
            except Exception:
                logger.debug(
                    "ignoring unparseable parameters: %s", parameters, exc_info=True
                )

        if incident_date:
            params["incident_date"] = incident_date
        if proceedings_date:
            params["proceedings_date"] = proceedings_date

        file_bytes = await file.read()
        scenario = scenario_service.create_scenario(
            organization_id=user.organization_id,
            user_id=user.id,
            title=title,
            description=description,
            jurisdiction=jurisdiction,
            domain=domain,
            tags=tag_list,
            fact_pattern=fact_pattern,
            parameters=params,
            document_ids=doc_id_list,
            filename=file.filename,
            file_content=file_bytes,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit(
        db,
        action="scenario_created_with_dossier",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="scenario",
        resource_id=scenario["id"],
    )
    return scenario


@router.get("/{scenario_id}")
def get_scenario(
    scenario_id: str,
    user: CurrentUser = Depends(require_module("sim", "scenario.view")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        scenario = scenario_service.get_scenario(
            scenario_id, organization_id=user.organization_id, db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    require_tenant(
        scenario["current_version"]["created_by"] and user.organization_id, user
    )
    return scenario


@router.put("/{scenario_id}")
def update_scenario(
    scenario_id: str,
    body: ScenarioUpdate,
    user: CurrentUser = Depends(require_module("sim", "scenario.edit")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        scenario = scenario_service.get_scenario(
            scenario_id, organization_id=user.organization_id, db=db
        )
        if scenario.get("status") == "archived":
            raise HTTPException(
                status_code=409, detail="archived scenarios cannot be edited"
            )
        updated = scenario_service.update_scenario(
            scenario_id,
            organization_id=user.organization_id,
            user_id=user.id,
            db=db,
            **body.model_dump(exclude_none=True),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit(
        db,
        action="scenario_updated",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="scenario",
        resource_id=scenario_id,
    )
    return updated


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(
    scenario_id: str,
    user: CurrentUser = Depends(require_module("sim", "scenario.edit")),
    db: Session = Depends(get_db),
) -> None:
    try:
        scenario_service.delete_scenario(
            scenario_id, organization_id=user.organization_id, db=db
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit(
        db,
        action="scenario_deleted",
        actor=user.id,
        organization_id=user.organization_id,
        resource_type="scenario",
        resource_id=scenario_id,
    )
