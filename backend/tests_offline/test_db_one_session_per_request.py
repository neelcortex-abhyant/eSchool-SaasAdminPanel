"""Regression: one database session (one pooled connection) per request.

Production bug (2026-11-13): the Add syllabus form loads 20 subjects and calls
GET /school-admin/subjects/{id}/classes for each at once. Every School Admin request opened
TWO sessions on the same pool: get_v1_db (auth) and central_db (handler), and held the
first while waiting for the second. 20 concurrent requests exhausted the 15-connection
pool, all waited for their second connection, and after the 30 s pool timeout 15 of 20
returned HTTP 500 ("The choices couldn't be loaded").

These tests use a real SQLAlchemy QueuePool capped at ONE connection, so a request that
needs two connections times out exactly like production did.
"""

from __future__ import annotations

import threading
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.api.deps import central_db
from app.core import database
from app.core.v1_database import get_v1_db


@pytest.fixture()
def one_connection_pool(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'pool.db'}",
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=2,
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(database, "_engine", engine)
    monkeypatch.setattr(database, "_SessionLocal", sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))
    yield engine
    engine.dispose()


def _auth(db: Annotated[Session, Depends(get_v1_db)]) -> Session:
    """Stands in for get_current_auth / require_school_admin: reads with the v1 session."""
    db.execute(text("SELECT 1"))  # checks a connection out and keeps it (open transaction)
    return db


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/school-admin-like")
    def handler(
        auth_db: Annotated[Session, Depends(_auth)],
        db: Annotated[Session, Depends(central_db)],
    ):
        db.execute(text("SELECT 2"))
        return {"same_session": auth_db is db}

    return app


def test_auth_and_handler_share_one_session(one_connection_pool):
    r = TestClient(_app()).get("/school-admin-like")
    assert r.status_code == 200, r.text
    assert r.json() == {"same_session": True}


def test_concurrent_requests_queue_instead_of_deadlocking(one_connection_pool):
    """8 requests at once on a 1-connection pool: all succeed (they wait in turn)."""
    client = TestClient(_app())
    results: list[int] = []

    def call():
        results.append(client.get("/school-admin-like").status_code)

    threads = [threading.Thread(target=call) for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=60)
    assert results == [200] * 8


def test_central_db_is_the_v1_dependency():
    """FastAPI caches a dependency per request by its callable, so they must be one object."""
    assert central_db is get_v1_db
