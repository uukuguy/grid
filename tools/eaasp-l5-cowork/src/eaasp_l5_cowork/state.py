"""Cowork card state machine + persistence (v3.13.1).

v3.13.1 — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action /
Approval) + 回溯闭环 (retrospective cycle).

Phase 03.13.1 ships:

- **Card state machine** — every Cowork card carries a state
  (``open`` → ``in_progress`` → ``closed`` or
  ``open`` → ``in_progress`` → ``escalated``). State transitions
  are append-only ledger entries in the L5 SQLite store so the
  Cowork UI can render a card's lifecycle.

- **Five SSE event family members** (D-36 extension):
    * ``cowork.card.<type>.created`` (already shipped in 03.13.0)
    * ``cowork.card.<type>.updated`` (NEW)
    * ``cowork.card.<type>.closed`` (NEW)
    * ``cowork.workflow.advanced`` (NEW — state transition
      notification)
    * ``cowork.workflow.escalated`` (NEW — escalation path)

- **SQLite persistence** — ``cowork_cards`` table (D-30 allows
  new tables ONLY when they live in a tool-local DB, NOT in
  shared L2/L3/L4 stores; the L5 Cowork store is a NEW
  projection-local DB at ``./data/cowork.db``).

State transitions:

- ``open`` → ``in_progress`` (operator / Cowork UI picks the
  card up). Emits ``cowork.card.<type>.updated`` + a
  ``cowork.workflow.advanced`` event with
  ``from_state=open to_state=in_progress``.
- ``in_progress`` → ``closed`` (operator closes the card).
  Emits ``cowork.card.<type>.closed``.
- ``open`` (or ``in_progress``) → ``escalated`` (operator
  escalates the card to a human reviewer). Emits
  ``cowork.card.<type>.updated`` + a
  ``cowork.workflow.escalated`` event.

The state machine is **append-only** — every transition is a
new row in ``cowork_card_transitions`` so the retrospective
trace can show the full card lifecycle (D-32 invariant +
RETROSPECTIVE-04 idempotency).

Frozen contract (audit §7.1): the state machine is best-effort.
Every transition wraps the underlying DB write in a try/except
and logs failures. State transitions NEVER invert an
authoritative L3 audit decision — they only annotate the
Cowork projection.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import aiosqlite


# ─── Card state constants ────────────────────────────────────────────────

STATE_OPEN = "open"
STATE_IN_PROGRESS = "in_progress"
STATE_CLOSED = "closed"
STATE_ESCALATED = "escalated"

ALL_STATES: frozenset[str] = frozenset(
    {STATE_OPEN, STATE_IN_PROGRESS, STATE_CLOSED, STATE_ESCALATED}
)

# ─── Card type constants ─────────────────────────────────────────────────

CARD_EVENT = "event"
CARD_EVIDENCE = "evidence"
CARD_ACTION = "action"
CARD_APPROVAL = "approval"
ALL_CARD_TYPES: frozenset[str] = frozenset(
    {CARD_EVENT, CARD_EVIDENCE, CARD_ACTION, CARD_APPROVAL}
)


# ─── SSE event family (D-36 extension) ──────────────────────────────────

EVENT_CREATED = "cowork.card.{type}.created"
EVENT_UPDATED = "cowork.card.{type}.updated"
EVENT_CLOSED = "cowork.card.{type}.closed"
EVENT_WORKFLOW_ADVANCED = "cowork.workflow.advanced"
EVENT_WORKFLOW_ESCALATED = "cowork.workflow.escalated"


def make_event_name(template: str, card_type: str) -> str:
    """Format a ``cowork.card.<type>.<event>`` SSE event name."""
    if "{type}" not in template:
        return template
    if card_type not in ALL_CARD_TYPES:
        raise ValueError(
            f"unknown card_type {card_type!r}; must be one of "
            f"{sorted(ALL_CARD_TYPES)}"
        )
    return template.replace("{type}", card_type)


# ─── Schema (L5-local — D-30 exception for tool-local stores) ────────────
#
# The D-30 invariant forbids new tables in the SHARED L2 / L3 /
# L4 stores. The Cowork store is a new tool-local DB (no shared
# component touch); the schema is intentionally minimal — every
# row references an underlying L2 / L3 / L4 row by id so the
# projection layer can re-derive the card payload on read
# (idempotent per RETROSPECTIVE-04).


_COWORK_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS cowork_cards (
    card_id       TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL,
    tenant_id     TEXT NOT NULL,
    card_type     TEXT NOT NULL
        CHECK(card_type IN ('event','evidence','action','approval')),
    source_id     TEXT NOT NULL,
    state         TEXT NOT NULL
        CHECK(state IN ('open','in_progress','closed','escalated')),
    summary       TEXT NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_cowork_cards_session
    ON cowork_cards(session_id, state, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cowork_cards_tenant
    ON cowork_cards(tenant_id, updated_at DESC);

-- Append-only state transition log (RETROSPECTIVE-04).
CREATE TABLE IF NOT EXISTS cowork_card_transitions (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id       TEXT NOT NULL,
    from_state    TEXT,
    to_state      TEXT NOT NULL,
    actor         TEXT,
    rationale     TEXT NOT NULL DEFAULT '',
    created_at    INTEGER NOT NULL,
    FOREIGN KEY(card_id) REFERENCES cowork_cards(card_id)
);

CREATE INDEX IF NOT EXISTS idx_cowork_card_transitions_card
    ON cowork_card_transitions(card_id, transition_id);
"""


# ─── Card state dataclass (projection-side) ──────────────────────────────


@dataclass
class CoworkCardState:
    """In-memory snapshot of a Cowork card's state row."""

    card_id: str
    session_id: str
    tenant_id: str
    card_type: str
    source_id: str
    state: str
    summary: str
    created_at: int
    updated_at: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "card_type": self.card_type,
            "source_id": self.source_id,
            "state": self.state,
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass
class CoworkTransition:
    """A single state-transition row."""

    transition_id: int
    card_id: str
    from_state: str | None
    to_state: str
    actor: str | None
    rationale: str
    created_at: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "card_id": self.card_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "actor": self.actor,
            "rationale": self.rationale,
            "created_at": self.created_at,
        }


# ─── State machine errors ────────────────────────────────────────────────


class CoworkStateError(Exception):
    """Base class for state machine failures."""


class CoworkCardNotFound(CoworkStateError):
    """Raised when ``card_id`` is unknown to the state machine."""

    def __init__(self, card_id: str) -> None:
        super().__init__(f"card_id {card_id!r} not found")
        self.card_id = card_id


class CoworkInvalidTransition(CoworkStateError):
    """Raised when a state transition violates the state machine."""

    def __init__(
        self, card_id: str, from_state: str, to_state: str
    ) -> None:
        super().__init__(
            f"invalid transition for {card_id!r}: {from_state!r} -> "
            f"{to_state!r}"
        )
        self.card_id = card_id
        self.from_state = from_state
        self.to_state = to_state


# ─── Valid transition map ────────────────────────────────────────────────


_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    STATE_OPEN: frozenset({STATE_IN_PROGRESS, STATE_CLOSED, STATE_ESCALATED}),
    STATE_IN_PROGRESS: frozenset({STATE_CLOSED, STATE_ESCALATED}),
    STATE_CLOSED: frozenset(),  # terminal
    STATE_ESCALATED: frozenset({STATE_IN_PROGRESS, STATE_CLOSED}),
}


def is_valid_transition(from_state: str, to_state: str) -> bool:
    """True iff ``from_state → to_state`` is allowed by the state machine."""
    return to_state in _VALID_TRANSITIONS.get(from_state, frozenset())


# ─── State store (SQLite-backed) ─────────────────────────────────────────


class CoworkStateStore:
    """SQLite-backed state machine for Cowork cards.

    Mirrors the conventions from ``eaasp_l4_orchestration.db``
    (WAL + foreign_keys + busy_timeout=5000). The state store
    is local to the L5 Cowork tool — it does NOT touch any of
    the L2 / L3 / L4 stores (D-30 invariant).
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def init_db(self) -> None:
        """Create schema if absent (idempotent)."""
        import os

        parent = os.path.dirname(os.path.abspath(self.db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_COWORK_SCHEMA)
            await db.commit()

    async def _open(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    # ─── Create ────────────────────────────────────────────────────────

    async def upsert_card(
        self,
        *,
        card_id: str,
        session_id: str,
        tenant_id: str,
        card_type: str,
        source_id: str,
        summary: str = "",
        metadata: dict[str, Any] | None = None,
        now: int | None = None,
    ) -> CoworkCardState:
        """Create the card row in ``open`` state if it doesn't exist.

        Idempotent on ``card_id`` — a second call with the same
        ``card_id`` is a no-op (the existing row is returned
        unchanged). This lets the SSE bridge call ``upsert_card``
        for every card event without worrying about re-emit.
        """
        if card_type not in ALL_CARD_TYPES:
            raise ValueError(
                f"card_type {card_type!r} not in {sorted(ALL_CARD_TYPES)}"
            )
        ts = now if now is not None else int(time.time())
        db = await self._open()
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT * FROM cowork_cards WHERE card_id = ?",
                    (card_id,),
                )
                row = await cur.fetchone()
                if row is not None:
                    await db.commit()
                    return _row_to_state(row)
                await db.execute(
                    """
                    INSERT INTO cowork_cards
                        (card_id, session_id, tenant_id, card_type,
                         source_id, state, summary, created_at,
                         updated_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        card_id,
                        session_id,
                        tenant_id,
                        card_type,
                        source_id,
                        STATE_OPEN,
                        summary,
                        ts,
                        ts,
                        json.dumps(metadata or {}),
                    ),
                )
                # Initial transition log row (None → open).
                await db.execute(
                    """
                    INSERT INTO cowork_card_transitions
                        (card_id, from_state, to_state, actor,
                         rationale, created_at)
                    VALUES (?, NULL, ?, NULL, ?, ?)
                    """,
                    (card_id, STATE_OPEN, "card created", ts),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        return CoworkCardState(
            card_id=card_id,
            session_id=session_id,
            tenant_id=tenant_id,
            card_type=card_type,
            source_id=source_id,
            state=STATE_OPEN,
            summary=summary,
            created_at=ts,
            updated_at=ts,
            metadata=metadata or {},
        )

    # ─── State transitions ─────────────────────────────────────────────

    async def transition(
        self,
        *,
        card_id: str,
        to_state: str,
        actor: str | None = None,
        rationale: str = "",
        now: int | None = None,
    ) -> tuple[CoworkCardState, CoworkTransition]:
        """Move the card to ``to_state``.

        Returns the updated ``CoworkCardState`` + the new
        ``CoworkTransition`` row. Raises
        ``CoworkCardNotFound`` when the card is unknown,
        ``CoworkInvalidTransition`` when the transition is not
        allowed by the state machine.
        """
        if to_state not in ALL_STATES:
            raise ValueError(
                f"to_state {to_state!r} not in {sorted(ALL_STATES)}"
            )
        ts = now if now is not None else int(time.time())
        db = await self._open()
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT * FROM cowork_cards WHERE card_id = ?",
                    (card_id,),
                )
                row = await cur.fetchone()
                if row is None:
                    await db.rollback()
                    raise CoworkCardNotFound(card_id)
                current = _row_to_state(row)
                if not is_valid_transition(current.state, to_state):
                    await db.rollback()
                    raise CoworkInvalidTransition(
                        card_id, current.state, to_state
                    )
                await db.execute(
                    """
                    UPDATE cowork_cards
                       SET state = ?, updated_at = ?
                     WHERE card_id = ?
                    """,
                    (to_state, ts, card_id),
                )
                cur = await db.execute(
                    """
                    INSERT INTO cowork_card_transitions
                        (card_id, from_state, to_state, actor,
                         rationale, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (card_id, current.state, to_state, actor, rationale, ts),
                )
                transition_id = int(cur.lastrowid or 0)
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        updated = CoworkCardState(
            card_id=current.card_id,
            session_id=current.session_id,
            tenant_id=current.tenant_id,
            card_type=current.card_type,
            source_id=current.source_id,
            state=to_state,
            summary=current.summary,
            created_at=current.created_at,
            updated_at=ts,
            metadata=current.metadata,
        )
        transition = CoworkTransition(
            transition_id=transition_id,
            card_id=card_id,
            from_state=current.state,
            to_state=to_state,
            actor=actor,
            rationale=rationale,
            created_at=ts,
        )
        return updated, transition

    # ─── Read ──────────────────────────────────────────────────────────

    async def list_cards(
        self, session_id: str, *, tenant_id: str | None = None
    ) -> list[CoworkCardState]:
        """Return every Cowork card for the session, tenant-bound."""
        db = await self._open()
        try:
            cur = await db.execute(
                """
                SELECT * FROM cowork_cards
                WHERE session_id = ?
                  AND (? IS NULL OR tenant_id = ?)
                ORDER BY updated_at DESC, card_id ASC
                """,
                (session_id, tenant_id, tenant_id),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()
        return [_row_to_state(r) for r in rows]

    async def list_transitions(
        self, card_id: str
    ) -> list[CoworkTransition]:
        """Return the full transition log for a card (append-only)."""
        db = await self._open()
        try:
            cur = await db.execute(
                """
                SELECT * FROM cowork_card_transitions
                WHERE card_id = ?
                ORDER BY transition_id ASC
                """,
                (card_id,),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()
        return [_row_to_transition(r) for r in rows]


# ─── Internal row converters ─────────────────────────────────────────────


def _row_to_state(row: Any) -> CoworkCardState:
    """Map a ``cowork_cards`` row to a dataclass."""
    raw_meta = row["metadata_json"]
    metadata = json.loads(raw_meta) if raw_meta else {}
    return CoworkCardState(
        card_id=str(row["card_id"]),
        session_id=str(row["session_id"]),
        tenant_id=str(row["tenant_id"]),
        card_type=str(row["card_type"]),
        source_id=str(row["source_id"]),
        state=str(row["state"]),
        summary=str(row["summary"] or ""),
        created_at=int(row["created_at"]),
        updated_at=int(row["updated_at"]),
        metadata=metadata,
    )


def _row_to_transition(row: Any) -> CoworkTransition:
    """Map a ``cowork_card_transitions`` row to a dataclass."""
    return CoworkTransition(
        transition_id=int(row["transition_id"]),
        card_id=str(row["card_id"]),
        from_state=row["from_state"],
        to_state=str(row["to_state"]),
        actor=row["actor"],
        rationale=str(row["rationale"] or ""),
        created_at=int(row["created_at"]),
    )


__all__ = [
    "ALL_CARD_TYPES",
    "ALL_STATES",
    "CARD_ACTION",
    "CARD_APPROVAL",
    "CARD_EVIDENCE",
    "CARD_EVENT",
    "CoworkCardNotFound",
    "CoworkCardState",
    "CoworkInvalidTransition",
    "CoworkStateError",
    "CoworkStateStore",
    "CoworkTransition",
    "EVENT_CLOSED",
    "EVENT_CREATED",
    "EVENT_UPDATED",
    "EVENT_WORKFLOW_ADVANCED",
    "EVENT_WORKFLOW_ESCALATED",
    "STATE_CLOSED",
    "STATE_ESCALATED",
    "STATE_IN_PROGRESS",
    "STATE_OPEN",
    "is_valid_transition",
    "make_event_name",
]
