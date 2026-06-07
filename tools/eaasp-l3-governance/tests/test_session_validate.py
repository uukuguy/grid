"""Contract 5 (partial) — Session validate endpoint tests (via FastAPI app).

Phase 7.3: Added D8 RBAC scope-check + D17 hook_id guard + D18 session_id validation.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio

# Default RBAC header for tests — wildcard scope bypasses all checks.
_SCOPE_HEADER = {"X-Session-Scope": "*"}


async def _deploy(app: AsyncClient, hooks: list[dict]) -> int:
    resp = await app.put(
        "/v1/policies/managed-hooks",
        json={"version": "v2.0.0-mvp", "hooks": hooks},
    )
    assert resp.status_code == 200, resp.text
    return int(resp.json()["version"])


async def test_validate_returns_hooks_matching_agent_id(app: AsyncClient) -> None:
    await _deploy(
        app,
        [
            {
                "hook_id": "h_global",
                "phase": "PostToolUse",
                "mode": "enforce",
                "agent_id": "*",
                "skill_id": "*",
            },
            {
                "hook_id": "h_threshold",
                "phase": "PreToolUse",
                "mode": "enforce",
                "agent_id": "agent_threshold",
                "skill_id": "*",
            },
            {
                "hook_id": "h_other",
                "phase": "PreToolUse",
                "mode": "enforce",
                "agent_id": "agent_somebody_else",
            },
        ],
    )

    resp = await app.post(
        "/v1/sessions/sess_abc/validate",
        json={"agent_id": "agent_threshold", "skill_id": "sk_threshold_v1"},
        headers=_SCOPE_HEADER,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["managed_settings_version"] == 1
    ids = [h["hook_id"] for h in body["hooks_to_attach"]]
    assert set(ids) == {"h_global", "h_threshold"}


async def test_validate_applies_mode_override(app: AsyncClient) -> None:
    await _deploy(
        app,
        [
            {
                "hook_id": "h_audit",
                "phase": "PostToolUse",
                "mode": "enforce",
                "agent_id": "*",
            }
        ],
    )

    # Flip audit hook to shadow.
    resp = await app.put("/v1/policies/h_audit/mode", json={"mode": "shadow"})
    assert resp.status_code == 200

    resp = await app.post(
        "/v1/sessions/s1/validate",
        json={"agent_id": "agent_threshold"},
        headers=_SCOPE_HEADER,
    )
    assert resp.status_code == 200
    hooks = resp.json()["hooks_to_attach"]
    assert len(hooks) == 1
    assert hooks[0]["hook_id"] == "h_audit"
    assert hooks[0]["mode"] == "shadow"  # override applied


async def test_validate_404_when_no_policy(app: AsyncClient) -> None:
    resp = await app.post(
        "/v1/sessions/s1/validate",
        json={"agent_id": "agent_threshold"},
        headers=_SCOPE_HEADER,
    )
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["code"] == "no_policy"


# ─── D8 / L3-04 — RBAC tests ──────────────────────────────────────────────


async def test_validate_rejects_missing_scope_header(app: AsyncClient) -> None:
    resp = await app.post(
        "/v1/sessions/s1/validate",
        json={"agent_id": "agent_threshold"},
        # No X-Session-Scope header
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"]["error"] == "forbidden"
    assert "missing X-Session-Scope" in body["detail"]["message"]


async def test_validate_skips_hook_with_mismatched_scope(app: AsyncClient) -> None:
    await _deploy(
        app,
        [
            {
                "hook_id": "h_ecom",
                "phase": "PostToolUse",
                "mode": "enforce",
                "agent_id": "*",
                "access_scope": "ecommerce",
            },
            {
                "hook_id": "h_fin",
                "phase": "PostToolUse",
                "mode": "enforce",
                "agent_id": "*",
                "access_scope": "finance",
            },
        ],
    )

    # Caller scope=ecommerce — should only see h_ecom, h_fin skipped.
    resp = await app.post(
        "/v1/sessions/s1/validate",
        json={"agent_id": "agent_threshold"},
        headers={"X-Session-Scope": "ecommerce"},
    )
    assert resp.status_code == 200
    hooks = resp.json()["hooks_to_attach"]
    hook_ids = [h["hook_id"] for h in hooks]
    assert hook_ids == ["h_ecom"]


async def test_validate_includes_hook_with_matching_scope(app: AsyncClient) -> None:
    await _deploy(
        app,
        [
            {
                "hook_id": "h_match",
                "phase": "PreToolUse",
                "mode": "enforce",
                "agent_id": "*",
                "access_scope": "ecommerce",
            },
        ],
    )

    resp = await app.post(
        "/v1/sessions/s1/validate",
        json={"agent_id": "agent_threshold"},
        headers={"X-Session-Scope": "ecommerce"},
    )
    assert resp.status_code == 200
    hooks = resp.json()["hooks_to_attach"]
    assert len(hooks) == 1
    assert hooks[0]["hook_id"] == "h_match"


async def test_validate_wildcard_scope_includes_all(app: AsyncClient) -> None:
    await _deploy(
        app,
        [
            {
                "hook_id": "h_ecom",
                "phase": "PostToolUse",
                "mode": "enforce",
                "agent_id": "*",
                "access_scope": "ecommerce",
            },
            {
                "hook_id": "h_fin",
                "phase": "PostToolUse",
                "mode": "enforce",
                "agent_id": "*",
                "access_scope": "finance",
            },
        ],
    )

    resp = await app.post(
        "/v1/sessions/s1/validate",
        json={"agent_id": "agent_threshold"},
        headers={"X-Session-Scope": "*"},
    )
    assert resp.status_code == 200
    hooks = resp.json()["hooks_to_attach"]
    hook_ids = [h["hook_id"] for h in hooks]
    assert set(hook_ids) == {"h_ecom", "h_fin"}


async def test_validate_hook_without_scope_included(app: AsyncClient) -> None:
    await _deploy(
        app,
        [
            {
                "hook_id": "h_no_scope",
                "phase": "PostToolUse",
                "mode": "enforce",
                "agent_id": "*",
                # No access_scope — backward compatible
            },
            {
                "hook_id": "h_scoped",
                "phase": "PostToolUse",
                "mode": "enforce",
                "agent_id": "*",
                "access_scope": "ecommerce",
            },
        ],
    )

    # Caller scope=ecommerce — h_no_scope should pass (no scope = backward compat),
    # h_scoped should also pass (matching scope).
    resp = await app.post(
        "/v1/sessions/s1/validate",
        json={"agent_id": "agent_threshold"},
        headers={"X-Session-Scope": "ecommerce"},
    )
    assert resp.status_code == 200
    hooks = resp.json()["hooks_to_attach"]
    hook_ids = [h["hook_id"] for h in hooks]
    assert set(hook_ids) == {"h_no_scope", "h_scoped"}
