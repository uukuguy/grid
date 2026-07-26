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

    # ── 3. Register both sessions via /v1/sessions/{id}/validate ───────
    # Security review [Issue 1 / HIGH]: /v1/evaluate no longer accepts
    # free-form session_id — the principal-binding guard requires the
    # session to have been registered at validate time.
    for sess in ("sess_disabled", "sess_disabled_read"):
        validate_resp = await app.post(
            f"/v1/sessions/{sess}/validate",
            json={"agent_id": "*"},
            headers={"X-Session-Scope": "*"},
        )
        assert validate_resp.status_code == 200, validate_resp.text

    # ── 4. Run an in-process gate evaluation through /v1/evaluate ──────
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

    # ── 5. Read risk_level → allow (auto-allowed) ──────────────────────
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
    surfaces as 404 (HookNotFoundError → our global handler maps it
    to a clean 404)."""
    r = await app.put(
        "/v1/policies/managed-hooks",
        json={"hooks": [{"hook_id": "h_real", "phase": "PreToolUse", "mode": "enforce"}]},
    )
    assert r.status_code == 200

    # Register the session so the principal-binding step does not short-circuit
    # with 403 before the hook resolution runs (security review Issue 1).
    validate_resp = await app.post(
        "/v1/sessions/sess_unk/validate",
        json={},
        headers={"X-Session-Scope": "*"},
    )
    assert validate_resp.status_code == 200

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
    # HookNotFoundError → 404 via the global exception handler.
    assert r.status_code == 404


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



# ─── Security [Issue 1 / HIGH] — cross-scope denial at /v1/evaluate ─────────


async def test_evaluate_rejects_unauthenticated_session_id(app):  # type: ignore[no-untyped-def]
    """session_id must have been registered via /v1/sessions/{id}/validate.

    Free-form session_id is no longer accepted by /v1/evaluate. This
    closes the bypass where a non-HTTP caller could mint a session_id
    and get a governance decision without going through validate.
    """
    body = {
        "session_id": "sess_unbound",
        "hook_id": "h_eval",
        "tool_name": "x",
        "risk_level": "read",
        "action_preview": "x",
    }
    resp = await app.post(
        "/v1/evaluate",
        json=body,
        headers={"X-Session-Scope": "tenant_a"},
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["error"] == "forbidden"
    assert "not authenticated" in detail["message"]


async def test_evaluate_rejects_cross_scope_session(app):  # type: ignore[no-untyped-def]
    """A session bound at scope A cannot be evaluated by a caller with scope B.

    Setup: validate registers the session at scope A; the caller
    invokes /v1/evaluate at scope B. The mismatch must deny the
    request (403). This is the cross-tenant isolation guard.
    """
    # Step 1: bind sess_cross to scope=tenant_a via validate.
    deploy_resp = await app.put(
        "/v1/policies/managed-hooks",
        json={"hooks": [{"hook_id": "h_cs", "phase": "PreToolUse", "mode": "shadow"}]},
    )
    assert deploy_resp.status_code == 200

    validate_resp = await app.post(
        "/v1/sessions/sess_cross/validate",
        json={"agent_id": "agent_a"},
        headers={"X-Session-Scope": "tenant_a"},
    )
    assert validate_resp.status_code == 200

    # Step 2: a caller with scope=tenant_b tries to evaluate the same
    # session_id; must be 403.
    body = {
        "session_id": "sess_cross",
        "hook_id": "h_cs",
        "tool_name": "x",
        "risk_level": "read",
        "action_preview": "x",
    }
    resp = await app.post(
        "/v1/evaluate",
        json=body,
        headers={"X-Session-Scope": "tenant_b"},
    )
    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["error"] == "forbidden"
    assert "caller scope" in detail["message"]


async def test_evaluate_rejects_hook_access_scope_mismatch(app):  # type: ignore[no-untyped-def]
    """When a hook declares ``access_scope=tenant_a`` and the caller's
    scope is ``tenant_b``, the request is 403'd even though the
    session_id is valid.

    This is the per-hook scope rule mirroring what /v1/sessions/.../validate
    already enforces (cross-scope hook filtering).
    """
    deploy_resp = await app.put(
        "/v1/policies/managed-hooks",
        json={
            "hooks": [
                {
                    "hook_id": "h_scoped",
                    "phase": "PreToolUse",
                    "mode": "shadow",
                    "access_scope": "tenant_a",
                }
            ]
        },
    )
    assert deploy_resp.status_code == 200

    validate_resp = await app.post(
        "/v1/sessions/sess_scoped/validate",
        json={"agent_id": "agent_a"},
        headers={"X-Session-Scope": "tenant_a"},
    )
    assert validate_resp.status_code == 200

    # The session is bound to tenant_a, but we forge a request with
    # the same session_id and a different scope header. Two distinct
    # failure modes apply here:
    #  - If the caller lies about their scope (``X-Session-Scope: tenant_b``
    #    on a session that was validated under tenant_a), the principal
    #    scope check fires FIRST ("caller scope does not match
    #    authenticated session scope") with status 403.
    body = {
        "session_id": "sess_scoped",
        "hook_id": "h_scoped",
        "tool_name": "x",
        "risk_level": "read",
        "action_preview": "x",
    }
    resp = await app.post(
        "/v1/evaluate",
        json=body,
        headers={"X-Session-Scope": "tenant_b"},
    )
    assert resp.status_code == 403


async def test_evaluate_wildcard_scope_bypasses_hook_scope_check(app):  # type: ignore[no-untyped-def]
    """``X-Session-Scope: *`` (admin / wildcard) bypasses the per-hook
    ``access_scope`` check. This matches the same wildcard carve-out
    that ``/v1/sessions/{id}/validate`` applies for scope=*.
    """
    deploy_resp = await app.put(
        "/v1/policies/managed-hooks",
        json={
            "hooks": [
                {
                    "hook_id": "h_locked",
                    "phase": "PreToolUse",
                    "mode": "shadow",
                    "access_scope": "tenant_a",
                }
            ]
        },
    )
    assert deploy_resp.status_code == 200

    # First bind the session via validate (admin must use * scope there too).
    validate_resp = await app.post(
        "/v1/sessions/sess_locked/validate",
        json={},
        headers={"X-Session-Scope": "*"},
    )
    assert validate_resp.status_code == 200

    # Now evaluate as wildcard — the hook's per-hook access_scope is
    # silently bypassed because the caller is wildcard.
    body = {
        "session_id": "sess_locked",
        "hook_id": "h_locked",
        "tool_name": "x",
        "risk_level": "read",
        "action_preview": "x",
    }
    resp = await app.post(
        "/v1/evaluate",
        json=body,
        headers={"X-Session-Scope": "*"},
    )
    # In-process gate: read risk → 200, allow decision.
    assert resp.status_code == 200, resp.text
    assert resp.json()["decision"] == "allow"


async def test_evaluate_admin_scope_bypasses_hook_scope_check(app):  # type: ignore[no-untyped-def]
    """``X-Session-Scope: admin`` also bypasses the per-hook scope check.

    This is the explicit admin carve-out — operators with the admin
    role need to evaluate hooks regardless of the hook's declared
    ``access_scope`` so that incident-response flows can drill in.
    """
    deploy_resp = await app.put(
        "/v1/policies/managed-hooks",
        json={
            "hooks": [
                {
                    "hook_id": "h_admin",
                    "phase": "PreToolUse",
                    "mode": "shadow",
                    "access_scope": "tenant_a",
                }
            ]
        },
    )
    assert deploy_resp.status_code == 200

    validate_resp = await app.post(
        "/v1/sessions/sess_admin/validate",
        json={},
        headers={"X-Session-Scope": "admin"},
    )
    assert validate_resp.status_code == 200

    body = {
        "session_id": "sess_admin",
        "hook_id": "h_admin",
        "tool_name": "x",
        "risk_level": "read",
        "action_preview": "x",
    }
    resp = await app.post(
        "/v1/evaluate",
        json=body,
        headers={"X-Session-Scope": "admin"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["decision"] == "allow"
