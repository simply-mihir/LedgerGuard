"""Participant-side trace conformance.

The coordinator trace says what the coordinator *recorded*. This module reads what each ledger
actually holds for the same transfer (intent, hold, settlement journal) and asks two questions:

1. **Ledger-local consistency** (:func:`local_violations`): do a ledger's own records agree with each
   other and with the transfer? An intent is ``CONFIRMED`` exactly when one settlement journal
   exists, the journal debits/credits the right accounts for exactly the transfer amount, a hold is
   ``CONSUMED``/``RELEASED``/``ACTIVE`` exactly when the intent is ``CONFIRMED``/``CANCELLED``/
   ``PREPARED``, and nothing is duplicated.
2. **Refinement against the specification** (:func:`check_participants`): replay the coordinator
   trace through the Python port of ``LedgerGuardTCC.tla`` and require that some reachable
   specification state has the same source state, destination state and hold as the ledgers. For a
   transfer still in flight the ledgers may be *ahead* of the coordinator's log (an acknowledgement
   not yet recorded); for a finished transfer they may not.

Abstraction: the specification has one hold amount, so a hold is abstracted to active/inactive; the
exact amount, accounts and journal lines are checked by the local rules above instead.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import psycopg

from ledgerguard.conformance.checker import (
    _CHECKS,
    _TRANSITIONS,
    KNOWN_TOKENS,
    SILENT,
    S,
    _closure,
)

CLEARING_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000002")
TERMINAL_STATES = frozenset({"SETTLED", "CANCELLED"})
_INTENT_TO_SPEC = {None: "NONE", "PREPARED": "PREPARED", "CONFIRMED": "CONFIRMED", "CANCELLED": "TOMBSTONE"}
_HOLD_FOR_INTENT = {"PREPARED": "ACTIVE", "CONFIRMED": "CONSUMED", "CANCELLED": "RELEASED"}


@dataclass(frozen=True)
class Journal:
    operation_type: str
    lines: tuple[tuple[UUID, str, int], ...]  # (account_id, side, amount_minor)


@dataclass(frozen=True)
class SideFacts:
    """Everything one ledger holds for one transfer."""

    intent_status: str | None = None
    intent_direction: str | None = None
    intent_amount: int | None = None
    intent_source: UUID | None = None
    intent_destination: UUID | None = None
    hold_status: str | None = None
    hold_amount: int | None = None
    hold_account: UUID | None = None
    journals: tuple[Journal, ...] = ()


@dataclass(frozen=True)
class TransferFacts:
    transfer_id: UUID
    state: str
    amount_minor: int
    source_account_id: UUID
    destination_account_id: UUID
    source: SideFacts
    destination: SideFacts


@dataclass(frozen=True)
class ParticipantResult:
    conforms: bool
    reasons: tuple[str, ...] = ()


def _settle_violations(side: str, facts: SideFacts, op: str, expected: set[tuple[UUID, str, int]],
                       own_intent: str, tid: UUID) -> list[str]:
    out: list[str] = []
    mine = [j for j in facts.journals if j.operation_type == op]
    confirmed = facts.intent_status == "CONFIRMED"
    if len(mine) > 1:
        out.append(f"{side}: {len(mine)} {op} journals for one transfer (double posting)")
    if confirmed and not mine:
        out.append(f"{side}: intent CONFIRMED but no {op} journal")
    if mine and not confirmed:
        out.append(f"{side}: {op} journal exists but intent is {facts.intent_status}")
    for j in mine:
        if set(j.lines) != expected or len(j.lines) != 2:
            out.append(f"{side}: {op} journal lines {sorted(map(str, j.lines))} differ from the transfer")
    if facts.intent_status is not None and facts.intent_direction != own_intent:
        out.append(f"{side}: intent direction {facts.intent_direction}, expected {own_intent}")
    return out


def local_violations(f: TransferFacts) -> list[str]:
    """Ledger-local consistency rules; an empty list means each ledger agrees with itself."""
    out: list[str] = []
    amt = f.amount_minor
    src, dst = f.source, f.destination

    for name, side in (("source", src), ("destination", dst)):
        if side.intent_status is not None:
            if side.intent_amount != amt:
                out.append(f"{name}: intent amount {side.intent_amount} != transfer amount {amt}")
            if (side.intent_source, side.intent_destination) != (f.source_account_id, f.destination_account_id):
                out.append(f"{name}: intent accounts differ from the transfer")

    out += _settle_violations(
        "source", src, "SOURCE_SETTLE",
        {(f.source_account_id, "DEBIT", amt), (CLEARING_ACCOUNT_ID, "CREDIT", amt)}, "OUTGOING", f.transfer_id)
    out += _settle_violations(
        "destination", dst, "DESTINATION_SETTLE",
        {(f.destination_account_id, "CREDIT", amt), (CLEARING_ACCOUNT_ID, "DEBIT", amt)}, "INCOMING", f.transfer_id)
    for name, side, op in (("source", src, "DESTINATION_SETTLE"), ("destination", dst, "SOURCE_SETTLE")):
        if any(j.operation_type == op for j in side.journals):
            out.append(f"{name}: carries a {op} journal that belongs to the other ledger")

    # Hold lifecycle (source only).
    if src.hold_status is not None:
        if src.intent_status is None:
            out.append("source: hold exists without an intent")
        elif _HOLD_FOR_INTENT[src.intent_status] != src.hold_status:
            out.append(f"source: hold {src.hold_status} but intent {src.intent_status}")
        if src.hold_amount != amt:
            out.append(f"source: hold amount {src.hold_amount} != transfer amount {amt}")
        if src.hold_account != f.source_account_id:
            out.append("source: hold is on a different account than the transfer's source")
    elif src.intent_status in ("PREPARED", "CONFIRMED"):
        out.append(f"source: intent {src.intent_status} but no hold")
    if dst.hold_status is not None:
        out.append("destination: a hold exists on the destination ledger")
    return out


@dataclass(frozen=True)
class Projection:
    src: str
    dst: str
    hold_active: bool


def project(f: TransferFacts) -> Projection:
    return Projection(
        src=_INTENT_TO_SPEC[f.source.intent_status],
        dst=_INTENT_TO_SPEC[f.destination.intent_status],
        hold_active=f.source.hold_status == "ACTIVE",
    )


_OBSERVABLE_STEPS = tuple(_TRANSITIONS.values())


def _closure_ahead(states: set[S]) -> set[S]:
    """Silent steps plus not-yet-recorded observable steps (participant ahead of the log)."""
    seen = set(states)
    frontier = list(states)
    steps = (*SILENT, *_OBSERVABLE_STEPS)
    while frontier:
        cur = frontier.pop()
        for step in steps:
            for nxt in step(cur):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
    return seen


def reachable_after(tokens: list[str]) -> set[S] | str:
    """Specification states reachable after the observed trace, or a reason it is not a behaviour."""
    current = _closure({S()})
    for i, tok in enumerate(tokens):
        if tok not in KNOWN_TOKENS:
            return f"unknown event token {tok!r}"
        if tok in _TRANSITIONS:
            nxt = {n for s in current for n in _TRANSITIONS[tok](s)}
        else:
            nxt = {s for s in current if _CHECKS[tok](s)}
        if not nxt:
            return f"event {tok!r} is not enabled after {tokens[:i]}"
        current = _closure(nxt)
    return current


def check_participants(tokens: list[str], f: TransferFacts) -> ParticipantResult:
    """Do the ledgers' records refine the specification state implied by the coordinator trace?"""
    reasons = local_violations(f)
    reachable = reachable_after(tokens)
    if isinstance(reachable, str):
        return ParticipantResult(False, (*reasons, f"coordinator trace: {reachable}"))
    p = project(f)
    terminal = f.state in TERMINAL_STATES
    candidates = reachable if terminal else _closure_ahead(reachable)
    if not any(s.src == p.src and s.dst == p.dst and (s.src_hold > 0) == p.hold_active for s in candidates):
        reasons.append(
            f"ledgers show source={p.src}, destination={p.dst}, hold_active={p.hold_active}, which no "
            f"specification state reachable from the coordinator trace "
            f"{'(finished transfer)' if terminal else '(in flight, ledgers may be ahead)'} has")
    if f.state == "CANCELLED":
        # A recorded cancel with no TRANSFER_CANCELLED marker (the reject path) is still a finished
        # transfer: nothing may remain prepared or reserved on either ledger.
        if p.src in ("PREPARED", "CONFIRMED") or p.dst in ("PREPARED", "CONFIRMED") or p.hold_active:
            reasons.append("transfer is CANCELLED but a ledger still holds prepared or confirmed state")
    if f.state == "SETTLED" and not (p.src == "CONFIRMED" and p.dst == "CONFIRMED"):
        reasons.append("transfer is SETTLED but a ledger has not confirmed")
    return ParticipantResult(not reasons, tuple(reasons))


# --------------------------------------------------------------------------- reading the databases


def _chunks(ids: list[UUID], n: int = 2000) -> Iterable[list[UUID]]:
    for i in range(0, len(ids), n):
        yield ids[i:i + n]


def _connect(target: str | psycopg.Connection[Any]) -> Any:
    """A context manager yielding a connection; an existing connection is borrowed, not closed."""
    if isinstance(target, str):
        return psycopg.connect(target)
    return contextlib.nullcontext(target)


def fetch_side_facts(ledger: str | psycopg.Connection[Any], transfer_ids: list[UUID]) -> dict[UUID, SideFacts]:
    """Read intents, holds and settlement journals for the given transfers from one ledger.

    ``ledger`` is a URL, or an open connection (so a test can read inside a transaction it rolls back).
    """
    intents: dict[UUID, tuple[Any, ...]] = {}
    holds: dict[UUID, tuple[Any, ...]] = {}
    journals: dict[UUID, dict[UUID, tuple[str, list[tuple[UUID, str, int]]]]] = {}
    with _connect(ledger) as c:
        for chunk in _chunks(transfer_ids):
            for r in c.execute(
                "SELECT transfer_id, status, direction, amount_minor, source_account_id, "
                "destination_account_id FROM transfer_intents WHERE transfer_id = ANY(%s)", (chunk,)):
                intents[r[0]] = r[1:]
            for r in c.execute(
                "SELECT transfer_id, status, amount_minor, account_id FROM holds "
                "WHERE transfer_id = ANY(%s)", (chunk,)):
                holds[r[0]] = r[1:]
            for tid, jid, op, acct, side, amount in c.execute(
                "SELECT h.transfer_id, h.journal_id, h.operation_type, l.account_id, l.side, l.amount_minor "
                "FROM journal_headers h JOIN journal_lines l ON l.journal_id = h.journal_id "
                "WHERE h.transfer_id = ANY(%s) AND h.operation_type IN ('SOURCE_SETTLE','DESTINATION_SETTLE') "
                "ORDER BY h.journal_id, l.line_no", (chunk,)):
                journals.setdefault(tid, {}).setdefault(jid, (op, []))[1].append((acct, side, int(amount)))
    out: dict[UUID, SideFacts] = {}
    for tid in set(intents) | set(holds) | set(journals):
        i = intents.get(tid)
        h = holds.get(tid)
        out[tid] = SideFacts(
            intent_status=i[0] if i else None, intent_direction=i[1] if i else None,
            intent_amount=int(i[2]) if i else None, intent_source=i[3] if i else None,
            intent_destination=i[4] if i else None,
            hold_status=h[0] if h else None, hold_amount=int(h[1]) if h else None,
            hold_account=h[2] if h else None,
            journals=tuple(Journal(op, tuple(lines)) for op, lines in journals.get(tid, {}).values()),
        )
    return out


def fetch_transfer_facts(coord_url: str, ledger_urls: dict[str, str | psycopg.Connection[Any]],
                         transfer_ids: Iterable[UUID] | None = None) -> list[TransferFacts]:
    """Join coordinator transfers with what each ledger holds for them."""
    wanted = list(transfer_ids) if transfer_ids is not None else None
    with psycopg.connect(coord_url) as c:
        if wanted is None:
            rows = c.execute(
                "SELECT transfer_id, state, amount_minor, source_account_id, destination_account_id, "
                "source_ledger_id, destination_ledger_id FROM transfers").fetchall()
        else:
            rows = c.execute(
                "SELECT transfer_id, state, amount_minor, source_account_id, destination_account_id, "
                "source_ledger_id, destination_ledger_id FROM transfers WHERE transfer_id = ANY(%s)",
                (wanted,)).fetchall()
    ids = [r[0] for r in rows]
    per_ledger = {lid: fetch_side_facts(url, ids) for lid, url in ledger_urls.items()}
    empty = SideFacts()
    return [
        TransferFacts(
            transfer_id=tid, state=str(state), amount_minor=int(amount), source_account_id=src, destination_account_id=dst,
            source=per_ledger.get(src_ledger, {}).get(tid, empty),
            destination=per_ledger.get(dst_ledger, {}).get(tid, empty))
        for tid, state, amount, src, dst, src_ledger, dst_ledger in rows
    ]


def orphan_participant_transfers(coord_url: str, ledger: str | psycopg.Connection[Any]) -> set[UUID]:
    """Transfer ids a ledger holds an intent or hold for that the coordinator has never heard of."""
    with psycopg.connect(coord_url) as c:
        known = {r[0] for r in c.execute("SELECT transfer_id FROM transfers")}
    with _connect(ledger) as c:
        held = {r[0] for r in c.execute(
            "SELECT transfer_id FROM transfer_intents UNION SELECT transfer_id FROM holds")}
    return held - known
