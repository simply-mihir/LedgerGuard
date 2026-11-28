"""Auth timing under clock skew: sessions, lockouts and approvals follow the database clock; the two
inherently wall-clock mechanisms (TOTP, signed MFA temp tokens) tolerate small skew and fail closed on large."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from ledgerguard.auth.models import CreateOperatorRequest
from ledgerguard.auth.service import (
    _generate_mfa_temp_token,
    _verify_mfa_temp_token,
    authenticate_operator,
    create_operator_account,
    validate_session,
)

pytestmark = pytest.mark.integration
YEAR = 365 * 24 * 3600


def _operator() -> tuple[str, str]:
    uid = uuid4().hex[:8]
    pwd = f"Pass_{uid}!Secure123"
    op = create_operator_account(CreateOperatorRequest(
        username=f"skew_{uid}", email=f"skew_{uid}@ledgerguard.internal", password=pwd,
        role="OPERATOR", enable_totp=False))
    return op.username, pwd


@pytest.mark.parametrize("offset", [+10 * YEAR, -10 * YEAR])
def test_a_session_is_valid_whatever_the_process_clock_says(monkeypatch: pytest.MonkeyPatch, offset: int) -> None:
    username, pwd = _operator()
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + offset)  # a wildly wrong application clock
    resp, raw, _csrf = authenticate_operator(username, pwd)
    assert resp.status == "SUCCESS"
    info, _ = validate_session(raw)
    assert info is not None and info.username == username, "expiry is measured by the database that stamped it"


def test_the_signed_mfa_temp_token_tolerates_small_skew_and_fails_closed_on_large(monkeypatch: pytest.MonkeyPatch) -> None:
    real = time.time
    op = uuid4()
    token = _generate_mfa_temp_token(op, ttl_seconds=300)
    assert _verify_mfa_temp_token(token) == op
    monkeypatch.setattr(time, "time", lambda: real() + 120)  # verifier two minutes ahead: still inside the 5 min TTL
    assert _verify_mfa_temp_token(token) == op
    monkeypatch.setattr(time, "time", lambda: real() + 3600)  # an hour ahead: expired, never accepted
    assert _verify_mfa_temp_token(token) is None
    monkeypatch.setattr(time, "time", lambda: real() - 3600)  # an hour behind: token is not "from the future" abuse
    assert _verify_mfa_temp_token(token) in (op, None)  # either is safe; it must not raise

