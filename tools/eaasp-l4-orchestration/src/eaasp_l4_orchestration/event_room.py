"""Event Room — long-lived coordination namespace spanning multiple sessions.

v3.12.1 — EAASP v2.0 Phase 4 (A2A / Event Room / multi-session).

Spec §4.4 / EVOLUTION_PATH §三 Phase 4 / ADR-V2-024 (engine vs
data/integration 双轴):

- An ``EventRoom`` is a *long-lived* coordination container. Sessions
  (single agent task units) join the room, fan-out events to every
  other member, and leave when they complete. The room outlives any
  individual session and persists its event stream append-only.
- Multi-session coordination lives at L4 (this module). Sessions are
  short-lived; rooms are long-lived. Both share the same SQLite
  append-only event stream (``session_events`` table) but rooms carry
  the additional ``room_id`` metadata so a fan-out consumer can
  distinguish ``governance.session.cross`` events from the canonical
  per-session stream.
- The 5-stage approval chain (``tools/eaasp-l3-governance``) is
  unchanged in this phase. Event rooms cooperate with the chain via
  ``MultiSessionCoordinator.resume_with_human_decision`` which
  accepts a ``principal`` argument and rejects principals that are
  not members of the relevant room (REQ-ROOM-01..03 +
  REQ-COORD-01..02 + REQ-APPROVAL-01..02).

Storage layout (added to ``db.py`` via idempotent ``ALTER TABLE`` +
``CREATE TABLE IF NOT EXISTS`` migration in ``init_db``):

    CREATE TABLE IF NOT EXISTS event_rooms (
        room_id          TEXT PRIMARY KEY,
        tenant_id        TEXT NOT NULL,
        owner_principal  TEXT NOT NULL,
        status           TEXT NOT NULL CHECK(status IN ('open','closed','expired')),
        created_at       INTEGER NOT NULL,
        expires_at       INTEGER NOT NULL,
        closed_at        INTEGER,
        name             TEXT
    );

    CREATE TABLE IF NOT EXISTS event_room_members (
        room_id     TEXT NOT NULL,
        session_id  TEXT NOT NULL,
        principal   TEXT NOT NULL,
        joined_at   INTEGER NOT NULL,
        PRIMARY KEY (room_id, session_id),
        FOREIGN KEY(room_id) REFERENCES event_rooms(room_id)
    );

    CREATE TABLE IF NOT EXISTS event_room_events (
        seq          INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id      TEXT NOT NULL,
        session_id   TEXT NOT NULL,
        event_type   TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at   INTEGER NOT NULL,
        FOREIGN KEY(room_id) REFERENCES event_rooms(room_id)
    );

The room event log is **append-only** (per audit §6.3); the table
schema does NOT allow UPDATE / DELETE and the public API only
exposes ``append_event`` (no overwrite). Indexes on
``(room_id, seq)`` and ``(room_id, session_id, seq)`` support both
the per-room SSE fan-out and the per-room cross-session audit
listing.

v3.12.1 contract:

- ``create(room_id, tenant_id, owner_principal, ...)`` returns
  ``EventRoom`` or raises ``EventRoomAlreadyExists``.
- ``close(room_id, principal)`` flips status to ``closed`` (only
  the owner can close; non-owner calls surface as
  ``EventRoomNotOwned``).
- ``add_member(room_id, session_id, principal)`` appends a member
  row and is idempotent on (room_id, session_id).
- ``remove_member(room_id, session_id, principal)`` deletes the
  member row (the room itself is not destroyed).
- ``list_active(tenant_id)`` returns all rooms with
  ``status='open' AND expires_at > now``. Expired rooms are flipped
  to ``status='expired'`` by ``expire_stale_rooms()``.
- ``fan_out_event(room_id, event_type, payload, origin_session_id)``
  appends ONE row to ``event_room_events`` (NOT one per recipient;
  SSE consumers dispatch per the canonical schema) and returns the
  new seq.

Frozen contract (audit §7.1): event delivery is best-effort and
NEVER inverts the authoritative audit ledger (L3
``governance_decisions`` + L4 ``session_events``). Failures in
``fan_out_event`` are logged and surface as ``None`` to callers.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from .db import connect

# Room status enum (mirrors the CHECK constraint on the table).
STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_EXPIRED = "expired"

_VALID_STATUSES: frozenset[str] = frozenset({STATUS_OPEN, STATUS_CLOSED, STATUS_EXPIRED})


# v3.12.1 — EVENT-ROOM SSE event family. Distinct from the per-session
# governance.* family so SSE consumers can subscribe to room-scoped
# events without re-implementing per-session routing. Spec §4.4
# "Event Room" — fan-out dispatch is a room-scoped event, not a
# per-session replay.
EVENT_ROOM_EVENT_TYPE_PREFIX = "governance.session.cross"


def make_event_room_event_type(event_subtype: str) -> str:
    """Build a canonical room event type (``governance.session.cross.<sub>``).

    The ``subtype`` must be a non-empty slug (lowercase ASCII + dashes).
    The function does NOT validate the slug content beyond
    non-emptiness — callers control the vocabulary and we keep the
    event_room module free of policy coupling.
    """
    if not event_subtype:
        raise ValueError("event_subtype must be a non-empty string")
    return f"{EVENT_ROOM_EVENT_TYPE_PREFIX}.{event_subtype}"


class EventRoomError(Exception):
    """Base class for Event Room failures.

    All public methods raise a subclass of this on validation /
    authorization failures so callers can ``except EventRoomError``
    once and recover.
    """

    def __init__(self, room_id: str, detail: str = "") -> None:
        self.room_id = room_id
        self.detail = detail
        super().__init__(f"event room {room_id}: {detail}".strip())


class EventRoomNotFound(EventRoomError):
    """Raised when the room_id is not present in ``event_rooms``."""


class EventRoomAlreadyExists(EventRoomError):
    """Raised when ``create`` is called with a room_id that already exists."""


class EventRoomNotOpen(EventRoomError):
    """Raised when an operation requires the room to be ``open`` but it isn't."""


class EventRoomNotOwned(EventRoomError):
    """Raised when a privileged operation is attempted by a non-owner."""


@dataclass
class EventRoom:
    """In-memory snapshot of an Event Room row.

    Public surface mirrors the columns of the ``event_rooms`` table
    plus the (lazy) member list. The dataclass is for **read** use
    only; mutating it does not write to the DB. Use
    ``EventRoomStore.add_member`` / ``remove_member`` to update
    membership.
    """

    room_id: str
    tenant_id: str
    owner_principal: str
    status: str
    created_at: int
    expires_at: int
    closed_at: int | None = None
    name: str | None = None
    members: list[str] = field(default_factory=list)

    def is_open(self) -> bool:
        """True iff the room is in the ``open`` state."""
        return self.status == STATUS_OPEN

    def is_expired(self, *, now: int | None = None) -> bool:
        """True iff the room has passed its ``expires_at`` deadline.

        Does NOT mutate the DB — that is the responsibility of
        ``EventRoomStore.expire_stale_rooms``.
        """
        ts = int(now if now is not None else time.time())
        return self.expires_at <= ts


class EventRoomStore:
    """SQLite-backed CRUD for Event Rooms + members + room event log.

    Mirrors the conventions from ``session_orchestrator.py`` and
    ``event_stream.py``:
    - WAL journal mode (set globally in ``db.py``).
    - ``BEGIN IMMEDIATE`` for every write path.
    - ``connect()`` helper for connection acquisition.
    - Input validation BEFORE any DB open.

    The store is intentionally NOT tied to a single FastAPI app
    instance — tests construct one with a ``tmp_db_path`` and run
    against it directly.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    # ─── Create ──────────────────────────────────────────────────────────

    async def create(
        self,
        *,
        room_id: str | None = None,
        tenant_id: str,
        owner_principal: str,
        name: str | None = None,
        ttl_seconds: int = 3600,
        now: int | None = None,
    ) -> EventRoom:
        """Create a new room.

        ``room_id`` defaults to ``er_<uuid4-hex[:16]>``. ``ttl_seconds``
        is clamped to ``[1..86400]`` (1 second .. 1 day) so a
        malformed CLI cannot create rooms that never expire.

        Returns the new ``EventRoom`` snapshot. Raises
        ``EventRoomAlreadyExists`` if ``room_id`` is already in use.
        """
        if not tenant_id:
            raise ValueError("tenant_id must be a non-empty string")
        if not owner_principal:
            raise ValueError("owner_principal must be a non-empty string")
        if name is not None and not isinstance(name, str):
            raise ValueError("name must be a string or None")
        safe_ttl = _clamp_ttl(ttl_seconds)

        final_room_id = room_id if room_id else f"er_{uuid.uuid4().hex[:16]}"
        if not final_room_id:
            raise ValueError("room_id must be a non-empty string")

        ts = int(now if now is not None else time.time())
        expires_at = ts + safe_ttl

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT 1 FROM event_rooms WHERE room_id = ?",
                    (final_room_id,),
                )
                row = await cur.fetchone()
                if row is not None:
                    await db.rollback()
                    raise EventRoomAlreadyExists(
                        final_room_id,
                        "room_id already exists",
                    )
                await db.execute(
                    """
                    INSERT INTO event_rooms
                        (room_id, tenant_id, owner_principal, status,
                         created_at, expires_at, name)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        final_room_id,
                        tenant_id,
                        owner_principal,
                        STATUS_OPEN,
                        ts,
                        expires_at,
                        name,
                    ),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        return EventRoom(
            room_id=final_room_id,
            tenant_id=tenant_id,
            owner_principal=owner_principal,
            status=STATUS_OPEN,
            created_at=ts,
            expires_at=expires_at,
            closed_at=None,
            name=name,
            members=[],
        )

    # ─── Get ─────────────────────────────────────────────────────────────

    async def get(self, room_id: str) -> EventRoom | None:
        """Return an ``EventRoom`` snapshot or ``None`` if absent.

        Membership is loaded lazily (``list_members``) — the
        snapshot returned by ``get`` does NOT include members by
        default to keep the cheap path cheap. Callers needing the
        member list should call ``list_members(room_id)`` separately.
        """
        if not room_id:
            raise ValueError("room_id must be a non-empty string")

        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT room_id, tenant_id, owner_principal, status,
                       created_at, expires_at, closed_at, name
                FROM event_rooms WHERE room_id = ?
                """,
                (room_id,),
            )
            row = await cur.fetchone()
        finally:
            await db.close()

        if row is None:
            return None
        return _row_to_event_room(row, members=[])

    # ─── Close ───────────────────────────────────────────────────────────

    async def close(self, room_id: str, principal: str) -> EventRoom:
        """Close the room. Only the owner may close.

        Sets ``status='closed'`` and ``closed_at=now``. Returns the
        refreshed snapshot. Idempotent: closing an already-closed
        room is a no-op that returns the existing snapshot (no
        error). Raises ``EventRoomNotFound`` if the room does not
        exist; ``EventRoomNotOwned`` if the principal is not the
        owner.
        """
        if not room_id:
            raise ValueError("room_id must be a non-empty string")
        if not principal:
            raise ValueError("principal must be a non-empty string")

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    """
                    SELECT room_id, tenant_id, owner_principal, status,
                           created_at, expires_at, closed_at, name
                    FROM event_rooms WHERE room_id = ?
                    """,
                    (room_id,),
                )
                row = await cur.fetchone()
                if row is None:
                    await db.rollback()
                    raise EventRoomNotFound(room_id, "no such room")
                if row["owner_principal"] != principal:
                    await db.rollback()
                    raise EventRoomNotOwned(
                        room_id,
                        f"principal {principal!r} is not the owner",
                    )
                if row["status"] == STATUS_CLOSED:
                    await db.commit()
                    return _row_to_event_room(row, members=[])
                ts = int(time.time())
                await db.execute(
                    """
                    UPDATE event_rooms
                       SET status = ?, closed_at = ?
                     WHERE room_id = ?
                    """,
                    (STATUS_CLOSED, ts, room_id),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        # Re-read for the canonical closed row.
        refreshed = await self.get(room_id)
        assert refreshed is not None
        return refreshed

    # ─── Membership ──────────────────────────────────────────────────────

    async def add_member(
        self, room_id: str, session_id: str, principal: str
    ) -> bool:
        """Bind a session to a room. Idempotent on (room_id, session_id).

        ``principal`` is the human/service principal who authorizes
        the bind (recorded for audit but NOT enforced as a join
        gate; the room owner / session orchestrator are the join
        gates in the v3.12.1 contract). Returns ``True`` if a new
        row was inserted, ``False`` if the (room_id, session_id)
        pair was already present.

        Raises ``EventRoomNotFound`` if the room does not exist;
        ``EventRoomNotOpen`` if the room is closed / expired.
        """
        if not room_id:
            raise ValueError("room_id must be a non-empty string")
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not principal:
            raise ValueError("principal must be a non-empty string")

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    "SELECT status FROM event_rooms WHERE room_id = ?",
                    (room_id,),
                )
                row = await cur.fetchone()
                if row is None:
                    await db.rollback()
                    raise EventRoomNotFound(room_id, "no such room")
                if row["status"] != STATUS_OPEN:
                    await db.rollback()
                    raise EventRoomNotOpen(
                        room_id,
                        f"room status is {row['status']!r}, not 'open'",
                    )

                # Idempotent insert: ON CONFLICT DO NOTHING. We then
                # read the inserted-or-existing row to know whether a
                # new row was created.
                ts = int(time.time())
                cur = await db.execute(
                    """
                    INSERT INTO event_room_members
                        (room_id, session_id, principal, joined_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(room_id, session_id) DO NOTHING
                    """,
                    (room_id, session_id, principal, ts),
                )
                inserted = cur.rowcount > 0
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        return inserted

    async def remove_member(
        self, room_id: str, session_id: str
    ) -> bool:
        """Unbind a session from a room. Returns ``True`` if a row was deleted.

        Idempotent: removing a non-member is a no-op that returns
        ``False``. The room itself is not destroyed; callers that
        want to close the room call ``close(room_id, principal)``.
        """
        if not room_id:
            raise ValueError("room_id must be a non-empty string")
        if not session_id:
            raise ValueError("session_id must be a non-empty string")

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    """
                    DELETE FROM event_room_members
                     WHERE room_id = ? AND session_id = ?
                    """,
                    (room_id, session_id),
                )
                removed = cur.rowcount > 0
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        return removed

    async def list_members(self, room_id: str) -> list[str]:
        """Return the session_ids currently bound to ``room_id``.

        Order is by ``joined_at`` ASC so the SSE fan-out consumer
        receives members in a stable order (audit-friendly).
        """
        if not room_id:
            raise ValueError("room_id must be a non-empty string")

        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT session_id FROM event_room_members
                 WHERE room_id = ?
                 ORDER BY joined_at ASC, session_id ASC
                """,
                (room_id,),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()

        return [r["session_id"] for r in rows]

    async def list_rooms_for_session(self, session_id: str) -> list[str]:
        """Return the room_ids a session is currently a member of.

        Useful for the session-close path so ``MultiSessionCoordinator``
        can auto-``leave_event_room`` without an explicit caller
        argument.
        """
        if not session_id:
            raise ValueError("session_id must be a non-empty string")

        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT room_id FROM event_room_members
                 WHERE session_id = ?
                 ORDER BY joined_at ASC, room_id ASC
                """,
                (session_id,),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()

        return [r["room_id"] for r in rows]

    # ─── Lifecycle (expiry sweep) ────────────────────────────────────────

    async def expire_stale_rooms(self, *, now: int | None = None) -> list[str]:
        """Flip every room with ``expires_at <= now`` and ``status='open'``
        to ``status='expired'``. Returns the list of newly-expired
        room_ids.

        Idempotent on the DB (the second sweep returns an empty
        list because the previous sweep already flipped the
        status). Safe to call on a schedule.
        """
        ts = int(now if now is not None else time.time())
        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    """
                    UPDATE event_rooms
                       SET status = ?
                     WHERE status = ? AND expires_at <= ?
                    """,
                    (STATUS_EXPIRED, STATUS_OPEN, ts),
                )
                rows_affected = cur.rowcount
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        if rows_affected == 0:
            return []

        # Re-read the IDs that flipped (read-only — no transaction).
        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT room_id FROM event_rooms
                 WHERE status = ? AND expires_at <= ?
                 ORDER BY room_id ASC
                """,
                (STATUS_EXPIRED, ts),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()
        return [r["room_id"] for r in rows]

    async def list_active(
        self, tenant_id: str | None = None
    ) -> list[EventRoom]:
        """Return every room with ``status='open' AND expires_at > now``.

        Optionally filtered by ``tenant_id``. Order is
        ``created_at`` DESC so the most recently created rooms
        surface first (operators usually care about the
        freshly-created ones).
        """
        ts = int(time.time())
        params: list[Any] = [STATUS_OPEN, ts]
        where = "status = ? AND expires_at > ?"
        if tenant_id is not None:
            if not tenant_id:
                raise ValueError("tenant_id must be a non-empty string")
            where += " AND tenant_id = ?"
            params.append(tenant_id)

        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                f"""
                SELECT room_id, tenant_id, owner_principal, status,
                       created_at, expires_at, closed_at, name
                FROM event_rooms
                WHERE {where}
                ORDER BY created_at DESC, room_id ASC
                """,
                tuple(params),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()

        return [_row_to_event_room(r, members=[]) for r in rows]

    # ─── Event fan-out ───────────────────────────────────────────────────

    async def fan_out_event(
        self,
        *,
        room_id: str,
        event_type: str,
        payload: dict[str, Any],
        origin_session_id: str,
    ) -> int | None:
        """Append ONE row to ``event_room_events`` and return its seq.

        The fan-out consumer (SSE bridge) reads ``event_room_events``
        and dispatches the row to every active session in the room.
        Per-session SSE clients see ``governance.session.cross.*``
        events without needing to know about rooms.

        Failures are logged and surface as ``None`` per audit §7.1:
        a fan-out failure NEVER inverts an authoritative decision.

        ``origin_session_id`` is the session that emitted the event
        (the room-scoped SSE replay can skip echoing the event back
        to the emitter).
        """
        if not room_id:
            raise ValueError("room_id must be a non-empty string")
        if not event_type:
            raise ValueError("event_type must be a non-empty string")
        if not origin_session_id:
            raise ValueError(
                "origin_session_id must be a non-empty string "
                "(the emitting session)"
            )
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

        payload_json = json.dumps(payload, sort_keys=True)
        ts = int(time.time())

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # Validate the room exists and is open BEFORE writing
                # the event row. Without this check, a stale session
                # could fan-out into a closed room and the SSE bridge
                # would deliver a phantom event.
                cur = await db.execute(
                    "SELECT status FROM event_rooms WHERE room_id = ?",
                    (room_id,),
                )
                row = await cur.fetchone()
                if row is None:
                    await db.rollback()
                    logger.warning(
                        "fan_out_event: room_id={} not found; dropping event_type={}",
                        room_id,
                        event_type,
                    )
                    return None
                if row["status"] != STATUS_OPEN:
                    await db.rollback()
                    logger.warning(
                        "fan_out_event: room_id={} status={!r} (not open); dropping event_type={}",
                        room_id,
                        row["status"],
                        event_type,
                    )
                    return None
                cur = await db.execute(
                    """
                    INSERT INTO event_room_events
                        (room_id, session_id, event_type, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (room_id, origin_session_id, event_type, payload_json, ts),
                )
                seq = cur.lastrowid
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        except Exception as exc:
            # Per audit §7.1: best-effort delivery.
            logger.warning(
                "fan_out_event: persistence failed (room_id={}, event_type={}): {}",
                room_id,
                event_type,
                exc,
            )
            return None
        finally:
            await db.close()

        assert seq is not None
        return int(seq)

    async def list_room_events(
        self,
        room_id: str,
        from_seq: int = 1,
        to_seq: int = 2**31 - 1,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Return room events in ascending ``seq`` order inside ``[from_seq, to_seq]``.

        ``limit`` is clamped to ``[1..500]`` (mirror of the
        session-stream ``list_events`` discipline).
        """
        if not room_id:
            raise ValueError("room_id must be a non-empty string")
        safe_limit = _clamp_limit(limit, default=500, maximum=500)
        if from_seq < 1:
            from_seq = 1
        if to_seq < from_seq:
            raise ValueError(
                f"to_seq ({to_seq}) must be >= from_seq ({from_seq})"
            )

        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT seq, room_id, session_id, event_type, payload_json, created_at
                FROM event_room_events
                WHERE room_id = ?
                  AND seq BETWEEN ? AND ?
                ORDER BY seq ASC
                LIMIT ?
                """,
                (room_id, from_seq, to_seq, safe_limit),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()

        return [
            {
                "seq": int(r["seq"]),
                "room_id": r["room_id"],
                "session_id": r["session_id"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload_json"]) if r["payload_json"] else {},
                "created_at": int(r["created_at"]),
            }
            for r in rows
        ]


# ─── Helpers ────────────────────────────────────────────────────────────────


def _row_to_event_room(row: Any, *, members: list[str]) -> EventRoom:
    """Build an ``EventRoom`` snapshot from a sqlite Row."""
    return EventRoom(
        room_id=row["room_id"],
        tenant_id=row["tenant_id"],
        owner_principal=row["owner_principal"],
        status=row["status"],
        created_at=int(row["created_at"]),
        expires_at=int(row["expires_at"]),
        closed_at=int(row["closed_at"]) if row["closed_at"] is not None else None,
        name=row["name"],
        members=list(members),
    )


def _clamp_ttl(ttl_seconds: int) -> int:
    """Clamp a TTL into the safe ``[1..86400]`` (1 second .. 1 day) range.

    Mirrors the per-request ``_clamp_limit`` discipline used by
    ``session_event_stream`` — callers that pass a nonsensical
    value (negative, >1 day) get a sensible default rather than
    a silent `0` or a runaway room.
    """
    if ttl_seconds is None or ttl_seconds <= 0:
        return 3600  # default 1 hour
    return min(int(ttl_seconds), 86400)


def _clamp_limit(value: int | None, *, default: int, maximum: int) -> int:
    """Clamp a query limit to a safe range (mirror of ``event_stream._clamp_limit``)."""
    if value is None or value <= 0:
        return default
    return min(int(value), maximum)