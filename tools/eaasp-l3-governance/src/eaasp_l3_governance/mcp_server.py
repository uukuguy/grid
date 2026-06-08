"""EAASP L3 Governance — MCP Server (dual-transport with REST).

Wraps 4 policy tools as MCP tools so L1 runtimes can connect via
ConnectMCP. REST endpoints remain the default for L4 consumers.
Uses SSE transport mounted alongside REST in FastAPI lifespan.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.types import TextContent, Tool

SERVER_NAME = "eaasp-l3-governance"
SERVER_VERSION = "0.1.0"

# ── MCP Tool Manifest ────────────────────────────────────────────────
_TOOL_MANIFEST: list[Tool] = [
    Tool(
        name="deploy_managed_hooks",
        description="Deploy a new managed-settings policy version. Accepts a pre-compiled JSON payload with hooks array.",
        inputSchema={
            "type": "object",
            "properties": {
                "version": {"type": "string", "description": "Caller-supplied semver"},
                "hooks": {
                    "type": "array",
                    "description": "List of ManagedHook definitions",
                    "items": {"type": "object"},
                },
            },
            "required": ["hooks"],
        },
    ),
    Tool(
        name="list_policy_versions",
        description="List deployed policy versions, newest first.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Max versions to return (default 100, max 500)",
                    "default": 100,
                },
            },
        },
    ),
    Tool(
        name="switch_hook_mode",
        description="Switch an individual hook between enforce/shadow mode without bumping the policy version.",
        inputSchema={
            "type": "object",
            "properties": {
                "hook_id": {
                    "type": "string",
                    "description": "Hook identifier from managed-settings",
                },
                "mode": {
                    "type": "string",
                    "enum": ["enforce", "shadow"],
                    "description": "Target mode: enforce or shadow",
                },
            },
            "required": ["hook_id", "mode"],
        },
    ),
    Tool(
        name="validate_session",
        description="Validate a session against the latest policy. Returns hooks_to_attach with mode overrides applied.",
        inputSchema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session identifier"},
                "agent_id": {
                    "type": "string",
                    "description": "Agent wildcard or exact ID",
                },
                "skill_id": {
                    "type": "string",
                    "description": "Skill wildcard or exact ID",
                },
                "runtime_tier": {
                    "type": "string",
                    "description": "Runtime tier designation",
                },
            },
            "required": ["session_id"],
        },
    ),
]

# ── Server Builder ───────────────────────────────────────────────────


def build_server(db_path: str) -> tuple[Server, str]:
    """Build an MCP Server with 4 policy tools wired to PolicyEngine.

    Returns (server, resolved_db_path) — testable without HTTP.
    """
    server = Server(SERVER_NAME)

    # Import here to avoid circular imports at module level
    from .policy_engine import HookNotFoundError, PolicyEngine

    policy = PolicyEngine(db_path)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return list(_TOOL_MANIFEST)

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            result = await _dispatch(policy, name, arguments)
        except HookNotFoundError as exc:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": "not_found", "message": str(exc)},
                        sort_keys=True,
                    ),
                )
            ]
        except ValueError as exc:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": "invalid_argument", "message": str(exc)},
                        sort_keys=True,
                    ),
                )
            ]
        except Exception as exc:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": "internal_error", "message": str(exc)[:500]},
                        sort_keys=True,
                    ),
                )
            ]
        return [
            TextContent(
                type="text",
                text=json.dumps(result, sort_keys=True, separators=(",", ":")),
            )
        ]

    return server, db_path


async def _dispatch(
    policy: Any,  # PolicyEngine
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch MCP tool name → PolicyEngine method call."""
    from pydantic import ValidationError

    from .managed_settings import ManagedSettings

    if name == "deploy_managed_hooks":
        try:
            settings = ManagedSettings.model_validate(arguments)
        except ValidationError as exc:
            from eaasp_common.errors import sanitize_errors

            raise ValueError(json.dumps(sanitize_errors(exc.errors()))) from exc
        result = await policy.deploy(settings)
        return result.model_dump()

    elif name == "list_policy_versions":
        limit = arguments.get("limit", 100)
        versions = await policy.list_versions(limit=int(limit))
        return {"versions": [v.model_dump() for v in versions]}

    elif name == "switch_hook_mode":
        hook_id = str(arguments["hook_id"])
        mode = str(arguments["mode"])
        result = await policy.switch_mode(hook_id, mode)
        return result.model_dump()

    elif name == "validate_session":
        session_id = str(arguments["session_id"])
        # Replicate the validate_session logic from api.py:174-240
        latest = await policy.latest_version()
        if latest is None:
            raise ValueError("no managed-settings version has been deployed yet")

        from .managed_settings import hook_matches

        hooks_to_attach: list[dict[str, Any]] = []
        for hook in latest.payload.get("hooks", []):
            agent_id = arguments.get("agent_id")
            skill_id = arguments.get("skill_id")
            if not hook_matches(hook, agent_id, skill_id):
                continue
            hook_id_val = hook.get("hook_id")
            if hook_id_val is None:
                continue
            override = await policy.get_mode_override(hook_id_val)
            merged = dict(hook)
            if override is not None:
                merged["mode"] = override.mode
            hooks_to_attach.append(merged)

        return {
            "session_id": session_id,
            "hooks_to_attach": hooks_to_attach,
            "managed_settings_version": latest.version,
            "validated_at": latest.created_at,
        }

    else:
        raise ValueError(f"unknown tool: {name}")
