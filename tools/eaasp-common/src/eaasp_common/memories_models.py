"""EAASP Memories — shared response / request models.

Phase E.5 (eaasp-memories-client). Mirrors the wire-format of
grid-server's /api/v1/memories surface.

Wire source: ``crates/grid-server/src/api/memories.rs``.

Phase E.5 design note — narrow scope: only the two endpoints
the React UI (Memory.tsx) actually consumes
(``search_memories`` + ``get_working_memory``). The full CRUD
surface (``create_memory``, ``delete_memory``,
``delete_memories_by_filter``, ``get_memory``) is out of
scope here — a future commit may add a fuller
``MemoryClient`` when a second caller (CLI or dashboard)
needs the broader surface.

Both endpoints return ``Json<serde_json::Value>`` on the
server (the wire is untyped). The Python mirror preserves
the dict shape verbatim and exposes typed wrappers via
``ListMemoriesParams`` for the query-string params the UI
currently passes (limit + session_id).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ─── Wire-shape dataclasses ──────────────────────────────────────────


@dataclass(frozen=True)
class ListMemoriesParams:
    """Query string for GET /api/v1/memories.

    Mirrors ``crates::grid_server::api::memories::MemorySearchParams``.
    ``limit`` defaults to 100 (matches the legacy UI's
    hardcoded ``?limit=100`` — see Memory.tsx line 123).
    """

    limit: int = 100
    session_id: str | None = None
    q: str | None = None


@dataclass(frozen=True)
class ListMemoriesResponse:
    """Body of GET /api/v1/memories.

    Server returns ``Json<serde_json::Value>`` shaped as
    ``{"results": [...]}`` (per memories.rs line 61/75). We
    preserve the dict shape verbatim — the entries list may
    be heterogeneous (FTS results vs list results vs
    error placeholders) and the typed projection happens at
    the call site. ``results`` is exposed as a list of dicts
    so callers can narrow per-field.
    """

    results: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class WorkingMemoryBlock:
    """One entry from GET /api/v1/memories/working.

    Server returns ``Json<serde_json::Value>`` shaped as
    ``{"blocks": [...]}`` (per memories.rs line 99). The
    legacy UI types a few fields (id / kind / label /
    value / priority / char_limit / is_readonly) — the
    Python mirror exposes a typed wrapper that the TS
    mirror then projects onto the React props.
    """

    id: str
    kind: str = ""
    label: str = ""
    value: str = ""
    priority: int = 0
    char_limit: int = 0
    is_readonly: bool = False


@dataclass(frozen=True)
class WorkingMemoryResponse:
    """Body of GET /api/v1/memories/working.

    Server returns ``Json<serde_json::Value>`` shaped as
    ``{"blocks": [...]}`` (per memories.rs line 99).
    """

    blocks: list[WorkingMemoryBlock] = field(default_factory=list)
