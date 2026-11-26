# End-to-End OpenTelemetry Tracing

## Overview

LedgerGuard V2 instruments the distributed transfer lifecycle across FastAPI HTTP boundaries, idempotency lookup, TCC coordination, outbox enqueue, participant inbox deduplication, forward recovery, and cross-ledger reconciliation (`src/ledgerguard/observability/tracing.py`).

## Configuration

- `LEDGERGUARD_OTEL_EXPORTER`: `none` | `console` | `otlp` | `memory` (default `memory` for local inspection and test verification).
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP HTTP collector endpoint (default `http://localhost:4318/v1/traces`).
- Optional Jaeger viewer via Compose profile:
  ```bash
  docker compose --profile observability up -d
  ```

## Security & Redaction

- `sanitize_attributes()` strips any attribute containing `password`, `secret`, `token`, `totp`, `csrf`, `cookie`, `authorization`, `session`, `email`, or `phone`.
- `amount_bucket()` maps integer paise to coarse buckets rather than emitting raw financial amounts in spans.
- Tracing failures never block financial transaction processing.
