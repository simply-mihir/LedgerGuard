"""Deterministic trace mutations and random traces for checker validation."""

from __future__ import annotations

import random

from ledgerguard.conformance.checker import _TRANSITIONS, KNOWN_TOKENS

_ORDERED_TOKENS = sorted(KNOWN_TOKENS)


def mutations(tokens: list[str]) -> list[tuple[str, list[str]]]:
    """Single-edit mutants: delete, swap adjacent, and insert any known event."""
    out: dict[tuple[str, ...], str] = {}

    def add(name: str, t: list[str]) -> None:
        if t != tokens:
            out.setdefault(tuple(t), name)

    for i in range(len(tokens)):
        add(f"delete[{i}]", tokens[:i] + tokens[i + 1 :])
    for i in range(len(tokens) - 1):
        swapped = list(tokens)
        swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
        add(f"swap[{i}]", swapped)
    for i in range(len(tokens) + 1):
        for tok in _ORDERED_TOKENS:
            add(f"insert[{i}]{tok}", tokens[:i] + [tok] + tokens[i:])
    return [(name, list(t)) for t, name in out.items()]


def random_traces(seed: int, count: int, max_len: int = 7) -> list[list[str]]:
    """Seeded random token sequences (mostly invalid) to stress the checker."""
    rng = random.Random(seed)
    seen: set[tuple[str, ...]] = set()
    while len(seen) < count:
        n = rng.randint(1, max_len)
        seen.add(tuple(rng.choice(_ORDERED_TOKENS) for _ in range(n)))
    return [list(t) for t in sorted(seen)]


def prefixes(tokens: list[str]) -> list[list[str]]:
    return [tokens[:i] for i in range(1, len(tokens) + 1)]


_CANCEL_ACKS = frozenset({"SOURCE_CANCELLED", "DESTINATION_CANCELLED"})


def state_changing(tokens: list[str]) -> list[str]:
    """Project a trace onto events that change specification state.

    After a CANCEL decision, cancel acknowledgements are legitimately optional: the
    reject path records none while the recovery path records both, and the specification
    accepts either. They are therefore projected away for cancelled transfers.
    """
    cancelled = "DECISION_MADE:CANCEL" in tokens
    return [t for t in tokens if t in _TRANSITIONS and not (cancelled and t in _CANCEL_ACKS)]


def is_benign_accept(base: list[str], mutant: list[str]) -> bool:
    """True if an accepted mutant only edits marker/acknowledgement events or truncates.

    Marker events (PHASE_PREPARE_STARTED, DECISION_COMMITTED, TRANSFER_SETTLED, ...) are
    pure state predicates in the specification, so deleting, repeating or moving them is
    unobservable. Truncation yields a valid prefix. Any other accepted mutant would mean the
    checker is too weak.
    """
    pm, pb = state_changing(mutant), state_changing(base)
    return pm == pb[: len(pm)]
