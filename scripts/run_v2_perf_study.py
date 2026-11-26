#!/usr/bin/env python3
"""Run LedgerGuard V2 concurrency and performance study."""

from __future__ import annotations

import argparse
from pathlib import Path

from ledgerguard.perf import ALL_PROFILES, run_perf_study, write_study_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LedgerGuard V2 performance study.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic PRNG seed")
    parser.add_argument("--smoke", action="store_true", help="Run fast bounded smoke study across profiles (workers=[1, 10], default ops=6)")
    parser.add_argument("--ops", type=int, default=12, help="Default measured ops per profile in full mode")
    parser.add_argument("--opposite-ops", type=int, default=100, help="Measured ops for opposite_direction contention profile")
    parser.add_argument("--warmup", type=int, default=2, help="Warmup operations before each measured window")
    parser.add_argument("--out-dir", default="docs/performance", help="Output directory for generated artifacts")
    parser.add_argument("--profiles", default="", help="Optional comma-separated subset of profile names")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow running on a dirty git working tree (marks working_tree_clean=false)")
    args = parser.parse_args()

    selected_profiles = (
        [p.strip() for p in args.profiles.split(",") if p.strip()]
        if args.profiles.strip()
        else list(ALL_PROFILES)
    )
    unknown = [p for p in selected_profiles if p not in ALL_PROFILES]
    if unknown:
        parser.error(f"Unknown profile(s): {', '.join(unknown)}")

    mode = "smoke" if args.smoke else "full"
    workers = [1, 10] if args.smoke else [1, 10, 50]
    ops = 6 if args.smoke else args.ops
    report = run_perf_study(
        seed=args.seed,
        profiles=selected_profiles,
        worker_levels=workers,
        warmup_ops=args.warmup,
        measured_ops=ops,
        per_profile_ops={"opposite_direction": args.opposite_ops},
        mode=mode,
        output_directory=args.out_dir,
        allow_dirty=args.allow_dirty,
    )
    paths = write_study_artifacts(report, Path(args.out_dir))
    print(f"Generated {len(report.results)} benchmark rows (schema v{report.schema_version}) -> {paths['md']}")


if __name__ == "__main__":
    main()
