"""eaasp-mcp-client tests — mirror test_obstack_client.py / test_sessions_client.py.

Phase E.2. Tests don't hit grid-server; they use an injected
http_getter that returns the parsed wire shape.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from eaasp_common import (
    CallToolRequest,
    CallToolResponse,
    McpClient,
    McpClientError,
    McpServer,
    McpServerStatus,
    McpToolInfo,
)


Handler = Callable[[str, str, dict[str, str], "dict | None"], Any]


def _make_fake_getter(responses: dict[str, Any]) -> Handler:
    """Return a 4-arg handler that maps (method, url, headers, body) → response.

    Mirrors the ObstackClient / SessionsClient test-seam pattern.
    """
    def fake_getter(method, url, headers, json_body):
        if url not in responses:
            raise KeyError(f"unexpected URL: {url}")
        return responses[url]
    return fake_getter


# ─── Models parse correctly ─────────────────────────────────────────


def test_mcp_server_from_dict() -> None:
    s = McpServer(
        id="srv-1",
        name="filesystem",
        source="filesystem-source",
        command="npx",
        args=["-y", "@fs/mcp"],
        transport="stdio",
    )
    assert s.id == "srv-1"
    assert s.transport == "stdio"
    assert s.enabled is True
    assert s.runtime_status == "stopped"


def test_mcp_server_status_from_dict() -> None:
    s = McpServerStatus(
        id="srv-1",
        name="filesystem",
        status="running",
        pid=12345,
        error=None,
        tool_count=4,
    )
    assert s.status == "running"
    assert s.pid == 12345
    assert s.tool_count == 4


def test_mcp_tool_info_from_dict() -> None:
    info = McpToolInfo(
        name="read_file",
        description="Read a file from the filesystem",
        input_schema={"type": "object"},
    )
    assert info.name == "read_file"
    assert info.input_schema == {"type": "object"}


# ─── list_servers (top-level array) ─────────────────────────────────


def test_list_servers_returns_typed_servers() -> None:
    body = [
        {"id": "s1", "name": "fs", "source": "x", "command": "npx", "args": [], "env": {}, "transport": "stdio", "url": None, "enabled": True, "runtime_status": "stopped", "tool_count": 0, "created_at": "t1", "updated_at": "t1"},
        {"id": "s2", "name": "gh", "source": "y", "command": "node", "args": ["x.js"], "env": {}, "transport": "stdio", "url": None, "enabled": True, "runtime_status": "running", "tool_count": 8, "created_at": "t2", "updated_at": "t2"},
    ]
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers": body}
        ),
    )
    servers = c.list_servers()
    assert len(servers) == 2
    assert all(isinstance(s, McpServer) for s in servers)
    assert servers[0].name == "fs"
    assert servers[1].tool_count == 8


# ─── get_server ──────────────────────────────────────────────────────


def test_get_server_returns_single_server() -> None:
    body = {"id": "s1", "name": "fs", "source": "x", "command": "npx"}
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers/s1": body}
        ),
    )
    srv = c.get_server("s1")
    assert isinstance(srv, McpServer)
    assert srv.id == "s1"


# ─── get_status (Json<Option<...>>) ─────────────────────────────────


def test_get_status_returns_status_when_present() -> None:
    body = {"id": "s1", "name": "fs", "status": "running", "pid": 12345, "error": None, "tool_count": 4}
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers/s1/status": body}
        ),
    )
    status = c.get_status("s1")
    assert isinstance(status, McpServerStatus)
    assert status.status == "running"
    assert status.pid == 12345


def test_get_status_returns_none_when_absent() -> None:
    """Server returns ``Json<Option<...>>`` — null payload means
    the server is unknown to the user. The client unwraps ``None``
    so callers don't have to handle the nullable JSON shape.
    """
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers/missing/status": None}
        ),
    )
    status = c.get_status("missing")
    assert status is None


# ─── Lifecycle ───────────────────────────────────────────────────────


def test_start_server_returns_status() -> None:
    body = {"id": "s1", "name": "fs", "status": "running", "pid": 12345, "error": None, "tool_count": 4}
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers/s1/start": body}
        ),
    )
    status = c.start_server("s1")
    assert isinstance(status, McpServerStatus)
    assert status.status == "running"


def test_stop_server_returns_status() -> None:
    body = {"id": "s1", "name": "fs", "status": "stopped", "pid": None, "error": None, "tool_count": 4}
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers/s1/stop": body}
        ),
    )
    status = c.stop_server("s1")
    assert status.status == "stopped"
    assert status.pid is None


# ─── Tools ──────────────────────────────────────────────────────────


def test_list_tools_returns_typed_tools() -> None:
    body = [
        {"name": "read_file", "description": "Read a file", "input_schema": {"type": "object"}, "annotations": None},
        {"name": "write_file", "description": None, "input_schema": {"type": "object"}, "annotations": None},
    ]
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers/s1/tools": body}
        ),
    )
    tools = c.list_tools("s1")
    assert len(tools) == 2
    assert all(isinstance(t, McpToolInfo) for t in tools)
    assert tools[0].name == "read_file"
    assert tools[1].description is None


def test_call_tool_returns_response_with_result() -> None:
    body = {"id": "exec-1", "server_id": "s1", "tool_name": "read_file", "result": {"content": "hello"}, "error": None, "duration_ms": 12, "executed_at": "2026-08-07T00:00:00Z"}
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers/s1/call": body}
        ),
    )
    resp = c.call_tool("s1", CallToolRequest(tool_name="read_file", arguments={"path": "/tmp/x"}))
    assert isinstance(resp, CallToolResponse)
    assert resp.error is None
    assert resp.result == {"content": "hello"}


def test_call_tool_returns_response_with_error() -> None:
    """Tool errors surface as a 200 OK with a populated ``error``
    field — the client maps this to a ``CallToolResponse`` so the
    caller branches on ``response.error`` rather than catching
    exceptions.
    """
    body = {"id": "exec-1", "server_id": "s1", "tool_name": "read_file", "result": None, "error": "permission denied", "duration_ms": 1, "executed_at": "2026-08-07T00:00:00Z"}
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers/s1/call": body}
        ),
    )
    resp = c.call_tool("s1", CallToolRequest(tool_name="read_file", arguments={"path": "/etc/shadow"}))
    assert resp.error == "permission denied"
    assert resp.result is None


# ─── list_executions (top-level array) ──────────────────────────────


def test_list_executions_returns_raw_list() -> None:
    """``Json<Vec<McpToolCallResponse>>`` wire shape — preserve the
    top-level array, return ``CallToolResponse`` instances.
    """
    body = [
        {"id": "e1", "server_id": "s1", "tool_name": "read_file", "result": {"content": "x"}, "error": None, "duration_ms": 5, "executed_at": "t1"},
        {"id": "e2", "server_id": "s1", "tool_name": "write_file", "result": None, "error": "boom", "duration_ms": 1, "executed_at": "t2"},
    ]
    c = McpClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/mcp/servers/s1/executions": body}
        ),
    )
    execs = c.list_executions("s1")
    assert len(execs) == 2
    assert all(isinstance(e, CallToolResponse) for e in execs)
    assert execs[0].tool_name == "read_file"
    assert execs[1].error == "boom"


# ─── Error path ─────────────────────────────────────────────────────


def test_raises_mcp_client_error_on_non_2xx() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 404, "Not Found", msg, None)

    c = McpClient("http://x", http_getter=getter)
    with pytest.raises(McpClientError) as exc:
        c.list_servers()
    assert exc.value.status == 404


def test_raises_mcp_client_error_on_lifecycle_call() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 500, "Server Error", msg, None)

    c = McpClient("http://x", http_getter=getter)
    with pytest.raises(McpClientError) as exc:
        c.start_server("s1")
    assert exc.value.status == 500


# ─── Auth-bypass regression (security fix for commit 822a4a90) ──────


def test_auth_token_reaches_list_servers() -> None:
    """Security fix: ``_get_array`` used to drop the Bearer header
    on ``list_servers`` / ``list_tools`` / ``list_executions``.
    Capture the headers on the wire and assert Bearer is set.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return []

    c = McpClient("http://x", auth_token="SECRET", http_getter=getter)
    c.list_servers()
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}


def test_auth_token_reaches_list_executions() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return []

    c = McpClient("http://x", auth_token="SECRET", http_getter=getter)
    c.list_executions("s1")
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}
