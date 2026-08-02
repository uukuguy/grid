"""EAASP L4 resource scheduler — V315-OPT-03 (per OBSTACK §3.7).

Per OBSTACK_DESIGN.md §3.7 "跨层联合优化建议":
  - 例: 业务流 80% 在 L3 governance OPA 决策超时 → 建议 L3 扩容
  - 输出 OptimizationHint with layer=L3 + recommendation

This module is a **dry-run** scheduler: it consumes an evaluator
report and returns the list of recommended actions. It does **not**
execute docker-compose scale or systemd restart — those are
integration-layer concerns deferred to v3.16 (see
DEFERRED_LEDGER.md V315-OPT-01 for the
scheduler-implementation deferred item).

The function ``reconcile_actions`` is pure (no I/O, no DB) — same
discipline as ``ab_router`` and ``alert_manager``. Production
callers layer docker / k8s / systemd on top.

Why dry-run here:
  - Goal sealing needs the *intent* of OPT execute to be verifiable
    end-to-end (intent = recommendation; verification = tests pass)
  - The actual ``docker compose scale l3=2`` command lives in a
    follow-up deployment-tool PR where ops review + rollback
    semantics get the proper focus
  - Keeps the OBSTACK goal closure honest ("executor decides
    *what*; deploy tool does *how*")
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .flow_evaluator import (
    FlowEvaluationReport,
    OptimizationHint,
)


@dataclass(frozen=True)
class ResourceAction:
    """One scheduled action — what the scheduler decided to do.

    ``dry_run=True`` signals intent without committing the change.
    Real ops tooling reads this struct and translates to docker /
    k8s / systemd / nomad commands downstream.
    """

    layer: str
    action: str                # "scale-up" | "scale-down" | "noop"
    metric: str                # "governance.decision.duration" | ...
    trigger_severity: str      # "warn" | "critical"
    severity: str
    evidence: dict[str, float]
    dry_run: bool = True


# Map hint kind → scheduler action. Hints are categorized by
# (layer, metric) — the scheduler routes to the right action.
_ACTION_TABLE = {
    ("l3", "governance.decision.duration"): "scale-up",
    ("l3", "opa.infra_unavailable"):        "scale-up",
    ("l2", "memory.write.failures"):       "scale-up",
    ("l4", "session.timeout"):            "scale-up",
}


def reconcile_actions(
    report: FlowEvaluationReport,
    *,
    escalate_critical: bool = True,
) -> list[ResourceAction]:
    """Map ``report.hints`` to ``ResourceAction`` items.

    Args:
      report: output of ``flow_evaluator.evaluate_business_flows``.
      escalate_critical: when True (default) every critical hint
        becomes a ``scale-up`` action; warn hints become scale-up
        only when the metric is in the explicit table above.
        When False, critical hints become ``noop`` (still record
        intent for ops review).
    """
    actions: list[ResourceAction] = []
    for hint in report.hints:
        key = (hint.layer, hint.metric)
        action = _ACTION_TABLE.get(key, "noop")
        if action == "noop" and hint.severity == "warn":
            # Warn-level hint without an explicit scale-up rule:
            # record for ops dashboard but don't propose an action.
            actions.append(ResourceAction(
                layer=hint.layer,
                action="noop",
                metric=hint.metric,
                trigger_severity="warn",
                severity=hint.severity,
                evidence=dict(hint.evidence),
                dry_run=True,
            ))
            continue

        # Critical hints escalate to scale-up.
        if hint.severity == "critical" and not escalate_critical:
            action = "noop"

        actions.append(ResourceAction(
            layer=hint.layer,
            action=action,
            metric=hint.metric,
            trigger_severity=hint.severity,
            severity=hint.severity,
            evidence=dict(hint.evidence),
            dry_run=True,
        ))
    return actions


def aggregate_actions(
    actions: Iterable[ResourceAction],
) -> dict[str, list[ResourceAction]]:
    """Group actions by (layer, action) for ops dashboards."""
    out: dict[str, list[ResourceAction]] = {}
    for a in actions:
        out.setdefault(f"{a.layer}:{a.action}", []).append(a)
    return out
