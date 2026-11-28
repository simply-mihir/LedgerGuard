#!/usr/bin/env python3
"""Run the real fault-injection campaign (SIGKILL, partitions, resets, container crashes)."""

from __future__ import annotations

import argparse
from pathlib import Path

from ledgerguard.evidence import require_clean_tree
from ledgerguard.faults.scenarios import report_json, run_campaign


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--containers", action="store_true",
        help="also SIGKILL the ledger-2 and coordinator PostgreSQL containers (needs Docker; "
             "briefly takes those shared dev databases down)",
    )
    parser.add_argument("--out-dir", type=Path, default=Path("docs/fault_injection"))
    parser.add_argument("--allow-dirty", action="store_true",
                        help="run on an uncommitted tree (recorded as working_tree_clean=false)")
    args = parser.parse_args()
    require_clean_tree(args.allow_dirty)

    report = run_campaign(seed=args.seed, include_containers=args.containers)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "results.json").write_text(report_json(report), encoding="utf-8")
    (args.out_dir / "results.md").write_text(report.to_markdown(), encoding="utf-8")
    print(report.to_markdown())
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
