"""Conformance of real LedgerGuard workflow histories against the TLA+ TCC specification."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest

from ledgerguard.chaos import ChaosCampaignConfig, ChaosCampaignEngine
from ledgerguard.comparison.scenarios import _new_account, _urls
from ledgerguard.config import settings
from ledgerguard.conformance import check_trace, fetch_traces, known_transfer_ids
from ledgerguard.conformance.corpus import is_benign_accept, mutations, prefixes, random_traces
from ledgerguard.conformance.tla_trace import tlc_accepts, tlc_available
from ledgerguard.coordinator.failpoints import FailpointError, FailpointManager
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.domain.models import AccountStatus
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import set_account_status
from ledgerguard.worker.orchestrator import recover_pending_transfers

SETTLED_TRACE = [
    "PHASE_PREPARE_STARTED", "DECISION_MADE:COMMIT", "DECISION_COMMITTED",
    "SOURCE_CONFIRMED", "DESTINATION_CONFIRMED", "TRANSFER_SETTLED",
]
CANCEL_TRACE = ["PHASE_PREPARE_STARTED", "DECISION_MADE:CANCEL", "DESTINATION_PREPARE_REJECTED"]
FAILPOINTS = [
    "FAIL_AFTER_SOURCE_PREPARE_REPLY",
    "FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM",
    "FAIL_AFTER_SOURCE_CONFIRM_BEFORE_DEST_CONFIRM",
    "FAIL_AFTER_DEST_CONFIRM_REPLY",
]
needs_tlc = pytest.mark.skipif(not tlc_available(), reason="java + tla2tools.jar not available")


def _submit(src: UUID, dst: UUID, amount: int, failpoint: str | None = None) -> UUID:
    tid = uuid4()
    fp = None
    if failpoint:
        fp = FailpointManager()
        fp.set_failpoint(failpoint, tid)
    try:
        submit_coordinator_transfer(
            settings.coordinator_db_url, _urls(), f"conf-{tid}", src, dst,
            AmountPaise(amount), transfer_id=tid, failpoint_mgr=fp,
        )
    except FailpointError:
        recover_pending_transfers(settings.coordinator_db_url, _urls(), transfer_id=tid)
    return tid


def _generate_workload() -> set[UUID]:
    """Create settled, rejected and crash-recovered transfers; return their ids."""
    before = known_transfer_ids(settings.coordinator_db_url)
    src = _new_account("ledger-1", 1_000_000)
    dst = _new_account("ledger-2", 0)
    _submit(src, dst, 1_000)
    for fp in FAILPOINTS:
        _submit(src, dst, 1_000, fp)
    _submit(_new_account("ledger-1", 100), dst, 1_000)  # insufficient funds -> source rejects
    closed = _new_account("ledger-2", 0)
    set_account_status(settings.ledger2_db_url, closed, AccountStatus.CLOSED, reason="conformance")
    _submit(src, closed, 1_000)  # destination rejects
    ChaosCampaignEngine().run(ChaosCampaignConfig(seed=7, operation_count=12, worker_count=2,
                                                  num_accounts=6))
    return known_transfer_ids(settings.coordinator_db_url) - before


@pytest.mark.integration
def test_every_real_history_conforms_to_the_specification() -> None:
    new_ids = _generate_workload()
    traces = [
        t for t in fetch_traces(settings.coordinator_db_url) if t.transfer_id in new_ids
    ]
    assert len(traces) >= 8
    failures = [(t.tokens, check_trace(list(t.tokens))) for t in traces
                if not check_trace(list(t.tokens)).accepted]
    assert not failures, failures
    shapes = {t.final_state for t in traces}
    assert {"SETTLED", "CANCELLED"} <= shapes
    assert any("SOURCE_PREPARE_REJECTED" in t.tokens for t in traces)
    assert any("DESTINATION_PREPARE_REJECTED" in t.tokens for t in traces)
    # Terminal coordinator state agrees with the last observed protocol event.
    for t in traces:
        if t.final_state == "SETTLED":
            assert t.tokens[-1] == "TRANSFER_SETTLED", t
        else:
            assert "TRANSFER_SETTLED" not in t.tokens, t


def test_single_edit_mutants_are_rejected_unless_unobservable() -> None:
    assert check_trace(SETTLED_TRACE).accepted
    rejected = 0
    for base in (SETTLED_TRACE, CANCEL_TRACE):
        for name, m in mutations(base):
            if check_trace(m).accepted:
                assert is_benign_accept(base, m), (name, m)
            else:
                rejected += 1
    assert rejected >= 100
    # Spot-check the violations that matter most for money safety.
    unsafe = {
        "confirm before decision": ["PHASE_PREPARE_STARTED", "SOURCE_CONFIRMED"],
        "commit then cancel": ["PHASE_PREPARE_STARTED", "DECISION_MADE:COMMIT",
                               "DECISION_MADE:CANCEL"],
        "cancel after commit": SETTLED_TRACE[:3] + ["SOURCE_CANCELLED"],
        "destination before source": SETTLED_TRACE[:3] + ["DESTINATION_CONFIRMED"],
        "settled without confirms": SETTLED_TRACE[:3] + ["TRANSFER_SETTLED"],
        "cancelled after commit": SETTLED_TRACE[:3] + ["TRANSFER_CANCELLED"],
        "double decision": SETTLED_TRACE[:2] + ["DECISION_MADE:COMMIT"],
        "confirm after cancel": CANCEL_TRACE[:2] + ["SOURCE_CONFIRMED"],
    }
    for label, tokens in unsafe.items():
        assert not check_trace(tokens).accepted, label


@pytest.mark.integration
def test_corrupted_workflow_history_is_detected_and_rolled_back() -> None:
    """A tampered audit log (cancel recorded after commit) must not conform."""
    src = _new_account("ledger-1", 100_000)
    dst = _new_account("ledger-2", 0)
    tid = _submit(src, dst, 500)
    with psycopg.connect(settings.coordinator_db_url) as conn:
        honest = [t for t in fetch_traces(conn=conn) if t.transfer_id == tid][0]
        assert check_trace(list(honest.tokens)).accepted
        conn.execute(
            "INSERT INTO workflow_events (transfer_id, event_type, details) "
            "VALUES (%s, 'SOURCE_CANCELLED', '{}');", (tid,),
        )
        forged = [t for t in fetch_traces(conn=conn) if t.transfer_id == tid][0]
        verdict = check_trace(list(forged.tokens))
        conn.rollback()  # never leave forged history behind
    assert not verdict.accepted
    assert "SOURCE_CANCELLED" in verdict.reason


@needs_tlc
def test_python_checker_agrees_with_tlc_on_a_trace_corpus() -> None:
    corpus: set[tuple[str, ...]] = {tuple(SETTLED_TRACE), tuple(CANCEL_TRACE)}
    corpus.update(tuple(p) for p in prefixes(SETTLED_TRACE))
    named = mutations(SETTLED_TRACE) + mutations(CANCEL_TRACE)
    corpus.update(tuple(m) for _, m in named[:: max(1, len(named) // 50)])
    corpus.update(tuple(t) for t in random_traces(seed=2026, count=30))
    ordered = sorted(corpus)
    with ThreadPoolExecutor(max_workers=4) as pool:
        tlc = list(pool.map(lambda t: tlc_accepts(list(t)), ordered))
    disagreements = [
        (t, v) for t, v in zip(ordered, tlc, strict=True) if v != check_trace(list(t)).accepted
    ]
    assert not disagreements, disagreements
    assert any(tlc) and not all(tlc)  # the corpus exercises both verdicts
