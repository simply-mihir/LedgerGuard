#!/usr/bin/env python3
"""Plan every catalogued hot query at volume and write JSON + Markdown evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ledgerguard.config import settings
from ledgerguard.db.query_plans import (
    CATALOG,
    COORD,
    LEDGER,
    N_HOLDS,
    N_LINES,
    N_OUTBOX,
    N_TRANSFERS,
    ScratchVolume,
    explain,
    explain_without_index,
    find_redundant_indexes,
    used_index_matches_intended,
)
from ledgerguard.evidence import require_clean_tree

CONTROLS = {"open_transfer_recovery_sweep", "operator_transfer_list", "transfer_by_idempotency_key",
            "outbox_claim", "holds_as_of", "statement_first_page"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("docs/query_plans"))
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    prov = require_clean_tree(args.allow_dirty)

    rows: list[dict[str, object]] = []
    for db in (COORD, LEDGER):
        with ScratchVolume(db) as vol:
            planned = {q.name: explain(vol, q) for q in CATALOG if q.db == db}
            for q in (q for q in CATALOG if q.db == db):
                r = planned[q.name]
                chose_intended = used_index_matches_intended(vol, r)  # before any control mutates
                degraded = explain_without_index(vol, q) if q.name in CONTROLS else None
                rows.append({
                    "query": q.name, "database": db, "table": q.relation, "intended_index": q.index,
                    "planner_chose_intended": chose_intended,
                    "seq_scan": r.seq_scan_on_relation,
                    "seq_scan_without_index": None if degraded is None else degraded.seq_scan_on_relation,
                    "note": q.note,
                })
    redundant = {n: find_redundant_indexes(u) for n, u in (
        ("coordinator", settings.coordinator_admin_db_url),
        ("ledger-1", settings.ledger1_admin_db_url), ("ledger-2", settings.ledger2_admin_db_url))}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"provenance": prov.model_dump(),
               "volume": {"transfers": N_TRANSFERS, "outbox_events": N_OUTBOX,
                          "journal_lines": N_LINES, "holds": N_HOLDS},
               "queries": rows, "redundant_indexes": redundant}
    (args.out_dir / "results.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                                               encoding="utf-8")
    md = ["# Query-plan results", "",
          f"Planned against copies of the real tables loaded with {N_TRANSFERS:,} transfers, "
          f"{N_OUTBOX:,} outbox rows, {N_LINES:,} journal lines and {N_HOLDS:,} holds, then ANALYZEd.",
          "", "| Query | Table | Intended index | Uses it | Seq scan | Seq scan without the index |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        ctl = "n/a" if r["seq_scan_without_index"] is None else ("yes" if r["seq_scan_without_index"] else "no")
        md.append(f"| {r['query']} | {r['table']} | `{r['intended_index']}` | "
                  f"{'yes' if r['planner_chose_intended'] else 'NO'} | "
                  f"{'YES' if r['seq_scan'] else 'no'} | {ctl} |")
    md += ["", "Redundant indexes found: " + (
        "none" if not any(redundant.values()) else json.dumps(redundant))]
    (args.out_dir / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
