"""A TOTP code is single-use even when submitted concurrently, and MFA lockout is judged on the DB clock."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from starlette.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.auth.models import CreateOperatorRequest
from ledgerguard.auth.service import (
    AuthenticationError,
    confirm_totp_enrollment,
    create_operator_account,
    enroll_totp,
    verify_mfa_login,
)
from ledgerguard.auth.totp import get_totp_code
from ledgerguard.config import settings

pytestmark = pytest.mark.integration
client = TestClient(app)


def _mfa_operator() -> dict[str, object]:
    uid = uuid4().hex[:8]
    pwd = f"Pass_{uid}!Secure123"
    op = create_operator_account(CreateOperatorRequest(
        username=f"mfarace_{uid}", email=f"mfarace_{uid}@ledgerguard.internal", password=pwd,
        role="ADMIN", enable_totp=True))
    secret, _, _ = enroll_totp(op.operator_id)
    confirm_totp_enrollment(op.operator_id, get_totp_code(secret, t=int(time.time()) - 30))
    return {"op": op, "password": pwd, "secret": secret}


def _temp_token(m: dict[str, object]) -> str:
    r = client.post("/v1/auth/login", json={"identifier": m["op"].username, "password": m["password"]})  # type: ignore[attr-defined]
    return str(r.json()["temp_token"])


def test_one_valid_code_submitted_concurrently_yields_exactly_one_session() -> None:
    m = _mfa_operator()
    code = get_totp_code(str(m["secret"]))
    tokens = [_temp_token(m) for _ in range(8)]  # eight pending logins, one stolen/shared code

    def attempt(tok: str) -> bool:
        try:
            verify_mfa_login(tok, code)
            return True
        except AuthenticationError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        wins = sum(pool.map(attempt, tokens))
    assert wins == 1, f"{wins} sessions were issued from a single-use code"
    with psycopg.connect(settings.coordinator_admin_db_url) as c:
        sessions = c.execute("SELECT count(*) FROM operator_sessions WHERE operator_id = %s",
                             (m["op"].operator_id,)).fetchone()[0]  # type: ignore[attr-defined, index]
    assert sessions == 1
