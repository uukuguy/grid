"""Business Flow Evaluator — production-grade evaluate/optimize capability.

Per v3.15.4 (OBSTACK_DESIGN.md §3.7). Computes the
"evaluate" half of the four production-grade capabilities: business
flow completion rate, layer-failure heatmap, and cross-layer
optimization suggestions.

Inputs: a sequence of ``BusinessFlowSummary`` records (typically
gathered from the ``flow_timeline`` aggregator across many sessions
in a time window). The evaluator is pure-function: no DB access, no
async — easy to unit-test, easy to schedule as a periodic job.

Outputs:

- ``FlowEvaluationReport`` — JSON-serializable rollup of the window
  (counts, completion rate, layer interruption heatmap, top
  optimization recommendations).

The evaluator is intentionally framework-free: no OTel, no DB. The
caller (CLI / scheduled job / L4 endpoint) wires it to data sources
and to a downstream sink (log line, JSON file, webhook).
"""

from __future__ import annotations

import math  # noqa: F401  # reserved for future statistical helpers (e.g. confidence intervals)
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from eaasp_common.business_flow import BusinessKey

from .flow_timeline import BusinessFlowSummary

# Default time window: 1 hour. Matches the design's "balance between
# responsiveness and sample size" guidance.
DEFAULT_WINDOW_SECONDS = 3600


# ─── Output model ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class OptimizationHint:
    """One concrete cross-layer optimization recommendation.

    Fields:
    - ``layer`` — which layer is the bottleneck.
    - ``metric`` — short human-readable metric name (e.g. "decision
      latency", "approval rate drop", "memory write failures").
    - ``severity`` — ``"info"`` / ``"warn"`` / ``"critical"``.
    - ``recommendation`` — what to do (e.g. "scale L3 governance
      sidecar to 2 replicas").
    - ``evidence`` — supporting numbers from the input summaries.
    """

    layer: str
    metric: str
    severity: str
    recommendation: str
    evidence: dict[str, float | int | str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "layer": self.layer,
            "metric": self.metric,
            "severity": self.severity,
            "recommendation": self.recommendation,
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True)
class FlowEvaluationReport:
    """Aggregator rollup over a time window.

    Fields:
    - ``window_seconds`` — the window size used.
    - ``total_flows`` — number of distinct flows observed.
    - ``status_counts`` — counts per terminal status.
    - ``completion_rate`` — fraction of flows that succeeded.
    - ``interruption_heatmap`` — counts of interruptions per layer.
    - ``hints`` — ranked optimization recommendations.
    """

    window_seconds: int
    total_flows: int
    status_counts: dict[str, int]
    completion_rate: float
    interruption_heatmap: dict[str, int]
    hints: list[OptimizationHint]

    def to_dict(self) -> dict[str, object]:
        return {
            "window_seconds": self.window_seconds,
            "total_flows": self.total_flows,
            "status_counts": dict(self.status_counts),
            "completion_rate": self.completion_rate,
            "interruption_heatmap": dict(self.interruption_heatmap),
            "hints": [h.to_dict() for h in self.hints],
        }


# ─── Thresholds for hint generation ─────────────────────────────────────────
#
# The evaluator emits hints when the aggregate crosses one of these
# thresholds. Conservative defaults; operator can override via the
# ``thresholds`` parameter.

DEFAULT_THRESHOLDS = {
    "completion_rate_warn": 0.90,  # below 90% success → warn
    "completion_rate_critical": 0.75,  # below 75% → critical
    "interruption_share_warn": 0.40,  # any single layer accounts for > 40% of interruptions → warn
    "min_sample_size": 10,  # do not emit hints with < 10 flows
}


# ─── Pure-function evaluation ──────────────────────────────────────────────


def _status_counts(summaries: Iterable[BusinessFlowSummary]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for s in summaries:
        counts[s.status] += 1
    return counts


def _interruption_heatmap(summaries: Iterable[BusinessFlowSummary]) -> Counter[str]:
    heat: Counter[str] = Counter()
    for s in summaries:
        if s.interrupted_layer:
            heat[s.interrupted_layer] += 1
    return heat


def _round_pct(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _generate_hints(
    *,
    total_flows: int,
    status_counts: Counter[str],
    interruption_heatmap: Counter[str],
    thresholds: dict[str, float],
) -> list[OptimizationHint]:
    """Translate the aggregates into ranked optimization hints."""
    if total_flows < thresholds.get("min_sample_size", 10):
        return [
            OptimizationHint(
                layer="-",
                metric="sample_size",
                severity="info",
                recommendation=(
                    f"Insufficient data ({total_flows} flows) to emit "
                    f"optimization hints; need ≥ {thresholds['min_sample_size']}"
                ),
                evidence={"total_flows": total_flows},
            )
        ]

    hints: list[OptimizationHint] = []

    # ─── completion-rate hint ────────────────────────────────────────────
    succeeded = status_counts.get("succeeded", 0)
    completion_rate = _round_pct(succeeded, total_flows)
    crit = thresholds["completion_rate_critical"]
    warn = thresholds["completion_rate_warn"]
    if completion_rate < crit:
        severity = "critical"
    elif completion_rate < warn:
        severity = "warn"
    else:
        severity = None
    if severity:
        hints.append(
            OptimizationHint(
                layer="cross-cutting",
                metric="completion_rate",
                severity=severity,
                recommendation=(
                    "Investigate the dominant interruption layer; "
                    "consider scaling that layer or reverting recent policy changes"
                ),
                evidence={
                    "completion_rate": completion_rate,
                    "succeeded": succeeded,
                    "total_flows": total_flows,
                },
            )
        )

    # ─── per-layer interruption share hint ───────────────────────────────
    total_interruptions = sum(interruption_heatmap.values())
    if total_interruptions > 0:
        share_threshold = thresholds.get("interruption_share_warn", 0.40)
        for layer, count in interruption_heatmap.most_common():
            share = count / total_interruptions
            if share >= share_threshold:
                hints.append(
                    OptimizationHint(
                        layer=layer,
                        metric="interruption_share",
                        severity="critical" if share >= 0.6 else "warn",
                        recommendation=(
                            f"Layer {layer} accounts for {int(share * 100)}% of "
                            f"interruptions; inspect its decision latency and "
                            f"downstream dependencies"
                        ),
                        evidence={
                            "interruption_count": count,
                            "total_interruptions": total_interruptions,
                            "share": round(share, 4),
                        },
                    )
                )

    return hints


def evaluate_business_flows(
    summaries: Sequence[BusinessFlowSummary],
    *,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    thresholds: dict[str, float] | None = None,
) -> FlowEvaluationReport:
    """Compute the evaluation report for a window of flow summaries.

    Pure function — no I/O, easy to test. The caller is responsible
    for:
    - gathering the right window of summaries (typically from the
      ``flow_timeline`` aggregator + a DB query)
    - persisting / forwarding the report (write JSON, log line,
      webhook, etc.)
    """
    merged_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    total = len(summaries)
    status_counts = _status_counts(summaries)
    heatmap = _interruption_heatmap(summaries)
    completion = _round_pct(status_counts.get("succeeded", 0), total)
    hints = _generate_hints(
        total_flows=total,
        status_counts=status_counts,
        interruption_heatmap=heatmap,
        thresholds=merged_thresholds,
    )
    return FlowEvaluationReport(
        window_seconds=window_seconds,
        total_flows=total,
        status_counts=dict(status_counts),
        completion_rate=completion,
        interruption_heatmap=dict(heatmap),
        hints=hints,
    )


# ─── Convenience: build summaries from raw events ──────────────────────────


def build_summaries_from_events(
    flows: Sequence[tuple[BusinessKey, Sequence[object]]],
) -> list[BusinessFlowSummary]:
    """Helper for callers that have raw events but no pre-built summaries.

    Each tuple is ``(key, events)``. The function is a thin wrapper
    around the timeline aggregator's ``summarize_business_flow`` —
    it lives here so the evaluator module is self-contained for
    callers that don't want to import the timeline module.

    For the canonical path use ``assemble_business_flow_timeline``
    + ``summarize_business_flow`` directly.
    """
    from .flow_timeline import summarize_business_flow  # local import to avoid cycle

    out: list[BusinessFlowSummary] = []
    for _key, events in flows:
        # The key is part of the input shape (parity with
        # ``assemble_business_flow_timeline``) but ``summarize_business_flow``
        # only inspects the events. Underscore-prefixed to silence linters.
        out.append(summarize_business_flow(events))  # type: ignore[arg-type]
    return out


__all__ = [
    "DEFAULT_THRESHOLDS",
    "DEFAULT_WINDOW_SECONDS",
    "FlowEvaluationReport",
    "OptimizationHint",
    "build_summaries_from_events",
    "evaluate_business_flows",
]
