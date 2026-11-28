# LedgerGuard V2 Master Demonstration Guide

Run the full V2 evidence sequence locally:

```bash
./scripts/demo_v2_master.sh
```

Or run individual demonstrations:
1. **Interrupted TCC Crash & Forward Recovery:** `./scripts/demo_signature_recovery.sh`
2. **Deterministic Chaos Campaign:** `uv run python scripts/run_chaos_campaign.py --seed 42 --ops 12 --workers 2`
3. **TLA+ Bounded Model Check:** `VERIFY_BROKEN=1 ./scripts/run_tla_model_check.sh`
4. **Tamper-Evident Journal Detection:** `./scripts/demo_tamper_detection.sh`
5. **Journal Chain Verification:** `uv run python -m ledgerguard.cli verify-all-ledgers`
6. **Performance Smoke Study:** `uv run python scripts/run_v2_perf_study.py --seed 42 --smoke --opposite-ops 100 --warmup 2 --out-dir docs/performance`
7. **Isolated Disaster Recovery Drill:** `./scripts/demo_disaster_recovery.sh --confirm-disposable`
8. **Security & Privacy Audit:** `python3 scripts/security_audit_scanner.py`
