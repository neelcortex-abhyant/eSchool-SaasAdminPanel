"""P0 regression: login rate limits key on the real client, not the shared proxy (DB-free)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import rate_limit


def _request(peer: str, *xff: str) -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in xff]
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


@pytest.fixture
def hops(monkeypatch):
    def set_hops(value: int):
        monkeypatch.setattr(
            "app.core.config.get_settings", lambda: SimpleNamespace(trusted_proxy_hops=value)
        )

    return set_hops


def test_default_uses_socket_peer(hops):
    hops(0)
    assert rate_limit.client_ip(_request("10.0.0.1", "1.1.1.1")) == "10.0.0.1"


def test_one_hop_uses_right_most_entry(hops):
    hops(1)
    assert rate_limit.client_ip(_request("10.0.0.1", "203.0.113.5")) == "203.0.113.5"


def test_spoofed_left_most_value_is_ignored(hops):
    hops(1)
    # Client sent "6.6.6.6"; the trusted proxy appended the real address.
    assert rate_limit.client_ip(_request("10.0.0.1", "6.6.6.6, 203.0.113.5")) == "203.0.113.5"


def test_two_hops_reads_through_netlify_proxy(hops):
    hops(2)
    # browser -> Netlify function (forwards XFF) -> Render edge
    assert rate_limit.client_ip(_request("10.0.0.1", "198.51.100.7, 54.1.2.3")) == "198.51.100.7"
    # multiple headers are joined in order
    assert rate_limit.client_ip(_request("10.0.0.1", "198.51.100.7", "54.1.2.3")) == "198.51.100.7"


def test_short_header_falls_back_to_left_most(hops):
    hops(3)
    assert rate_limit.client_ip(_request("10.0.0.1", "203.0.113.5")) == "203.0.113.5"


def test_no_header_uses_peer(hops):
    hops(2)
    assert rate_limit.client_ip(_request("10.0.0.1")) == "10.0.0.1"


def test_users_behind_same_proxy_no_longer_share_a_bucket(hops):
    """The H3 bug: 50 failures from anyone behind the proxy locked out every user."""
    hops(1)
    limiter = rate_limit.SlidingWindowLimiter("p0_test", limit=2, window_seconds=60)
    try:
        attacker = rate_limit.client_ip(_request("10.0.0.1", "203.0.113.5"))
        teacher = rate_limit.client_ip(_request("10.0.0.1", "198.51.100.9"))
        limiter.record(attacker)
        limiter.record(attacker)
        with pytest.raises(HTTPException) as err:
            limiter.check(attacker)
        assert err.value.status_code == 429
        limiter.check(teacher)  # not blocked
    finally:
        rate_limit._LIMITERS.remove(limiter)
