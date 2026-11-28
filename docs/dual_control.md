# Four-Eyes Dual Control & RBAC

## Roles

- `VIEWER`: Read-only console observation; prohibited from state-changing actions.
- `AUDITOR`: Read-only audit & reconciliation (`ledgerguard_reporter` isolation preserved); prohibited from state-changing actions.
- `OPERATOR`: Initiates operational workflows and sensitive approval requests.
- `APPROVER`: Approves/rejects pending requests (requires MFA + recent authentication).
- `ADMIN`: Administrative privileges (requires MFA + recent authentication; cannot self-approve).

## Guarantees

- **No Self-Approval:** `initiator_id != approver_id` is enforced in backend service logic.
- **Immutable Payload Hashing:** Payloads are SHA-256 hashed at submission; any tampering invalidates approval.
- **Idempotent Execution:** `approval_requests` rows are locked `FOR UPDATE` during execution; replayed executions return `duplicate_ignored=True`.
- **Immutable Audit Trail:** `approval_events` rejects `UPDATE` and `DELETE` via PostgreSQL triggers.
