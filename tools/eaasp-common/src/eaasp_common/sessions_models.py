"""EAASP Sessions — shared response models.

Phase E.1 (eaasp-sessions-client). Mirrors the wire-format of
grid-server's /api/v1/sessions/* surface, which the React UI and
the eaasp-cli-v2 session subcommands both consume.

When grid-server changes a field, update this file (and the
TS mirror in web/src/api/sessions_types.ts) so both consumers see
the new shape at the same time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ─── Session shape ────────────────────────────────────────────


@dataclass(frozen=True)
class SessionInfo:
    """One row in /api/v1/sessions/active and the inner ``session``
    field of /api/v1/sessions/{id}.
    """

    id: str
    created_at: str  # ISO-8601 string per grid-server
    status: str  # "running" | "stopped" | "completed" | "failed"


@dataclass(frozen=True)
class ActiveSessionsResponse:
    """Response body of GET /api/v1/sessions/active."""

    sessions: list[SessionInfo] = field(default_factory=list)


@dataclass(frozen=True)
class StartSessionRequest:
    """Body of POST /api/v1/sessions/start.

    ``agent_id`` selects which agent to run. ``input`` is a free-form
    dict that's forwarded to the agent (the exact schema depends on
    the agent type).
    """

    agent_id: str
    input: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StartSessionResponse:
    """Response body of POST /api/v1/sessions/start."""

    session_id: str


# ─── Query params ───────────────────────────────────────────


@dataclass(frozen=True)
class ListExecutionsParams:
    """Query string for GET /api/v1/sessions/{id}/executions.

    Phase E.1 — single field today; the dataclass exists so a future
    pagination/cursor argument lands at the right place.
    """

    limit: int = 100
