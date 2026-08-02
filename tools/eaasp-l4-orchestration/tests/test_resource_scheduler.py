"""Tests for resource_scheduler.py — V315-OPT-03 dry-run scheduling.

The scheduler is a pure function over ``flow_evaluator`` report
hints. It proposes actions (mostly ``scale-up``) but does NOT
execute docker / k8s commands — that's deferred to v3.16.
"""

from __future__ import annotations

from eaasp_l4_orchestration.flow_evaluator import OptimizationHint
from eaasp_l4_orchestration.resource_scheduler import (
    ResourceAction,
    aggregate_actions,
    reconcile_actions,
)


def _hint(
    *,
    layer: str = "l3",
    metric: str = "governance.decision.duration",
    severity: str = "warn",
    recommendation: str = "scale L3",
    evidence: dict[str, float] | None = None,
) -> OptimizationHint:
    return OptimizationHint(
        layer=layer,
        metric=metric,
        severity=severity,
        recommendation=recommendation,
        evidence=evidence or {"completion_rate": 0.85},
    )


def _report(hints: list[OptimizationHint]):
    class _R:
        pass

    r = _R()
    r.hints = hints
    return r


def test_empty_report_yields_empty_actions() -> None:
    actions = reconcile_actions(_report([]))
    assert actions == []


def test_l3_governance_warn_hint_becomes_scale_up() -> None:
    """The most common OBSTACK §3.7 example: L3 OPA decision slow
    → recommend L3 scale-up."""
    actions = reconcile_actions(_report([
        _hint(layer="l3", metric="governance.decision.duration",
              severity="warn"),
    ]))
    assert len(actions) == 1
    a = actions[0]
    assert a.layer == "l3"
    assert a.action == "scale-up"
    assert a.dry_run is True
    assert a.trigger_severity == "warn"
    assert a.metric == "governance.decision.duration"


def test_l3_opa_infra_unavailable_hint_becomes_scale_up() -> None:
    actions = reconcile_actions(_report([
        _hint(metric="opa.infra_unavailable", severity="critical"),
    ]))
    assert len(actions) == 1
    assert actions[0].action == "scale-up"


def test_unknown_metric_warn_becomes_noop_with_intent_recorded() -> None:
    """Warn-level hint on an unknown (layer, metric) pair → record
    for ops dashboard without proposing a scale action."""
    actions = reconcile_actions(_report([
        _hint(layer="l1", metric="rust.panic", severity="warn"),
    ]))
    assert len(actions) == 1
    a = actions[0]
    assert a.action == "noop"
    assert a.layer == "l1"


def test_critical_escalation_disabled_keeps_noop() -> None:
    actions = reconcile_actions(
        _report([_hint(severity="critical")]),
        escalate_critical=False,
    )
    assert len(actions) == 1
    assert actions[0].action == "noop"


def test_critical_escalation_default_is_scale_up() -> None:
    actions = reconcile_actions(_report([_hint(severity="critical")]))
    assert actions[0].action == "scale-up"


def test_aggregate_actions_groups_by_layer_action() -> None:
    actions = reconcile_actions(_report([
        _hint(metric="governance.decision.duration", severity="warn"),
        _hint(metric="opa.infra_unavailable", severity="critical"),
        _hint(layer="l2", metric="memory.write.failures", severity="warn"),
    ]))
    grouped = aggregate_actions(actions)
    # l3 hits are scale-up; l2 hit is scale-up.
    assert set(grouped.keys()) == {"l3:scale-up", "l2:scale-up"}
    assert len(grouped["l3:scale-up"]) == 2
    assert len(grouped["l2:scale-up"]) == 1


def test_resource_action_carries_evidence() -> None:
    actions = reconcile_actions(_report([
        _hint(evidence={"completion_rate": 0.75, "interruption_share": 0.6}),
    ]))
    assert actions[0].evidence == {"completion_rate": 0.75,
                                  "interruption_share": 0.6}
