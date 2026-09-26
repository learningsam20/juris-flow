"""Scenario CRUD and versioning (PRD §5.1, §6.3)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.constants import SIM_COLLECTION
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.embeddings.factory import get_embeddings
from app.ingestion.chunker import chunk_text
from app.ingestion.parser import parse_document
from app.models import Scenario, ScenarioVersion
from app.vectorstore.factory import get_vectorstore

logger = logging.getLogger(__name__)


def create_scenario(
    *,
    organization_id: str,
    user_id: str,
    title: str,
    description: str = "",
    jurisdiction: str = "",
    domain: str = "",
    tags: list[str] | None = None,
    fact_pattern: str = "",
    parameters: dict | None = None,
    document_ids: list[str] | None = None,
    file_content: bytes | None = None,
    filename: str | None = None,
    db: Session,
) -> dict:
    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("scenario title is required")

    existing = (
        db.query(Scenario)
        .filter(
            Scenario.organization_id == organization_id,
            func.lower(Scenario.title) == clean_title.lower(),
        )
        .first()
    )
    if existing:
        raise ConflictError(f"A scenario titled '{clean_title}' already exists.")

    params = dict(parameters or {})
    final_fact_pattern = fact_pattern

    scenario_id = uuid.uuid4().hex
    version_id = uuid.uuid4().hex

    # If an uploaded scenario dossier file (PDF, TXT, DOCX) is provided, index it into SIM_COLLECTION
    if file_content and filename:
        try:
            parsed = parse_document(filename, file_content)
            dossier_text = (parsed.text or "").strip()
            if dossier_text:
                if not final_fact_pattern:
                    final_fact_pattern = dossier_text[:1200]
                chunks = chunk_text(dossier_text)
                if chunks:
                    params["dossier"] = {
                        "filename": filename,
                        "size_bytes": len(file_content),
                        "chunks_count": len(chunks),
                        "indexed": False,
                        "collection": SIM_COLLECTION,
                        "excerpt": dossier_text[:400],
                    }
                    try:
                        embedder = get_embeddings()
                        vectors = embedder.embed(chunks)
                        store = get_vectorstore()
                        store.ensure_collection(
                            SIM_COLLECTION, dimensions=len(vectors[0]) if vectors else 0
                        )
                        c_ids = [f"{scenario_id}:{i}" for i in range(len(chunks))]
                        payloads = [
                            {
                                "scenario_id": scenario_id,
                                "scenario_version_id": version_id,
                                "organization_id": organization_id,
                                "filename": filename,
                                "chunk_index": i,
                                "text": chunk,
                            }
                            for i, chunk in enumerate(chunks)
                        ]
                        store.upsert(SIM_COLLECTION, c_ids, vectors, payloads)
                        params["dossier"]["indexed"] = True
                    except Exception as exc:
                        logger.warning(
                            "Scenario dossier vector indexing failed: %s", exc
                        )
        except Exception as exc:
            logger.warning("Scenario dossier parsing failed: %s", exc)

    scenario = Scenario(
        id=scenario_id,
        organization_id=organization_id,
        title=clean_title,
        description=description,
        jurisdiction=jurisdiction,
        domain=domain,
        tags=tags or [],
        created_by=user_id,
    )
    db.add(scenario)
    db.flush()
    version = ScenarioVersion(
        id=version_id,
        scenario_id=scenario.id,
        version=1,
        title=clean_title,
        fact_pattern=final_fact_pattern,
        parameters=params,
        document_ids=document_ids or [],
        created_by=user_id,
    )
    db.add(version)
    db.commit()
    return scenario_to_dict(scenario, version)


def list_scenarios(*, organization_id: str, db: Session) -> list[dict]:
    scenarios = (
        db.query(Scenario)
        .filter(Scenario.organization_id == organization_id)
        .order_by(Scenario.updated_at.desc())
        .all()
    )
    return [scenario_to_dict(s, latest_version(db, s)) for s in scenarios]


def get_scenario(scenario_id: str, *, organization_id: str, db: Session) -> dict:
    s = db.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if s is None or s.organization_id != organization_id:
        raise NotFoundError("scenario not found")
    return scenario_to_dict(s, latest_version(db, s), include_versions=True)


def update_scenario(
    scenario_id: str, *, organization_id: str, user_id: str, db: Session, **fields
) -> dict:
    s = db.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if s is None or s.organization_id != organization_id:
        raise NotFoundError("scenario not found")

    if fields.get("title"):
        clean_title = fields["title"].strip()
        if clean_title.lower() != s.title.lower():
            existing = (
                db.query(Scenario)
                .filter(
                    Scenario.organization_id == organization_id,
                    Scenario.id != scenario_id,
                    func.lower(Scenario.title) == clean_title.lower(),
                )
                .first()
            )
            if existing:
                raise ConflictError(
                    f"A scenario titled '{clean_title}' already exists."
                )
        s.title = clean_title

    for key in ("description", "jurisdiction", "domain", "tags", "status"):
        if key in fields:
            setattr(s, key, fields[key])
    # content edits produce a new version
    version = latest_version(db, s)
    params = dict(fields.get("parameters", version.parameters if version else {}) or {})
    if "incident_date" in fields:
        params["incident_date"] = fields["incident_date"]
    if "proceedings_date" in fields:
        params["proceedings_date"] = fields["proceedings_date"]

    version = ScenarioVersion(
        id=uuid.uuid4().hex,
        scenario_id=scenario_id,
        version=(version.version if version else 0) + 1,
        title=fields.get("title", s.title),
        fact_pattern=fields.get(
            "fact_pattern", version.fact_pattern if version else ""
        ),
        parameters=params,
        document_ids=fields.get(
            "document_ids", version.document_ids if version else []
        ),
        created_by=user_id,
    )
    db.add(version)
    db.commit()
    return scenario_to_dict(s, version)


def delete_scenario(scenario_id: str, *, organization_id: str, db: Session) -> None:
    s = db.query(Scenario).filter(Scenario.id == scenario_id).one_or_none()
    if s is None or s.organization_id != organization_id:
        raise NotFoundError("scenario not found")

    from app.models.simulation import CaseStudy, Simulation, SimulationTurn

    version_ids = [v.id for v in s.versions]
    if version_ids:
        sims = (
            db.query(Simulation)
            .filter(Simulation.scenario_version_id.in_(version_ids))
            .all()
        )
        for sim in sims:
            db.query(CaseStudy).filter(CaseStudy.simulation_id == sim.id).delete()
            db.query(SimulationTurn).filter(
                SimulationTurn.simulation_id == sim.id
            ).delete()
            db.delete(sim)

    try:
        store = get_vectorstore()
        store.delete(SIM_COLLECTION, filters={"scenario_id": scenario_id})
    except Exception as exc:
        logger.warning(
            "Failed to clean up scenario dossier vectors for %s: %s", scenario_id, exc
        )

    db.delete(s)
    db.commit()


def latest_version(db: Session, scenario: Scenario) -> ScenarioVersion | None:
    return (
        db.query(ScenarioVersion)
        .filter(ScenarioVersion.scenario_id == scenario.id)
        .order_by(ScenarioVersion.version.desc())
        .first()
    )


def scenario_to_dict(
    scenario: Scenario, version: ScenarioVersion | None, include_versions: bool = False
) -> dict:
    params = (version.parameters or {}) if version else {}
    data: dict[str, Any] = {
        "id": scenario.id,
        "title": scenario.title,
        "description": scenario.description,
        "jurisdiction": scenario.jurisdiction,
        "domain": scenario.domain,
        "tags": scenario.tags or [],
        "status": scenario.status,
        "incident_date": params.get("incident_date"),
        "proceedings_date": params.get("proceedings_date"),
        "parameters": params,
        "fact_pattern": version.fact_pattern if version else "",
        "created_by": scenario.created_by,
        "updated_at": scenario.updated_at.isoformat() if scenario.updated_at else None,
    }
    if version:
        data["current_version"] = version_to_dict(version)
    if include_versions:
        data["versions"] = [version_to_dict(v) for v in scenario.versions]
    return data


def version_to_dict(v: ScenarioVersion) -> dict:
    params = v.parameters or {}
    return {
        "id": v.id,
        "version": v.version,
        "title": v.title,
        "fact_pattern": v.fact_pattern,
        "parameters": params,
        "incident_date": params.get("incident_date"),
        "proceedings_date": params.get("proceedings_date"),
        "document_ids": v.document_ids or [],
        "created_by": v.created_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }
