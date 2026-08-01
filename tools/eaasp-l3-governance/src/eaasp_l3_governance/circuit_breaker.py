"""Circuit breaker for OPA sidecar — protects L3 governance from cascading
failures when the sidecar is unreachable.

Per v3.15.0 design (PHASE_3_5_DESIGN.md §3.1). 3-state machine:

    closed  --(N consecutive failures)--> open
    open    --(cool-down elapses)--------> half_open
    half_open --(next call succeeds)-----> closed
    half_open --(next call fails)--------> open

When state is ``open``, calls are short-circuited without hitting the
upstream. This prevents the L3 governance process from queuing up
hundreds of timed-out httpx calls per second when the OPA sidecar is
crashed / down for maintenance / network-partitioned.

The breaker is intentionally minimal — no thread safety guarantees beyond
what ``asyncio.Lock`` provides, no metrics, no per-endpoint breakers.
Per v3.15.0, the "metrics" concern is deferred to v3.15.2 (OTel counters).
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class BreakerState(str, Enum):
    """Three-state breaker (industry standard: Nygard, Fowler, Hystrix)."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when ``call()`` is short-circuited because the breaker is open.

    The caller (PolicyEngine) translates this into the same fail-closed
    OPADecision envelope as a connection-refused error, with a stable
    ``cause`` identifier so the audit ledger can distinguish "sidecar
    down + breaker tripped" from "sidecar down + breaker still closed".
    """

    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__(
            f"circuit_breaker_open: retry after {retry_after_seconds:.1f}s"
        )
        self.retry_after_seconds = retry_after_seconds


@dataclass
class CircuitBreaker:
    """Asyncio-friendly circuit breaker for OPA sidecar calls.

    Parameters
    ----------
    failure_threshold : int
        Number of consecutive failures in CLOSED state that trips the
        breaker to OPEN. Default 5 per v3.15.0 design §3.1.
    cool_down_seconds : float
        Seconds to wait in OPEN before allowing a HALF_OPEN probe.
        Default 30s per design.
    name : str
        Human-readable label for logging / metrics attributes.

    The ``clock`` parameter is injectable for tests; production passes
    ``time.monotonic`` (default).
    """

    failure_threshold: int = 5
    cool_down_seconds: float = 30.0
    name: str = "opa_backend"
    clock: Callable[[], float] = field(default=time.monotonic)

    _state: BreakerState = BreakerState.CLOSED
    _consecutive_failures: int = 0
    _opened_at_monotonic: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def state(self) -> BreakerState:
        """Current state — read-only; mutates are guarded by ``_lock``."""
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    def _now(self) -> float:
        return self.clock()

    def _maybe_transition_to_half_open(self) -> None:
        """If we're in OPEN and the cool-down has elapsed, flip to HALF_OPEN.

        Not guarded by lock — callers must hold ``_lock``. The transition
        is one-way (OPEN→HALF_OPEN) and does not require an external
        event; the next ``call()`` triggers it.
        """
        if self._state is BreakerState.OPEN:
            elapsed = self._now() - self._opened_at_monotonic
            if elapsed >= self.cool_down_seconds:
                self._state = BreakerState.HALF_OPEN

    async def call(self, fn: Callable[..., Awaitable[T]], /, *args: Any, **kwargs: Any) -> T:
        """Run ``fn`` through the breaker.

        - CLOSED: call directly; on success reset failure counter; on
          failure increment and possibly trip to OPEN.
        - OPEN: short-circuit with ``CircuitOpenError`` unless cool-down
          has elapsed (in which case transition to HALF_OPEN and probe).
        - HALF_OPEN: call once; success → CLOSED + reset; failure → OPEN
          + restart cool-down clock.
        """
        async with self._lock:
            self._maybe_transition_to_half_open()
            if self._state is BreakerState.OPEN:
                retry_after = max(
                    0.0,
                    self.cool_down_seconds - (self._now() - self._opened_at_monotonic),
                )
                raise CircuitOpenError(retry_after)
            state_at_entry = self._state

        try:
            result = await fn(*args, **kwargs)
        except BaseException:
            async with self._lock:
                self._consecutive_failures += 1
                if state_at_entry is BreakerState.HALF_OPEN:
                    # Probe failed → back to OPEN, restart cool-down.
                    self._state = BreakerState.OPEN
                    self._opened_at_monotonic = self._now()
                elif (
                    state_at_entry is BreakerState.CLOSED
                    and self._consecutive_failures >= self.failure_threshold
                ):
                    self._state = BreakerState.OPEN
                    self._opened_at_monotonic = self._now()
            raise

        async with self._lock:
            # Success: reset failure counter and close the breaker if we
            # just probed successfully.
            self._consecutive_failures = 0
            if state_at_entry is BreakerState.HALF_OPEN:
                self._state = BreakerState.CLOSED
        return result

    async def reset(self) -> None:
        """Force-reset to CLOSED. For operator use / tests."""
        async with self._lock:
            self._state = BreakerState.CLOSED
            self._consecutive_failures = 0
            self._opened_at_monotonic = 0.0
