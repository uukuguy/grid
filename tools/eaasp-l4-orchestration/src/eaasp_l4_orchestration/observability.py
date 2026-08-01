"""EAASP L4 orchestration observability — OpenTelemetry metrics + tracing.

Per v3.15.0 (OBSTACK_DESIGN.md §3.3). Self-contained mirror of the
``l3.opa.decision.*`` pattern adapted for L4 orchestration (sessions,
event rooms, business-flow aggregation).

Provides:

1. **Metrics** — OTel ``Counter`` / ``Histogram`` / ``UpDownCounter``
   for the 4 key L4 indicator families (one per primary surface):

   - ``l4.session.{total,duration}``         (session create/close)
   - ``l4.room.{total,duration}``            (event room publish/subscribe)
   - ``l4.flow.{total,duration}``            (business-flow timeline/eval)
   - ``l4.event.{total,duration}``           (event room fan-out)
   - ``l4.errors.total``                     (Counter, label: kind, source)
   - ``l4.in_flight``                        (UpDownCounter, label: op)

2. **Tracing** — OTel ``Tracer`` for L4 process; ``/v1/sessions/*``
   and ``/v1/rooms/*`` and ``/v1/business-flows/*`` are root spans.

3. **Stdout exporter** (optional) — when ``EAASP_OTEL_EXPORTER=stdout``,
   metrics are exported to stdout every 30s. Default (``none``) is a
   no-op provider so tests don't accidentally emit metrics.

Strict-by-default (per ADR-V2-028):

- No env var is required. The default exporter is a no-op so existing
  callers see no behavior change.
- When OTel deps are missing, the module exposes no-op handles for
  ``get_meter()`` / ``get_tracer()`` so other modules can import
  observability unconditionally.

Note (OBSTACK §4.4 boundary discipline): this module is intentionally
self-contained and does NOT import from eaasp-l3-governance
(ADR-V2-029 dual-axis boundary). The pattern overlap is by design,
not by dependency.
"""

from __future__ import annotations

import os
import time
from typing import Any

# ─── OTel import (graceful degradation) ─────────────────────────────────────

_OTEL_AVAILABLE = False
_otel_metrics: Any = None
_otel_trace: Any = None
_Resource: Any = None
_PeriodicExportingMetricReader: Any = None
_ConsoleMetricExporter: Any = None
_SdkMeterProvider: Any = None
_SdkTracerProvider: Any = None
_BatchSpanProcessor: Any = None
_ConsoleSpanExporter: Any = None

try:
    from opentelemetry import metrics as _otel_metrics
    from opentelemetry import trace as _otel_trace
    from opentelemetry.sdk.metrics import MeterProvider as _SdkMeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter as _ConsoleMetricExporter,
    )
    from opentelemetry.sdk.metrics.export import (
        PeriodicExportingMetricReader as _PeriodicExportingMetricReader,
    )
    from opentelemetry.sdk.resources import Resource as _Resource
    from opentelemetry.sdk.trace import TracerProvider as _SdkTracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor as _BatchSpanProcessor,
    )
    from opentelemetry.sdk.trace.export import (
        ConsoleSpanExporter as _ConsoleSpanExporter,
    )

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover — exercised by OTel-missing test
    pass


_SERVICE_NAME = "eaasp-l4-orchestration"
_SERVICE_VERSION = "0.1.0"


class _NoopCounter:
    def add(self, amount: int, attributes: dict[str, Any] | None = None) -> None:
        del amount, attributes
        return None


class _NoopHistogram:
    def record(self, amount: float, attributes: dict[str, Any] | None = None) -> None:
        del amount, attributes
        return None


class _NoopUpDownCounter:
    def add(self, amount: int, attributes: dict[str, Any] | None = None) -> None:
        del amount, attributes
        return None


class _NoopMeter:
    def create_counter(self, name: str, **kw: Any) -> _NoopCounter:
        del name, kw
        return _NoopCounter()

    def create_histogram(self, name: str, **kw: Any) -> _NoopHistogram:
        del name, kw
        return _NoopHistogram()

    def create_up_down_counter(self, name: str, **kw: Any) -> _NoopUpDownCounter:
        del name, kw
        return _NoopUpDownCounter()


class _NoopTracer:
    def start_as_current_span(self, name: str, **kw: Any):
        del name, kw
        from contextlib import nullcontext

        return nullcontext()


_NOOP_METER = _NoopMeter()
_NOOP_TRACER = _NoopTracer()

_meter: Any = _NOOP_METER
_tracer: Any = _NOOP_TRACER
_initialized: bool = False


def is_initialized() -> bool:
    return _initialized


def init_observability(*, exporter: str | None = None) -> None:
    """Initialize the OTel MeterProvider + TracerProvider.

    ``exporter``:
    - ``None`` / unset → use ``EAASP_OTEL_EXPORTER`` env var
    - ``"none"`` → keep no-op (default; minimal overhead)
    - ``"stdout"`` → install ConsoleMetricExporter + ConsoleSpanExporter
    - ``"otlp"`` → OTLP exporter (deferred; requires extra dep)
    """
    global _meter, _tracer, _initialized

    if not _OTEL_AVAILABLE:
        _meter = _NOOP_METER
        _tracer = _NOOP_TRACER
        _initialized = True
        return

    chosen = (
        exporter
        if exporter is not None
        else os.environ.get("EAASP_OTEL_EXPORTER", "none")
    ).lower()

    resource = _Resource.create(
        {
            "service.name": _SERVICE_NAME,
            "service.version": _SERVICE_VERSION,
        }
    )

    if chosen == "stdout":
        reader = _PeriodicExportingMetricReader(
            _ConsoleMetricExporter(),
            export_interval_millis=30_000,
        )
        meter_provider = _SdkMeterProvider(resource=resource, metric_readers=[reader])
        tracer_provider = _SdkTracerProvider(resource=resource)
        tracer_provider.add_span_processor(
            _BatchSpanProcessor(_ConsoleSpanExporter())
        )
    else:
        # "none" or any unrecognized value — no-op.
        meter_provider = None
        tracer_provider = None

    if meter_provider is not None:
        _otel_metrics.set_meter_provider(meter_provider)
        _meter = meter_provider.get_meter(_SERVICE_NAME, _SERVICE_VERSION)
    else:
        _meter = _NOOP_METER

    if tracer_provider is not None:
        _otel_trace.set_tracer_provider(tracer_provider)
        _tracer = tracer_provider.get_tracer(_SERVICE_NAME, _SERVICE_VERSION)
    else:
        _tracer = _NOOP_TRACER

    _initialized = True


def get_meter() -> Any:
    """Return the global meter. Returns a no-op if not initialized."""
    return _meter


def get_tracer() -> Any:
    """Return the global tracer. Returns a no-op if not initialized."""
    return _tracer


# ─── L4-specific metric helpers ─────────────────────────────────────────────
# Names are part of the platform contract per OBSTACK_DESIGN.md §3.3.
# Mirror L3's ``l3.opa.*`` naming: ``<layer>.<entity>.<measurement>``.
# DO NOT rename without a coordinated update across L0–L5.

_OPS = ("session", "room", "flow", "event")


def _record_op(op: str, status: str, duration_seconds: float | None) -> None:
    """Shared helper for the 4 L4 surface ops.

    ``op`` ∈ {"session","room","flow","event"}.
    ``status`` ∈ {"ok","error"} — kept low-cardinality for OTel cost.
    ``duration_seconds`` is optional (some entry points don't measure).
    """
    if op not in _OPS:
        # Defensive: refuse unknown ops so a typo doesn't pollute metrics.
        raise ValueError(
            f"unknown L4 op {op!r}; expected one of {_OPS}"
        )
    attrs = {"status": status}
    meter = get_meter()
    meter.create_counter(
        f"l4.{op}.total",
        description=f"Number of L4 {op} operations, by status",
    ).add(1, attributes=attrs)
    if duration_seconds is not None:
        meter.create_histogram(
            f"l4.{op}.duration",
            unit="s",
            description=f"L4 {op} wall-clock duration",
        ).record(duration_seconds, attributes=attrs)


def record_session(*, status: str, duration_seconds: float | None = None) -> None:
    """L4 session lifecycle operation outcome (create/close)."""
    _record_op("session", status, duration_seconds)


def record_room(*, status: str, duration_seconds: float | None = None) -> None:
    """L4 event room publish/subscribe operation outcome."""
    _record_op("room", status, duration_seconds)


def record_flow(*, status: str, duration_seconds: float | None = None) -> None:
    """L4 business-flow aggregator outcome (timeline / evaluate)."""
    _record_op("flow", status, duration_seconds)


def record_event(*, status: str, duration_seconds: float | None = None) -> None:
    """L4 event-room fan-out dispatch outcome."""
    _record_op("event", status, duration_seconds)


def record_error(*, kind: str, source: str) -> None:
    """Record a generic L4 error (per-kind / per-source cardinality).

    ``kind`` ∈ {"validation","not_found","permission","backend","io","sse"}.
    ``source`` identifies the call site (e.g. ``"api:/v1/business-flows"``).
    """
    get_meter().create_counter(
        "l4.errors.total",
        description="Number of L4 errors, by kind/source",
    ).add(1, attributes={"kind": kind, "source": source})


def in_flight_inc(*, op: str) -> None:
    get_meter().create_up_down_counter(
        "l4.in_flight",
        description="Number of L4 operations currently in flight",
    ).add(1, attributes={"op": op})


def in_flight_dec(*, op: str) -> None:
    get_meter().create_up_down_counter(
        "l4.in_flight",
        description="Number of L4 operations currently in flight",
    ).add(-1, attributes={"op": op})


def time_block() -> "_Timer":
    return _Timer()


class _Timer:
    """Minimal context manager: ``with time_block() as t: ...; t.record(op, status)``."""

    def __init__(self) -> None:
        self._t0: float = 0.0

    def __enter__(self) -> "_Timer":
        self._t0 = time.monotonic()
        return self

    def __exit__(self, *exc: Any) -> None:
        del exc
        return None

    def elapsed(self) -> float:
        return time.monotonic() - self._t0

    def record(self, op: str, *, status: str = "ok") -> float:
        sec = self.elapsed()
        _record_op(op, status, sec)
        return sec
