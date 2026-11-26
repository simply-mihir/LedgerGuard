#!/usr/bin/env python3
"""Run the TCC vs XA 2PC vs Saga comparison and write JSON + Markdown evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from ledgerguard.comparison import ComparisonConfig, run_comparison
from ledgerguard.comparison.scenarios import report_json
from ledgerguard.evidence import require_clean_tree


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ops", type=int, default=48, help="transfers per throughput workload")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--bystander-timeout-ms", type=int, default=1500)
    parser.add_argument("--out-dir", type=Path, default=Path("docs/comparison"))
    parser.add_argument("--allow-dirty", action="store_true",
                        help="run on an uncommitted tree (recorded as working_tree_clean=false)")
    args = parser.parse_args()
    require_clean_tree(args.allow_dirty)

    report = run_comparison(
        ComparisonConfig(
            ops=args.ops,
            workers=args.workers,
            bystander_timeout_ms=args.bystander_timeout_ms,
        )
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "results.json").write_text(report_json(report), encoding="utf-8")
    (args.out_dir / "results.md").write_text(report.to_markdown(), encoding="utf-8")
    print(report.to_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
