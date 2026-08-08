"""EAASP Collaboration — sync HTTP client (Phase E.4).

Target backend: grid-server :3001 (NOT L4).

Same pattern as ``obstack_client`` / ``sessions_client`` /
``mcp_client`` / ``tasks_client``:
  - Single class, sync methods
  - Injectable ``http_getter`` (test seam — matches the
    4-arg ``install_mock`` fixture pattern across the family)
  - ``_iscoroutine`` accepts either sync or async getters
    (Phase D.4 lesson — the CLI runs inside an asyncio event
    loop)
  - Returns typed dataclasses; preserves raw-list wire shapes
    via a bypass that avoids the ``_request`` dict-shape wrapping
  - Bearer header is injected on every transport method
    (Phase E.4 lesson — never let the auth-token reach ``{}``
    on its way to the wire, per E.3 security fix commit 1787083e)
  - ``urllib.parse.quote(safe="")`` on every path-segment
    interpolation (Phase E.4 lesson — never allow raw
    task_id / proposal_id input to restructure a URL, per E.3
    security fix commit 1787083e)

Phase E.4 scope:
  - get_status / list_agents / list_events / list_proposals /
    create_proposal / vote_on_proposal / get_shared_state

Wire-shape notes:
  - get_status, create_proposal, vote_on_proposal,
    get_shared_state return DICT-shaped payloads (use
    ``_get`` / ``_post``)
  - list_agents, list_events, list_proposals return TOP-LEVEL
    JSON arrays (use ``_get_array`` to preserve shape)
  - list_events carries ``#[serde(flatten)] event: Value``
    on the server; the Python mirror exposes
    ``event: dict`` to preserve the wire shape verbatim
  - vote_on_proposal is the only path-interpolating mutator
    (``/api/v1/collaboration/proposals/{id}/vote``) — E.4
    applies ``quote(safe="")`` here
"""

from __future__ import annotations

import json
from urllib.parse import quote
from typing import Any

from .obstack_client import _iscoroutine
from .collaboration_models import (
    CollaborationAgent,
    CollaborationEvent,
    CollaborationStatus,
    CreateProposalRequest,
    Proposal,
    SharedStateEntry,
    SharedStateResponse,
    Vote,
    VoteRequest,
)


class CollaborationClientError(Exception):
    """Raised on any non-2xx response or transport failure.

    Same exit-code taxonomy as ``ObstackClientError`` /
    ``SessionsClientError`` / ``McpClientError`` /
    ``TasksClientError``.
    """

    def __init__(self, status: int, message: str, body: str = "") -> None:
        self.status = status
        self.message = message
        self.body = body
        super().__init__(message)


class CollaborationClient:
    """Synchronous client for the grid-server /api/v1/collaboration/*
    surface.

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

    # ─── Status + agents + events + proposals ───────────────
    def get_status(self) -> CollaborationStatus:
        """GET /api/v1/collaboration/status — dict payload."""
        body = self._get("/api/v1/collaboration/status")
        return CollaborationStatus(**body)

    def list_agents(self) -> list[CollaborationAgent]:
        """GET /api/v1/collaboration/agents — top-level JSON array."""
        body = self._get_array("/api/v1/collaboration/agents")
        return [CollaborationAgent(**row) for row in body]

    def list_events(self) -> list[CollaborationEvent]:
        """GET /api/v1/collaboration/events — top-level JSON array.

        Each event in the wire response uses
        ``#[serde(flatten)] event: Value`` on the server, so the
        Python mirror keeps the per-row ``event`` dict field for
        the TS consumer to unwrap (``e.event ?? e``).
        """
        body = self._get_array("/api/v1/collaboration/events")
        return [CollaborationEvent(event=row) for row in body]

    def list_proposals(self) -> list[Proposal]:
        """GET /api/v1/collaboration/proposals — top-level JSON array."""
        body = self._get_array("/api/v1/collaboration/proposals")
        return [
            Proposal(
                id=row["id"],
                from_agent=row["from_agent"],
                action=row["action"],
                description=row["description"],
                status=row["status"],
                votes=[Vote(**v) for v in row.get("votes", [])],
            )
            for row in body
        ]

    # ─── Mutations ─────────────────────────────────────────
    def create_proposal(self, req: CreateProposalRequest) -> Proposal:
        """POST /api/v1/collaboration/proposals — create a proposal.

        Returns the server's persisted ``Proposal`` row.
        """
        body = self._post(
            "/api/v1/collaboration/proposals",
            json_data={
                "from_agent": req.from_agent,
                "action": req.action,
                "description": req.description,
            },
        )
        return Proposal(
            id=body["id"],
            from_agent=body["from_agent"],
            action=body["action"],
            description=body["description"],
            status=body["status"],
            votes=[Vote(**v) for v in body.get("votes", [])],
        )

    def vote_on_proposal(
        self, proposal_id: str, req: VoteRequest,
    ) -> Vote:
        """POST /api/v1/collaboration/proposals/{id}/vote — cast a vote.

        ``proposal_id`` is percent-encoded with ``safe=""`` so
        attacker-supplied input cannot restructure the URL
        (per E.3 path-injection fix on commit 1787083e).
        """
        encoded = quote(proposal_id, safe="")
        body = self._post(
            f"/api/v1/collaboration/proposals/{encoded}/vote",
            json_data={
                "agent_id": req.agent_id,
                "approve": req.approve,
                "reason": req.reason,
            },
        )
        return Vote(**body)

    def get_shared_state(self) -> SharedStateResponse:
        """GET /api/v1/collaboration/shared-state — dict payload,
        unwrapping ``entries`` into a typed dataclass.
        """
        body = self._get("/api/v1/collaboration/shared-state")
        return SharedStateResponse(
            entries=[SharedStateEntry(**row) for row in body.get("entries", [])]
        )

    # ─── Internals ──────────────────────────────────────────
    def _auth_headers(self) -> dict[str, str]:
        """Build the Bearer auth header dict (E.3 lesson: never
        pass ``{}`` here — that's how commit 1787083e had to fix
        the same bug across three client families). Mirrors the
        ``ObstackClient._request`` pattern that already works.
        """
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        return {}

    def _get(self, path: str) -> Any:
        url = self.base_url + path
        headers = self._auth_headers()
        try:
            result = self._http_getter("GET", url, headers, None)
        except CollaborationClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise CollaborationClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            result = asyncio.run(result)
        return result or {}

    def _post(self, path: str, json_data: "dict | None" = None) -> Any:
        url = self.base_url + path
        headers = self._auth_headers()
        try:
            result = self._http_getter("POST", url, headers, json_data)
        except CollaborationClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise CollaborationClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            result = asyncio.run(result)
        return result or {}

    def _get_array(self, path: str) -> list[Any]:
        """Top-level JSON array passthrough (mirrors
        ``SessionsClient.list_executions``,
        ``McpClient.list_servers``, ``TasksClient.list_tasks``
        — the array-shape bypass that avoids the
        ``_request`` dict-shape wrapping). Headers injected
        via ``_auth_headers`` to satisfy the Phase E.4 lesson.
        """
        url = self.base_url + path
        headers = self._auth_headers()
        try:
            result: Any = self._http_getter("GET", url, headers, None)
        except CollaborationClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise CollaborationClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            resolved = asyncio.run(result)
            return resolved
        return result


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
        raise CollaborationClientError(
            e.code, f"HTTP {e.code} from {url}", body,
        ) from e
    except urllib.error.URLError as e:
        raise CollaborationClientError(
            0, f"transport error from {url}: {e.reason}",
        ) from e
