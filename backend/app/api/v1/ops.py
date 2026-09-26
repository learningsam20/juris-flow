"""Operations/health endpoints: readiness, OPA policy self-check, adapter health."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.opa.engine import get_engine
from app.queue import healthcheck as queue_healthcheck

router = APIRouter(tags=["ops"])


def _settings_snapshot() -> dict[str, Any]:
    settings = get_settings()
    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "ask_llm_model": settings.ask_llm_model,
        "llm_temperature": settings.llm_temperature,
        "ask_llm_temperature": settings.ask_llm_temperature,
        "ollama_base_url": settings.ollama_base_url,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "vector_provider": settings.vector_provider,
        "vector_distance": settings.vertex_vector_distance,
        "max_upload_mb": settings.max_upload_mb,
        "ocr_provider": settings.ocr_provider,
        "ocr_enabled": settings.ocr_enabled,
        "ocr_vision_model": settings.ocr_vision_model,
        "ocr_max_pages": settings.ocr_max_pages,
        "sim_judge_effort": settings.sim_judge_effort,
        "sim_judge_max_rounds": settings.sim_judge_max_rounds,
    }


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import text

    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "database": db_ok, "app": "jurisflow", "version": "1.0.0"}


@router.get("/ready")
def readiness() -> dict:
    engine = get_engine()
    decision = engine.decide(
        "rbac",
        {
            "action": "module",
            "user": {
                "platform_roles": ["org_admin"],
                "module_roles": ["sim.sim_educator"],
            },
            "resource": {"module": "sim", "permission": "scenario.view"},
        },
    )
    return {
        "status": "ready" if decision.allow else "degraded",
        **_settings_snapshot(),
        "opa_mode": "embedded",
        "opa_self_check": decision.allow,
        "queue": queue_healthcheck(),
    }


@router.get("/config")
def config() -> dict[str, Any]:
    return _settings_snapshot()


@router.patch("/config")
def update_config(payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    allowed_keys = {
        "llm_provider",
        "llm_model",
        "ask_llm_model",
        "llm_temperature",
        "ask_llm_temperature",
        "ollama_base_url",
        "sim_judge_effort",
        "sim_judge_max_rounds",
    }

    for key, value in payload.items():
        if key in allowed_keys:
            setattr(settings, key, value)

    return _settings_snapshot()
