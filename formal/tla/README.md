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

## Concurrent multi-transfer model

`LedgerGuardTCCMulti.tla` models three transfers sharing one source and one destination account (message layer abstracted). `LedgerGuardTCCMulti.cfg` must pass; `LedgerGuardTCCMulti_broken.cfg` sets `IgnoreHolds = TRUE` and must yield a `NoOverspend` counterexample. Both run from `scripts/run_tla_model_check.sh` (`VERIFY_BROKEN=1` for the defective variants). See `docs/trace_conformance.md`.
