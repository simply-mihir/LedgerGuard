"""OpenTelemetry instrumentation, W3C trace propagation, and sensitive-data redaction."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from ledgerguard.config import settings

_SENSITIVE_KEYWORDS = (
    "password",
    "secret",
    "token",
    "totp",
    "csrf",
    "cookie",
    "authorization",
    "session",
    "email",
    "phone",
)

_PROPAGATOR = TraceContextTextMapPropagator()
_MEMORY_EXPORTER: InMemorySpanExporter | None = None
_PROVIDER_INITIALIZED = False
_PROVIDER_LOCK = threading.Lock()


def amount_bucket(amount_minor: int) -> str:
    """Map integer paise to a coarse bucket to avoid attaching raw sensitive financial amounts."""
    rupees = amount_minor // 100
    if rupees < 100:
        return "<100_INR"
    if rupees < 1_000:
        return "100_to_999_INR"
    if rupees < 10_000:
        return "1k_to_9999_INR"
    if rupees < 100_000:
        return "10k_to_99999_INR"
    return ">=100k_INR"


def sanitize_attributes(attrs: dict[str, Any] | None) -> dict[str, str | int | float | bool]:
    """Filter out sensitive keys and coerce values to OTel-safe primitives."""
    if not attrs:
        return {}
    clean: dict[str, str | int | float | bool] = {}
    for k, v in attrs.items():
        lk = k.lower()
        if any(bad in lk for bad in _SENSITIVE_KEYWORDS):
            continue
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


def configure_tracing(mode: str | None = None) -> InMemorySpanExporter | None:
    """Configure global TracerProvider according to mode (none, console, otlp, memory)."""
    global _MEMORY_EXPORTER, _PROVIDER_INITIALIZED
    selected = mode or settings.otel_exporter

    if selected == "none":
        return None

    with _PROVIDER_LOCK:
        if _PROVIDER_INITIALIZED:
            return _MEMORY_EXPORTER

        resource = Resource.create({"service.name": "ledgerguard", "deployment.environment": settings.env})
        provider = TracerProvider(resource=resource)

        exporter: SpanExporter | None = None
        if selected == "memory":
            _MEMORY_EXPORTER = InMemorySpanExporter()
            exporter = _MEMORY_EXPORTER
        elif selected == "console":
            exporter = ConsoleSpanExporter()
        elif selected == "otlp":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)

        if exporter is not None:
            provider.add_span_processor(SimpleSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        _PROVIDER_INITIALIZED = True
        return _MEMORY_EXPORTER


def get_in_memory_exporter() -> InMemorySpanExporter | None:
    """Return the active in-memory exporter (initializing memory mode if configured)."""
    global _PROVIDER_INITIALIZED
    if not _PROVIDER_INITIALIZED and settings.otel_exporter != "none":
        configure_tracing(settings.otel_exporter)
    return _MEMORY_EXPORTER


def _get_tracer() -> trace.Tracer:
    global _PROVIDER_INITIALIZED
    if not _PROVIDER_INITIALIZED and settings.otel_exporter != "none":
        configure_tracing(settings.otel_exporter)
    return trace.get_tracer("ledgerguard")


def inject_trace_carrier(carrier: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inject W3C traceparent into a dict carrier for async/DB propagation."""
    target: dict[str, Any] = dict(carrier or {})
    try:
        str_carrier: dict[str, str] = {}
        _PROPAGATOR.inject(str_carrier)
        if "traceparent" in str_carrier:
            target["traceparent"] = str_carrier["traceparent"]
        if "tracestate" in str_carrier:
            target["tracestate"] = str_carrier["tracestate"]
    except Exception:
        pass
    return target


def extract_trace_context(carrier: dict[str, Any] | None) -> Context | None:
    """Extract W3C trace context from a dict or HTTP headers."""
    if not carrier:
        return None
    try:
        str_carrier = {str(k).lower(): str(v) for k, v in carrier.items() if v is not None}
        if "traceparent" not in str_carrier:
            return None
        return _PROPAGATOR.extract(str_carrier)
    except Exception:
        return None


@contextmanager
def safe_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
    parent_context: Context | None = None,
) -> Iterator[trace.Span | None]:
    """Start an OpenTelemetry span safely; tracing errors never block business logic."""
    try:
        tracer = _get_tracer()
        clean_attrs = sanitize_attributes(attributes)
        with tracer.start_as_current_span(name, context=parent_context, attributes=clean_attrs) as span:
            try:
                yield span
            except Exception as exc:
                try:
                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    span.set_attribute("error.type", type(exc).__name__)
                except Exception:
                    pass
                raise
    except Exception as exc:
        # If the exception came from business logic inside yield, re-raise it;
        # only swallow tracing setup failures.
        if not isinstance(exc, RuntimeError) or "opentelemetry" not in str(exc).lower():
            raise


def _span_to_dict(span: ReadableSpan) -> dict[str, Any]:
    ctx = span.get_span_context()
    parent_id = f"{span.parent.span_id:016x}" if span.parent else None
    start_ns = span.start_time or 0
    end_ns = span.end_time or start_ns
    return {
        "trace_id": f"{ctx.trace_id:032x}" if ctx else "",
        "span_id": f"{ctx.span_id:016x}" if ctx else "",
        "parent_span_id": parent_id,
        "name": span.name,
        "duration_ms": round((end_ns - start_ns) / 1_000_000.0, 3),
        "start_time_ns": start_ns,
        "end_time_ns": end_ns,
        "status": span.status.status_code.name if span.status else "UNSET",
        "attributes": dict(span.attributes or {}),
    }


def list_recent_traces(limit: int = 30) -> list[dict[str, Any]]:
    """Summarize recent traces from the in-memory exporter."""
    exp = get_in_memory_exporter()
    if exp is None:
        return []
    spans = list(exp.get_finished_spans())
    by_trace: dict[str, list[ReadableSpan]] = {}
    for s in spans:
        ctx = s.get_span_context()
        if ctx:
            tid = f"{ctx.trace_id:032x}"
            by_trace.setdefault(tid, []).append(s)

    summaries: list[dict[str, Any]] = []
    for tid, group in list(by_trace.items())[-limit:]:
        min_start = min((s.start_time or 0) for s in group)
        max_end = max((s.end_time or 0) for s in group)
        transfer_id = None
        has_error = False
        has_recovery = False
        for s in group:
            attrs = s.attributes or {}
            if not transfer_id and "transfer.id" in attrs:
                transfer_id = str(attrs["transfer.id"])
            if s.status and s.status.status_code == StatusCode.ERROR:
                has_error = True
            if attrs.get("recovery.flag") is True or "recovery" in s.name:
                has_recovery = True
        summaries.append(
            {
                "trace_id": tid,
                "transfer_id": transfer_id,
                "span_count": len(group),
                "total_duration_ms": round((max_end - min_start) / 1_000_000.0, 3),
                "has_error": has_error,
                "has_recovery": has_recovery,
                "root_name": group[0].name,
            }
        )
    return list(reversed(summaries))


def get_trace_waterfall_for_transfer(transfer_id: str) -> dict[str, Any]:
    """Return span waterfall and derived latency breakdown for a transfer ID."""
    exp = get_in_memory_exporter()
    if exp is None:
        return {"transfer_id": transfer_id, "spans": [], "metrics": {}}
    matching_trace_ids: set[str] = set()
    all_spans = list(exp.get_finished_spans())
    for s in all_spans:
        attrs = s.attributes or {}
        if str(attrs.get("transfer.id", "")) == transfer_id:
            ctx = s.get_span_context()
            if ctx:
                matching_trace_ids.add(f"{ctx.trace_id:032x}")

    spans = []
    for s in all_spans:
        s_ctx = s.get_span_context()
        if s_ctx is not None and f"{s_ctx.trace_id:032x}" in matching_trace_ids:
            spans.append(_span_to_dict(s))
    spans.sort(key=lambda x: x["start_time_ns"])

    participant_ms = sum(
        s["duration_ms"] for s in spans if s["name"].startswith("tcc.") or s["name"].startswith("participant.")
    )
    recovery_spans = [s for s in spans if "recovery" in s["name"] or s["attributes"].get("recovery.flag") is True]
    error_spans = [s for s in spans if s["status"] == "ERROR"]
    total_ms = 0.0
    if spans:
        total_ms = round((max(s["end_time_ns"] for s in spans) - min(s["start_time_ns"] for s in spans)) / 1_000_000.0, 3)

    return {
        "transfer_id": transfer_id,
        "trace_ids": sorted(matching_trace_ids),
        "spans": spans,
        "metrics": {
            "total_settlement_ms": total_ms,
            "participant_latency_ms": round(participant_ms, 3),
            "recovery_span_count": len(recovery_spans),
            "error_span_count": len(error_spans),
            "retry_count": max(0, len(recovery_spans)),
        },
    }
