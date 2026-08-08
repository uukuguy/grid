"""EAASP Memories — sync HTTP client (Phase E.5).

Target backend: grid-server :3001 (NOT L4).

Phase E.5 narrow scope — only the two endpoints the React UI
(Memory.tsx) currently consumes:

  - list_memories   (GET /api/v1/memories?limit=&session_id=&q=)
  - working_memory  (GET /api/v1/memories/working)

Both endpoints return ``Json<serde_json::Value>`` on the
server (the wire is untyped). The Python mirror preserves
the dict shape verbatim and exposes typed dataclasses over
the well-known wrap (``{"results": [...]}`` /
``{"blocks": [...]}``).

Pattern (matches the ObstackClient / SessionsClient /
McpClient / TasksClient / CollaborationClient family):
  - Single class, sync methods
  - Injectable ``http_getter`` (test seam — matches the
    4-arg ``install_mock`` fixture pattern)
  - ``_iscoroutine`` accepts either sync or async getters
    (Phase D.4 lesson — CLI runs inside an asyncio event loop)
  - Bearer header is injected on every transport method
    (Phase E.4 lesson — first-write security fix from
    commit 1787083e; never let ``auth_token`` fall through
    ``{}`` to the wire)
  - Query-string parameters are URL-encoded via
    ``urllib.parse.urlencode`` (RFC 3986 standard form,
    matches grid-server's ``axum::extract::Query`` parser)
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from .obstack_client import _iscoroutine
from .memories_models import (
    ListMemoriesParams,
    ListMemoriesResponse,
    WorkingMemoryBlock,
    WorkingMemoryResponse,
)


class MemoriesClientError(Exception):
    """Raised on any non-2xx response or transport failure.

    Same exit-code taxonomy as the prior client families
    (ObstackClientError / SessionsClientError /
    McpClientError / TasksClientError /
    CollaborationClientError).
    """

    def __init__(self, status: int, message: str, body: str = "") -> None:
        self.status = status
        self.message = message
        self.body = body
        super().__init__(message)


class MemoriesClient:
    """Synchronous client for the grid-server /api/v1/memories/*
    surface (Phase E.5 narrow scope).

    Construct with a base URL (e.g. ``http://127.0.0.1:3001`` —
    grid-server's default). Auth token is sent as a Bearer
    header on every request.
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

    # ─── Read surface (E.5 narrow scope) ─────────────────────
    def list_memories(
        self, params: ListMemoriesParams | None = None,
    ) -> ListMemoriesResponse:
        """GET /api/v1/memories?limit=&session_id=&q= —
        wraps ``{"results": [...]}`` into a typed dataclass.

        ``params`` defaults to ``ListMemoriesParams()`` so
        the URL always carries ``?limit=N`` (matches the
        ``ObstackClient.list_business_flows`` /
        ``SessionsClient.list_executions`` pattern — the
        wire shape stays deterministic regardless of
        whether the caller omits ``params``).

        ``params.session_id`` and ``params.q`` are optional
        filters — omitted keys aren't added to the URL
        (matches the legacy UI's behavior of passing
        ``session_id=...`` only when the user picked one).
        """
        # Phase E.5 narrow-scope note: the ``None`` branch +
        # direct attribute access pattern confuses Pyright's
        # optional-member narrowing. Bind once with a
        # non-Optional type via the walrus operator so the
        # rest of the function sees ``params`` as a typed
        # dataclass (not ``None``).
        if params is None:
            params = ListMemoriesParams()
        assert params is not None  # noqa: S101 — narrowed above
        search: dict[str, str] = {"limit": str(params.limit)}
        if params.session_id is not None:
            search["session_id"] = params.session_id
        if params.q is not None:
            search["q"] = params.q
        body = self._get(
            "/api/v1/memories?" + urllib.parse.urlencode(search)
        )
        return ListMemoriesResponse(
            results=list(body.get("results", []) or []),
        )

    def working_memory(self) -> WorkingMemoryResponse:
        """GET /api/v1/memories/working — wraps ``{"blocks":
        [...]}`` into a typed dataclass (each block decoded
        into a ``WorkingMemoryBlock``).

        Server returns ``Json<serde_json::Value>`` on
        error paths (it falls through to a ``{"blocks":
        []}`` envelope on failure per memories.rs line 99).
        ``WorkingMemoryBlock(**row)`` ignores any extra
        fields the server might add in a future wire
        version — additive compatibility.
        """
        body = self._get("/api/v1/memories/working")
        raw_blocks = body.get("blocks", []) or []
        return WorkingMemoryResponse(
            blocks=[WorkingMemoryBlock(**row) for row in raw_blocks],
        )

    # ─── Internals ──────────────────────────────────────────
    def _auth_headers(self) -> dict[str, str]:
        """Build the Bearer auth header dict (E.4 lesson from
        commit 1787083e — first-write security fix; never
        pass ``{}`` here).
        """
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        return {}

    def _get(self, path: str) -> Any:
        url = self.base_url + path
        headers = self._auth_headers()
        try:
            result = self._http_getter("GET", url, headers, None)
        except MemoriesClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise MemoriesClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            result = asyncio.run(result)
        return result or {}


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
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise MemoriesClientError(e.code, f"HTTP {e.code} from {url}", body) from e
    except urllib.error.URLError as e:
        raise MemoriesClientError(0, f"transport error from {url}: {e.reason}") from e
