"""FastAPI application entrypoint (lifespan: DB init, policy self-check, CORS)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.agents.tools as _agents_tools  # noqa: F401  (registers MCP tools in the gateway registry)
import app.models as _models  # noqa: F401  (ensures model registry imported)
from app.api.v1.router import api_router
from app.config import get_settings
from app.core.errors import JurisFlowError, PolicyDeniedError, UnauthorizedError
from app.core.logging import configure_logging, get_correlation_id
from app.core.telemetry import init_otel
from app.db.base import Base
from app.db.migrate import sync_schema
from app.db.session import engine
from app.opa.selfcheck import policy_selfcheck

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_otel(app)
    Base.metadata.create_all(bind=engine)
    sync_schema(engine)

    status = policy_selfcheck()
    if not status["ok"]:
        logger.warning(
            "OPA policy self-check incomplete; start/stop simulations may be restricted",
            extra={"failures": status["failures"]},
        )
    try:
        from app.vectorstore.factory import get_vectorstore

        get_vectorstore()
    except Exception as exc:
        logger.warning("Vector store pre-warm warning: %s", exc)
    settings = get_settings()
    logger.info(
        "jurisflow startup",
        extra={
            "llm": settings.llm_provider,
            "embedding": settings.embedding_provider,
            "vector": settings.vector_provider,
            "database": settings.database_url,
        },
    )
    yield


settings = get_settings()
app = FastAPI(
    title="JurisFlow API",
    version="1.0.0",
    description="Multi-agent legal simulation and document review platform (educational).",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "ops"},
        {"name": "auth"},
        {"name": "users"},
        {"name": "scenarios"},
        {"name": "simulations"},
        {"name": "documents"},
        {"name": "reviews"},
        {"name": "knowledge"},
        {"name": "exports"},
        {"name": "analytics"},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1")

# Serve synthesized narration / role-play clips under `/media/{simulation_id}/{file}`.
_tts_media_dir = Path(get_settings().tts_data_dir)
_tts_media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(_tts_media_dir)), name="media")


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    from app.core.logging import set_correlation_id

    set_correlation_id(request.headers.get("X-Correlation-ID"))
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = get_correlation_id()
    return response


@app.exception_handler(PolicyDeniedError)
async def policy_denied_handler(request: Request, exc: PolicyDeniedError):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=403, content={"detail": str(exc), "policy": exc.code}
    )


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(JurisFlowError)
async def jurisflow_error_handler(request: Request, exc: JurisFlowError):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.get("/")
def root() -> dict:
    return {"service": "jurisflow", "docs": "/docs", "health": "/api/v1/health"}
