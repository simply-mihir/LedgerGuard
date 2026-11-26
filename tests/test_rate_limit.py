"""API-wide rate limiting: token-bucket maths and the middleware's HTTP behaviour."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ledgerguard.api.app import create_app
from ledgerguard.api.rate_limit import TokenBuckets
from ledgerguard.config import settings


def test_bucket_allows_a_burst_then_throttles_and_refills() -> None:
    now = [0.0]
    b = TokenBuckets(clock=lambda: now[0])
    key = ("1.2.3.4", "r")
    assert [b.take(key, 60) for _ in range(60)] == [0.0] * 60  # a full minute's burst
    wait = b.take(key, 60)
    assert wait == pytest.approx(1.0)  # 60/min refills one token per second
    now[0] += 1.0
    assert b.take(key, 60) == 0.0
    assert b.take(key, 60) > 0.0


def test_bucket_keys_are_independent_and_zero_disables() -> None:
    b = TokenBuckets(clock=lambda: 0.0)
    assert b.take(("a", "r"), 1) == 0.0 and b.take(("a", "r"), 1) > 0.0
    assert b.take(("b", "r"), 1) == 0.0  # another client is unaffected
    assert b.take(("a", "w"), 1) == 0.0  # reads and writes are separate buckets
    assert all(b.take(("c", "r"), 0) == 0.0 for _ in range(100))  # 0 = unlimited


def test_bucket_table_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ledgerguard.api.rate_limit._MAX_TRACKED_CLIENTS", 50)
    b = TokenBuckets(clock=lambda: 0.0)
    for i in range(500):
        b.take((f"ip{i}", "r"), 10)
    assert len(b._state) == 50


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "rate_limit_per_minute", 5)
    monkeypatch.setattr(settings, "write_rate_limit_per_minute", 2)
    return TestClient(create_app())


def test_reads_are_limited_with_retry_after(client: TestClient) -> None:
    codes = [client.get("/v1/does-not-exist").status_code for _ in range(8)]
    assert codes[:5] == [404] * 5
    assert set(codes[5:]) == {429}
    r = client.get("/v1/does-not-exist")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert r.json() == {"detail": "Rate limit exceeded. Retry later."}


def test_writes_have_a_tighter_separate_bucket(client: TestClient) -> None:
    codes = [client.post("/v1/does-not-exist").status_code for _ in range(4)]
    assert codes[:2] == [404, 404] and codes[2:] == [429, 429]
    assert client.get("/v1/does-not-exist").status_code == 404  # read bucket untouched


def test_health_is_never_limited(client: TestClient) -> None:
    assert all(client.get("/health").status_code == 200 for _ in range(50))


def test_forwarded_clients_get_their_own_bucket_only_via_trusted_proxy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Do not depend on the environment's trusted-proxy list (.env differs between machines).
    monkeypatch.setattr(settings, "trusted_proxies_raw", "testclient,127.0.0.1")
    for _ in range(5):
        client.get("/v1/x", headers={"X-Forwarded-For": "9.9.9.9"})
    assert client.get("/v1/x", headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 429
    assert client.get("/v1/x", headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 404
    # If the peer is not a trusted proxy, X-Forwarded-For is ignored (cannot be used to evade).
    monkeypatch.setattr(settings, "trusted_proxies_raw", "10.0.0.1")
    codes = [client.get("/v1/x", headers={"X-Forwarded-For": f"7.7.7.{i}"}).status_code for i in range(8)]
    assert 429 in codes


def test_limit_zero_disables_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_per_minute", 0)
    c = TestClient(create_app())
    assert all(c.get("/v1/does-not-exist").status_code == 404 for _ in range(30))
