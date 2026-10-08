"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

from .models import Base


def make_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def init_engine(database_url: str | None = None) -> sessionmaker[Session]:
    """Create the engine, the tables, and the session factory (idempotent)."""
    global _engine, _SessionLocal
    _engine = make_engine(database_url)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _SessionLocal


def get_session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        return init_engine()
    return _SessionLocal


def get_db() -> Iterator[Session]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()
