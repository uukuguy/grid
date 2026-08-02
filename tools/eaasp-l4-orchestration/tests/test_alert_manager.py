"""Tests for alert_manager.py — V315-OPT-02 alert fan-out."""

from __future__ import annotations

import pytest

from eaasp_l4_orchestration.alert_manager import (
    InMemorySink,
    fire_alerts,
)
from eaasp_l4_orchestration.flow_evaluator import (
    OptimizationHint,
)


def _hint(*, severity: str = "warn", layer: str = "l3", metric: str = "completion",
          recommendation: str = "scale L3") -> OptimizationHint:
    return OptimizationHint(
        layer=layer,
        metric=metric,
        severity=severity,
        recommendation=recommendation,
        evidence={"completion_rate": 0.85},
    )


def _report(hints: list[OptimizationHint]):
    """Build a minimal FlowEvaluationReport-shaped object.

    The fire_alerts helper only reads ``report.hints`` so a
    duck-typed object is enough.
    """

    class _R:
        pass

    r = _R()
    r.hints = hints
    return r


def test_empty_sinks_is_noop() -> None:
    decision = fire_alerts(_report([_hint()]), sinks=[])
    assert decision == 0


def test_empty_hints_is_noop() -> None:
    sink = InMemorySink()
    decision = fire_alerts(_report([]), sinks=[sink])
    assert decision == 0
    assert sink.received == []


def test_warn_hints_forward_with_default_threshold() -> None:
    sink = InMemorySink()
    hints = [_hint(severity="warn"), _hint(severity="critical")]
    decision = fire_alerts(_report(hints), sinks=[sink])
    assert decision == 2
    assert len(sink.received) == 2


def test_info_hints_suppressed_under_warn_threshold() -> None:
    sink = InMemorySink()
    hints = [_hint(severity="info")]
    decision = fire_alerts(_report(hints), sinks=[sink])
    assert decision == 0
    assert sink.received == []


def test_info_hints_forward_under_info_threshold() -> None:
    sink = InMemorySink()
    hints = [_hint(severity="info"), _hint(severity="warn")]
    decision = fire_alerts(
        _report(hints), sinks=[sink], severity_threshold="info"
    )
    assert decision == 2


def test_critical_threshold_filters_out_warn() -> None:
    sink = InMemorySink()
    hints = [_hint(severity="warn"), _hint(severity="critical")]
    decision = fire_alerts(
        _report(hints), sinks=[sink], severity_threshold="critical"
    )
    assert decision == 1
    assert sink.received[0].severity == "critical"


def test_multiple_sinks_each_receive() -> None:
    sink_a, sink_b = InMemorySink(), InMemorySink()
    hints = [_hint(severity="critical")]
    decision = fire_alerts(_report(hints), sinks=[sink_a, sink_b])
    assert decision == 2  # 1 hint × 2 sinks = 2 deliveries
    assert len(sink_a.received) == 1
    assert len(sink_b.received) == 1
    assert sink_a.received[0] is sink_b.received[0]
