#!/usr/bin/env python3
"""Run LedgerGuard V2 concurrency and performance study."""

from __future__ import annotations

import argparse
from pathlib import Path

from ledgerguard.perf import ALL_PROFILES, run_perf_study, write_study_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LedgerGuard V2 performance study.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--smoke", action="store_true", help="Run fast bounded smoke study across all 12 profiles")
    parser.add_argument("--ops", type=int, default=12)
    parser.add_argument("--opposite-ops", type=int, default=100, help="Measured ops for opposite_direction contention profile")
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--out-dir", default="docs/performance")
    args = parser.parse_args()

    workers = [1, 10] if args.smoke else [1, 10, 50]
    ops = 6 if args.smoke else args.ops
    report = run_perf_study(
        seed=args.seed,
        profiles=list(ALL_PROFILES),
        worker_levels=workers,
        warmup_ops=args.warmup,
        measured_ops=ops,
        per_profile_ops={"opposite_direction": args.opposite_ops},
    )
    paths = write_study_artifacts(report, Path(args.out_dir))
    print(f"Generated {len(report.results)} benchmark rows -> {paths['md']}")


if __name__ == "__main__":
    main()
