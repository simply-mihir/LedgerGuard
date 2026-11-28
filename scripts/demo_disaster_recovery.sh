#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" != "--confirm-disposable" ]; then
  echo "ERROR: Refusing to run disaster recovery drill without --confirm-disposable." >&2
  echo "Usage: $0 --confirm-disposable" >&2
  exit 2
fi

echo "=== LedgerGuard Stage 12: Isolated Disaster Recovery & Replay Drill ==="
uv run python - <<'PY'
from ledgerguard.dr import run_disposable_dr_drill

rep = run_disposable_dr_drill(confirm_disposable=True)
print(rep.model_dump_json(indent=2))
assert rep.status == "PASS", f"DR drill failed: {rep.status}"
PY
