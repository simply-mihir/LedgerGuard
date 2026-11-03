# ADR 0003: Durable Tombstone Semantics and In-Flight Account Closure Protection

## Status
Accepted

## Context
In distributed asynchronous messaging systems, command packets may arrive out of order due to network retries, route changes, or worker interleaving. Specifically, if a transfer aborts (e.g., due to coordinator timeout or destination rejection), a `CANCEL` command might reach the source ledger **before** a delayed `PREPARE` command. Furthermore, customer accounts undergoing closure must not leave unresolved obligations hanging in external systems.

## Decision
1. **Durable Cancellation Tombstones:**
   - When `apply_participant_cancel` is invoked for a transfer that has not yet prepared locally, it inserts a durable tombstone record into `transfer_intents` with status `CANCELLED`.
   - If the delayed `source_prepare` command subsequently arrives, it queries `transfer_intents`. Upon observing the existing `CANCELLED` tombstone, it rejects immediately with status `REJECTED` and creates zero holds.
2. **Account Closure Discipline:**
   - Account closure (`update_account_status(..., 'CLOSED')`) requires that posted balance is exactly 0.
   - In addition, database migration `006_closure_unresolved_obligations.sql` introduces an explicit verification trigger: closure is unconditionally rejected if the account has any `holds` with status `ACTIVE` OR any `transfer_intents` with status `PREPARED`.
3. **Account Freezing Semantics:**
   - Freezing an account prevents new outgoing transfers and new incoming prepares.
   - However, once an incoming or outgoing transfer has already been accepted and prepared, subsequent freezing of the account does not block internal TCC settlement of that committed obligation.

## Consequences
- **Positive:** Network reordering can never cause funds to be permanently orphaned in hold state by a late-arriving prepare.
- **Positive:** Accounts cannot be deleted or closed while in-flight financial obligations are outstanding.
- **Negative:** Tombstone rows must be retained indefinitely to prevent replays across arbitrary time horizons.
