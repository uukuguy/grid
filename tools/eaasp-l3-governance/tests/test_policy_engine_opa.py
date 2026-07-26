"""Tests for the OPA-backed policy-engine path (v3.11.1 / ADR-V2-034).

Coverage matrix:

- ``opa_enabled`` flag flips when an OPABackend is injected.
- ``evaluate_with_opa`` happy path: OPA returns allow → audit row recorded
  with allow, the OPA reason.
- ``evaluate_with_opa`` approval state: OPA returns approval → audit row
  recorded with ``gate_request`` (the audit shape) and the OPA reason.
- ``evaluate_with_opa`` fail-closed: OPA returns connection-refused →
  audit row recorded with ``deny`` AND the rationale carries the OPA cause
  identifier so postmortem can pivot on it.
- ``evaluate_with_opa`` without an injected backend raises ``RuntimeError``.
- In-process ``evaluate_gate`` continues to work when OPA is enabled
  (engine still exposes both surfaces; the API chooses which to use).
- In-process ``evaluate_gate`` still works when OPA is NOT enabled
  (regression guard for the dev/test path).
- ``evaluate_with_opa`` honors mode override (override > declared) the
  same way ``evaluate_gate`` does.
- ``evaluate_with_opa`` raises ``HookNotFoundError`` for unknown hooks.
- ``evaluate_with_opa`` raises ``ValueError`` for empty inputs BEFORE any
  OPA call (regression guard for the input-validation contract).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from eaasp_l3_governance.audit import AuditStore
from eaasp_l3_governance.opa_backend import (
    OPABackend,
    OPAConfig,
    OPADecision,
)
from eaasp_l3_governance.policy_engine import (
    GateDecision,
    HookNotFoundError,
    PolicyEngine,
)


pytestmark = pytest.mark.asyncio


# ─── Helpers ────────────────────────────────────────────────────────────────


def _settings(hook_id: str = "h_1", mode: str = "enforce") -> "ManagedSettings":  # type: ignore[name-defined]
    from eaasp_l3_governance.managed_settings import ManagedSettings

    return ManagedSettings(
        version="v3.11.1",
        hooks=[{"hook_id": hook_id, "phase": "PreToolUse", "mode": mode}],  # type: ignore[list-item]
    )


def _opa_backend(handler) -> OPABackend:  # type: ignore[no-untyped-def]
    """Build an OPABackend with a mocked httpx client (no real network)."""
    cfg = OPAConfig(
        base_url="http://127.0.0.1:18181",
        timeout_seconds=2.0,
        bundle_dir="/tmp",
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OPABackend(cfg, client=client)


def _ok(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json=payload)


# ─── Flag flip ──────────────────────────────────────────────────────────────


async def test_opa_enabled_is_false_when_no_backend_injected(
    policy_engine: PolicyEngine,
) -> None:
    assert policy_engine.opa_enabled is False


async def test_opa_enabled_is_true_when_backend_injected(
    db_path: str, audit_store: AuditStore,
) -> None:
    async def _h(req: httpx.Request) -> httpx.Response:
        return _ok({"result": {"allow": True, "decision": "allow", "reason": "x", "obligations": []}})

    backend = _opa_backend(_h)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    try:
        assert engine.opa_enabled is True
    finally:
        await backend.aclose()


# ─── Happy path: OPA returns allow ──────────────────────────────────────────


async def test_evaluate_with_opa_allow_persists_audit_row(
    db_path: str, audit_store: AuditStore,
) -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        # OPA REST API wraps the request in {"input": ...}; unpack here
        # so the assertion operates on the inner input shape (not the
        # OPA wire envelope).
        inner = body["input"]
        # Adapter forwards risk_level + mode correctly
        assert inner["risk_level"] == "read"
        assert inner["mode"] == "enforce"
        return _ok(
            {
                "result": {
                    "allow": True,
                    "decision": "allow",
                    "reason": "read risk auto-allowed by rego policy",
                    "obligations": [],
                }
            }
        )

    backend = _opa_backend(handler)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    await engine.deploy(_settings("h_pre", mode="enforce"))

    decision = await engine.evaluate_with_opa(
        session_id="sess_opa_allow",
        hook_id="h_pre",
        tool_name="scada_read_snapshot",
        risk_level="read",
        action_preview="read xfmr-042",
    )
    assert isinstance(decision, GateDecision)
    assert decision.decision == "allow"
    assert "auto-allowed" in decision.rationale

    rows = await audit_store.query_governance_decisions(session_id="sess_opa_allow")
    assert len(rows) == 1
    assert rows[0].decision_id == decision.decision_id
    assert rows[0].decision == "allow"
    assert rows[0].risk_level == "read"
    assert "auto-allowed" in rows[0].rationale
    await backend.aclose()


# ─── Approval state: OPA returns approval → audit row is gate_request ──────


async def test_evaluate_with_opa_approval_maps_to_gate_request(
    db_path: str, audit_store: AuditStore,
) -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok(
            {
                "result": {
                    "allow": False,
                    "decision": "approval",
                    "reason": "write_external requires human review",
                    "obligations": ["notify:admin"],
                }
            }
        )

    backend = _opa_backend(handler)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    await engine.deploy(_settings("h_pre", mode="enforce"))

    decision = await engine.evaluate_with_opa(
        session_id="sess_opa_approval",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="xfmr-042/temperature_limit_c=70.0",
    )
    # OPA's 3-state 'approval' maps to the 4-state audit-shape 'gate_request'
    # so the audit row stays within the DB CHECK constraint. The OPA reason
    # is preserved in the rationale.
    assert decision.decision == "gate_request"
    assert "human review" in decision.rationale

    rows = await audit_store.query_governance_decisions(session_id="sess_opa_approval")
    assert len(rows) == 1
    assert rows[0].decision == "gate_request"
    assert rows[0].risk_level == "write_external"
    await backend.aclose()


# ─── Fail-closed: connection refused → audit row carries infra info ───────


async def test_evaluate_with_opa_fail_closed_records_deny_with_cause(
    db_path: str, audit_store: AuditStore,
) -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=req)

    backend = _opa_backend(handler)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    await engine.deploy(_settings("h_pre", mode="enforce"))

    decision = await engine.evaluate_with_opa(
        session_id="sess_opa_fail",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="xfmr-042/temperature_limit_c=70.0",
    )
    # Fail-closed: deny + the OPA cause identifier in the rationale.
    assert decision.decision == "deny"
    assert "infra_unavailable" in decision.rationale
    assert "opa_connection_refused" in decision.rationale

    rows = await audit_store.query_governance_decisions(session_id="sess_opa_fail")
    assert len(rows) == 1
    # The audit ledger does NOT have an `infra_unavailable` column; the
    # invariant from ADR-V2-034 §4 is "carry the cause in the rationale so
    # the audit row can be filtered by cause in postmortem". Verify the
    # rationale carries the stable cause identifier.
    assert rows[0].decision == "deny"
    assert "opa_connection_refused" in rows[0].rationale
    await backend.aclose()


async def test_evaluate_with_opa_fail_closed_timeout_records_cause(
    db_path: str, audit_store: AuditStore,
) -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timed out", request=req)

    backend = _opa_backend(handler)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    await engine.deploy(_settings("h_pre", mode="enforce"))

    decision = await engine.evaluate_with_opa(
        session_id="sess_opa_timeout",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="x",
    )
    assert decision.decision == "deny"
    assert "opa_timeout" in decision.rationale
    await backend.aclose()


# ─── Mode override semantics ───────────────────────────────────────────────


async def test_evaluate_with_opa_honors_mode_override(
    db_path: str, audit_store: AuditStore,
) -> None:
    """Override > declared: declared enforce → override shadow → request
    to OPA must carry mode='shadow' (not 'enforce')."""
    captured: dict[str, Any] = {}

    async def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.content)
        return _ok({"result": {"allow": True, "decision": "allow", "reason": "shadow ok", "obligations": []}})

    backend = _opa_backend(handler)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    await engine.deploy(_settings("h_pre", mode="enforce"))
    # Flip to shadow via override
    await engine.switch_mode("h_pre", "shadow")

    await engine.evaluate_with_opa(
        session_id="sess_override",
        hook_id="h_pre",
        tool_name="x",
        risk_level="write_external",
        action_preview="x",
    )
    assert captured["body"]["input"]["mode"] == "shadow"
    await backend.aclose()


# ─── Validation guards ────────────────────────────────────────────────────


async def test_evaluate_with_opa_no_backend_raises_runtime_error(
    policy_engine: PolicyEngine,
) -> None:
    await policy_engine.deploy(_settings("h_pre", mode="enforce"))
    with pytest.raises(RuntimeError, match="OPA backend not configured"):
        await policy_engine.evaluate_with_opa(
            session_id="sess_x",
            hook_id="h_pre",
            tool_name="x",
            risk_level="read",
            action_preview="x",
        )


async def test_evaluate_with_opa_unknown_hook_raises(
    db_path: str, audit_store: AuditStore,
) -> None:
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok({"result": {"allow": True, "decision": "allow", "reason": "x", "obligations": []}})

    backend = _opa_backend(handler)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    await engine.deploy(_settings("h_pre", mode="enforce"))

    with pytest.raises(HookNotFoundError):
        await engine.evaluate_with_opa(
            session_id="sess_x",
            hook_id="h_does_not_exist",
            tool_name="x",
            risk_level="read",
            action_preview="x",
        )
    await backend.aclose()


async def test_evaluate_with_opa_empty_inputs_raise_before_opa_call(
    db_path: str, audit_store: AuditStore,
) -> None:
    """Empty inputs must fail BEFORE the OPA call — no audit row, no network."""
    call_count = {"n": 0}

    async def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return _ok({"result": {"allow": True, "decision": "allow", "reason": "x", "obligations": []}})

    backend = _opa_backend(handler)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    await engine.deploy(_settings("h_pre", mode="enforce"))

    bad_inputs = [
        {"session_id": "", "hook_id": "h_pre", "tool_name": "x", "action_preview": "x"},
        {"session_id": "s", "hook_id": "", "tool_name": "x", "action_preview": "x"},
        {"session_id": "s", "hook_id": "h_pre", "tool_name": "", "action_preview": "x"},
        {"session_id": "s", "hook_id": "h_pre", "tool_name": "x", "action_preview": ""},
    ]
    for inputs in bad_inputs:
        with pytest.raises(ValueError):
            await engine.evaluate_with_opa(risk_level="read", **inputs)

    # OPA handler never called; no audit rows
    assert call_count["n"] == 0
    rows = await audit_store.query_governance_decisions(session_id="sess_x")
    assert rows == []
    await backend.aclose()


async def test_evaluate_with_opa_unknown_risk_level_raises_before_opa_call(
    db_path: str, audit_store: AuditStore,
) -> None:
    call_count = {"n": 0}

    async def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return _ok({"result": {"allow": True, "decision": "allow", "reason": "x", "obligations": []}})

    backend = _opa_backend(handler)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    await engine.deploy(_settings("h_pre", mode="enforce"))

    with pytest.raises(ValueError, match="risk_level"):
        await engine.evaluate_with_opa(
            session_id="sess_r",
            hook_id="h_pre",
            tool_name="x",
            risk_level="execute_arbitrary",
            action_preview="x",
        )
    assert call_count["n"] == 0
    await backend.aclose()


# ─── In-process regression: both surfaces coexist ─────────────────────────


async def test_evaluate_gate_still_works_when_opa_enabled(
    db_path: str, audit_store: AuditStore,
) -> None:
    """opa_enabled=True must NOT change the in-process evaluate_gate
    surface — backward compat for callers that bypass the API switch."""
    async def handler(req: httpx.Request) -> httpx.Response:
        return _ok({"result": {"allow": True, "decision": "allow", "reason": "x", "obligations": []}})

    backend = _opa_backend(handler)
    engine = PolicyEngine(db_path, audit_store=audit_store, opa_backend=backend)
    await engine.deploy(_settings("h_pre", mode="enforce"))

    # evaluate_gate uses the in-process matrix (NOT the OPA backend).
    decision = await engine.evaluate_gate(
        session_id="sess_inproc",
        hook_id="h_pre",
        tool_name="x",
        risk_level="write_external",
        action_preview="x",
    )
    assert decision.decision == "gate_request"
    assert decision.rationale == "approval required"
    await backend.aclose()


async def test_evaluate_gate_still_works_when_opa_disabled(
    policy_engine: PolicyEngine,
) -> None:
    """opa_enabled=False (default) regression — in-process path unchanged."""
    assert policy_engine.opa_enabled is False
    await policy_engine.deploy(_settings("h_pre", mode="enforce"))
    decision = await policy_engine.evaluate_gate(
        session_id="sess_inproc2",
        hook_id="h_pre",
        tool_name="x",
        risk_level="read",
        action_preview="x",
    )
    assert decision.decision == "allow"
    assert decision.rationale == "read auto-allowed"
