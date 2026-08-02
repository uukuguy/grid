"""Shared fixtures for the v3.15 platform SLA baseline test suite.

Per OBSTACK_DESIGN.md §5.2 (Verification / 集成测试):
  - tests/platform_sla/test_grid_runtime_llm.py  — L1 SLA
  - tests/platform_sla/test_l2_memory.py         — L2 SLA
  - tests/platform_sla/test_l3_opa.py           — L3 SLA
  - tests/platform_sla/test_l4_orchestration.py — L4 SLA

The platform-level goal is: when a layer crosses its threshold, the
business-flow evaluator emits a hint, and the alert manager (separate
component, v3.15.5-OPT follow-up) lights up.

For these baseline tests:
- We exercise each layer's read/write path 10–50 times per case.
- We measure wall-clock latency (p50 / p95) with a tight upper bound.
- The bounds are baseline values; a 2× regression would catch most
  realistic issues (DB hiccups, OPA sidecar lag, etc).

Threshold strategy:
  - p50 upper bound = generous "small workload" budget
  - p95 upper bound = tighter "hot path" budget
  - The gap between p50 and p95 caps pathological tail latency

NOTE: these are "microbench-style" SLA tests, not load tests. They
run in <2 seconds total and gate PR review. Production load
testing is a separate concern (out of scope for v3.15 SLA baseline).
"""

from __future__ import annotations

import time
from typing import Callable


def percentile(samples: list[float], pct: float) -> float:
    """Return the pct-th percentile (0.0–1.0) of a sample list.

    Linear interpolation between adjacent samples (same convention
    numpy uses for ``np.percentile`` with ``interpolation='linear'``,
    which is the default in numpy < 2.0).
    """
    if not samples:
        return 0.0
    s = sorted(samples)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def time_loop(
    fn: Callable[[], None],
    *,
    iterations: int,
    warmup: int = 2,
) -> list[float]:
    """Run ``fn`` once per iteration and return the per-call durations.

    Drops the first ``warmup`` samples (JIT-style warm-up). All
    durations are in seconds.
    """
    # Warm-up (untimed)
    for _ in range(warmup):
        fn()
    durations: list[float] = []
    for _ in range(iterations):
        t0 = time.monotonic()
        fn()
        durations.append(time.monotonic() - t0)
    return durations


def assert_within(
    samples: list[float],
    *,
    p50_max: float,
    p95_max: float,
    label: str,
) -> None:
    """Assert SLA: p50 within p50_max, p95 within p95_max.

    Failure mode: prints actual p50/p95 for diagnosis before raising.
    """
    p50 = percentile(samples, 0.50)
    p95 = percentile(samples, 0.95)
    if p50 > p50_max or p95 > p95_max:
        actual_p99 = percentile(samples, 0.99)
        raise AssertionError(
            f"SLA regression for {label}: "
            f"p50={p50*1000:.2f}ms (max {p50_max*1000:.2f}ms), "
            f"p95={p95*1000:.2f}ms (max {p95_max*1000:.2f}ms), "
            f"p99={actual_p99*1000:.2f}ms, n={len(samples)}"
        )
