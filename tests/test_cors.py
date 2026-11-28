"""CORS answers only for configured origins; credentials are never offered to anyone else."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.config import settings

client = TestClient(app)
GOOD = settings.get_trusted_origins()[0]


def _preflight(origin: str):
    return client.options("/v1/accounts", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type"})


def test_trusted_origin_preflight_is_allowed_with_credentials() -> None:
    r = _preflight(GOOD)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == GOOD
    assert r.headers["access-control-allow-credentials"] == "true"


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://localhost:3300.evil.example",
                                    GOOD.replace("http://", "https://")])
def test_untrusted_origin_gets_no_allow_origin_header(origin: str) -> None:
    r = _preflight(origin)
    assert "access-control-allow-origin" not in r.headers
    assert r.status_code == 400  # Starlette refuses a preflight from a disallowed origin


def test_wildcard_origin_cannot_be_configured_with_credentials() -> None:
    from ledgerguard.auth.origins import normalize_origin

    for bad in ("*", "null"):
        with pytest.raises(ValueError):
            normalize_origin(bad)
