"""Real-PostgreSQL tests for the TCC / XA 2PC / Saga comparison harness."""

from __future__ import annotations

import json

import pytest

from ledgerguard.comparison import (
    ComparisonConfig,
    SagaProtocol,
    TccProtocol,
    XaProtocol,
    XaUnavailableError,
)
from ledgerguard.comparison.protocols import SETTLED
from ledgerguard.comparison.scenarios import (
    _clearing_total,
    _crash,
    _customer_total,
    _failure,
    _new_account,
    _urls,
    report_json,
    run_comparison,
)
from ledgerguard.config import settings
from ledgerguard.domain.money import AmountPaise

CFG = ComparisonConfig(ops=6, workers=2, bystander_timeout_ms=800)


@pytest.fixture(scope="module")
def protocols() -> dict[str, object]:
    urls = _urls()
    try:
        xa = XaProtocol(urls)
    except XaUnavailableError as exc:  # pragma: no cover - environment guard
        pytest.skip(str(exc))
    xa.abort_all_prepared()
    return {
        "TCC": TccProtocol(settings.coordinator_db_url, urls),
        "XA-2PC": xa,
        "Saga": SagaProtocol(urls),
    }


@pytest.mark.integration
@pytest.mark.parametrize("name", ["TCC", "XA-2PC", "Saga"])
def test_every_protocol_settles_and_conserves_funds(protocols, name) -> None:
    proto = protocols[name]
    src = _new_account("ledger-1", 100_000)
    dst = _new_account("ledger-2", 0)
    accounts = {src: "ledger-1", dst: "ledger-2"}
    funds0, clearing0 = _customer_total(accounts), _clearing_total()

    out = proto.transfer(src, dst, AmountPaise(2_500))

    assert out.state == SETTLED
    assert _customer_total(accounts) == funds0
    assert _clearing_total() == clearing0


@pytest.mark.integration
def test_crash_window_semantics_differ_by_protocol(protocols) -> None:
    tcc = _crash(protocols["TCC"], CFG)
    xa = _crash(protocols["XA-2PC"], CFG)
    saga = _crash(protocols["Saga"], CFG)

    # TCC: funds only held as rows; nothing posted early; other work proceeds.
    assert tcc.partial_posting_visible is False
    assert tcc.bystander_state == "SETTLED"
    # XA: prepared transactions pin row locks; a bystander on the same account blocks.
    assert xa.bystander_state == "BLOCKED"
    assert xa.bystander_wait_ms >= CFG.bystander_timeout_ms * 0.9
    assert "prepared" in xa.resources_pinned_in_window
    # Saga: the debit is already committed and visible while the transfer is in doubt.
    assert saga.partial_posting_visible is True
    assert saga.customer_funds_delta_in_window == -CFG.amount_minor

    # Every protocol recovers to a conserved, fully resolved state.
    for r in (tcc, xa, saga):
        assert r.customer_funds_delta_after == 0, r
        assert r.clearing_delta_after == 0, r
        assert r.unresolved_after == 0, r


@pytest.mark.integration
def test_destination_rejection_is_atomic_but_saga_pollutes_ledger(protocols) -> None:
    results = {n: _failure(protocols[n], CFG) for n in ("TCC", "XA-2PC", "Saga")}
    for r in results.values():
        assert r.final_state == "CANCELLED"
        assert r.atomic, r
    assert results["TCC"].journals_written == 0
    assert results["XA-2PC"].journals_written == 0
    # Saga must write the debit and a compensating credit: two journals for a failed transfer.
    assert results["Saga"].journals_written == 2


@pytest.mark.integration
def test_full_report_renders_and_serialises(protocols) -> None:
    report = run_comparison(ComparisonConfig(ops=4, workers=2, bystander_timeout_ms=800))
    md = report.to_markdown()
    for section in ("S1.", "S2.", "S3."):
        assert section in md
    assert {t.protocol for t in report.throughput} == {"TCC", "XA-2PC", "Saga"}
    assert all(t.settled == t.ops for t in report.throughput)
    assert json.loads(report_json(report))["schema_version"] == 1
    assert protocols["XA-2PC"].prepared_count() == 0
