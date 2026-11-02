# ADR 0004: Multi-Database Reachability Probing and Clearing Reconciliation

## Status
Accepted

## Context
When verifying financial integrity across multiple independent databases, network partitions or participant outages can mislead reconciliation engines into asserting a false global `PASS`. Furthermore, cross-ledger clearing must maintain exact double-entry balance without assuming instantaneous global ACID snapshots.

## Decision
1. **Fast Reachability Probing:**
   - Multi-database reconciliation begins by probing every configured database connection using a strict 2-second timeout (`connect_timeout=2`).
   - If any participant ledger is unreachable, the audit report immediately flags `coverage="PARTIAL"` and `status="INCOMPLETE"`. It is architecturally prohibited for a partial audit to return `status="PASS"`.
2. **Inter-Ledger Clearing Control Invariant:**
   - Each ledger maintains a system `CONTROL` account named `Inter-Ledger Clearing Control` (`00000000-0000-0000-0000-000000000002`).
   - At all times in a quiesced system, the algebraic sum of posted balances on this clearing account across all participants must equal zero:
     $$\sum_{i=1}^{N} \text{ClearingBalance}_i = 0$$
   - During live execution, any non-zero clearing balance must be strictly explainable by active in-flight transfers currently executing between source confirmation and destination confirmation.
3. **Active Hold Cache Verification:**
   - Every participant ledger maintains a cached `held_amount_minor` on `account_balances`.
   - The reconciliation engine independently aggregates `SUM(amount_minor) FROM holds WHERE status = 'ACTIVE'` and asserts an exact match against the cached value for every account.
4. **Stopped-and-Drained Audit Mode:**
   - In stopped-and-drained mode (`drained=True`), the engine asserts zero in-flight transfers, zero active holds, and zero net clearing imbalance.

## Consequences
- **Positive:** Operators receive transparent, mathematically verifiable audit certificates without the danger of false greens during network cuts.
- **Positive:** Any desynchronization between wallet hold caches and authoritative hold rows is detected immediately.
- **Negative:** Running full reconciliation across large historical datasets requires read queries against participant databases; mitigated by dedicated reporter role credentials.
