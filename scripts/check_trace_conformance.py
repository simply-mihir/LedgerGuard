#!/usr/bin/env python3
"""Check every recorded transfer history against the TLA+ TCC specification."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ledgerguard.config import settings
from ledgerguard.conformance import check_trace, fetch_traces
from ledgerguard.conformance.corpus import is_benign_accept, mutations
from ledgerguard.conformance.tla_trace import tlc_accepts, tlc_available
from ledgerguard.evidence import require_clean_tree


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tlc", action="store_true", help="cross-check unique traces with TLC")
    parser.add_argument("--out-dir", type=Path, default=Path("docs/conformance"))
    parser.add_argument("--allow-dirty", action="store_true",
                        help="run on an uncommitted tree (recorded as working_tree_clean=false)")
    args = parser.parse_args()
    prov = require_clean_tree(args.allow_dirty)

    traces = fetch_traces(settings.coordinator_db_url)
    results = {t.transfer_id: check_trace(list(t.tokens)) for t in traces}
    rejected = [t for t in traces if not results[t.transfer_id].accepted]
    shapes = Counter((t.final_state, t.tokens) for t in traces)

    unique = sorted({t.tokens for t in traces})
    mutants: dict[tuple[str, ...], str] = {}
    escaped: list[tuple[str, ...]] = []  # accepted mutants that are NOT benign
    benign = 0
    for u in unique:
        for name, m in mutations(list(u)):
            mutants.setdefault(tuple(m), name)
            if check_trace(m).accepted:
                if is_benign_accept(list(u), m):
                    benign += 1
                else:
                    escaped.append(tuple(m))

    tlc_agree: int | None = None
    if args.tlc:
        if not tlc_available():
            raise SystemExit("--tlc requires java and tla2tools.jar (run scripts/run_tla_model_check.sh once)")
        sample = list(unique) + sorted(mutants)[:40]
        with ThreadPoolExecutor(max_workers=4) as pool:
            verdicts = list(pool.map(lambda t: tlc_accepts(list(t)), sample))
        tlc_agree = sum(1 for t, v in zip(sample, verdicts, strict=True) if v == check_trace(list(t)).accepted)
        if tlc_agree != len(sample):
            raise SystemExit(f"checker disagrees with TLC on {len(sample) - tlc_agree} traces")

    report = {
        "source": {"git_sha": prov.git_sha, "git_tree": prov.git_tree,
                   "working_tree_clean": prov.working_tree_clean},
        "transfers_checked": len(traces),
        "accepted": len(traces) - len(rejected),
        "rejected": [str(t.transfer_id) for t in rejected],
        "unique_shapes": [
            {"final_state": fs, "events": list(tok), "count": n} for (fs, tok), n in shapes.most_common()
        ],
        "single_edit_mutants": len(mutants),
        "mutants_accepted_benign_marker_or_prefix": benign,
        "mutants_accepted_unexpected": len(escaped),
        "tlc_cross_checked": None if tlc_agree is None else len(sample),
        "tlc_agreement": tlc_agree,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 1 if rejected or escaped else 0


if __name__ == "__main__":
    raise SystemExit(main())
