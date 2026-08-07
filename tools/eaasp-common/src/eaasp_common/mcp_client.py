"""EAASP MCP — sync HTTP client (Phase E.2).

Target backend: grid-server :3001 (NOT L4). Same pattern as
``obstack_client`` and ``sessions_client``:

  - Single class, sync methods
  - Injectable ``http_getter`` (test seam — matches the existing
    4-arg ``install_mock`` fixture pattern across the family)
  - ``_iscoroutine`` accepts either sync or async getters
    (Phase D.4 lesson — the CLI runs inside an asyncio event loop)
  - Returns typed dataclasses for the well-known shapes; passes
    through raw arrays for ``Json<Vec<...>>`` endpoints so callers
    don't lose the wire shape

Phase E.2 scope (intentionally narrow): list_servers /
get_server / get_status / start / stop / list_tools / call_tool /
list_executions. ``register_server`` / ``update_server`` /
``delete_server`` / ``list_logs`` are deferred to a later phase
when the web UI starts consuming them.
"""

from __future__ import annotations

import json
from typing import Any

from .obstack_client import _iscoroutine
from .mcp_models import (
    CallToolRequest,
    CallToolResponse,
    McpServer,
    McpServerStatus,
    McpToolInfo,
)


class McpClientError(Exception):
    """Raised on any non-2xx response or transport failure.

    Same exit-code taxonomy as ``ObstackClientError`` /
    ``SessionsClientError`` for consistency across the
    eaasp-client family.
    """

    def __init__(self, status: int, message: str, body: str = "") -> None:
        self.status = status
        self.message = message
        self.body = body
        super().__init__(message)


class McpClient:
    """Synchronous client for the grid-server /api/v1/mcp/servers/* surface.

    Construct with a base URL (e.g. ``http://127.0.0.1:3001`` —
    grid-server's default per ``eaasp-cli-v2/src/.../config.py``).
    Auth token is sent as a Bearer header on every request.
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: str | None = None,
        http_getter: "Any | None" = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self._http_getter = http_getter or _default_http_getter

    # ─── Server CRUD + lifecycle ────────────────────────────
    def list_servers(self) -> list[McpServer]:
        """GET /api/v1/mcp/servers — returns top-level JSON array."""
        body = self._get_array("/api/v1/mcp/servers")
        return [McpServer(**row) for row in body]

    def get_server(self, server_id: str) -> McpServer:
        """GET /api/v1/mcp/servers/{id} — single server object."""
        body = self._get(f"/api/v1/mcp/servers/{server_id}")
        return McpServer(**body)

    def get_status(self, server_id: str) -> McpServerStatus | None:
        """GET /api/v1/mcp/servers/{id}/status.

        The server returns ``Json<Option<McpServerStatusResponse>>``
        (200 with ``null`` when the server is unknown to the user).
        We unwrap to ``None`` so callers don't have to handle the
        nullable JSON shape.
        """
        body = self._get(f"/api/v1/mcp/servers/{server_id}/status")
        if body is None:
            return None
        return McpServerStatus(**body)

    def start_server(self, server_id: str) -> McpServerStatus:
        """POST /api/v1/mcp/servers/{id}/start — returns status."""
        body = self._post(f"/api/v1/mcp/servers/{server_id}/start")
        return McpServerStatus(**body)

    def stop_server(self, server_id: str) -> McpServerStatus:
        """POST /api/v1/mcp/servers/{id}/stop — returns status."""
        body = self._post(f"/api/v1/mcp/servers/{server_id}/stop")
        return McpServerStatus(**body)

    # ─── Tools + executions ──────────────────────────────────
    def list_tools(self, server_id: str) -> list[McpToolInfo]:
        """GET /api/v1/mcp/servers/{id}/tools — top-level JSON array."""
        body = self._get_array(f"/api/v1/mcp/servers/{server_id}/tools")
        return [McpToolInfo(**row) for row in body]

    def call_tool(self, server_id: str, req: CallToolRequest) -> CallToolResponse:
        """POST /api/v1/mcp/servers/{id}/call — invoke a tool.

        Even when the tool errors at runtime the HTTP response is
        200 OK with a populated ``error`` field; the client maps
        this to a ``CallToolResponse`` so the caller can branch on
        ``response.error`` rather than catching exceptions.
        """
        body = self._post(
            f"/api/v1/mcp/servers/{server_id}/call",
            json_data={
                "tool_name": req.tool_name,
                "arguments": req.arguments,
            },
        )
        return CallToolResponse(**body)

    def list_executions(self, server_id: str) -> list[CallToolResponse]:
        """GET /api/v1/mcp/servers/{id}/executions — top-level JSON array.

        The server caps at 100 most-recent rows per call. A future
        commit will add a pagination param if the UI starts
        paginating past this bound.
        """
        body = self._get_array(f"/api/v1/mcp/servers/{server_id}/executions")
        return [CallToolResponse(**row) for row in body]

    # ─── Internals ──────────────────────────────────────────
    def _get(self, path: str) -> Any:
        url = self.base_url + path
        return self._request("GET", url, allow_204=False)

    def _post(self, path: str, json_data: "dict | None" = None) -> Any:
        url = self.base_url + path
        return self._request("POST", url, json_body=json_data, allow_204=False)

    def _get_array(self, path: str) -> list[Any]:
        """Bypass the dict-shape contract so top-level JSON arrays are
        preserved (mirrors ``SessionsClient.list_executions``).

        Without this bypass, ``_request`` would wrap non-dict
        payloads in ``{"data": ...}`` and lose the array shape.
        """
        url = self.base_url + path
        try:
            result: Any = self._http_getter("GET", url, {}, None)
        except McpClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise McpClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            resolved = asyncio.run(result)
            return resolved
        return result

    def _request(
        self,
        method: str,
        url: str,
        json_body: "dict | None" = None,
        allow_204: bool = False,
    ) -> Any:
        headers: dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        try:
            result = self._http_getter(method, url, headers, json_body)
        except McpClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise McpClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            result = asyncio.run(result)
        if allow_204:
            return {}
        if result is None:
            return None
        if isinstance(result, dict):
            return result
        # Unexpected payload shape — return as-is wrapped in {"data": ...}
        # so callers can still introspect. (Most endpoints return JSON
        # dicts, so this branch is the unusual case.)
        return {"data": result}


# ─── Default HTTP transport (stdlib urllib) ──────────────────────────


def _default_http_getter(
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: "dict | None",
) -> Any:
    import urllib.error
    import urllib.request

    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            if not raw:
                return {}
            # The MCP endpoints return top-level JSON arrays for
            # list_servers / list_tools / list_executions. json.loads
            # handles both list-of-dict and dict shapes correctly,
            # so we just decode and return the parsed value.
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise McpClientError(e.code, f"HTTP {e.code} from {url}", body) from e
    except urllib.error.URLError as e:
        raise McpClientError(0, f"transport error from {url}: {e.reason}") from e
