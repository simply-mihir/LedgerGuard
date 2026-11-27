#!/usr/bin/env python3
"""Run the journal-partitioning study and write JSON + Markdown evidence."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from ledgerguard.db.partition_study import report_markdown, run_partition_study, server_version
from ledgerguard.evidence import require_clean_tree


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("docs/partitioning"))
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    prov = require_clean_tree(args.allow_dirty)

    findings = run_partition_study()
    version = server_version()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"provenance": prov.model_dump(), "server_version": version,
               "findings": [asdict(f) for f in findings]}
    (args.out_dir / "results.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = report_markdown(findings, version)
    (args.out_dir / "results.md").write_text(md, encoding="utf-8")
    print(md)
    return 0 if all(f.holds for f in findings) else 1


if __name__ == "__main__":
    raise SystemExit(main())
