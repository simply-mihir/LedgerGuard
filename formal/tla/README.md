# LedgerGuard TCC TLA+ Formal Model

## Files

- `LedgerGuardTCC.tla` / `LedgerGuardTCC.cfg`: Passing bounded specification of LedgerGuard's application-level Try-Confirm-Cancel (TCC) protocol.
- `LedgerGuardTCC_broken.tla` / `LedgerGuardTCC_broken.cfg`: Intentionally flawed variant omitting the `decision = "NONE"` guard on `DecideCancel`, used to confirm TLC detects `NoCancelAfterCommit` violations.

## Execution

```bash
./scripts/run_tla_model_check.sh
VERIFY_BROKEN=1 ./scripts/run_tla_model_check.sh
```

See [`docs/formal_verification.md`](../../docs/formal_verification.md) for abstraction boundaries, fairness assumptions, state-space bounds, and the implementation traceability table.
