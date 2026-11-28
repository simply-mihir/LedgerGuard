# Explainable Recovery Diagnostics

## Overview

`src/ledgerguard/recovery_explain/engine.py` provides a strictly deterministic, rule-based diagnostic engine explaining why any transfer is unresolved and what forward-recovery or cancellation action follows.

## Guarantees

- **No LLM in Transaction State:** Transaction state and recovery actions are decided exclusively by deterministic rules over authoritative coordinator and participant records.
- **Evidence Citations:** Every explanation cites real `transfer_id`, `decision`, `source_intent`, `dest_intent`, `source_hold`, and reachability evidence.
- **Contradiction & Unknown Handling:** Contradictory combinations (e.g., `COMMIT` decision with `CANCELLED` state) return `CONTRADICTORY_STATE_DETECTED`; unknown combinations return `UNCLASSIFIED_STATE`.

## Endpoints & Console

- `GET /v1/operator/transfers/{transfer_id}/explain`
- `GET /v1/operator/recovery/queue`
- Operator Console: `/console/recovery` (under **Operate**)
