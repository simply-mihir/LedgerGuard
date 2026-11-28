"""Python port of the ``LedgerGuardTCC.tla`` transition relation and a trace acceptor.

The acceptor answers: *is there a behaviour of the TLA+ specification whose observable
steps equal this recorded workflow trace?* (the "trace validation" question). Unobserved
steps - participant prepares, duplicate deliveries, message loss, worker crash/recovery,
retries and silent cancel handling - may occur between observed events.

This port is kept honest by a differential test: for a corpus of real, mutated and random
traces, its verdict must equal TLC's verdict on the generated trace specification
(``tla_trace.py``). Constants mirror ``formal/tla/LedgerGuardTCC.cfg``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# Constants from formal/tla/LedgerGuardTCC.cfg
INIT_SOURCE_BAL = 10
INIT_DEST_BAL = 0
AMOUNT = 4
MAX_LOSSES = 1
MAX_CRASHES = 1


@dataclass(frozen=True)
class S:
    """One state of the abstract single-transfer TCC model."""

    tx: str = "INIT"
    decision: str = "NONE"
    src: str = "NONE"
    dst: str = "NONE"
    src_bal: int = INIT_SOURCE_BAL
    src_hold: int = 0
    dst_bal: int = INIT_DEST_BAL
    clearing: int = 0
    msgs: frozenset[str] = frozenset({"SRC_PREPARE"})
    processed: frozenset[str] = frozenset()
    worker_up: bool = True
    losses: int = 0
    crashes: int = 0


def source_prepare(s: S) -> list[S]:
    if "SRC_PREPARE" not in s.msgs or "SRC_PREPARE" in s.processed:
        return []
    done = s.processed | {"SRC_PREPARE"}
    if s.src == "TOMBSTONE":
        return [replace(s, processed=done)]
    if s.src_bal - s.src_hold >= AMOUNT and s.src == "NONE":
        return [replace(
            s, src="PREPARED", src_hold=s.src_hold + AMOUNT,
            tx="SOURCE_PREPARED" if s.tx == "INIT" else s.tx,
            processed=done, msgs=s.msgs | {"DST_PREPARE"},
        )]
    return [replace(s, processed=done)]


def destination_prepare(s: S) -> list[S]:
    if "DST_PREPARE" not in s.msgs or "DST_PREPARE" in s.processed:
        return []
    done = s.processed | {"DST_PREPARE"}
    if s.dst == "TOMBSTONE":
        return [replace(s, processed=done)]
    return [replace(
        s, dst="PREPARED",
        tx="DESTINATION_PREPARED" if s.tx == "SOURCE_PREPARED" else s.tx,
        processed=done,
    )]


def decide_commit(s: S) -> list[S]:
    if not (s.worker_up and s.decision == "NONE" and s.src == "PREPARED" and s.dst == "PREPARED"):
        return []
    return [replace(s, decision="COMMIT", tx="COMMITTING", msgs=s.msgs | {"SRC_CONFIRM"})]


def decide_cancel(s: S) -> list[S]:
    if not (s.worker_up and s.decision == "NONE" and s.tx in ("INIT", "SOURCE_PREPARED")):
        return []
    return [replace(s, decision="CANCEL", tx="CANCELLING",
                    msgs=s.msgs | {"SRC_CANCEL", "DST_CANCEL"})]


def source_confirm(s: S) -> list[S]:
    if not ("SRC_CONFIRM" in s.msgs and "SRC_CONFIRM" not in s.processed
            and s.decision == "COMMIT" and s.src == "PREPARED"):
        return []
    return [replace(
        s, src="CONFIRMED", src_hold=s.src_hold - AMOUNT, src_bal=s.src_bal - AMOUNT,
        clearing=s.clearing - AMOUNT, processed=s.processed | {"SRC_CONFIRM"},
        msgs=s.msgs | {"DST_CONFIRM"},
    )]


def destination_confirm(s: S) -> list[S]:
    if not ("DST_CONFIRM" in s.msgs and "DST_CONFIRM" not in s.processed
            and s.decision == "COMMIT" and s.src == "CONFIRMED" and s.dst == "PREPARED"):
        return []
    return [replace(
        s, dst="CONFIRMED", dst_bal=s.dst_bal + AMOUNT, clearing=s.clearing + AMOUNT,
        tx="SETTLED", processed=s.processed | {"DST_CONFIRM"},
    )]


def cancel_source(s: S) -> list[S]:
    if not ("SRC_CANCEL" in s.msgs and "SRC_CANCEL" not in s.processed and s.decision == "CANCEL"):
        return []
    return [replace(
        s, src_hold=s.src_hold - AMOUNT if s.src == "PREPARED" else s.src_hold,
        src="TOMBSTONE", processed=s.processed | {"SRC_CANCEL"},
        tx="CANCELLED" if s.dst == "TOMBSTONE" else s.tx,
    )]


def cancel_destination(s: S) -> list[S]:
    if not ("DST_CANCEL" in s.msgs and "DST_CANCEL" not in s.processed and s.decision == "CANCEL"):
        return []
    return [replace(
        s, dst="TOMBSTONE", processed=s.processed | {"DST_CANCEL"},
        tx="CANCELLED" if s.src == "TOMBSTONE" else s.tx,
    )]


def worker_crash(s: S) -> list[S]:
    if not (s.worker_up and s.crashes < MAX_CRASHES):
        return []
    return [replace(s, worker_up=False, crashes=s.crashes + 1)]


def worker_recover(s: S) -> list[S]:
    return [] if s.worker_up else [replace(s, worker_up=True)]


def lose_message(s: S) -> list[S]:
    if s.losses >= MAX_LOSSES:
        return []
    return [replace(s, msgs=s.msgs - {m}, losses=s.losses + 1)
            for m in s.msgs if m not in s.processed]


def retry_pending(s: S) -> list[S]:
    if not s.worker_up:
        return []
    if s.decision == "COMMIT" and s.tx == "COMMITTING":
        add = {"SRC_CONFIRM"} if s.src != "CONFIRMED" else {"DST_CONFIRM"}
        return [replace(s, msgs=s.msgs | add)]
    if s.decision == "CANCEL" and s.tx == "CANCELLING":
        return [replace(s, msgs=s.msgs | {"SRC_CANCEL", "DST_CANCEL"})]
    if s.decision == "NONE" and s.src == "NONE" and "SRC_PREPARE" not in s.msgs:
        return [replace(s, msgs=s.msgs | {"SRC_PREPARE"})]
    if (s.decision == "NONE" and s.src == "PREPARED" and s.dst == "NONE"
            and "DST_PREPARE" not in s.msgs):
        return [replace(s, msgs=s.msgs | {"DST_PREPARE"})]
    return [s]


# Steps that may happen without being recorded in the workflow log.
SILENT = (
    source_prepare, destination_prepare, worker_crash, worker_recover, lose_message,
    retry_pending, cancel_source, cancel_destination,
)

# Observed event token -> transition (or state predicate for pure checks).
_TRANSITIONS = {
    "DECISION_MADE:COMMIT": decide_commit,
    "DECISION_MADE:CANCEL": decide_cancel,
    "SOURCE_CONFIRMED": source_confirm,
    "DESTINATION_CONFIRMED": destination_confirm,
    "SOURCE_CANCELLED": cancel_source,
    "DESTINATION_CANCELLED": cancel_destination,
}
_CHECKS = {
    "PHASE_PREPARE_STARTED": lambda s: True,
    "DECISION_COMMITTED": lambda s: s.decision == "COMMIT",
    "TRANSFER_SETTLED": lambda s: s.tx == "SETTLED",
    "TRANSFER_CANCELLED": lambda s: s.tx == "CANCELLED",
    "SOURCE_PREPARE_REJECTED": lambda s: s.decision == "CANCEL" and s.src in ("NONE", "TOMBSTONE"),
    "DESTINATION_PREPARE_REJECTED":
        lambda s: s.decision == "CANCEL" and s.src != "CONFIRMED" and s.dst != "CONFIRMED",
}

KNOWN_TOKENS = frozenset(_TRANSITIONS) | frozenset(_CHECKS)


def _closure(states: set[S]) -> set[S]:
    seen = set(states)
    frontier = list(states)
    while frontier:
        cur = frontier.pop()
        for step in SILENT:
            for nxt in step(cur):
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
    return seen


@dataclass(frozen=True)
class AcceptResult:
    accepted: bool
    matched: int  # number of trace tokens that could be matched in order
    reason: str = ""


def check_trace(tokens: list[str]) -> AcceptResult:
    """Return whether ``tokens`` is an observable behaviour of the TCC specification."""
    current = _closure({S()})
    for i, tok in enumerate(tokens):
        if tok not in KNOWN_TOKENS:
            return AcceptResult(False, i, f"unknown event token {tok!r}")
        if tok in _TRANSITIONS:
            nxt = {n for s in current for n in _TRANSITIONS[tok](s)}
        else:
            nxt = {s for s in current if _CHECKS[tok](s)}
        if not nxt:
            return AcceptResult(False, i, f"event {tok!r} is not enabled after {tokens[:i]}")
        current = _closure(nxt)
    return AcceptResult(True, len(tokens))
