"""EAASP L4 AB router — production-grade Optimizer executor (v3.15.5).

Per OBSTACK_DESIGN.md §3.7 "业务流 A/B 路由":
  - L4 入口根据"过去 1h 业务流达成率"选 L1 runtime
  - 不只单层 metrics，是业务流整体效果

This module is a thin wrapper around ``flow_evaluator.evaluate_business_flows``
that produces a runtime selection. The router:

  - Reads recent summaries from a pluggable ``SummarySource`` (default
    in-memory; production callers wire ``L4 flow SSE bus`` subscriptions).
  - Computes completion rate per ``(business_object_id, runtime_id)`` pair
    in the lookback window.
  - For each new session that carries a business_object_id, picks
    the runtime with the highest completion rate. Tie-break:
    alphabetical runtime_id. Unknown business_object_id → default
    ``"grid-runtime"`` (Tier 1 Harness — preserves existing behavior).

The module is intentionally dependency-free and synchronous so that
``create_l1_client`` callers in ``session_orchestrator`` can call
``choose_runtime(business_object_id)`` cheaply.

Failure modes:

  - ``SummarySource`` returns empty data → default ``"grid-runtime"``
    and log a ``tracing::info!``.
  - Summary evaluation finds the same completion_rate for 2+ runtimes
    → alphabetical first.

Stateless by design (within a process); the L4 server's flow_sse
bus re-evaluates and calls the router on each new session.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .flow_evaluator import (
    FlowEvaluationReport,
    evaluate_business_flows,
)
from .flow_timeline import BusinessFlowSummary

FlowSummaryLike = BusinessFlowSummary

# Default runtime when the router has no signal. Keeps grid-runtime's
# Tier 1 Harness guarantee intact (per ADR-V2-024 engine 接入面).
DEFAULT_RUNTIME_ID = "grid-runtime"

# Default evaluator thresholds — same DEFENSIVE set used by
# flow_evaluator.ensure_no_hints_overrides so the two paths stay
# in lockstep.
_DEFAULT_THRESHOLDS = {
    "completion_rate_warn": 0.90,
    "completion_rate_critical": 0.75,
    "interruption_share_warn": 0.40,
    "min_sample_size": 10,
}


@dataclass(frozen=True)
class RouterDecision:
    """The router's pick for one incoming session.

    Attributes:
      runtime_id:        the runtime to use for this session.
      reason:            short human-readable summary ("highest completion rate"
                         / "default — no signal").
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
    summaries: Iterable[FlowSummaryLike],
    *,
    thresholds: dict[str, float] | None = None,
) -> RouterDecision:
    """Pick a runtime_id based on recent business-flow completion rates.

    Args:
      business_object_id: triple that ties this session to recent
        flows. ``None`` → no signal, default runtime.
      summaries: feed of FlowSummaryLike records spanning the
        lookback window (e.g. 1h per OBSTACK §3.7).
      thresholds: optional override of the evaluator thresholds
        (mirrors ``evaluate_business_flows``).

    Returns a ``RouterDecision`` containing the pick + the rationale
    so callers can log it without re-evaluating.
    """
    threshold_set = thresholds or _DEFAULT_THRESHOLDS
    summaries_list = list(summaries)
    if not summaries_list or not business_object_id:
        return RouterDecision(
            runtime_id=DEFAULT_RUNTIME_ID,
            reason=(
                "no signal — empty summaries or missing business_object_id; "
                "defaulting to {DEFAULT_RUNTIME_ID}"
            ),
            sample_size=0,
            completion_rates={},
        )

    report: FlowEvaluationReport = evaluate_business_flows(
        summaries_list,
        thresholds=threshold_set,
    )

    # Filter summaries that match the requested business_object_id.
    relevant = [s for s in summaries_list if _matches(s, business_object_id)]
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

    # Group by runtime_id; compute per-runtime completion rate.
    per_runtime_total: dict[str, int] = defaultdict(int)
    per_runtime_succeeded: dict[str, int] = defaultdict(int)
    for s in relevant:
        rid = _runtime_id_of(s) or DEFAULT_RUNTIME_ID
        per_runtime_total[rid] += 1
        if _status_of(s) == "succeeded":
            per_runtime_succeeded[rid] += 1

    completion_rates: dict[str, float] = {
        rid: per_runtime_succeeded[rid] / per_runtime_total[rid]
        for rid in per_runtime_total
    }

    # Pick highest completion rate; tie-break alphabetical.
    best_rid, best_rate = sorted(
        completion_rates.items(),
        key=lambda kv: (-kv[1], kv[0]),
    )[0]

    # Min-sample guard: with < min_sample_size flows the rate is noisy;
    # fall back to default.
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


def _matches(summary: FlowSummaryLike, business_object_id: str) -> bool:
    """Return True iff this summary is for the requested business object.

    Currently we accept any summary whose ``business_object_id`` field
    matches. If the summary object lacks that attribute, fall back
    to matching by prefix (first session_id token — same caveat as
    Python ``BusinessKey.matches``).
    """
    obj_id = getattr(summary, "business_object_id", None)
    if obj_id:
        return obj_id == business_object_id
    # Fallback: pull from raw session_id if FlowSummaryLike is a dict.
    sid = getattr(summary, "session_id", "")
    return sid.startswith(business_object_id.split("|")[0])


def _runtime_id_of(summary: FlowSummaryLike) -> str | None:
    rid = getattr(summary, "runtime_id", None)
    if rid:
        return rid
    # Last-resort fallback: pull from any structured source attached.
    return None


def _status_of(summary: FlowSummaryLike) -> str | None:
    return getattr(summary, "status", None)
