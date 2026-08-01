"""Tests for flow_evaluator.py — v3.15.4 business flow evaluation.

Covers:
- Status counting + completion rate
- Interruption heatmap + per-layer hint
- Completion-rate hint at critical vs warn thresholds
- Sample-size gate (do not emit hints with < min_sample_size)
- to_dict() round-trip
- Custom threshold override
- build_summaries_from_events helper
"""

from __future__ import annotations

from eaasp_common.business_flow import BusinessKey
from eaasp_l4_orchestration.flow_evaluator import (
    DEFAULT_THRESHOLDS,
    DEFAULT_WINDOW_SECONDS,
    OptimizationHint,
    build_summaries_from_events,
    evaluate_business_flows,
)
from eaasp_l4_orchestration.flow_timeline import (
    BusinessFlowEvent,
    BusinessFlowSummary,
)


def _summary(
    status: str,
    *,
    interrupted: str | None = None,
    started: int = 1000,
    completed: int | None = 1500,
) -> BusinessFlowSummary:
    return BusinessFlowSummary(
        status=status,
        started_at=started,
        completed_at=completed,
        total_duration_ms=(completed - started) if completed else None,
        event_count=3,
        layer_counts={"L4": 3},
        interrupted_layer=interrupted,
    )


# ─── Counting ───────────────────────────────────────────────────────────────


def test_empty_window() -> None:
    r = evaluate_business_flows([])
    assert r.total_flows == 0
    assert r.completion_rate == 0.0
    assert r.status_counts == {}
    assert r.interruption_heatmap == {}
    # Below min sample size → emit an info hint about insufficient data
    assert len(r.hints) == 1
    assert r.hints[0].severity == "info"


def test_status_counts() -> None:
    r = evaluate_business_flows([
        _summary("succeeded"),
        _summary("succeeded"),
        _summary("failed", interrupted="L3"),
        _summary("aborted", interrupted="L3"),
    ])
    assert r.total_flows == 4
    assert r.status_counts == {"succeeded": 2, "failed": 1, "aborted": 1}
    assert r.completion_rate == 0.5


def test_completion_rate_100_percent() -> None:
    r = evaluate_business_flows([_summary("succeeded") for _ in range(5)])
    assert r.completion_rate == 1.0


# ─── Interruption heatmap ──────────────────────────────────────────────────


def test_interruption_heatmap() -> None:
    r = evaluate_business_flows([
        _summary("failed", interrupted="L3"),
        _summary("failed", interrupted="L3"),
        _summary("failed", interrupted="L1"),
    ])
    assert r.interruption_heatmap == {"L3": 2, "L1": 1}


def test_interruption_heatmap_ignores_succeeded() -> None:
    r = evaluate_business_flows([_summary("succeeded") for _ in range(5)])
    assert r.interruption_heatmap == {}


# ─── Hint generation ──────────────────────────────────────────────────────


def _large_dataset(n: int = 50) -> list[BusinessFlowSummary]:
    """50 flows: 30 succeeded, 20 failed on L3.

    The ``n`` parameter is reserved for callers that want a different
    dataset size; the helper currently produces a fixed 30/20 split
    sized for the threshold tests.
    """
    del n  # unused; reserved for future parametrization
    out = [_summary("succeeded") for _ in range(30)]
    out += [_summary("failed", interrupted="L3") for _ in range(20)]
    return out


def test_completion_rate_critical_hint() -> None:
    r = evaluate_business_flows(_large_dataset())
    # 30/50 = 60% → below critical (0.75) → critical hint
    assert any(
        h.metric == "completion_rate" and h.severity == "critical" for h in r.hints
    )


def test_completion_rate_warn_hint() -> None:
    # 80% success → warn but not critical
    flows = [_summary("succeeded") for _ in range(16)]
    flows += [_summary("failed", interrupted="L3") for _ in range(4)]
    r = evaluate_business_flows(flows)
    assert any(
        h.metric == "completion_rate" and h.severity == "warn" for h in r.hints
    )


def test_no_completion_hint_when_healthy() -> None:
    flows = [_summary("succeeded") for _ in range(20)]
    r = evaluate_business_flows(flows)
    assert not any(h.metric == "completion_rate" for h in r.hints)


def test_interruption_layer_share_hint() -> None:
    r = evaluate_business_flows(_large_dataset())
    # L3 accounts for 100% of interruptions → critical
    hints_l3 = [h for h in r.hints if h.layer == "L3" and h.metric == "interruption_share"]
    assert len(hints_l3) == 1
    assert hints_l3[0].severity == "critical"


def test_interruption_layer_below_threshold() -> None:
    # 20 flows: 15 succeeded, 3 failed L1, 2 failed L3
    # L1 share = 3/5 = 60% (above 40% threshold)
    # L3 share = 2/5 = 40% (at threshold, but not above)
    flows = [_summary("succeeded") for _ in range(15)]
    flows += [_summary("failed", interrupted="L1") for _ in range(3)]
    flows += [_summary("failed", interrupted="L3") for _ in range(2)]
    r = evaluate_business_flows(flows)
    layers = [h.layer for h in r.hints if h.metric == "interruption_share"]
    assert "L1" in layers
    # 40% is at threshold but not strictly greater; check default threshold
    if DEFAULT_THRESHOLDS["interruption_share_warn"] > 0.4:
        assert "L3" not in layers


# ─── Sample size gate ──────────────────────────────────────────────────────


def test_below_min_sample_emits_info() -> None:
    r = evaluate_business_flows([_summary("succeeded") for _ in range(5)])
    assert len(r.hints) == 1
    assert r.hints[0].severity == "info"
    assert "Insufficient data" in r.hints[0].recommendation


# ─── Custom threshold ──────────────────────────────────────────────────────


def test_custom_threshold_override() -> None:
    flows = [_summary("succeeded") for _ in range(5)] + [
        _summary("failed", interrupted="L1")
    ]
    # Custom threshold: completion_rate_critical = 0.50
    # 5/6 = 0.833 → not below 0.50
    r = evaluate_business_flows(
        flows, thresholds={"completion_rate_critical": 0.50}
    )
    assert not any(h.metric == "completion_rate" for h in r.hints)


# ─── to_dict round-trip ───────────────────────────────────────────────────


def test_report_to_dict() -> None:
    r = evaluate_business_flows(_large_dataset())
    d = r.to_dict()
    assert d["total_flows"] == 50
    assert d["window_seconds"] == DEFAULT_WINDOW_SECONDS
    assert isinstance(d["status_counts"], dict)
    assert isinstance(d["interruption_heatmap"], dict)
    assert isinstance(d["hints"], list)
    for h in d["hints"]:
        assert set(h.keys()) == {
            "layer",
            "metric",
            "severity",
            "recommendation",
            "evidence",
        }


def test_hint_to_dict() -> None:
    h = OptimizationHint(
        layer="L3",
        metric="foo",
        severity="warn",
        recommendation="bar",
        evidence={"k": 1},
    )
    d = h.to_dict()
    assert d["layer"] == "L3"
    assert d["evidence"] == {"k": 1}


# ─── build_summaries_from_events helper ────────────────────────────────────


def test_build_summaries_from_events() -> None:
    flows = [
        (
            BusinessKey(session_id="s1"),
            [
                BusinessFlowEvent(
                    ts=1000, layer="L4", component="session", event_type="session.created", payload={}
                ),
                BusinessFlowEvent(
                    ts=1500,
                    layer="L4",
                    component="session",
                    event_type="session.closed",
                    payload={"status": "closed"},
                ),
            ],
        ),
    ]
    summaries = build_summaries_from_events(flows)
    assert len(summaries) == 1
    assert summaries[0].status == "succeeded"
    assert summaries[0].event_count == 2
