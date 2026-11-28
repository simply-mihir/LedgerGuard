"""Infrastructure failures (disk full, shutdown, lost connection) are never reported as bad requests."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from ledgerguard.api.app import create_app
from ledgerguard.db.errors import is_infrastructure_error
from ledgerguard.domain.constants import SYSTEM_CASH_ACCOUNT_ID
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant import posting_service
from ledgerguard.participant.posting_service import PostingError, simulate_funding

E = psycopg.errors

INFRASTRUCTURE = [
    E.DiskFull("x"), E.OutOfMemory("x"), E.TooManyConnections("x"), E.AdminShutdown("x"),
    E.CrashShutdown("x"), E.CannotConnectNow("x"), E.IoError("x"), E.LockNotAvailable("x"),
    E.DeadlockDetected("x"), E.SerializationFailure("x"), E.ConnectionFailure("x"),
    psycopg.OperationalError("connection refused"),  # no SQLSTATE: never reached the server
]
BUSINESS = [
    E.ObjectNotInPrerequisiteState("account CLOSED"),  # SQLSTATE 55000, class 55 but a business rule
    E.CheckViolation("unbalanced"), E.ForeignKeyViolation("no account"), E.UniqueViolation("dup"),
    ValueError("not a database error"),
]


@pytest.mark.parametrize("exc", INFRASTRUCTURE, ids=lambda e: type(e).__name__)
def test_classifier_marks_infrastructure_failures(exc: Exception) -> None:
    assert is_infrastructure_error(exc)


@pytest.mark.parametrize("exc", BUSINESS, ids=lambda e: type(e).__name__)
def test_classifier_leaves_business_rejections_alone(exc: Exception) -> None:
    assert not is_infrastructure_error(exc)


class _Cur:
    def __init__(self, fail_with: Exception) -> None:
        self.fail_with = fail_with
        self.rows: list[dict[str, Any]] = []

    def __enter__(self) -> _Cur:
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> None:
        if "post_journal" in sql:
            raise self.fail_with
        self.rows = [{"account_id": a, "account_type": "ASSET" if a == SYSTEM_CASH_ACCOUNT_ID else "LIABILITY"}
                     for a in params[0]]

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class _Conn:
    def __init__(self, fail_with: Exception) -> None:
        self.fail_with, self.rolled_back = fail_with, False

    def __enter__(self) -> _Conn:
        return self

    def __exit__(self, *a: object) -> None:
        return None

    def cursor(self, **_: Any) -> _Cur:
        return _Cur(self.fail_with)

    def rollback(self) -> None:
        self.rolled_back = True


def test_posting_propagates_a_full_disk_instead_of_wrapping_it(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _Conn(E.DiskFull("could not extend file"))
    monkeypatch.setattr(posting_service, "get_db_connection", lambda url: conn)
    with pytest.raises(E.DiskFull):
        simulate_funding("ignored", uuid4(), AmountPaise(100))
    assert conn.rolled_back  # the failed transaction is rolled back, nothing half-applied


def test_posting_still_wraps_a_business_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _Conn(E.ObjectNotInPrerequisiteState("Account is CLOSED"))
    monkeypatch.setattr(posting_service, "get_db_connection", lambda url: conn)
    with pytest.raises(PostingError):
        simulate_funding("ignored", uuid4(), AmountPaise(100))
    assert conn.rolled_back


@pytest.mark.parametrize("exc", [E.DiskFull("No space left on device"), E.AdminShutdown("x"),
                                 psycopg.OperationalError("connection refused")],
                         ids=lambda e: type(e).__name__)
def test_api_returns_503_without_leaking_server_detail(exc: Exception) -> None:
    app = create_app()

    def boom() -> None:
        raise exc

    app.add_api_route("/__boom", boom)
    res = TestClient(app).get("/__boom")
    assert res.status_code == 503
    assert res.headers["Retry-After"] == "5"
    assert res.json() == {"detail": "The ledger database is temporarily unavailable. Retry later."}


def test_api_does_not_turn_an_escaped_business_error_into_a_503() -> None:
    app = create_app()

    def boom() -> None:
        raise psycopg.errors.ObjectNotInPrerequisiteState("account closed")

    app.add_api_route("/__boom", boom)
    res = TestClient(app, raise_server_exceptions=False).get("/__boom")
    assert res.status_code == 500
