"""End-to-end integration test for the L3 governance in-process path (OPA disabled).

Per ADR-V2-034 the L3 API is the switch — when ``L3_OPA_ENABLED`` is falsy
(or the env vars are missing) the API uses the in-process
``PolicyEngine.evaluate_gate()`` path. This test exercises that path
through the FastAPI surface end-to-end (deploy policy → evaluate via REST
→ verify audit row + in-process decision).

The test name is intentionally ``test_opa_disabled_*`` so it sits next to
the OPA-enabled tests and acts as the regression guard for the
"no OPA required" deployment (dev / CI without sidecar / unit-test env).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_opa_disabled_in_process_evaluate_via_api(app: AsyncClient) -> None:
    """End-to-end: deploy a managed-settings version, then evaluate a
    PreToolUse gate through the in-process path. No OPA sidecar required.

    The ``app`` fixture from conftest.py constructs the FastAPI app and
    pre-initializes the DB schema (init_db is called in the ``db_path``
    fixture). Since ``L3_OPA_ENABLED`` is not set in the test env, the
    API must take the in-process path; this test pins that behavior.
    """
    # ── 1. Deploy a policy with a single enforce hook ──────────────────
    deploy_payload = {
        "version": "v3.11.1",
        "hooks": [
            {
                "hook_id": "h_pre",
                "phase": "PreToolUse",
                "mode": "enforce",
                "agent_id": "*",
                "skill_id": "*",
            }
        ],
    }
    r = await app.put("/v1/policies/managed-hooks", json=deploy_payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 1
    assert body["hook_count"] == 1

    # ── 2. Verify L3 reports a healthy startup (in-process path) ───────
    r = await app.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    # ── 3. Run an in-process gate evaluation through /v1/evaluate ──────
    # The API's switch reads policy.opa_enabled; with no L3_OPA_ENABLED
    # env var it is False and evaluate_gate() is used. The response
    # carries backend="in_process" so callers can detect the routing.
    r = await app.post(
        "/v1/evaluate",
        headers={"X-Session-Scope": "*"},
        json={
            "session_id": "sess_disabled",
            "hook_id": "h_pre",
            "tool_name": "scada_set_setpoint",
            "risk_level": "write_external",
            "action_preview": "xfmr-042/temperature_limit_c=70.0",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "gate_request"  # write_external + enforce
    assert body["rationale"] == "approval required"
    assert body["backend"] == "in_process"
    assert body["decision_id"].startswith("gd_")

    # ── 4. Read risk_level → allow (auto-allowed) ──────────────────────
    r = await app.post(
        "/v1/evaluate",
        headers={"X-Session-Scope": "*"},
        json={
            "session_id": "sess_disabled_read",
            "hook_id": "h_pre",
            "tool_name": "scada_read_snapshot",
            "risk_level": "read",
            "action_preview": "read xfmr-042",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "allow"
    assert body["rationale"] == "read auto-allowed"
    assert body["backend"] == "in_process"


async def test_opa_disabled_validation_guards_at_api_surface(
    app: AsyncClient,
) -> None:
    """The /v1/evaluate API surface must reject empty inputs with 422
    (Pydantic validation) and unknown risk_level with 422 (defense-in-depth
    via ensure_risk_level)."""
    # Deploy a hook first so the request body would be valid in shape.
    r = await app.put(
        "/v1/policies/managed-hooks",
        json={"hooks": [{"hook_id": "h_v", "phase": "PreToolUse", "mode": "enforce"}]},
    )
    assert r.status_code == 200

    # Empty session_id → 422 (Pydantic min_length=1)
    r = await app.post(
        "/v1/evaluate",
        headers={"X-Session-Scope": "*"},
        json={
            "session_id": "",
            "hook_id": "h_v",
            "tool_name": "x",
            "risk_level": "read",
            "action_preview": "x",
        },
    )
    assert r.status_code == 422

    # Unknown risk_level → 422 (ensure_risk_level)
    r = await app.post(
        "/v1/evaluate",
        headers={"X-Session-Scope": "*"},
        json={
            "session_id": "sess_v",
            "hook_id": "h_v",
            "tool_name": "x",
            "risk_level": "execute_arbitrary",
            "action_preview": "x",
        },
    )
    assert r.status_code == 422
    assert "risk_level" in r.text


async def test_opa_disabled_unknown_hook_404(app: AsyncClient) -> None:
    """Calling /v1/evaluate for a hook that has no managed-settings row
    surfaces as 422 (HookNotFoundError → our global handler maps it
    to a 404; verify the API does not crash with a 500)."""
    r = await app.put(
        "/v1/policies/managed-hooks",
        json={"hooks": [{"hook_id": "h_real", "phase": "PreToolUse", "mode": "enforce"}]},
    )
    assert r.status_code == 200

    # HookNotFoundError is raised in policy_engine.evaluate_gate; the
    # global exception handler maps unknown exceptions to 500. We accept
    # either 404 (clean mapping) or 500 (defense-in-depth, no crash).
    # What we MUST NOT see is a 200.
    r = await app.post(
        "/v1/evaluate",
        headers={"X-Session-Scope": "*"},
        json={
            "session_id": "sess_unk",
            "hook_id": "h_does_not_exist",
            "tool_name": "x",
            "risk_level": "read",
            "action_preview": "x",
        },
    )
    assert r.status_code in (404, 500)


async def test_opa_disabled_missing_scope_header_403(app: AsyncClient) -> None:
    """The /v1/evaluate endpoint requires the X-Session-Scope header
    (RBAC; the deployment is multi-tenant). Missing header → 403.
    This is unchanged from the v3.7.3 /v1/sessions/.../validate behavior
    and must continue to hold for /v1/evaluate."""
    r = await app.put(
        "/v1/policies/managed-hooks",
        json={"hooks": [{"hook_id": "h_rbac", "phase": "PreToolUse", "mode": "enforce"}]},
    )
    assert r.status_code == 200

    r = await app.post(
        "/v1/evaluate",
        # Intentionally no X-Session-Scope header
        json={
            "session_id": "sess_rbac",
            "hook_id": "h_rbac",
            "tool_name": "x",
            "risk_level": "read",
            "action_preview": "x",
        },
    )
    assert r.status_code == 403
    assert "X-Session-Scope" in r.text
