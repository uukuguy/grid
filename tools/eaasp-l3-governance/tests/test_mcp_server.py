"""MCP server wrapper tests — tool manifest, call_tool dispatch, error handling."""

from __future__ import annotations

import json
from typing import Any

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams

from eaasp_l3_governance.mcp_server import (
    SERVER_NAME,
    SERVER_VERSION,
    _TOOL_MANIFEST,
    build_server,
)

pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────


async def _call(
    db_path: str, tool_name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Build a fresh server, invoke a tool, return parsed JSON result."""
    server, _ = build_server(db_path)
    handler = server.request_handlers[CallToolRequest]
    req = CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(name=tool_name, arguments=arguments),
    )
    resp = await handler(req)
    result = resp.root
    assert len(result.content) >= 1
    return json.loads(result.content[0].text)


# ── Identity & Manifest ──────────────────────────────────────────────


def test_server_identity() -> None:
    assert SERVER_NAME == "eaasp-l3-governance"
    assert SERVER_VERSION == "0.1.0"


def test_tool_manifest_exposes_four_tools() -> None:
    names = {tool.name for tool in _TOOL_MANIFEST}
    expected = {
        "deploy_managed_hooks",
        "list_policy_versions",
        "switch_hook_mode",
        "validate_session",
    }
    assert names == expected


def test_tool_manifest_schemas_have_required_fields() -> None:
    by_name = {tool.name: tool for tool in _TOOL_MANIFEST}

    deploy = by_name["deploy_managed_hooks"].inputSchema
    assert deploy["required"] == ["hooks"]

    switch = by_name["switch_hook_mode"].inputSchema
    assert set(switch["required"]) == {"hook_id", "mode"}

    validate = by_name["validate_session"].inputSchema
    assert validate["required"] == ["session_id"]


def test_build_server_returns_configured_instance(db_path: str) -> None:
    server, resolved = build_server(db_path)
    assert server.name == SERVER_NAME
    assert resolved == db_path


# ── call_tool dispatch ───────────────────────────────────────────────


async def test_call_tool_deploy_and_list(db_path: str) -> None:
    """Deploy a policy via call_tool, then list versions."""
    deploy_data = await _call(
        db_path,
        "deploy_managed_hooks",
        {
            "version": "v1.0.0",
            "hooks": [
                {"hook_id": "h1", "phase": "PostToolUse", "mode": "enforce"},
                {"hook_id": "h2", "phase": "PreToolUse", "mode": "shadow"},
            ],
        },
    )
    assert deploy_data["version"] == 1
    assert deploy_data["hook_count"] == 2
    assert deploy_data["mode_summary"] == {"enforce": 1, "shadow": 1}
    assert deploy_data["created_at"]  # non-empty

    list_data = await _call(db_path, "list_policy_versions", {"limit": 10})
    assert len(list_data["versions"]) == 1
    assert list_data["versions"][0]["version"] == 1


async def test_call_tool_switch_mode_round_trip(db_path: str) -> None:
    """Deploy, then switch mode via call_tool, verify override."""
    await _call(
        db_path,
        "deploy_managed_hooks",
        {
            "hooks": [
                {"hook_id": "h_sw", "phase": "PostToolUse", "mode": "enforce"},
            ],
        },
    )
    switch_data = await _call(
        db_path,
        "switch_hook_mode",
        {
            "hook_id": "h_sw",
            "mode": "shadow",
        },
    )
    assert switch_data["hook_id"] == "h_sw"
    assert switch_data["mode"] == "shadow"


async def test_call_tool_switch_mode_unknown_hook_returns_error(db_path: str) -> None:
    """D19: switching unknown hook_id returns error in content, not crash."""
    await _call(
        db_path,
        "deploy_managed_hooks",
        {
            "hooks": [
                {"hook_id": "h_known", "phase": "PostToolUse", "mode": "enforce"}
            ],
        },
    )
    data = await _call(
        db_path,
        "switch_hook_mode",
        {
            "hook_id": "h_unknown",
            "mode": "shadow",
        },
    )
    assert data["error"] == "not_found"


async def test_call_tool_unknown_tool_returns_error(db_path: str) -> None:
    """Unknown tool name returns error, not crash."""
    data = await _call(db_path, "totally_unknown_tool", {})
    assert data["error"] in ("invalid_argument", "internal_error")


async def test_call_tool_validate_session_no_policy_returns_error(db_path: str) -> None:
    """Validate without deployed policy returns error."""
    data = await _call(
        db_path,
        "validate_session",
        {
            "session_id": "sess-001",
        },
    )
    assert "error" in data
