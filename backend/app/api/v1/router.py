"""Versioned API assembly."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    audio,
    auth,
    documents,
    exports,
    knowledge,
    ops,
    reviews,
    scenarios,
    simulations,
    users,
)

api_router = APIRouter()
api_router.include_router(ops.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(scenarios.router)
api_router.include_router(simulations.router)
api_router.include_router(documents.router)
api_router.include_router(reviews.router)
api_router.include_router(knowledge.router)
api_router.include_router(exports.router)
api_router.include_router(analytics.router)
api_router.include_router(audio.router)
api_router.include_router(audio.router)


__all__ = ["api_router"]
