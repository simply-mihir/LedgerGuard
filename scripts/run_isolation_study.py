#!/usr/bin/env python3
"""Run the isolation-level study and write JSON + Markdown evidence."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ledgerguard.evidence import require_clean_tree
from ledgerguard.isolation import report_markdown, run_isolation_study


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out-dir", type=Path, default=Path("docs/isolation"))
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    prov = require_clean_tree(args.allow_dirty)

    report = run_isolation_study(real_workers=args.workers)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "provenance": prov.model_dump(),
        "server_version": report.server_version,
        "cells": [asdict(c) for c in report.cells],
        "real_post_journal": [asdict(r) for r in report.real],
    }
    (args.out_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "results.md").write_text(report_markdown(report), encoding="utf-8")
    print(report_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
