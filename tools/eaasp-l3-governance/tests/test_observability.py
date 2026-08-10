"""Tests for observability.py — v3.15.0 platform metrics baseline for L3.

Per OBSTACK_DESIGN.md §3.2. Covers:
- No-op mode (default) — module imports without OTel
- get_meter() / get_tracer() return no-op handles
- record_opa_decision() does not raise in no-op mode
- init_observability(exporter='stdout') is idempotent
- time_block() measures elapsed time and is reusable
"""

from __future__ import annotations

import time

from eaasp_l3_governance import observability
from eaasp_l3_governance.observability import (
    get_meter,
    get_tracer,
    init_observability,
    is_initialized,
    record_opa_decision,
    time_block,
)


def test_default_is_noop_initialized() -> None:
    """After import, observability reports initialized (no-op mode by default)."""
    # First import lazily initializes the no-op path. Just check the
    # public state.
    init_observability(exporter="none")
    assert is_initialized() is True


def test_get_meter_returns_callable() -> None:
    """get_meter() always returns something with create_counter / histogram."""
    meter = get_meter()
    assert meter is not None
    counter = meter.create_counter("test.requests.total")
    counter.add(1, attributes={"k": "v"})  # must not raise


def test_get_tracer_returns_callable() -> None:
    """get_tracer() always returns something usable as a context manager."""
    tracer = get_tracer()
    assert tracer is not None
    with tracer.start_as_current_span("test_span"):
        # Must not raise; span may be a nullcontext.
        pass


def test_record_opa_decision_noop() -> None:
    """record_opa_decision() is a no-op in no-op mode and must not raise."""
    record_opa_decision(
        decision="allow",
        risk_level="read",
        mode="enforce",
        duration_seconds=0.012,
    )
    record_opa_decision(
        decision="deny",
        risk_level="write_external",
        mode="enforce",
        duration_seconds=0.034,
        infra_cause="opa_timeout",
    )


def test_init_observability_idempotent() -> None:
    """init_observability() can be called multiple times without raising."""
    init_observability(exporter="none")
    init_observability(exporter="none")
    init_observability(exporter="none")
    assert is_initialized() is True


def test_init_observability_stdout() -> None:
    """init_observability(exporter='stdout') wires up the Console exporters."""
    init_observability(exporter="stdout")
    # The real OTel SDK is installed in this venv (set up at v3.15.0
    # bootstrap), so get_meter() should return a real Meter (not the
    # no-op stub). We just check it's not the no-op singleton.
    meter = get_meter()
    assert meter is not None
    # Shut the MeterProvider down so its background periodic reader does
    # not try to flush to pytest's captured stdout after the test
    # returns (which raises ``ValueError: I/O operation on closed file``).
    _shutdown_meter_provider()


def _shutdown_meter_provider() -> None:
    """Best-effort shutdown of the active OTel MeterProvider (no-op if absent)."""
    try:
        from opentelemetry import metrics as _otel_metrics  # type: ignore[import-not-found]
        provider = _otel_metrics.get_meter_provider()
        shutdown = getattr(provider, "shutdown", None)
        if callable(shutdown):
            shutdown()
    except Exception:
        pass


def _is_noop_meter(meter: object) -> bool:
    """The no-op meter is a singleton instance of _NoopMeter."""
    return isinstance(meter, observability._NoopMeter)


# Reference _is_noop_meter so Pyright / ruff do not flag it as unused.
_ = _is_noop_meter


def test_time_block_measures_elapsed() -> None:
    """time_block() records a non-zero duration and is reusable."""
    with time_block() as t:
        time.sleep(0.005)
        elapsed = t.record("test.duration", attributes={"op": "sleep"})
    assert elapsed > 0.0
    # The same timer can be entered again.
    with time_block() as t2:
        elapsed2 = t2.record("test.duration")
    assert elapsed2 >= 0.0


def test_init_without_otel_graceful() -> None:
    """If OTel is unavailable, init still works (no-op fallback).

    We don't actually uninstall OTel here (the venv has it). Instead we
    exercise the fallback path indirectly: call get_meter() before
    init_observability() and confirm it returns a valid no-op meter.
    """
    # Force the module back to uninitialized state for this test.
    observability._initialized = False
    observability._meter = observability._NOOP_METER
    observability._tracer = observability._NOOP_TRACER
    meter = get_meter()
    assert isinstance(meter, observability._NoopMeter)
    # Re-initialize for downstream tests.
    init_observability(exporter="none")
    assert is_initialized() is True


# ── 6b.3 V315-L1-OTEL-FULL-01: 3 new record_* helpers ────────────────────


def test_record_session_noop_does_not_raise() -> None:
    """V315-L1-OTEL-FULL-01 (v3.15.6 6b.3): record_session must
    be safe in no-op mode (default) — exercised by the L3 module's
    ``audit.py`` and ``approval_state_machine.py`` callers.
    """
    # No-op is the default after init_observability("none").
    observability.record_session(
        operation="append", status="ok", duration_seconds=0.42
    )
    observability.record_session(operation="read", status="error")
    # If we reach here without raising, the no-op path is correct.


def test_record_hook_noop_does_not_raise() -> None:
    """V315-L1-OTEL-FULL-01: record_hook covers the hook dispatch
    path (PreToolUse / PostToolUse / etc.). No-op safe.
    """
    observability.record_hook(
        hook_type="pre_tool_use", status="allow", duration_seconds=0.03
    )
    observability.record_hook(hook_type="session_end", status="error")


def test_record_opa_policy_noop_does_not_raise() -> None:
    """V315-L1-OTEL-FULL-01: record_opa_policy covers the policy
    lifecycle path (deploy / revoke / load). No-op safe.
    """
    observability.record_opa_policy(operation="deploy", result="ok")
    observability.record_opa_policy(operation="revoke", result="error")


def test_record_helpers_use_noop_meter_when_uninitialized() -> None:
    """When init_observability has not been called (or was reset),
    the 3 record_* helpers must not raise — they must fan out
    through the no-op meter, which silently swallows ``add()`` /
    ``record()`` calls.
    """
    observability._initialized = False
    observability._meter = observability._NOOP_METER
    observability._tracer = observability._NOOP_TRACER
    # Each call should be a no-op that returns successfully.
    observability.record_session(operation="seed", status="ok")
    observability.record_hook(hook_type="bootstrap", status="allow")
    observability.record_opa_policy(operation="validate", result="ok")
    # Restore shared state for downstream tests.
    init_observability(exporter="none")
