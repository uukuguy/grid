"""EAASP Sessions — sync HTTP client (Phase E.1).

Target backend: grid-server :3001 (NOT L4). grid-server proxies
to L4 internally for the heavy work; the surface exposed to the
React UI and the eaasp-cli-v2 subcommand is grid-server's
/api/v1/sessions/* routes.

Same shape as obstack_client (commit 24): single class, sync
methods that read from the wire format. Tests inject ``http_getter``
in the same way; ``_iscoroutine`` accepts either sync or async
getters (Phase D.4 lesson — the CLI runs inside an asyncio event
loop so a sync callable on the wrong thread path would deadlock).
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from .obstack_client import _iscoroutine  # shared with obstack_client
from .sessions_models import (
    ActiveSessionsResponse,
    ListExecutionsParams,
    SessionInfo,
    StartSessionRequest,
    StartSessionResponse,
)


class SessionsClientError(Exception):
    """Raised on any non-2xx response or transport failure.

    Same exit-code taxonomy as ``obstack_client.ObstackClientError``
    for consistency across the eaasp-client family.
    """

    def __init__(self, status: int, message: str, body: str = "") -> None:
        self.status = status
        self.message = message
        self.body = body
        super().__init__(message)


class SessionsClient:
    """Synchronous client for the grid-server /api/v1/sessions/* surface.

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

    # ─── List / get ──────────────────────────────────────
    def list_active(self) -> ActiveSessionsResponse:
        body = self._get("/api/v1/sessions/active")
        return ActiveSessionsResponse(
            sessions=[SessionInfo(**s) for s in body.get("sessions", [])]
        )

    def get_session(self, session_id: str) -> SessionInfo:
        body = self._get(f"/api/v1/sessions/{session_id}")
        return SessionInfo(**body)

    def list_executions(
        self, session_id: str, params: ListExecutionsParams | None = None
    ) -> Any:
        """GET /api/v1/sessions/{id}/executions — raw wire format.

        Phase E.1 keeps this as a passthrough return because the
        grid-server endpoint returns a top-level JSON array
        (``Json<Vec<ToolExecution>>`` — see
        ``crates/grid-server/src/api/executions.rs``). A future
        commit will add a typed ``ToolExecution`` model when we
        standardize the shape; callers should treat the return as
        ``list[dict[str, Any]]`` for now.

        Note: this method intentionally bypasses ``self._get``'s
        dict-shape contract and returns ``Any`` so the raw list
        doesn't get wrapped in ``{"data": [...]}`` by the fallback
        branch in ``self._request``.
        """
        search: dict[str, str] = {}
        if params is not None:
            search["limit"] = str(params.limit)
        else:
            # OBSTACK Phase E.1 (commit 2/2) — match the ObstackClient
            # ``list_business_flows`` pattern: when the caller omits
            # ``params``, materialize a default so the URL always
            # carries ``?limit=N``. The web client (which goes through
            # the TS mirror that ALWAYS passes ``{limit:100}``) also
            # benefits — the wire shape is deterministic either way.
            search["limit"] = str(ListExecutionsParams().limit)
        url = self.base_url + f"/api/v1/sessions/{session_id}/executions"
        if search:
            url += "?" + urllib.parse.urlencode(search)
        # Use the raw http_getter so we keep the wire shape (a list,
        # not a dict). The shared ``_request`` path wraps non-dict
        # payloads in ``{"data": ...}`` which would lose the array
        # shape callers expect.
        try:
            result: Any = self._http_getter("GET", url, {}, None)
        except SessionsClientError:
            raise  # don't double-wrap
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise SessionsClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            resolved = asyncio.run(result)
            return resolved
        return result

    # ─── Lifecycle ─────────────────────────────────────
    def start_session(self, req: StartSessionRequest) -> StartSessionResponse:
        body = self._post(
            "/api/v1/sessions/start",
            json_data=req.__dict__,
        )
        return StartSessionResponse(session_id=body["session_id"])

    def stop_session(self, session_id: str) -> None:
        """DELETE /api/v1/sessions/{id}/stop — returns 204 on success."""
        self._delete(f"/api/v1/sessions/{session_id}/stop")

    def kill_session(self, session_id: str) -> None:
        """POST /api/v1/sessions/{id}/kill — emergency stop (deprecated
        alias for ``stop_session``; the kill endpoint is used by the
        SessionControls UI and is a true POST for backwards compat).
        """
        self._post(f"/api/v1/sessions/{session_id}/kill", json_data=None)

    def resume_session(self, session_id: str) -> None:
        """POST /api/v1/sessions/{id}/resume — bring a stopped session
        back to running. Returns 204 on success.
        """
        self._post(f"/api/v1/sessions/{session_id}/resume", json_data=None)

    # ─── Internals ─────────────────────────────────────
    def _get(self, path: str, search: dict[str, str] | None = None) -> dict[str, Any]:
        url = self.base_url + path
        if search:
            url += "?" + urllib.parse.urlencode(search)
        return self._request("GET", url)

    def _post(self, path: str, json_data: "dict | None") -> dict[str, Any]:
        url = self.base_url + path
        return self._request("POST", url, json_body=json_data)

    def _delete(self, path: str) -> None:
        url = self.base_url + path
        self._request("DELETE", url, allow_204=True)

    def _request(
        self,
        method: str,
        url: str,
        json_body: "dict | None" = None,
        allow_204: bool = False,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        # Phase E.1 — wrap the injected getter in the same
        # try/except the default transport uses. Tests use raising
        # getters to assert SessionsClientError propagation; without
        # the wrap the HTTPError would leak past _request and the
        # caller would see the raw urllib exception.
        try:
            result = self._http_getter(method, url, headers, json_body)
        except SessionsClientError:
            raise  # don't double-wrap
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise SessionsClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio
            result = asyncio.run(result)
        # 204 No Content — endpoints that mutate state return 204;
        # the caller asked for it explicitly via allow_204=True.
        if allow_204:
            return {}
        if not result:
            # Some GETs return an empty object; treat as a no-op.
            return {}
        if isinstance(result, dict):
            return result
        # Unexpected payload shape — return as-is wrapped in {"data": ...}
        # so callers can still introspect. (Most endpoints return JSON
        # dicts, so this branch is the unusual case.)
        return {"data": result}


# ─── Default HTTP transport (stdlib urllib) ───────────────────


def _default_http_getter(
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: "dict | None",
) -> dict[str, Any]:
    import json
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
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise SessionsClientError(e.code, f"HTTP {e.code} from {url}", body) from e
    except urllib.error.URLError as e:
        raise SessionsClientError(0, f"transport error from {url}: {e.reason}") from e
