"""Real School Admin routes under concurrency on PostgreSQL (isolated test DB only).

Before the fix every School Admin request held two pooled connections (auth session +
handler session). With the pool shrunk to 2 connections, 6 simultaneous requests would each
take one connection, wait for a second, and fail with 500 after the 30 s pool timeout.
After the fix each request uses one session, so they queue and all succeed.
"""

from __future__ import annotations

import threading
import time

import pytest

from tests.v1.test_phase3_school_admin import _auth_header, _create_school, _school_admin_token, _super_admin_headers


@pytest.fixture()
def small_pool(monkeypatch):
    monkeypatch.setenv("POOL_SIZE", "2")
    monkeypatch.setenv("MAX_OVERFLOW", "0")
    yield


def test_concurrent_school_admin_reads_do_not_exhaust_pool(small_pool, v1_client, v1_db):
    from app.core.database import get_engine

    assert get_engine().pool.size() == 2  # the small pool is really in use
    headers = _super_admin_headers(v1_client, v1_db, email="pool-sa@eschool.com")
    school_id = _create_school(v1_client, headers, code="POOL01", support_email="pool@eschool.com").json()["id"]
    token = _school_admin_token(v1_client, headers, school_id, "pool-admin@eschool.com")
    h = _auth_header(token)
    assert v1_client.get("/api/v1/school-admin/subjects", headers=h).status_code == 200

    results: list[tuple[int, float]] = []
    lock = threading.Lock()

    def call(path: str):
        start = time.monotonic()
        code = v1_client.get(path, headers=h).status_code
        with lock:
            results.append((code, time.monotonic() - start))

    paths = ["/api/v1/school-admin/subjects?page=1&page_size=50"] * 3 + [
        "/api/v1/school-admin/subjects/999999/classes?page=1&page_size=50"
    ] * 3
    threads = [threading.Thread(target=call, args=(p,)) for p in paths]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=120)

    codes = sorted(code for code, _ in results)
    assert len(results) == 6
    assert 500 not in codes, results
    assert codes == [200, 200, 200, 404, 404, 404], results
    assert max(sec for _, sec in results) < 30, results  # nobody hit the pool timeout
