# Reversals, Refunds, and Chargeback Disputes

## Overview

LedgerGuard V2 implements three compensating financial workflows without erasing or mutating original journal history (`I12`):

1. **Reversal (`execute_reversal`):** Equal and opposite compensating journal entries referencing the original transfer.
2. **Refund (`issue_refund`):** Full or partial integer-paise compensating transfer from recipient back to sender, serialized under row lock on `transfers.refunded_amount_minor` to prevent concurrent over-refunds.
3. **Chargeback / Dispute (`open_dispute`, `transition_dispute`):** Governed 8-state dispute machine (`OPENED`, `EVIDENCE_PENDING`, `UNDER_REVIEW`, `PROVISIONAL_HOLD`, `APPROVED`, `REJECTED`, `COMPENSATION_PENDING`, `RESOLVED`) with immutable `dispute_events` audit trail.
