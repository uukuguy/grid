"""Tests for ab_router.py — V315-OPT-01 A/B runtime selection.

Per OBSTACK_DESIGN.md §3.7 "业务流 A/B 路由":
  - L4 入口根据"过去 1h 业务流达成率"选 L1 runtime
  - 不只单层 metrics，是业务流整体效果

The router sits between ``flow_evaluator`` (which produces the
OptimizationHint set) and the L4 ``session_orchestrator``
(which is responsible for actually creating the L1 client).
This test exercises the router in isolation — see
``session_orchestrator`` tests for end-to-end wiring.
"""

from __future__ import annotations

from typing import Iterable

import pytest

from eaasp_l4_orchestration.ab_router import (
    DEFAULT_RUNTIME_ID,
    FlowMeta,
    RouterDecision,
    choose_runtime,
)
from eaasp_l4_orchestration.flow_timeline import BusinessFlowSummary


def _summary(
    *,
    status: str = "succeeded",
    duration_seconds: float = 1.0,
    event_count: int = 5,
) -> BusinessFlowSummary:
    """Build a real BusinessFlowSummary with the fields the router reads."""
    return BusinessFlowSummary(
        status=status,
        started_at=1000,
        completed_at=int(1000 + duration_seconds * 1000),
        total_duration_ms=int(duration_seconds * 1000),
        event_count=event_count,
        layer_counts={"L4": 5},
        interrupted_layer=None,
    )


def _pairs(
    *,
    n: int,
    runtime_id: str,
    success_count: int,
    object_id: str = "sla-obj",
) -> list[tuple[BusinessFlowSummary, FlowMeta]]:
    """Build (summary, meta) pairs with the given success/fail split."""
    return [
        (
            _summary(status="succeeded" if i < success_count else "failed"),
            FlowMeta(business_object_id=object_id, runtime_id=runtime_id),
        )
        for i in range(n)
    ]


def test_empty_signal_returns_default() -> None:
    decision = choose_runtime(None, iter([]))
    assert decision.runtime_id == DEFAULT_RUNTIME_ID
    assert decision.sample_size == 0
    assert "no signal" in decision.reason


def test_empty_summaries_returns_default() -> None:
    decision = choose_runtime("sla-obj", iter([]))
    assert decision.runtime_id == DEFAULT_RUNTIME_ID


def test_unknown_business_object_returns_default() -> None:
    pairs = _pairs(n=20, runtime_id="grid-runtime", success_count=18)
    decision = choose_runtime("nonexistent-obj", iter(pairs))
    assert decision.runtime_id == DEFAULT_RUNTIME_ID
    assert "no business flow history" in decision.reason


def test_single_runtime_with_enough_samples_picked() -> None:
    pairs = _pairs(n=20, runtime_id="grid-runtime", success_count=20)
    decision = choose_runtime("sla-obj", iter(pairs))
    assert decision.runtime_id == "grid-runtime"
    assert decision.sample_size == 20
    assert "highest completion rate" in decision.reason
    assert decision.completion_rates == {"grid-runtime": 1.0}


def test_picks_runtime_with_highest_completion_rate() -> None:
    """claude-code-runtime has 90% success; grid-runtime has 60%."""
    grid = _pairs(n=20, runtime_id="grid-runtime", success_count=12)
    claude = _pairs(n=20, runtime_id="claude-code-runtime", success_count=18)
    decision = choose_runtime("sla-obj", iter(grid + claude))
    assert decision.runtime_id == "claude-code-runtime"
    assert decision.completion_rates == {
        "grid-runtime": pytest.approx(0.6),
        "claude-code-runtime": pytest.approx(0.9),
    }


def test_tie_break_falls_through_to_alphabetical() -> None:
    """Both runtime_ids hit exactly 0.5 completion rate; pick the one
    that comes first alphabetically."""
    grid = _pairs(n=20, runtime_id="a-runtime", success_count=10)
    z_grid = _pairs(n=20, runtime_id="z-runtime", success_count=10)
    decision = choose_runtime("sla-obj", iter(grid + z_grid))
    assert decision.runtime_id == "a-runtime"


def test_below_min_sample_size_returns_default() -> None:
    """Both candidates below min_sample_size=10 → default."""
    grid = _pairs(n=5, runtime_id="grid-runtime", success_count=5)
    claude = _pairs(n=5, runtime_id="claude-code-runtime", success_count=5)
    decision = choose_runtime("sla-obj", iter(grid + claude))
    assert decision.runtime_id == DEFAULT_RUNTIME_ID
    assert "only 5 flows" in decision.reason


def test_best_runtime_passes_guard_with_enough_samples() -> None:
    """When best candidate has ≥ min_sample_size, it's picked even
    if the runner-up is below the threshold."""
    grid = _pairs(n=5, runtime_id="grid-runtime", success_count=5)
    claude = _pairs(n=20, runtime_id="claude-code-runtime", success_count=20)
    decision = choose_runtime("sla-obj", iter(grid + claude))
    assert decision.runtime_id == "claude-code-runtime"
    assert decision.sample_size == 25


def test_threshold_override_changes_min_sample_size() -> None:
    """Lowering ``min_sample_size`` lets small samples through."""
    grid = _pairs(n=5, runtime_id="grid-runtime", success_count=5)
    claude = _pairs(n=5, runtime_id="claude-code-runtime", success_count=5)
    decision = choose_runtime(
        "sla-obj",
        iter(grid + claude),
        thresholds={
            "completion_rate_warn": 0.9,
            "completion_rate_critical": 0.75,
            "interruption_share_warn": 0.4,
            "min_sample_size": 5,
        },
    )
    # With min_sample_size=5, the guard no longer fires even on
    # 5 samples. completion_rate tie at 1.0 → alphabetical first
    # ("claude-code-runtime" < "grid-runtime" alphabetically).
    assert decision.runtime_id == "claude-code-runtime"
    assert decision.sample_size == 10


def test_status_field_includes_succeeded_only() -> None:
    """The router counts "succeeded" as completion. "running",
    "aborted", "failed", "unknown" all do not contribute to
    completion rate."""
    pairs = [
        (
            _summary(status="succeeded", duration_seconds=1.0),
            FlowMeta(business_object_id="sla-obj", runtime_id="grid-runtime"),
        ),
        (
            _summary(status="failed", duration_seconds=1.0),
            FlowMeta(business_object_id="sla-obj", runtime_id="grid-runtime"),
        ),
        (
            _summary(status="aborted", duration_seconds=1.0),
            FlowMeta(business_object_id="sla-obj", runtime_id="grid-runtime"),
        ),
        (_summary(status="running", duration_seconds=1.0),
         FlowMeta(business_object_id="sla-obj", runtime_id="grid-runtime")),
    ] * 4  # 16 total (4 each), 4 succeeded, completion_rate = 0.25
    decision = choose_runtime("sla-obj", iter(pairs))
    assert decision.runtime_id == DEFAULT_RUNTIME_ID
    # 25% is below completion_rate_warn (0.90) but min_sample_size=10
    # is satisfied so the decision uses the chosen runtime.
    assert decision.completion_rates["grid-runtime"] == pytest.approx(0.25)
