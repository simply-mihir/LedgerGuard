#!/usr/bin/env python3
"""Check every recorded transfer's ledger records against the coordinator trace and the TLA+ spec."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from ledgerguard.config import settings
from ledgerguard.conformance import fetch_traces
from ledgerguard.conformance.participant import (
    check_participants,
    fetch_transfer_facts,
    orphan_participant_transfers,
)
from ledgerguard.evidence import require_clean_tree


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("docs/conformance"))
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    prov = require_clean_tree(args.allow_dirty)

    coord = settings.coordinator_admin_db_url
    ledgers = {"ledger-1": settings.ledger1_admin_db_url, "ledger-2": settings.ledger2_admin_db_url}
    facts = fetch_transfer_facts(coord, ledgers)
    tokens = {t.transfer_id: list(t.tokens) for t in fetch_traces(coord)}

    failures: list[dict[str, object]] = []
    by_state: Counter[str] = Counter()
    for f in facts:
        by_state[f.state] += 1
        res = check_participants(tokens.get(f.transfer_id, []), f)
        if not res.conforms:
            failures.append({"transfer_id": str(f.transfer_id), "state": f.state, "reasons": list(res.reasons)})

    report = {
        "source": {"git_sha": prov.git_sha, "git_tree": prov.git_tree,
                   "working_tree_clean": prov.working_tree_clean},
        "transfers_checked": len(facts),
        "by_final_state": dict(by_state),
        "non_conforming": failures,
        # Participant state the coordinator never recorded (e.g. participant-level tests that call a
        # ledger directly). Not a refinement failure, but reserved funds with no owning transfer.
        "orphan_participant_transfers": {
            lid: len(orphan_participant_transfers(coord, url)) for lid, url in ledgers.items()},
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "participant_results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
