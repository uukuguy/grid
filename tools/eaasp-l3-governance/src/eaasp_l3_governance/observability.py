"""EAASP L3 governance observability — OpenTelemetry metrics + tracing.

Per v3.15.0 (PLATFORM_OBSERVABILITY_DESIGN.md §3.2 / §3.3). Provides:

1. **Metrics** — OTel ``Counter`` and ``Histogram`` for the 5 key indicator
   families defined in the design:

   - ``l3.requests.total`` (Counter, label: route, method, status)
   - ``l3.request.duration`` (Histogram, label: route, method)
   - ``l3.errors.total`` (Counter, label: route, kind)
   - ``l3.in_flight`` (UpDownCounter, label: route)
   - ``l3.opa.decision.total`` (Counter, label: decision, risk_level, mode)
   - ``l3.opa.decision.duration`` (Histogram, label: decision, mode)
   - ``l3.opa.infra_unavailable.total`` (Counter, label: cause)

2. **Tracing** — OTel ``Tracer`` for L3 process; ``/v1/governance/decision``
   requests are root spans, OPA backend calls are child spans.

3. **Stdout exporter** (optional) — when ``EAASP_OTEL_EXPORTER=stdout``,
   metrics are exported to stdout every 30s. Default (``none``) is a
   no-op provider so tests don't accidentally emit metrics.

Strict-by-default (per ADR-V2-028):

- No env var is required. The default exporter is a no-op so existing
  callers see no behavior change.
- When OTel deps are missing, the module exposes a no-op
  ``get_meter()`` / ``get_tracer()`` that returns dummy objects. This
  is tested by ``test_observability.py`` and means the rest of the
  code can import observability unconditionally.
"""

from __future__ import annotations

import os
import time
from typing import Any

# ─── OTel import (graceful degradation) ─────────────────────────────────────
# If the OTel SDK is not installed, we still want ``observability.py`` to
# import so other modules can call ``get_meter()`` / ``get_tracer()`` and
# get no-op handles. The pure-stdlib stub is checked first to avoid a
# real OTel install being silently masked.

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


_SERVICE_NAME = "eaasp-l3-governance"
_SERVICE_VERSION = "0.1.0"


class _NoopCounter:
    """Stand-in for OTel Counter when OTel is unavailable."""

    def add(self, amount: int, attributes: dict[str, Any] | None = None) -> None:
        del amount, attributes  # unused; present for interface parity
        return None


class _NoopHistogram:
    """Stand-in for OTel Histogram when OTel is unavailable."""

    def record(self, amount: float, attributes: dict[str, Any] | None = None) -> None:
        del amount, attributes  # unused; present for interface parity
        return None


class _NoopUpDownCounter:
    """Stand-in for OTel UpDownCounter when OTel is unavailable."""

    def add(self, amount: int, attributes: dict[str, Any] | None = None) -> None:
        del amount, attributes  # unused; present for interface parity
        return None


class _NoopMeter:
    def create_counter(self, name: str, **kw: Any) -> _NoopCounter:
        del name, kw  # unused; present for interface parity
        return _NoopCounter()

    def create_histogram(self, name: str, **kw: Any) -> _NoopHistogram:
        del name, kw  # unused; present for interface parity
        return _NoopHistogram()

    def create_up_down_counter(self, name: str, **kw: Any) -> _NoopUpDownCounter:
        del name, kw  # unused; present for interface parity
        return _NoopUpDownCounter()


class _NoopTracer:
    def start_as_current_span(self, name: str, **kw: Any):  # type: ignore[no-untyped-def]
        del name, kw  # unused; present for interface parity
        from contextlib import nullcontext

        return nullcontext()


_NOOP_METER = _NoopMeter()
_NOOP_TRACER = _NoopTracer()

# Module-level singletons; set by ``init_observability()`` or stay noop.
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

    Safe to call multiple times — subsequent calls re-initialize the
    global providers (useful for tests).
    """
    global _meter, _tracer, _initialized

    if not _OTEL_AVAILABLE:
        _meter = _NOOP_METER
        _tracer = _NOOP_TRACER
        _initialized = True
        return

    chosen = (exporter if exporter is not None else os.environ.get("EAASP_OTEL_EXPORTER", "none")).lower()

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
        # "none" or any unrecognized value — no-op meter/tracer.
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
    """Return the global meter. Always callable; returns a no-op if not initialized."""
    return _meter


def get_tracer() -> Any:
    """Return the global tracer. Always callable; returns a no-op if not initialized."""
    return _tracer


# ─── L3-specific metric helpers ─────────────────────────────────────────────
# These wrap ``get_meter()`` so call sites read like L3-domain operations
# rather than raw OTel calls. The metric NAMES are part of the platform
# contract per PLATFORM_OBSERVABILITY_DESIGN.md §3.2 — DO NOT rename
# without a coordinated update across L1/L2/L4.

_LABELS_DECISION = ("decision", "risk_level", "mode")
_LABELS_DURATION = ("decision", "mode")


def record_opa_decision(
    *,
    decision: str,
    risk_level: str,
    mode: str,
    duration_seconds: float,
    infra_cause: str | None = None,
) -> None:
    """Record one OPA decision outcome.

    Called from ``OPABackend.evaluate()`` after the response is parsed
    (or after fail-closed synthesis). The decision + risk_level + mode
    labels match the design's required cardinality.
    """
    attrs = dict(zip(_LABELS_DECISION, (decision, risk_level, mode), strict=True))
    get_meter().create_counter(
        "l3.opa.decision.total",
        description="Number of OPA governance decisions, by outcome / risk / mode",
    ).add(1, attributes=attrs)
    get_meter().create_histogram(
        "l3.opa.decision.duration",
        unit="s",
        description="OPA decision wall-clock duration",
    ).record(duration_seconds, attributes=dict(zip(_LABELS_DURATION, (decision, mode), strict=True)))
    if infra_cause is not None:
        get_meter().create_counter(
            "l3.opa.infra_unavailable.total",
            description="Number of OPA fail-closed outcomes, by cause",
        ).add(1, attributes={"cause": infra_cause})


def time_block() -> "_Timer":
    """Return a context-manager-ish timer for ad-hoc duration measurement."""
    return _Timer()


class _Timer:
    """Minimal context manager: ``with time_block() as t: ...; t.record(metric)``."""

    def __init__(self) -> None:
        self._t0: float = 0.0

    def __enter__(self) -> "_Timer":
        self._t0 = time.monotonic()
        return self

    def __exit__(self, *exc: Any) -> None:
        del exc  # unused; context-manager protocol requires this signature
        return None

    def record(self, histogram_name: str, *, attributes: dict[str, Any] | None = None) -> float:
        elapsed = time.monotonic() - self._t0
        get_meter().create_histogram(histogram_name, unit="s").record(elapsed, attributes=attributes)
        return elapsed
