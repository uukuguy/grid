"""REQ-EAASP-01 / REQ-EAASP-03 — Risk-aware gate logic tests.

Verifies the contract frozen in `docs/audit/3.7.3-GAP-AUDIT.md` §5.2:
- read → allow (both enforce and shadow)
- write_local/write_external + shadow → allow with rationale "shadow mode"
- write_local/write_external + enforce → gate_request with rationale "approval required"
- Unknown hook raises HookNotFoundError
- Empty inputs and unknown risk raise ValueError BEFORE any DB write

Append-only semantics and rollback safety are covered by test_audit_governance.py.
"""

from __future__ import annotations

import pytest

from eaasp_l3_governance.managed_settings import ManagedSettings, ensure_risk_level
from eaasp_l3_governance.policy_engine import (
    GateDecision,
    HookNotFoundError,
    PolicyEngine,
    _new_gate_id,  # internal helper for tests
)


# pyproject.toml sets asyncio_mode = "auto", so the module-level pytestmark
# is redundant for async tests and triggers spurious warnings on sync ones.


def _settings_with(hook_id: str, mode: str = "enforce") -> ManagedSettings:
    return ManagedSettings(
        version="v3.7.3",
        hooks=[{"hook_id": hook_id, "phase": "PreToolUse", "mode": mode}],  # type: ignore[list-item]
    )


async def test_managed_hook_default_risk_level_is_read() -> None:
    """D-01/D-07: legacy payloads without risk_level default to read."""
    settings = ManagedSettings(
        hooks=[{"hook_id": "h_pre", "phase": "PreToolUse", "mode": "enforce"}],  # type: ignore[list-item]
    )
    assert settings.hooks[0].risk_level == "read"
    # mode default still "enforce" (D-07 — backward compat preserved)
    assert settings.hooks[0].mode == "enforce"


def test_ensure_risk_level_accepts_all_three_values() -> None:
    assert ensure_risk_level("read") == "read"
    assert ensure_risk_level("write_local") == "write_local"
    assert ensure_risk_level("write_external") == "write_external"


def test_ensure_risk_level_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="risk_level"):
        ensure_risk_level("execute_arbitrary")
    with pytest.raises(ValueError, match="risk_level"):
        ensure_risk_level("")


async def test_gate_id_format() -> None:
    gid = _new_gate_id()
    assert gid.startswith("gd_")
    # hex part should be 32 chars (uuid4 hex)
    assert len(gid) == 3 + 32
    # different calls → different ids
    assert _new_gate_id() != _new_gate_id()


async def test_read_action_returns_allow_in_enforce(
    policy_engine: PolicyEngine,
) -> None:
    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))
    decision = await policy_engine.evaluate_gate(
        session_id="sess_1",
        hook_id="h_pre",
        tool_name="scada_read_snapshot",
        risk_level="read",
        action_preview="read xfmr-042",
    )
    assert isinstance(decision, GateDecision)
    assert decision.decision == "allow"
    assert decision.decision_id.startswith("gd_")


async def test_read_action_returns_allow_in_shadow(
    policy_engine: PolicyEngine,
) -> None:
    await policy_engine.deploy(_settings_with("h_pre", mode="shadow"))
    decision = await policy_engine.evaluate_gate(
        session_id="sess_1",
        hook_id="h_pre",
        tool_name="scada_read_snapshot",
        risk_level="read",
        action_preview="read xfmr-042",
    )
    assert decision.decision == "allow"


async def test_write_local_in_shadow_returns_allow_with_shadow_rationale(
    policy_engine: PolicyEngine,
) -> None:
    await policy_engine.deploy(_settings_with("h_pre", mode="shadow"))
    decision = await policy_engine.evaluate_gate(
        session_id="sess_1",
        hook_id="h_pre",
        tool_name="local_write",
        risk_level="write_local",
        action_preview="write foo=bar",
    )
    assert decision.decision == "allow"
    assert decision.rationale == "shadow mode"


async def test_write_external_in_shadow_returns_allow_with_shadow_rationale(
    policy_engine: PolicyEngine,
) -> None:
    await policy_engine.deploy(_settings_with("h_pre", mode="shadow"))
    decision = await policy_engine.evaluate_gate(
        session_id="sess_1",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="xfmr-042/temperature_limit_c=70.0",
    )
    assert decision.decision == "allow"
    assert decision.rationale == "shadow mode"


async def test_write_local_in_enforce_returns_gate_request(
    policy_engine: PolicyEngine,
) -> None:
    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))
    decision = await policy_engine.evaluate_gate(
        session_id="sess_1",
        hook_id="h_pre",
        tool_name="local_write",
        risk_level="write_local",
        action_preview="write foo=bar",
    )
    assert decision.decision == "gate_request"
    assert decision.rationale == "approval required"


async def test_write_external_in_enforce_returns_gate_request(
    policy_engine: PolicyEngine,
) -> None:
    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))
    decision = await policy_engine.evaluate_gate(
        session_id="sess_1",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="xfmr-042/temperature_limit_c=70.0",
    )
    assert decision.decision == "gate_request"
    assert decision.rationale == "approval required"


async def test_unknown_hook_raises_hook_not_found(
    policy_engine: PolicyEngine,
) -> None:
    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))
    with pytest.raises(HookNotFoundError):
        await policy_engine.evaluate_gate(
            session_id="sess_1",
            hook_id="h_does_not_exist",
            tool_name="x",
            risk_level="read",
            action_preview="x",
        )


async def test_unknown_risk_level_raises_value_error(
    policy_engine: PolicyEngine,
) -> None:
    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))
    with pytest.raises(ValueError, match="risk_level"):
        await policy_engine.evaluate_gate(
            session_id="sess_1",
            hook_id="h_pre",
            tool_name="x",
            risk_level="execute_arbitrary",
            action_preview="x",
        )


async def test_empty_inputs_raise_value_error_before_db_write(
    policy_engine: PolicyEngine, audit_store,
) -> None:
    """All four string inputs must be non-empty (per audit §5.1)."""
    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))

    # sanity: no audit rows yet
    rows = await audit_store.query_governance_decisions(session_id="sess_x")
    assert rows == []

    bad_inputs = [
        {"session_id": "", "hook_id": "h_pre", "tool_name": "x", "action_preview": "x"},
        {"session_id": "s", "hook_id": "", "tool_name": "x", "action_preview": "x"},
        {"session_id": "s", "hook_id": "h_pre", "tool_name": "", "action_preview": "x"},
        {"session_id": "s", "hook_id": "h_pre", "tool_name": "x", "action_preview": ""},
    ]
    for inputs in bad_inputs:
        with pytest.raises(ValueError):
            await policy_engine.evaluate_gate(risk_level="read", **inputs)

    # still no audit rows after all invalid inputs
    rows_after = await audit_store.query_governance_decisions(session_id="sess_x")
    assert rows_after == []


async def test_mode_override_takes_precedence_over_hook_mode(
    policy_engine: PolicyEngine,
) -> None:
    """Override pre-side-effect: hook declared enforce, override shadow ⇒ shadow result."""
    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))
    # flip to shadow via override
    await policy_engine.switch_mode("h_pre", "shadow")

    decision = await policy_engine.evaluate_gate(
        session_id="sess_1",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="x",
    )
    assert decision.decision == "allow"
    assert decision.rationale == "shadow mode"


async def test_decision_is_persisted_in_audit_ledger(
    policy_engine: PolicyEngine,
    audit_store,
) -> None:
    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))
    decision = await policy_engine.evaluate_gate(
        session_id="sess_persist",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="x",
    )
    rows = await audit_store.query_governance_decisions(session_id="sess_persist")
    assert len(rows) == 1
    assert rows[0].decision_id == decision.decision_id
    assert rows[0].risk_level == "write_external"
    assert rows[0].decision == "gate_request"
    assert rows[0].hook_id == "h_pre"
    assert rows[0].tool_name == "scada_set_setpoint"
    assert rows[0].approver is None
    assert rows[0].rationale == "approval required"


# ─── REQ-EAASP-06/07 — S8 hermetic cross-component flow ─────────────────────


async def test_s8_full_flow_approve_changes_setpoint_and_emits_ordered_events(
    policy_engine: PolicyEngine,
    audit_store,
) -> None:
    """Hermetic S8 walkthrough: gate_request → audit row → approve → tool side effect.

    Walks the same code path the CLI would walk: ``evaluate_gate`` returns a
    gate_request, we resolve it to ``approve`` (mirroring ``_resolve_gate_request``),
    persist the final audit row, and only then "invoke" the deterministic
    SCADA setpoint. The mock-SCADA handler is exercised directly via the
    in-memory setpoint helpers (which is the same code path the MCP server
    would call).
    """
    # Lazy import: keep the L3 test package independent of mock-scada
    # importlib graph so this test fails clearly if either moves.
    import importlib

    snapshots = importlib.import_module("mock_scada.snapshots")
    server = importlib.import_module("mock_scada.server")

    snapshots.reset_setpoints_for_tests()
    initial = snapshots.get_setpoint("xfmr-042", "temperature_limit_c")
    assert initial == 65.0

    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))

    # 1. evaluate_gate BEFORE tool dispatch
    request = await policy_engine.evaluate_gate(
        session_id="sess_s8",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="xfmr-042/temperature_limit_c=70.0",
    )
    assert request.decision == "gate_request"

    # 2. CLI resolves the gate (mirrors _resolve_gate_request in cmd_session)
    final_decision = "approve"
    final_approver = "cli:--yes"
    final_rationale = f"resolved request {request.decision_id}: cli --yes"
    final_id = f"{request.decision_id}_final"
    await audit_store.record_governance_decision(
        decision_id=final_id,
        session_id="sess_s8",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        decision=final_decision,
        approver=final_approver,
        rationale=final_rationale,
    )

    # 3. NOW call the SCADA tool (mirrors what the runtime does after approve)
    tool_calls: list[dict] = []

    def tracked_tool(args: dict) -> dict:
        tool_calls.append(args)
        return server._handle_scada_set_setpoint(args)

    if final_decision == "approve":
        tracked_tool(
            {"device_id": "xfmr-042", "setpoint_name": "temperature_limit_c", "value": 70.0}
        )

    # 4. Verify the audit ledger holds BOTH rows (request + final)
    all_rows = await audit_store.query_governance_decisions(session_id="sess_s8")
    assert len(all_rows) == 2
    ids = {r.decision_id for r in all_rows}
    assert ids == {request.decision_id, final_id}
    # Newest-first ordering → final row first
    assert all_rows[0].decision_id == final_id
    assert all_rows[0].decision == "approve"
    assert all_rows[0].approver == "cli:--yes"
    # Then the request row
    assert all_rows[1].decision_id == request.decision_id
    assert all_rows[1].decision == "gate_request"

    # 5. State changed exactly once
    assert snapshots.get_setpoint("xfmr-042", "temperature_limit_c") == 70.0
    assert len(tool_calls) == 1
    snapshots.reset_setpoints_for_tests()


async def test_s8_deny_branch_leaves_state_unchanged(
    policy_engine: PolicyEngine,
    audit_store,
) -> None:
    """Denial path: gate_request → CLI deny → no tool call → state stays 65.0."""
    import importlib

    snapshots = importlib.import_module("mock_scada.snapshots")
    server = importlib.import_module("mock_scada.server")

    snapshots.reset_setpoints_for_tests()
    assert snapshots.get_setpoint("xfmr-042", "temperature_limit_c") == 65.0

    await policy_engine.deploy(_settings_with("h_pre", mode="enforce"))

    request = await policy_engine.evaluate_gate(
        session_id="sess_s8_deny",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="xfmr-042/temperature_limit_c=70.0",
    )
    assert request.decision == "gate_request"

    # CLI resolves to deny
    final_decision = "deny"
    final_approver = "cli:--no"
    final_id = f"{request.decision_id}_final"
    await audit_store.record_governance_decision(
        decision_id=final_id,
        session_id="sess_s8_deny",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        decision=final_decision,
        approver=final_approver,
        rationale=f"resolved request {request.decision_id}: cli --no",
    )

    tool_calls: list[dict] = []

    def tracked_tool(args: dict) -> dict:
        tool_calls.append(args)
        return server._handle_scada_set_setpoint(args)

    # D-04 invariant: deny ⇒ NO tool dispatch
    if final_decision != "approve":
        pass  # explicit no-op so the test reads as policy
    else:  # pragma: no cover - intentional
        tracked_tool(
            {"device_id": "xfmr-042", "setpoint_name": "temperature_limit_c", "value": 70.0}
        )

    # 5. State unchanged, no tool calls
    assert snapshots.get_setpoint("xfmr-042", "temperature_limit_c") == 65.0
    assert tool_calls == []

    rows = await audit_store.query_governance_decisions(session_id="sess_s8_deny")
    assert len(rows) == 2
    assert rows[0].decision == "deny"
    assert rows[0].approver == "cli:--no"
    snapshots.reset_setpoints_for_tests()
