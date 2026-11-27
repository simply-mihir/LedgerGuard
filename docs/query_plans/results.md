# Query-plan results

Planned against copies of the real tables loaded with 60,000 transfers, 60,000 outbox rows, 100,000 journal lines and 60,000 holds, then ANALYZEd.

| Query | Table | Intended index | Uses it | Seq scan | Seq scan without the index |
|---|---|---|---|---|---|
| transfer_by_id_for_update | transfers | `transfers_pkey` | yes | no | n/a |
| decision_by_transfer | transfer_decisions | `transfer_decisions_pkey` | yes | no | n/a |
| api_idempotency_lookup | api_idempotency | `api_idempotency_pkey` | yes | no | n/a |
| transfer_by_idempotency_key | transfer_idempotency_claims | `transfer_idempotency_claims_pkey` | yes | no | yes |
| open_transfer_recovery_sweep | transfers | `idx_transfers_open_created` | yes | no | yes |
| operator_transfer_list | transfers | `idx_transfers_created_desc` | yes | no | yes |
| workflow_timeline | workflow_events | `uq_workflow_events_transfer_event` | yes | no | n/a |
| outbox_claim | outbox_events | `idx_outbox_pending` | yes | no | yes |
| outbox_claim_for_aggregate | outbox_events | `idx_outbox_pending` | yes | no | n/a |
| statement_first_page | journal_lines | `uq_account_sequence` | yes | no | yes |
| statement_after_cursor | journal_lines | `uq_account_sequence` | yes | no | n/a |
| ledger_idempotency_lookup | idempotency_records | `idempotency_records_pkey` | yes | no | n/a |
| local_transfer_by_id | local_transfers | `local_transfers_pkey` | yes | no | n/a |
| intent_by_transfer | transfer_intents | `transfer_intents_transfer_id_key` | yes | no | n/a |
| hold_by_transfer | holds | `holds_transfer_id_key` | yes | no | n/a |
| inbox_by_command | command_inbox | `command_inbox_pkey` | yes | no | n/a |
| holds_as_of | holds | `idx_holds_account_created` | yes | no | yes |
| journal_headers_from_sequence | journal_headers | `journal_headers_sequence_number_key` | yes | no | n/a |

Redundant indexes found: none
