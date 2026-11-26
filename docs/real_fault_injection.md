# Real Fault Injection

The earlier chaos campaign (`scripts/run_chaos_campaign.py`) injects faults through
in-process hooks. This campaign injects faults that the operating system and network
produce, against the real three-database PostgreSQL 17 deployment, then runs the
production recovery loop and checks every invariant.

## Faults

| Fault | Mechanism |
|---|---|
| Process crash | `SIGKILL` of an out-of-process transfer worker, including inside the window after the durable COMMIT decision and before the confirms |
| Network latency | In-repo TCP proxy (`ledgerguard.faults.FaultProxy`) delaying every chunk |
| Partition | Proxy black-holes a ledger link; the hung worker is then killed |
| Connection reset | Proxy severs live sockets with `SO_LINGER 0` (TCP RST) |
| API crash | `SIGKILL` of a uvicorn process mid-burst, then retry of the same `Idempotency-Key`s |
| Database crash | `docker kill -s KILL` of a PostgreSQL container (real WAL crash recovery), opt-in |

## Invariants checked after recovery

All transfers terminal; customer funds conserved; clearing nets to zero; no orphaned
holds; one settlement per transfer; a COMMIT/CANCEL decision never reverses;
cross-ledger reconciliation passes; journal hash chains verify; every recorded workflow
history is accepted by the TLA+ transition relation. The API scenario instead checks
that each key succeeds on replay, replays return the same transfer, each key is applied
exactly once, acknowledged transfers survive, and local reconciliation passes.

A negative control (`test_negative_control_invariants_detect_unrecovered_crash`)
confirms the checker fails when a crashed transfer is not recovered, so a pass is not
vacuous.

## Result

Seed 1 campaign with containers: 8 scenarios, all invariants pass
(`docs/fault_injection/results.{md,json}`). Kills landed 4/4 inside the commit window in
the targeted scenario.

## Reproduce

```bash
uv run python scripts/run_real_fault_campaign.py                # no container kills
uv run python scripts/run_real_fault_campaign.py --containers   # also kills the dev DB containers
LEDGERGUARD_ALLOW_CONTAINER_FAULTS=1 uv run pytest tests/test_real_fault_injection.py
```

`--containers` briefly takes down the shared dev coordinator and ledger-2 databases;
data persists and they restart automatically.

## Limitations

- Single machine, seeded but not fully deterministic (OS scheduling decides exact kill points).
- The proxy is bespoke rather than Toxiproxy; it models latency, loss, refusal and RST only, not reordering or corruption.
- The API-kill scenario covers local transfers; cross-ledger crashes are covered via the worker.
- Disk faults, clock skew and power-loss fsync behaviour are not simulated.
- `git_sha` in the results is the commit the run started from; the new files were uncommitted at that time.
