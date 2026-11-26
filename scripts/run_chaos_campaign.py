#!/usr/bin/env python3
"""Run a deterministic LedgerGuard chaos campaign and emit a JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ledgerguard.chaos import ChaosCampaignConfig, run_chaos_campaign


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic LedgerGuard chaos campaign.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic PRNG seed (default: 42)")
    parser.add_argument("--ops", type=int, default=20, help="Number of operations (default: 20)")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent worker count (default: 4)")
    parser.add_argument("--accounts", type=int, default=6, help="Synthetic account count (default: 6)")
    parser.add_argument("--output", type=str, default="", help="Optional path to write JSON report")
    args = parser.parse_args()

    cfg = ChaosCampaignConfig(
        seed=args.seed,
        operation_count=args.ops,
        worker_count=args.workers,
        num_accounts=args.accounts,
    )
    report = run_chaos_campaign(cfg)
    payload = report.model_dump_json(indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    print(
        json.dumps(
            {
                "campaign_id": report.campaign_id,
                "seed": report.seed,
                "status": report.status,
                "operations_attempted": report.operations_attempted,
                "settled_count": report.settled_count,
                "recovered_count": report.recovered_count,
                "duplicate_messages_ignored": report.duplicate_messages_ignored,
                "reconciliation_status": report.reconciliation_result.get("status"),
            },
            indent=2,
        )
    )
    return 0 if report.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
