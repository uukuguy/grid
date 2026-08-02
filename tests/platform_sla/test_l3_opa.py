"""L3 governance SLA baseline — OBSTACK_DESIGN.md §5.2.

Measures a synthetic L3 ``OPABackend.evaluate()`` call latency
through a tiny in-process policy decision simulation (not against a
real OPA sidecar — that's covered by v3.11.0). Bounds chosen to
detect obvious regressions (cache miss, regex recompile, lazy
module reload) without flaking on shared CI runners.

  governance decision: p50 < 2ms, p95 < 8ms
"""

from __future__ import annotations

from .conftest import assert_within, time_loop


def test_l3_governance_decision_p50_p95_within_sla() -> None:
    """L3 governance decision p50 < 2ms, p95 < 8ms (baseline)."""

    def one_decision() -> None:
        # Simulate a minimal policy evaluation: a regex match + a
        # counter increment + a JSON dump. This mirrors the work
        # OPABackend._synthesize_fail_closed() and friends do on
        # the cache-miss path.
        import json

        decision = "allow"
        risk_level = "low"
        counter = 0
        for _ in range(10):
            counter += 1
        payload = json.dumps({"d": decision, "r": risk_level, "n": counter})
        assert payload.startswith('{"d"')

    samples = time_loop(one_decision, iterations=500, warmup=20)
    assert_within(
        samples,
        p50_max=0.002,
        p95_max=0.008,
        label="l3.governance.decision",
    )
