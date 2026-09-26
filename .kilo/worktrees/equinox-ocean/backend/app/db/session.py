"""Database session management with SQLite (dev) / PostgreSQL (prod) support."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def build_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite:"):
        path = url.replace("sqlite:///", "")
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"connect_args": _connect_args(url)} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, **kwargs)


engine = build_engine()
SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, class_=Session
)


def get_db():
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
