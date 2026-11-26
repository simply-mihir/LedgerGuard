# Trace conformance: do real histories obey the TLA+ specification?

Model checking proves properties of an *abstraction*. This feature closes the loop in the
other direction: it takes the workflow history the running system actually recorded and asks
whether the TLA+ specification (`formal/tla/LedgerGuardTCC.tla`) could have produced it.

## What is checked

1. **Trace validation.** Every transfer's `workflow_events` (ordered by `created_at,
   event_id`) is normalised into specification tokens and checked for acceptance: *is there a
   behaviour of the spec whose observable steps equal this trace?* Unobserved steps (participant
   prepares, duplicate deliveries, message loss, worker crash/recovery, retries, silent cancel
   handling) may interleave.
2. **Two independent implementations of the check.**
   * `ledgerguard.conformance.checker` - a Python port of the spec's transition relation (fast,
     used in CI and by the CLI).
   * `ledgerguard.conformance.tla_trace` - generates a TLA+ trace module and asks **TLC** to find
     a behaviour that consumes the whole trace (an invariant violation of `NotAccepted` means
     "accepted"). A differential test requires both to agree on a corpus of real, mutated, prefix
     and random traces, so the Python port cannot silently drift from the spec.
3. **A concurrent multi-transfer model.** `LedgerGuardTCCMulti.tla` models three transfers
   sharing one source and one destination account. TLC checks `NoOverspend`, conservation,
   commit/cancel exclusivity, finished-clearing-zero, decision monotonicity and termination
   (2,232 distinct states, no symmetry reduction). Setting `IgnoreHolds = TRUE` (a Try phase that
   checks only posted balance) yields a TLC counterexample: three concurrent holds on a balance of
   10.

## Event-to-spec mapping

| Recorded event | Specification meaning |
|---|---|
| `DECISION_MADE` (decision in details) | `DecideCommit` / `DecideCancel` |
| `SOURCE_CONFIRMED`, `DESTINATION_CONFIRMED` | `SourceConfirm`, `DestinationConfirm` |
| `SOURCE_CANCELLED`, `DESTINATION_CANCELLED` | `CancelSource`, `CancelDestination` |
| `DECISION_COMMITTED`, `TRANSFER_SETTLED`, `TRANSFER_CANCELLED`, `*_PREPARE_REJECTED`, `PHASE_PREPARE_STARTED` | state predicates (no transition) |

## Results

Reproduce:

```bash
docker compose up -d
uv run python scripts/check_trace_conformance.py --tlc        # writes docs/conformance/results.json
VERIFY_BROKEN=1 ./scripts/run_tla_model_check.sh              # includes the multi-transfer model
uv run pytest tests/test_trace_conformance.py tests/test_tla_multi_transfer.py
```

* Every recorded transfer history in the development database conforms (see
  `docs/conformance/results.json` for the count and the distinct trace shapes).
* Single-edit mutants (delete, swap adjacent, insert any event) of the settled and cancelled
  traces are rejected, except mutants that only touch *marker* events or truncate the trace; the
  CLI and tests assert there are **zero** other accepted mutants.
* Safety-critical violations are rejected explicitly: confirm before decision, commit then cancel,
  cancel after commit, destination confirm before source confirm, settled without confirms, double
  decision, confirm after cancel.
* A tampered audit log (a `SOURCE_CANCELLED` row injected after a settled transfer) is detected;
  the test performs the injection inside a transaction it rolls back.

## Observations about the system

* The reject path (`SOURCE_PREPARE_REJECTED` / `DESTINATION_PREPARE_REJECTED`) records neither
  cancel acknowledgements nor `TRANSFER_CANCELLED`, whereas the recovery path records both.
  Both are valid per the spec, but a reader of the audit log cannot tell "cancelled" from
  "cancel in progress" on the reject path except via `transfers.state`. This is a completeness gap
  in the audit trail, not a safety bug, and is left unchanged.

## Limitations

* Trace validation is existential and weak per trace; its strength comes from the mutation
  results and from the invariants TLC proves on the specification itself.
* Only coordinator-observable events are in the trace. Participant tables (holds, inbox) are not
  yet projected into tokens, so participant-side divergence is not detected here.
* Marker events are only constrained by state predicates, so their relative order is not checked.
* The spec is bounded (`MaxLosses = MaxCrashes = 1`) and single-transfer; the multi-transfer
  model drops the message layer. Neither is a proof about the Python/PostgreSQL implementation.
* TLC-backed tests are skipped where Java or the pinned `tla2tools.jar` is unavailable; the CI
  `TLA+ Bounded Model Checking` job runs `scripts/run_tla_model_check.sh`, which now covers the
  multi-transfer model, but does not run the database-backed conformance tests.
