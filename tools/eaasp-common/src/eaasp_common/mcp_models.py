"""EAASP MCP — shared response / request models.

Phase E.2 (eaasp-mcp-client). Mirrors the wire-format of
grid-server's /api/v1/mcp/servers/* surface, which the React UI
(ServerList.tsx, ToolInvoker.tsx) and (future) eaasp-cli-v2 mcp
subcommands both consume.

When grid-server changes a field, update this file (and the TS
mirror in web/src/api/mcp_types.ts) so both consumers see the new
shape at the same time.

Wire sources:
  - crates/grid-server/src/api/mcp_servers.rs (CRUD + lifecycle)
  - crates/grid-server/src/api/mcp_tools.rs (tool list + call + execs)
  - crates/grid-engine/src/mcp/traits.rs (McpToolInfo core shape)

Note: these dataclasses are Python-only mirrors. They use the
``dict[str, Any]`` convention for ``serde_json::Value`` fields so
callers don't need a separate JSON-equivalent class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ─── Server responses ───────────────────────────────────────────────


@dataclass(frozen=True)
class McpServer:
    """GET /api/v1/mcp/servers / {id} body.

    Mirrors ``crates/grid-server::api::mcp_servers::McpServerResponse``.
    ``args`` and ``env`` are stored as strings on disk; the wire
    response serializes them as structured lists / maps — we keep
    that shape here.
    """

    id: str
    name: str
    source: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    transport: str = "stdio"  # "stdio" | "sse"
    url: str | None = None
    enabled: bool = True
    runtime_status: str = "stopped"  # "stopped" | "running" | "error"
    tool_count: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class McpServerStatus:
    """GET /api/v1/mcp/servers/{id}/status body.

    Mirrors ``crates/grid-server::api::mcp_servers::McpServerStatusResponse``.
    The endpoint returns ``Json<Option<...>>`` — absent servers
    surface as a 200 ``null`` payload, which the client maps to
    ``None``.
    """

    id: str
    name: str
    status: str  # "running" | "stopped" | "error"
    pid: int | None = None
    error: str | None = None
    tool_count: int = 0


# ─── Tool responses ──────────────────────────────────────────────────


@dataclass(frozen=True)
class McpToolInfo:
    """GET /api/v1/mcp/servers/{id}/tools body element.

    Mirrors ``crates/grid-engine::mcp::traits::McpToolInfo``.
    """

    name: str
    description: str | None = None
    input_schema: Any = None  # JSON object (any shape)
    annotations: dict[str, Any] | None = None


@dataclass(frozen=True)
class CallToolRequest:
    """POST /api/v1/mcp/servers/{id}/call body.

    Mirrors ``crates/grid-server::api::mcp_tools::McpToolCallRequest``.
    ``arguments`` is an arbitrary JSON value (the MCP tool's input
    parameter shape varies per tool).
    """

    tool_name: str
    arguments: Any = None


@dataclass(frozen=True)
class CallToolResponse:
    """POST /api/v1/mcp/servers/{id}/call response.

    Mirrors ``crates/grid-server::api::mcp_tools::McpToolCallResponse``.
    Same wire shape is used for GET /api/v1/mcp/servers/{id}/executions.
    """

    id: str
    server_id: str
    tool_name: str
    result: Any | None = None  # JSON value when succeeded
    error: str | None = None  # error string when failed
    duration_ms: int = 0
    executed_at: str = ""


# ─── Lifecycle requests ──────────────────────────────────────────────


@dataclass(frozen=True)
class StartStopResult:
    """Response body of POST /api/v1/mcp/servers/{id}/start + /stop.

    The server returns a generic ``{"id": ..., "status": ...}``
    ``McpServerStatusResponse`` shape on lifecycle mutating calls.
    We re-use ``McpServerStatus`` for this (the fields are the
    same).
    """


# Lifecycle calls reuse McpServerStatus — no separate dataclass.
