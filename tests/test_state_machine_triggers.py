"""The database itself refuses illegal state transitions; every attempt runs in a rolled-back transaction."""

from __future__ import annotations

from itertools import product
from uuid import uuid4

import psycopg
import pytest

from ledgerguard.config import settings

COORD = settings.coordinator_admin_db_url
LEDGER = settings.ledger1_admin_db_url
STATES = ["ACCEPTED", "PREPARING", "COMMITTING", "CANCELLING", "SETTLED", "CANCELLED", "REJECTED"]
LEGAL = {("ACCEPTED", "PREPARING"), ("ACCEPTED", "COMMITTING"), ("ACCEPTED", "CANCELLING"),
         ("ACCEPTED", "CANCELLED"), ("ACCEPTED", "REJECTED"), ("PREPARING", "COMMITTING"),
         ("PREPARING", "CANCELLING"), ("PREPARING", "CANCELLED"), ("PREPARING", "REJECTED"),
         ("COMMITTING", "SETTLED"), ("CANCELLING", "CANCELLED")}
NEEDS = {"COMMITTING": "COMMIT", "SETTLED": "COMMIT", "CANCELLING": "CANCEL", "CANCELLED": "CANCEL"}
# The decision a transfer already carries when it sits in each state.
HAS_DECISION = {"COMMITTING": "COMMIT", "SETTLED": "COMMIT", "CANCELLING": "CANCEL", "CANCELLED": "CANCEL"}
PATH = {"ACCEPTED": [], "PREPARING": ["PREPARING"], "COMMITTING": ["COMMITTING"],
        "CANCELLING": ["CANCELLING"], "SETTLED": ["COMMITTING", "SETTLED"],
        "CANCELLED": ["CANCELLING", "CANCELLED"], "REJECTED": ["REJECTED"]}


def _new_transfer(c: psycopg.Connection, state: str = "ACCEPTED"):
    tid = uuid4()
    c.execute(
        "INSERT INTO transfers (transfer_id, idempotency_key, source_account_id, destination_account_id, "
        "amount_minor, currency, transfer_type, state, source_ledger_id, destination_ledger_id) "
        "VALUES (%s, %s, %s, %s, 100, 'INR', 'CROSS_LEDGER', %s, 'ledger-1', 'ledger-2')",
        (tid, f"sm-{tid}", uuid4(), uuid4(), state))
    return tid


def _decide(c: psycopg.Connection, tid, decision: str) -> None:
    c.execute("INSERT INTO transfer_decisions (transfer_id, decision, decision_version, reason, decided_at) "
              "VALUES (%s, %s, 1, 'test', NOW())", (tid, decision))


def _move(c: psycopg.Connection, tid, state: str) -> None:
    c.execute("UPDATE transfers SET state = %s WHERE transfer_id = %s", (state, tid))


def _attempt(from_state: str, to_state: str, decision_for_target: bool = True) -> bool:
    """True if the database allowed the transition; always rolls back."""
    with psycopg.connect(COORD) as c:
        try:
            tid = _new_transfer(c)
            existing = HAS_DECISION.get(from_state)
            if existing:
                _decide(c, tid, existing)
            for step in PATH[from_state]:
                _move(c, tid, step)
            needed = NEEDS.get(to_state)
            if needed and existing is None and decision_for_target:
                _decide(c, tid, needed)
            _move(c, tid, to_state)
            return True
        except psycopg.errors.ObjectNotInPrerequisiteState:
            return False
        finally:
            c.rollback()


def test_transition_table_matches_the_documented_machine() -> None:
    with psycopg.connect(COORD) as c:
        rows = {tuple(r) for r in c.execute("SELECT from_state, to_state FROM transfer_state_transitions")}
    assert rows == LEGAL


@pytest.mark.parametrize("src,dst", [p for p in product(STATES, STATES) if p[0] != p[1]])
def test_transfer_transition_is_allowed_exactly_when_legal_and_decided(src: str, dst: str) -> None:
    existing = HAS_DECISION.get(src)
    decision_ok = NEEDS.get(dst) is None or existing is None or NEEDS[dst] == existing
    assert _attempt(src, dst) is ((src, dst) in LEGAL and decision_ok)


@pytest.mark.parametrize("dst", ["COMMITTING", "CANCELLING"])
def test_a_decided_state_without_its_decision_is_refused(dst: str) -> None:
    # SETTLED and CANCELLED are reachable only through these, so they are covered transitively.
    assert _attempt("PREPARING", dst, decision_for_target=False) is False


def test_commit_decision_cannot_drive_a_cancel_and_vice_versa() -> None:
    with psycopg.connect(COORD) as c:
        tid = _new_transfer(c)
        _decide(c, tid, "COMMIT")
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="CANCEL decision"):
            _move(c, tid, "CANCELLING")
        c.rollback()
        tid = _new_transfer(c)
        _decide(c, tid, "CANCEL")
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="COMMIT decision"):
            _move(c, tid, "COMMITTING")
        c.rollback()


@pytest.mark.parametrize("state", [s for s in STATES if s != "ACCEPTED"])
def test_a_transfer_cannot_be_created_in_a_later_state(state: str) -> None:
    with psycopg.connect(COORD) as c:
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="created in state ACCEPTED"):
            _new_transfer(c, state)
        c.rollback()


def test_a_durable_decision_cannot_be_flipped() -> None:
    with psycopg.connect(COORD) as c:
        tid = _new_transfer(c)
        _decide(c, tid, "COMMIT")
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="immutable"):
            c.execute("UPDATE transfer_decisions SET decision = 'CANCEL' WHERE transfer_id = %s", (tid,))
        c.rollback()


def test_updating_other_columns_of_a_settled_transfer_is_still_allowed() -> None:
    with psycopg.connect(COORD) as c:
        tid = _new_transfer(c)
        _decide(c, tid, "COMMIT")
        for s in ("COMMITTING", "SETTLED"):
            _move(c, tid, s)
        c.execute("UPDATE transfers SET refunded_amount_minor = 10, attention_required = TRUE "
                  "WHERE transfer_id = %s", (tid,))
        c.rollback()


# --------------------------------------------------------------------------- participant ledger


def _account(c: psycopg.Connection):
    a = uuid4()
    c.execute("INSERT INTO ledger_accounts (account_id, account_type, normal_side, currency, status) "
              "VALUES (%s, 'LIABILITY', 'CREDIT', 'INR', 'ACTIVE')", (a,))
    c.execute("INSERT INTO account_balances (account_id) VALUES (%s)", (a,))
    return a


def _hold(c: psycopg.Connection, a, status: str = "ACTIVE"):
    h = uuid4()
    c.execute("INSERT INTO holds (hold_id, account_id, transfer_id, amount_minor, status) "
              "VALUES (%s, %s, %s, 500, %s)", (h, a, uuid4(), status))
    return h


def _intent(c: psycopg.Connection, a, status: str = "PREPARED"):
    t = uuid4()
    c.execute("INSERT INTO transfer_intents (transfer_id, direction, source_account_id, "
              "destination_account_id, amount_minor, status) VALUES (%s, 'OUTGOING', %s, %s, 500, %s)",
              (t, a, uuid4(), status))
    return t


def _ledger_attempt(build, sql: str, params_from) -> bool:
    with psycopg.connect(LEDGER) as c:
        try:
            a = _account(c)
            key = build(c, a)
            c.execute(sql, params_from(key, a))
            return True
        except psycopg.errors.ObjectNotInPrerequisiteState:
            return False
        finally:
            c.rollback()


HOLD_STATES = ["ACTIVE", "CONSUMED", "RELEASED"]
HOLD_LEGAL = {("ACTIVE", "CONSUMED"), ("ACTIVE", "RELEASED")}


@pytest.mark.parametrize("src,dst", [p for p in product(HOLD_STATES, HOLD_STATES) if p[0] != p[1]])
def test_hold_transitions(src: str, dst: str) -> None:
    def build(c, a):
        h = _hold(c, a)
        if src != "ACTIVE":
            c.execute("UPDATE holds SET status = %s WHERE hold_id = %s", (src, h))
        return h
    allowed = _ledger_attempt(build, "UPDATE holds SET status = %s WHERE hold_id = %s", lambda h, a: (dst, h))
    assert allowed is ((src, dst) in HOLD_LEGAL)


@pytest.mark.parametrize("column,value", [("amount_minor", 501), ("account_id", None), ("transfer_id", None)])
def test_hold_facts_are_immutable(column: str, value: object) -> None:
    def build(c, a):
        return _hold(c, a)
    v = value if value is not None else uuid4()
    with psycopg.connect(LEDGER) as c:
        a = _account(c)
        h = _hold(c, a)
        if column == "account_id":
            v = _account(c)
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="immutable"):
            c.execute(f"UPDATE holds SET {column} = %s WHERE hold_id = %s", (v, h))
        c.rollback()


def test_a_hold_cannot_be_created_already_consumed() -> None:
    with psycopg.connect(LEDGER) as c:
        a = _account(c)
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="created ACTIVE"):
            _hold(c, a, "CONSUMED")
        c.rollback()


INTENT_STATES = ["PREPARED", "CONFIRMED", "CANCELLED"]
INTENT_LEGAL = {("PREPARED", "CONFIRMED"), ("PREPARED", "CANCELLED")}


@pytest.mark.parametrize("src,dst", [p for p in product(INTENT_STATES, INTENT_STATES) if p[0] != p[1]])
def test_intent_transitions(src: str, dst: str) -> None:
    def build(c, a):
        t = _intent(c, a, "CANCELLED" if src == "CANCELLED" else "PREPARED")
        if src == "CONFIRMED":
            c.execute("UPDATE transfer_intents SET status = 'CONFIRMED' WHERE transfer_id = %s", (t,))
        return t
    allowed = _ledger_attempt(build, "UPDATE transfer_intents SET status = %s WHERE transfer_id = %s",
                              lambda t, a: (dst, t))
    assert allowed is ((src, dst) in INTENT_LEGAL)


def test_an_intent_may_be_created_as_a_cancel_tombstone_but_not_confirmed() -> None:
    with psycopg.connect(LEDGER) as c:
        a = _account(c)
        _intent(c, a, "CANCELLED")
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="PREPARED or CANCELLED"):
            _intent(c, a, "CONFIRMED")
        c.rollback()


@pytest.mark.parametrize("column,value", [("amount_minor", 501), ("direction", "INCOMING"), ("currency", "USD")])
def test_intent_facts_are_immutable(column: str, value: object) -> None:
    with psycopg.connect(LEDGER) as c:
        t = _intent(c, _account(c))
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="immutable"):
            c.execute(f"UPDATE transfer_intents SET {column} = %s WHERE transfer_id = %s", (value, t))
        c.rollback()


def test_account_status_lifecycle_and_immutable_facts() -> None:
    with psycopg.connect(LEDGER) as c:
        a = _account(c)
        for ok in ("FROZEN", "ACTIVE", "FROZEN", "CLOSED"):
            c.execute("UPDATE ledger_accounts SET status = %s WHERE account_id = %s", (ok, a))
        for bad in ("ACTIVE", "FROZEN"):
            with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="cannot be reopened"):
                c.execute("UPDATE ledger_accounts SET status = %s WHERE account_id = %s", (bad, a))
            c.rollback()
            a = _account(c)
            c.execute("UPDATE ledger_accounts SET status = 'CLOSED' WHERE account_id = %s", (a,))
        for col, val in (("currency", "USD"), ("account_type", "ASSET"), ("normal_side", "DEBIT")):
            with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match="immutable"):
                c.execute(f"UPDATE ledger_accounts SET {col} = %s WHERE account_id = %s", (val, a))
            c.rollback()
            a = _account(c)
        c.rollback()
