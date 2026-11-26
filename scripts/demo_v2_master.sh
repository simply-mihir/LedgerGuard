#!/usr/bin/env bash
set -euo pipefail

echo "=== LedgerGuard V2 Master Verification & Demonstration ==="
./scripts/demo_signature_recovery.sh
uv run python scripts/run_chaos_campaign.py --seed 42 --ops 12 --workers 2
VERIFY_BROKEN=1 ./scripts/run_tla_model_check.sh
./scripts/demo_tamper_detection.sh
uv run python -m ledgerguard.cli verify-all-ledgers
./scripts/demo_disaster_recovery.sh --confirm-disposable
python3 scripts/security_audit_scanner.py
echo "=== ALL V2 DEMONSTRATIONS PASSED ==="
