"""EAASP Collaboration — shared response / request models.

Phase E.4 (eaasp-collaboration-client). Mirrors the wire-format
of grid-server's /api/v1/collaboration/* surface, which the
React UI (Collaboration.tsx + ProposalList.tsx) and (future)
eaasp-cli-v2 collab subcommands both consume.

Wire source:
  - crates/grid-server/src/api/collaboration.rs

Phase E.4 lesson from E.1/E.2/E.3 + security fix commit
1787083e: the new client MUST apply the ObstackClient Bearer-
header pattern to every transport method and ``quote(safe='')``
to every path-segment interpolation on first write (not via
follow-up fix). The docstring on each class below marks the
wire contract so the TS mirror stays in lockstep.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ─── Response dataclasses ────────────────────────────────────────────


@dataclass(frozen=True)
class CollaborationStatus:
    """Mirrors ``crates::grid_server::api::collaboration::
    CollaborationStatusResponse`` — GET /api/v1/collaboration/status.

    Wire: dict (NOT top-level array).
    """

    id: str
    agent_count: int = 0
    active_agent: str | None = None
    pending_proposals: int = 0
    event_count: int = 0
    state_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CollaborationAgent:
    """Mirrors ``CollaborationAgentResponse``.

    Wire: returned as a JSON array via GET
    /api/v1/collaboration/agents.
    """

    id: str
    name: str
    capabilities: list[str] = field(default_factory=list)
    session_id: str = ""


@dataclass(frozen=True)
class CollaborationEvent:
    """Mirrors ``CollaborationEventResponse``.

    The wire shape uses ``#[serde(flatten)] pub event: Value`` —
    every event field (type / timestamp / payload / etc.) lives
    at the top level, NOT under an ``event`` key. The legacy TS
    UI unwrapped ``e.event ?? e`` to handle both shapes (some
    callers serialized the value as a nested object, others
    flattened). The Python mirror preserves the dict shape so
    the TS client can do the same.
    """

    event: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Vote:
    """Mirrors ``VoteResponse``.

    Each ``proposal.votes`` row.
    """

    agent_id: str
    approve: bool
    reason: str | None = None


@dataclass(frozen=True)
class Proposal:
    """Mirrors ``ProposalResponse``.

    Wire: returned as a JSON array via GET
    /api/v1/collaboration/proposals.
    """

    id: str
    from_agent: str
    action: str
    description: str
    status: str
    votes: list[Vote] = field(default_factory=list)


@dataclass(frozen=True)
class SharedStateEntry:
    """Mirrors ``SharedStateEntry``."""

    key: str
    value: Any = None


@dataclass(frozen=True)
class SharedStateResponse:
    """Mirrors ``SharedStateResponse`` — GET
    /api/v1/collaboration/shared-state.

    Wire: dict (NOT top-level array) — wrapped object so we
    don't strip the ``entries: ...`` field.
    """

    entries: list[SharedStateEntry] = field(default_factory=list)


# ─── Request dataclasses ─────────────────────────────────────────────


@dataclass(frozen=True)
class CreateProposalRequest:
    """Body of POST /api/v1/collaboration/proposals.

    Mirrors ``CreateProposalRequest``.
    """

    from_agent: str
    action: str
    description: str


@dataclass(frozen=True)
class VoteRequest:
    """Body of POST /api/v1/collaboration/proposals/{id}/vote.

    Mirrors ``VoteRequest``.
    """

    agent_id: str
    approve: bool
    reason: str | None = None
