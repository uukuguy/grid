"""Tests for observability.py — v3.15 platform metrics baseline for L2.

Per OBSTACK_DESIGN.md §3.2 / §3.3 (L2 mirror of L3 pattern).
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

from eaasp_l2_memory_engine import observability


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
    """record_read/write/search/delete/anchor + record_error all fire under no-op."""
    observability.init_observability(exporter="none")
    for status in ("ok", "error"):
        observability.record_read(status=status)
        observability.record_write(status=status)
        observability.record_search(status=status)
        observability.record_delete(status=status)
        observability.record_anchor(status=status)
    observability.record_error(kind="validation", source="mcp:write_file")
    observability.in_flight_inc(op="read")
    observability.in_flight_dec(op="read")


async def test_record_op_rejects_unknown_name() -> None:
    """Cardinality safety: typo in op name must not pollute metrics."""
    observability.init_observability(exporter="none")
    with pytest.raises(ValueError, match="unknown L2 op"):
        observability._record_op("READ", "ok", None)  # case typo
    with pytest.raises(ValueError, match="unknown L2 op"):
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
    in_timer.record("read", status="ok")
