"""EAASP L2 memory engine observability — OpenTelemetry metrics + tracing.

Per v3.15.0 (OBSTACK_DESIGN.md §3.3). Self-contained mirror of the
``l3.opa.decision.*`` pattern adapted for L2 memory operations.

Provides:

1. **Metrics** — OTel ``Counter`` / ``Histogram`` / ``UpDownCounter``
   for the 5 key L2 indicator families (one per primary tool):

   - ``l2.memory.read.total``           (Counter, label: status)
   - ``l2.memory.read.duration``        (Histogram, label: status)
   - ``l2.memory.write.total``          (Counter, label: status)
   - ``l2.memory.write.duration``       (Histogram, label: status)
   - ``l2.memory.search.total``         (Counter, label: status)
   - ``l2.memory.search.duration``      (Histogram, label: status)
   - ``l2.memory.delete.total``         (Counter, label: status)
   - ``l2.memory.anchor.total``         (Counter, label: status)
   - ``l2.memory.errors.total``         (Counter, label: kind, source)
   - ``l2.memory.in_flight``            (UpDownCounter, label: op)

2. **Tracing** — OTel ``Tracer`` for L2 process; ``/v1/memory/*`` and
   the 5 L2 MCP tools (``read``/``write_file``/``search``/``delete``/
   ``anchor``) are root spans.

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

# v3.16 (V316-L2L3L4-OBS-01) — module-level strong references to the
# providers. Without these the local vars go out of scope at the end of
# init_observability() and the periodic reader is GC'd, so a process
# exports at most one batch and then nothing. Same defect class as
# grid-runtime 6g's `drop(provider)` and same fix shape.
_METER_PROVIDER: Any = None
_TRACER_PROVIDER: Any = None

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


_SERVICE_NAME = "eaasp-l2-memory-engine"
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
        # v3.16 (V316-L2L3L4-OBS-01): hold a strong reference so the
        # periodic reader outlives this function. Without this, the
        # process exports one batch and the pipeline dies — the same
        # shape as L1 6g's `drop(provider)`.
        global _METER_PROVIDER
        _METER_PROVIDER = meter_provider
        _otel_metrics.set_meter_provider(meter_provider)
        _meter = meter_provider.get_meter(_SERVICE_NAME, _SERVICE_VERSION)
    else:
        _meter = _NOOP_METER

    if tracer_provider is not None:
        global _TRACER_PROVIDER
        _TRACER_PROVIDER = tracer_provider
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


# ─── L2-specific metric helpers ─────────────────────────────────────────────
# Names are part of the platform contract per OBSTACK_DESIGN.md §3.3.
# Mirror L3's ``l3.opa.*`` naming: ``<layer>.<entity>.<measurement>``.
# DO NOT rename without a coordinated update across L0–L5.

_OPS = ("read", "write", "search", "delete", "anchor")


def _record_op(op: str, status: str, duration_seconds: float | None) -> None:
    """Shared helper for the 5 L2 tool ops.

    ``op`` ∈ {"read","write","search","delete","anchor"}.
    ``status`` ∈ {"ok","error"} — kept low-cardinality for OTel cost.
    ``duration_seconds`` is optional (some entry points don't measure).
    """
    if op not in _OPS:
        # Defensive: refuse unknown ops so a typo doesn't pollute metrics.
        raise ValueError(
            f"unknown L2 op {op!r}; expected one of {_OPS}"
        )
    attrs = {"status": status}
    meter = get_meter()
    meter.create_counter(
        f"l2.memory.{op}.total",
        description=f"Number of L2 memory {op} operations, by status",
    ).add(1, attributes=attrs)
    if duration_seconds is not None:
        meter.create_histogram(
            f"l2.memory.{op}.duration",
            unit="s",
            description=f"L2 memory {op} wall-clock duration",
        ).record(duration_seconds, attributes=attrs)


def record_read(*, status: str, duration_seconds: float | None = None) -> None:
    """L2 memory read operation outcome."""
    _record_op("read", status, duration_seconds)


def record_write(*, status: str, duration_seconds: float | None = None) -> None:
    """L2 memory write operation outcome."""
    _record_op("write", status, duration_seconds)


def record_search(*, status: str, duration_seconds: float | None = None) -> None:
    """L2 memory search operation outcome."""
    _record_op("search", status, duration_seconds)


def record_delete(*, status: str, duration_seconds: float | None = None) -> None:
    """L2 memory delete operation outcome."""
    _record_op("delete", status, duration_seconds)


def record_anchor(*, status: str, duration_seconds: float | None = None) -> None:
    """L2 memory anchor operation outcome (write_file with evidence_refs)."""
    _record_op("anchor", status, duration_seconds)


def record_error(*, kind: str, source: str) -> None:
    """Record a generic L2 error (per-kind / per-source cardinality).

    ``kind`` ∈ {"validation","not_found","permission","backend","io"}.
    ``source`` identifies the call site (e.g. ``"mcp:write_file"``).
    """
    get_meter().create_counter(
        "l2.memory.errors.total",
        description="Number of L2 memory errors, by kind/source",
    ).add(1, attributes={"kind": kind, "source": source})


def in_flight_inc(*, op: str) -> None:
    get_meter().create_up_down_counter(
        "l2.memory.in_flight",
        description="Number of L2 memory operations currently in flight",
    ).add(1, attributes={"op": op})


def in_flight_dec(*, op: str) -> None:
    get_meter().create_up_down_counter(
        "l2.memory.in_flight",
        description="Number of L2 memory operations currently in flight",
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
