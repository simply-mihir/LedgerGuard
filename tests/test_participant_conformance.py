"""Participant-side conformance: ledger records must refine the specification state of the trace."""

from __future__ import annotations

from dataclasses import replace
from itertools import product
from uuid import UUID, uuid4

import psycopg
import pytest

from ledgerguard.comparison.scenarios import _new_account, _urls
from ledgerguard.config import settings
from ledgerguard.conformance import fetch_traces
from ledgerguard.conformance.participant import (
    CLEARING_ACCOUNT_ID,
    Journal,
    SideFacts,
    TransferFacts,
    check_participants,
    fetch_transfer_facts,
    local_violations,
    orphan_participant_transfers,
)
from ledgerguard.coordinator.failpoints import FailpointError, FailpointManager
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.domain.models import AccountStatus
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import set_account_status
from ledgerguard.worker.orchestrator import recover_pending_transfers

SETTLED_TRACE = ["PHASE_PREPARE_STARTED", "DECISION_MADE:COMMIT", "DECISION_COMMITTED",
                 "SOURCE_CONFIRMED", "DESTINATION_CONFIRMED", "TRANSFER_SETTLED"]
CANCEL_TRACE = ["PHASE_PREPARE_STARTED", "DECISION_MADE:CANCEL", "DESTINATION_PREPARE_REJECTED"]
COMMITTING_TRACE = ["PHASE_PREPARE_STARTED", "DECISION_MADE:COMMIT", "DECISION_COMMITTED"]
AMT = 1_000
SRC, DST, TID = uuid4(), uuid4(), uuid4()
LEDGERS = {"ledger-1": settings.ledger1_admin_db_url, "ledger-2": settings.ledger2_admin_db_url}
COORD = settings.coordinator_admin_db_url


def _src_side(intent: str | None) -> SideFacts:
    if intent is None:
        return SideFacts()
    j = ()
    if intent == "CONFIRMED":
        j = (Journal("SOURCE_SETTLE", ((SRC, "DEBIT", AMT), (CLEARING_ACCOUNT_ID, "CREDIT", AMT))),)
    hold = {"PREPARED": "ACTIVE", "CONFIRMED": "CONSUMED", "CANCELLED": "RELEASED"}[intent]
    return SideFacts(intent, "OUTGOING", AMT, SRC, DST, hold, AMT, SRC, j)


def _dst_side(intent: str | None) -> SideFacts:
    if intent is None:
        return SideFacts()
    j = ()
    if intent == "CONFIRMED":
        j = (Journal("DESTINATION_SETTLE", ((DST, "CREDIT", AMT), (CLEARING_ACCOUNT_ID, "DEBIT", AMT))),)
    return SideFacts(intent, "INCOMING", AMT, SRC, DST, None, None, None, j)


def facts(state: str, src: str | None, dst: str | None, hold: str | None = "auto") -> TransferFacts:
    s = _src_side(src)
    if hold != "auto":
        s = replace(s, hold_status=hold, hold_amount=AMT if hold else None, hold_account=SRC if hold else None)
    return TransferFacts(TID, state, AMT, SRC, DST, s, _dst_side(dst))


INTENTS = (None, "PREPARED", "CONFIRMED", "CANCELLED")


def _accepted(tokens: list[str], state: str) -> set[tuple[str | None, str | None]]:
    return {(s, d) for s, d in product(INTENTS, INTENTS)
            if check_participants(tokens, facts(state, s, d)).conforms}


def test_settled_trace_accepts_only_both_ledgers_confirmed() -> None:
    assert _accepted(SETTLED_TRACE, "SETTLED") == {("CONFIRMED", "CONFIRMED")}


def test_cancel_trace_accepts_only_quiesced_ledgers() -> None:
    # Nothing prepared or confirmed may remain once the transfer is CANCELLED.
    assert _accepted(CANCEL_TRACE, "CANCELLED") == {
        (s, d) for s in (None, "CANCELLED") for d in (None, "CANCELLED")}


def test_in_flight_commit_lets_ledgers_run_ahead_of_the_log_but_never_backwards() -> None:
    ok = _accepted(COMMITTING_TRACE, "COMMITTING")
    assert ok == {("PREPARED", "PREPARED"), ("CONFIRMED", "PREPARED"), ("CONFIRMED", "CONFIRMED")}
    # A destination credit before the source debit, or any cancel after commit, never conforms.
    assert ("PREPARED", "CONFIRMED") not in ok and ("CANCELLED", "PREPARED") not in ok


def test_a_cancelled_transfer_with_a_still_active_hold_is_flagged() -> None:
    r = check_participants(CANCEL_TRACE, facts("CANCELLED", "PREPARED", None))
    assert not r.conforms and any("CANCELLED" in x for x in r.reasons)


def test_settled_transfer_whose_source_hold_is_released_is_flagged() -> None:
    r = check_participants(SETTLED_TRACE, facts("SETTLED", "CONFIRMED", "CONFIRMED", hold="RELEASED"))
    assert not r.conforms


def test_clean_synthetic_records_have_no_local_violations() -> None:
    assert local_violations(facts("SETTLED", "CONFIRMED", "CONFIRMED")) == []
    assert local_violations(facts("CANCELLED", "CANCELLED", "CANCELLED")) == []


@pytest.mark.parametrize("mutate,needle", [
    (lambda f: replace(f, source=replace(f.source, journals=f.source.journals * 2)), "double posting"),
    (lambda f: replace(f, source=replace(f.source, journals=())), "no SOURCE_SETTLE"),
    (lambda f: replace(f, destination=replace(f.destination, journals=())), "no DESTINATION_SETTLE"),
    (lambda f: replace(f, source=replace(f.source, intent_amount=AMT + 1)), "intent amount"),
    (lambda f: replace(f, source=replace(f.source, hold_amount=AMT - 1)), "hold amount"),
    (lambda f: replace(f, source=replace(f.source, hold_status="ACTIVE")), "hold ACTIVE but intent CONFIRMED"),
    (lambda f: replace(f, source=replace(f.source, hold_account=uuid4())), "different account"),
    (lambda f: replace(f, destination=replace(f.destination, hold_status="ACTIVE")), "hold exists on the destination"),
    (lambda f: replace(f, destination=replace(f.destination, intent_direction="OUTGOING")), "direction"),
    (lambda f: replace(f, source=replace(f.source, journals=(
        Journal("SOURCE_SETTLE", ((SRC, "DEBIT", AMT + 5), (CLEARING_ACCOUNT_ID, "CREDIT", AMT + 5))),))),
     "differ from the transfer"),
    (lambda f: replace(f, destination=replace(f.destination, journals=(
        Journal("DESTINATION_SETTLE", ((uuid4(), "CREDIT", AMT), (CLEARING_ACCOUNT_ID, "DEBIT", AMT))),))),
     "differ from the transfer"),
    (lambda f: replace(f, source=replace(f.source, journals=f.source.journals + f.destination.journals)),
     "belongs to the other ledger"),
])
def test_each_local_rule_detects_its_corruption(mutate, needle: str) -> None:  # type: ignore[no-untyped-def]
    bad = mutate(facts("SETTLED", "CONFIRMED", "CONFIRMED"))
    assert any(needle in v for v in local_violations(bad)), local_violations(bad)
    assert not check_participants(SETTLED_TRACE, bad).conforms


def test_journal_without_a_confirmed_intent_is_flagged() -> None:
    f = facts("SETTLED", "PREPARED", "CONFIRMED")
    f = replace(f, source=replace(f.source, journals=_src_side("CONFIRMED").journals))
    assert any("journal exists but intent is PREPARED" in v for v in local_violations(f))


# --------------------------------------------------------------------------- real databases


def _submit(src: UUID, dst: UUID, amount: int, failpoint: str | None = None) -> UUID:
    tid = uuid4()
    fp = None
    if failpoint:
        fp = FailpointManager()
        fp.set_failpoint(failpoint, tid)
    try:
        submit_coordinator_transfer(settings.coordinator_db_url, _urls(), f"pconf-{tid}", src, dst,
                                    AmountPaise(amount), transfer_id=tid, failpoint_mgr=fp)
    except FailpointError:
        recover_pending_transfers(settings.coordinator_db_url, _urls(), transfer_id=tid)
    return tid


@pytest.fixture(scope="module")
def workload() -> dict[str, UUID]:
    src = _new_account("ledger-1", 1_000_000)
    dst = _new_account("ledger-2", 0)
    out = {"settled": _submit(src, dst, 1_000)}
    for fp in ("FAIL_AFTER_SOURCE_PREPARE_REPLY", "FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM",
               "FAIL_AFTER_SOURCE_CONFIRM_BEFORE_DEST_CONFIRM", "FAIL_AFTER_DEST_CONFIRM_REPLY"):
        out[fp] = _submit(src, dst, 1_000, fp)
    out["source_rejects"] = _submit(_new_account("ledger-1", 100), dst, 1_000)
    closed = _new_account("ledger-2", 0)
    set_account_status(settings.ledger2_db_url, closed, AccountStatus.CLOSED, reason="participant conformance")
    out["destination_rejects"] = _submit(src, closed, 1_000)
    return out


def _check(ids: list[UUID] | None) -> dict[UUID, tuple[str, list[str]]]:
    tf = fetch_transfer_facts(COORD, LEDGERS, ids)
    traces = {t.transfer_id: list(t.tokens) for t in fetch_traces(COORD)}
    return {f.transfer_id: (f.state, list(check_participants(traces[f.transfer_id], f).reasons)) for f in tf}


@pytest.mark.integration
def test_ledgers_conform_for_settled_rejected_and_crash_recovered_transfers(workload: dict[str, UUID]) -> None:
    res = _check(list(workload.values()))
    assert {s for s, _ in res.values()} >= {"SETTLED", "CANCELLED"}
    assert {k: v for k, (_, v) in res.items() if v} == {}


@pytest.mark.integration
def test_every_recorded_transfer_in_the_database_conforms(workload: dict[str, UUID]) -> None:
    res = _check(None)
    assert len(res) >= len(workload)
    assert {k: v for k, (_, v) in res.items() if v} == {}


def _tamper(ledger: str, sql: str, tid: UUID, expect_state: str, *, bypass_triggers: bool) -> list[str]:
    """Apply ``sql`` on one ledger inside a transaction, check the transfer, then roll back.

    The ledger's own state-machine triggers refuse these edits, so ``bypass_triggers`` simulates the
    case the conformance check exists for: a store that was corrupted *around* the triggers (restore
    from a bad backup, a disabled trigger, direct file damage).
    """
    other = "ledger-2" if ledger == "ledger-1" else "ledger-1"
    with psycopg.connect(LEDGERS[ledger]) as bad, psycopg.connect(LEDGERS[other]) as good:
        if bypass_triggers:
            bad.execute("SET LOCAL session_replication_role = replica")
        bad.execute(sql, {"t": tid})
        tf = fetch_transfer_facts(COORD, {ledger: bad, other: good}, [tid])[0]
        assert tf.state == expect_state
        trace = next(t for t in fetch_traces(COORD) if t.transfer_id == tid)
        reasons = list(check_participants(list(trace.tokens), tf).reasons)
        bad.rollback()
        return reasons


TAMPERS = [
    ("UPDATE holds SET status = 'ACTIVE' WHERE transfer_id = %(t)s", "hold ACTIVE"),
    ("UPDATE transfer_intents SET status = 'CANCELLED' WHERE transfer_id = %(t)s", "journal exists but intent"),
    ("UPDATE transfer_intents SET amount_minor = amount_minor + 1 WHERE transfer_id = %(t)s", "intent amount"),
]


@pytest.mark.integration
@pytest.mark.parametrize("sql,needle", TAMPERS)
def test_the_ledger_refuses_to_tamper_with_a_settled_transfer(
        workload: dict[str, UUID], sql: str, needle: str) -> None:
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        _tamper("ledger-1", sql, workload["settled"], "SETTLED", bypass_triggers=False)


@pytest.mark.integration
@pytest.mark.parametrize("sql,needle", TAMPERS)
def test_tampering_that_bypasses_the_triggers_is_still_detected_by_conformance(
        workload: dict[str, UUID], sql: str, needle: str) -> None:
    reasons = _tamper("ledger-1", sql, workload["settled"], "SETTLED", bypass_triggers=True)
    assert any(needle in r for r in reasons), reasons


@pytest.mark.integration
def test_orphan_participant_state_is_reported_without_failing_known_transfers() -> None:
    orphan = uuid4()
    with psycopg.connect(LEDGERS["ledger-1"]) as c:
        c.execute("INSERT INTO transfer_intents (transfer_id, direction, source_account_id, "
                  "destination_account_id, amount_minor, status) VALUES (%s,'OUTGOING',%s,%s,1,'PREPARED')",
                  (orphan, uuid4(), uuid4()))
        assert orphan in orphan_participant_transfers(COORD, c)
        c.rollback()
