"""EAASP L4 alert manager — V315-OPT-02 (per OBSTACK §3.7).

Per OBSTACK_DESIGN.md §3.7 "自动告警":
  - 达成率跌破 90% trigger
  - 输出 OptimizationHint with severity="critical"

This module plugs into the ``flow_evaluator`` pipeline: callers
hand it a ``FlowEvaluationReport`` and a list of ``AlertSink``
implementations; for each ``hints`` entry from the report the
manager forwards the hint's severity + evidence to each sink.

Strict-by-default (ADR-V2-028):
  - Default severity threshold for "fires alert" is ``warn``.
  - Empty sinks list → no-op.
  - Same evaluator thresholds as ``ab_router`` so the 3 executor
    pieces (router / alerts / scheduler) stay coherent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from .flow_evaluator import FlowEvaluationReport, OptimizationHint

DEFAULT_SEVERITY_THRESHOLD = "warn"


class AlertSink(Protocol):
    """Anything that can receive an alert event.

    Production sinks: HTTP webhook to PagerDuty / Slack; stdout JSON
    for ops dashboards; syslog for SIEM. Tests use the in-memory
    ``RecordingSink`` below.
    """

    def send(self, hint: OptimizationHint) -> None:
        """Receive one alert. Implementations should be idempotent —
        re-delivery is expected during HA failover.
        """
        ...


@dataclass
class InMemorySink:
    """Append each hint to an in-memory list. Useful in tests."""

    received: list[OptimizationHint]

    def __init__(self) -> None:
        self.received = []

    def send(self, hint: OptimizationHint) -> None:
        self.received.append(hint)


def fire_alerts(
    report: FlowEvaluationReport,
    *,
    sinks: Iterable[AlertSink],
    severity_threshold: str | None = None,
) -> int:
    """Forward each hint from ``report`` to every sink.

    Args:
      report: output of ``flow_evaluator.evaluate_business_flows``.
      sinks: zero or more sinks; each hint is broadcast to all of
        them. Empty sinks → no-op returns 0.
      severity_threshold: minimum hint severity to forward —
        ``"critical"`` (only critical), ``"warn"`` (warn + critical),
        ``"info"`` (everything). ``None`` defaults to ``DEFAULT_SEVERITY_THRESHOLD``.

    Returns:
      Number of hints forwarded (one hint × each sink = 1 unit;
      we count hint emission, not sink dispatches — a hint with
      2 sinks counts as 2 emissions).
    """
    threshold = severity_threshold or DEFAULT_SEVERITY_THRESHOLD
    severity_order = {"info": 0, "warn": 1, "critical": 2}
    min_level = severity_order.get(threshold.lower(), 1)
    forward_targets = [
        hint for hint in report.hints
        if severity_order.get(hint.severity.lower(), 0) >= min_level
    ]
    target_sinks = list(sinks)
    if not target_sinks or not forward_targets:
        return 0
    for hint in forward_targets:
        for sink in target_sinks:
            sink.send(hint)
    return len(forward_targets) * len(target_sinks)
