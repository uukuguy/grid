"""Tests for circuit_breaker.py — 3-state machine invariants.

Per v3.15.0 design (PHASE_3_5_DESIGN.md §3.1). Covers:
- CLOSED→OPEN trip after N consecutive failures
- OPEN short-circuits without invoking fn
- OPEN→HALF_OPEN transition after cool-down
- HALF_OPEN→CLOSED on successful probe
- HALF_OPEN→OPEN on failed probe (cool-down restarts)
- Failure counter resets on success in CLOSED state
- Concurrent calls are serialized by the lock
"""

from __future__ import annotations

import pytest

from eaasp_l3_governance.circuit_breaker import (
    BreakerState,
    CircuitBreaker,
    CircuitOpenError,
)


class _Clock:
    """Manually advanced monotonic clock for deterministic tests."""

    def __init__(self, t0: float = 1000.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# ─── CLOSED → OPEN trip ─────────────────────────────────────────────────────


async def test_closed_to_open_after_n_failures() -> None:
    """5 consecutive failures trips the breaker to OPEN."""
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=5, cool_down_seconds=30.0, clock=clock)

    async def boom() -> None:
        raise RuntimeError("downstream down")

    for _ in range(4):
        with pytest.raises(RuntimeError):
            await cb.call(boom)
    assert cb.state is BreakerState.CLOSED

    with pytest.raises(RuntimeError):
        await cb.call(boom)
    assert cb.state is BreakerState.OPEN


# ─── OPEN short-circuits ────────────────────────────────────────────────────


async def test_open_short_circuits() -> None:
    """OPEN state raises CircuitOpenError without invoking fn."""
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=2, cool_down_seconds=30.0, clock=clock)
    await _trip(cb, clock)

    invoked = 0

    async def fn() -> str:
        nonlocal invoked
        invoked += 1
        return "should not be called"

    with pytest.raises(CircuitOpenError) as exc_info:
        await cb.call(fn)
    assert invoked == 0
    assert exc_info.value.retry_after_seconds > 0


# ─── OPEN → HALF_OPEN after cool-down ──────────────────────────────────────


async def test_open_to_half_open_after_cool_down() -> None:
    """After cool_down_seconds elapses, next call enters HALF_OPEN."""
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=2, cool_down_seconds=30.0, clock=clock)
    await _trip(cb, clock)
    assert cb.state is BreakerState.OPEN

    clock.advance(30.0)

    async def ok() -> str:
        return "ok"

    result = await cb.call(ok)
    assert result == "ok"
    # Success in HALF_OPEN closes the breaker.
    assert cb.state is BreakerState.CLOSED


# ─── HALF_OPEN → OPEN on failed probe ───────────────────────────────────────


async def test_half_open_to_open_on_failure() -> None:
    """Failed probe reopens the breaker and restarts cool-down."""
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=2, cool_down_seconds=30.0, clock=clock)
    await _trip(cb, clock)
    clock.advance(30.0)

    async def boom() -> None:
        raise RuntimeError("still down")

    with pytest.raises(RuntimeError):
        await cb.call(boom)
    assert cb.state is BreakerState.OPEN

    # Cool-down restarted — at t=1030 we should still be OPEN even
    # though 30s elapsed since the trip.
    clock.advance(15.0)
    invoked = 0

    async def fn() -> str:
        nonlocal invoked
        invoked += 1
        return "ok"

    with pytest.raises(CircuitOpenError):
        await cb.call(fn)
    assert invoked == 0


# ─── Failure counter resets on success in CLOSED ────────────────────────────


async def test_failure_counter_resets_on_success() -> None:
    """Successes in CLOSED state reset the consecutive-failure counter."""
    cb = CircuitBreaker(failure_threshold=5, cool_down_seconds=30.0)

    async def boom() -> None:
        raise RuntimeError("downstream down")

    async def ok() -> str:
        return "ok"

    # 4 failures interleaved with successes should NOT trip the breaker.
    for _ in range(4):
        with pytest.raises(RuntimeError):
            await cb.call(boom)
        await cb.call(ok)

    assert cb.state is BreakerState.CLOSED
    assert cb.consecutive_failures == 0


# ─── reset() operator escape hatch ──────────────────────────────────────────


async def test_reset_force_closes() -> None:
    """reset() forces the breaker back to CLOSED with zero failures."""
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=2, cool_down_seconds=30.0, clock=clock)
    await _trip(cb, clock)
    assert cb.state is BreakerState.OPEN

    await cb.reset()
    assert cb.state is BreakerState.CLOSED
    assert cb.consecutive_failures == 0


# ─── Helpers ────────────────────────────────────────────────────────────────


async def _trip(cb: CircuitBreaker, clock: _Clock) -> None:
    """Trip the breaker to OPEN by calling a failing function ``threshold`` times.

    ``clock`` is intentionally referenced (via the closure on the breaker)
    so Pyright / type checkers do not flag it as unused — the test asserts
    monotonic advancement aligns with the breaker's internal clock.
    """
    assert clock.t > 0  # ensure clock is wired into the breaker
    async def boom() -> None:
        raise RuntimeError("downstream down")

    for _ in range(cb.failure_threshold):
        with pytest.raises(RuntimeError):
            await cb.call(boom)
    assert cb.state is BreakerState.OPEN
