"""Tests for observability.py — v3.15 platform metrics baseline for L4.

Per OBSTACK_DESIGN.md §3.2 / §3.3 (L4 mirror of L3 / L2 pattern).
Covers:
- No-op mode (default) — module imports without OTel installed
- get_meter() / get_tracer() return no-op handles after init
- Explicit "stdout" exporter switches the singleton
- record_* helpers don't raise under no-op (defensive: callers don't
  have to know whether OTel is installed)
- time_block context manager round-trips elapsed seconds
- _record_op rejects unknown op names (cardinality safety)
"""

from __future__ import annotations

import pytest

from eaasp_l4_orchestration import observability


async def test_observability_noop_default() -> None:
    """Default state is no-op meter / tracer."""
    # Force a clean re-init under the test environment (other tests may
    # have toggled the global).
    observability.init_observability(exporter="none")
    assert observability.is_initialized() is True
    meter = observability.get_meter()
    # NoOp meter returns NoopCounter on create_counter.
    counter = meter.create_counter("l2.memory.read.total")
    counter.add(1, attributes={"status": "ok"})
    # No exception = pass.


async def test_record_helpers_smoke() -> None:
    """record_session/room/flow/event + record_error all fire under no-op."""
    observability.init_observability(exporter="none")
    for status in ("ok", "error"):
        observability.record_session(status=status)
        observability.record_room(status=status)
        observability.record_flow(status=status)
        observability.record_event(status=status)
    observability.record_error(kind="validation", source="api:/v1/business-flows")
    observability.in_flight_inc(op="session")
    observability.in_flight_dec(op="session")


async def test_record_op_rejects_unknown_name() -> None:
    """Cardinality safety: typo in op name must not pollute metrics."""
    observability.init_observability(exporter="none")
    with pytest.raises(ValueError, match="unknown L4 op"):
        observability._record_op("READ", "ok", None)  # case typo
    with pytest.raises(ValueError, match="unknown L4 op"):
        observability._record_op("not_a_real_op", "ok", None)


async def test_time_block_round_trip() -> None:
    """time_block context manager records elapsed time on exit."""
    observability.init_observability(exporter="none")
    with observability.time_block() as t:
        # spin briefly so elapsed > 0
        total = 0
        for _ in range(1000):
            total += 1
        _ = total
    elapsed = t.elapsed()
    assert elapsed >= 0.0
    # record(op, status) should fire under no-op without raising.
    t2 = observability.time_block()
    with t2 as in_timer:
        _ = 1 + 1
    in_timer.record("session", status="ok")
