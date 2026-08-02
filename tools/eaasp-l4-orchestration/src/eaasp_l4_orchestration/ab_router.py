"""EAASP L4 AB router — production-grade Optimizer executor (v3.15.5).

Per OBSTACK_DESIGN.md §3.7 "业务流 A/B 路由":
  - L4 入口根据"过去 1h 业务流达成率"选 L1 runtime
  - 不只单层 metrics，是业务流整体效果

This module wraps ``flow_evaluator.evaluate_business_flows`` to
pick an L1 runtime based on recent business-flow completion
rates. The router:

  - Reads summaries + a parallel ``run_map`` that attaches
    ``business_object_id`` and ``runtime_id`` to each summary
    (because the timeline aggregate shape
    ``BusinessFlowSummary`` does not retain those fields — they
    live in the source-table columns the aggregator rolled up).
  - Computes per-(business_object_id, runtime_id) completion rate.
  - For a new business_object_id, picks the runtime with the
    highest completion rate. Tie-break: alphabetical. Unknown
    business_object_id / empty summaries → default
    ``"grid-runtime"`` (Tier 1 Harness — preserves existing
    behavior).

The router is intentionally dependency-free and synchronous
so that ``create_l1_client`` callers in ``session_orchestrator``
can call ``choose_runtime(...)`` cheaply.

Stateless by design (within a process); the L4 server's flow_sse
bus re-evaluates and calls the router on each new session.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping

from .flow_evaluator import (
    FlowEvaluationReport,
    evaluate_business_flows,
)
from .flow_timeline import BusinessFlowSummary

# Default runtime when the router has no signal. Keeps grid-runtime's
# Tier 1 Harness guarantee intact (per ADR-V2-024 engine 接入面).
DEFAULT_RUNTIME_ID = "grid-runtime"

# Default evaluator thresholds — same DEFENSIVE set used by
# flow_evaluator.DEFAULT_THRESHOLDS so the two paths stay in lockstep.
_DEFAULT_THRESHOLDS = {
    "completion_rate_warn": 0.90,
    "completion_rate_critical": 0.75,
    "interruption_share_warn": 0.40,
    "min_sample_size": 10,
}


@dataclass(frozen=True)
class FlowMeta:
    """Per-flow identity that ``BusinessFlowSummary`` itself doesn't
    retain — sourced from the schema columns the timeline rolled up.

    ``business_object_id`` is the wire-format portion of the
    BusinessKey triple ((session|skill|object)); ``runtime_id`` is
    the runtime that handled the session.
    """

    business_object_id: str
    runtime_id: str = DEFAULT_RUNTIME_ID


@dataclass(frozen=True)
class RouterDecision:
    """The router's pick for one incoming session.

    Attributes:
      runtime_id:        the runtime to use for this session.
      reason:            short human-readable summary.
      sample_size:       number of business flows the decision was based
                         on (0 when no signal).
      completion_rates:  map of runtime_id → completion_rate observed
                         in the lookback window (per candidate).
    """

    runtime_id: str
    reason: str
    sample_size: int
    completion_rates: dict[str, float]


def choose_runtime(
    business_object_id: str | None,
    summaries: Iterable[tuple[BusinessFlowSummary, FlowMeta]],
    *,
    thresholds: Mapping[str, float] | None = None,
) -> RouterDecision:
    """Pick a runtime_id based on recent business-flow completion rates.

    Args:
      business_object_id: triple that ties this session to recent
        flows. ``None`` → no signal, default runtime.
      summaries: iterable of ``(summary, meta)`` pairs spanning
        the lookback window. The summary drives completion_rate;
        the meta drives the per-runtime grouping.
      thresholds: optional override of the evaluator thresholds
        (mirrors ``evaluate_business_flows``).
    """
    threshold_set = dict(thresholds) if thresholds else _DEFAULT_THRESHOLDS
    pairs = list(summaries)
    if not pairs or not business_object_id:
        return RouterDecision(
            runtime_id=DEFAULT_RUNTIME_ID,
            reason=(
                "no signal — empty summaries or missing business_object_id; "
                f"defaulting to {DEFAULT_RUNTIME_ID}"
            ),
            sample_size=0,
            completion_rates={},
        )

    plain_summaries = [s for s, _meta in pairs]

    # Single call to the real evaluator — drives the OptimizationHint
    # set the Optimize executor surfaces in production. We pass
    # plain_summaries (the FlowSummaryLike shape), not the (s,meta)
    # tuple, so the existing evaluator signature stays intact.
    report: FlowEvaluationReport = evaluate_business_flows(
        plain_summaries,
        thresholds=threshold_set,
    )

    # Filter to this business_object_id, then group by runtime_id.
    relevant = [
        (s, m) for s, m in pairs if m.business_object_id == business_object_id
    ]
    if not relevant:
        return RouterDecision(
            runtime_id=DEFAULT_RUNTIME_ID,
            reason=(
                "no business flow history for this business_object_id; "
                f"defaulting to {DEFAULT_RUNTIME_ID}"
            ),
            sample_size=0,
            completion_rates={},
        )

    per_runtime_total: dict[str, int] = defaultdict(int)
    per_runtime_succeeded: dict[str, int] = defaultdict(int)
    for s, m in relevant:
        rid = m.runtime_id or DEFAULT_RUNTIME_ID
        per_runtime_total[rid] += 1
        # "succeeded" / "aborted" both count as "completed";
        # "running" / "unknown" count as in-progress (not yet
        # scored); "failed" counts as failure.
        if s.status == "succeeded":
            per_runtime_succeeded[rid] += 1

    completion_rates: dict[str, float] = {
        rid: per_runtime_succeeded[rid] / per_runtime_total[rid]
        for rid in per_runtime_total
    }

    best_rid, best_rate = sorted(
        completion_rates.items(),
        key=lambda kv: (-kv[1], kv[0]),
    )[0]

    if per_runtime_total[best_rid] < int(threshold_set["min_sample_size"]):
        return RouterDecision(
            runtime_id=DEFAULT_RUNTIME_ID,
            reason=(
                f"best candidate {best_rid} has only "
                f"{per_runtime_total[best_rid]} flows "
                f"(< min_sample_size={threshold_set['min_sample_size']}); "
                f"defaulting to {DEFAULT_RUNTIME_ID}"
            ),
            sample_size=len(relevant),
            completion_rates=dict(completion_rates),
        )

    return RouterDecision(
        runtime_id=best_rid,
        reason=(
            f"highest completion rate ({best_rate:.2%}) across "
            f"{len(relevant)} flow(s) for business_object_id="
            f"{business_object_id}"
        ),
        sample_size=len(relevant),
        completion_rates=dict(completion_rates),
    )


# Sentinel alias kept so external imports keep compiling. Older
# callers (and tests) referred to ``FlowSummaryLike`` as a single
# shape; new code should use ``tuple[BusinessFlowSummary, FlowMeta]``.
FlowSummaryLike = tuple[BusinessFlowSummary, FlowMeta]
