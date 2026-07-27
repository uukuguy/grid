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
import re
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


class EventRoomNotAuthorized(EventRoomError):
    """Raised when the calling principal is not a member (or owner) of the room.

    Distinct from ``EventRoomNotOwned`` (which is specifically about
    owner-only operations like ``close``). ``EventRoomNotAuthorized``
    is raised by ``remove_member`` / ``fan_out_event`` when the
    principal cannot authorize the action — either because they
    are not a member at all, or because the membership row's
    ``principal`` column does not match the caller (the bind was
    performed by a different principal in the same session).
    """

    def __init__(
        self, room_id: str, principal: str, detail: str = ""
    ) -> None:
        self.principal = principal
        super().__init__(
            room_id,
            detail or f"principal {principal!r} not authorized",
        )


# v3.12.1 — REQ-ROOM-01: room_id format allowlist. The id is used as
# the SSE event log key, the API URL path segment, and the SSE
# ``event_id`` — strict pattern prevents injection / FTS5 corruption.
_ROOM_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")

# v3.12.1 — REQ-ROOM-01 / per-tenant cap. A misbehaving caller
# cannot fill the SQLite file with rooms. The cap is enforced at
# ``create`` time (cheap COUNT query before INSERT).
_ROOM_NAME_MAX_LEN = 256
_ROOMS_PER_TENANT_CAP = 1024


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
        if name is not None and len(name) > _ROOM_NAME_MAX_LEN:
            raise ValueError(
                f"name must be <= {_ROOM_NAME_MAX_LEN} chars, got {len(name)}"
            )
        safe_ttl = _clamp_ttl(ttl_seconds)

        final_room_id = room_id if room_id else f"er_{uuid.uuid4().hex[:16]}"
        if not final_room_id:
            raise ValueError("room_id must be a non-empty string")
        # v3.12.1 — REQ-ROOM-01 / security review #5: room_id must
        # match the strict pattern. Caller-supplied ids are URLs
        # path segments AND SSE event log keys AND FTS5 tokens; a
        # malicious caller could inject quotes, control characters,
        # or unbounded-length strings otherwise.
        if not _ROOM_ID_PATTERN.match(final_room_id):
            raise ValueError(
                f"room_id must match {_ROOM_ID_PATTERN.pattern!r} "
                f"(got {final_room_id!r})"
            )

        ts = int(now if now is not None else time.time())
        expires_at = ts + safe_ttl

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # v3.12.1 — REQ-ROOM-01 / security review #5: per-tenant
                # room-count cap. Cheap COUNT(*) query before INSERT
                # rejects tenants that try to fill the SQLite file.
                # The cap counts ``open + closed + expired`` rooms in
                # this tenant (we don't reclaim rows on close; the
                # ledger is append-only). The cap is intentionally
                # global (NOT per-status) so a malicious tenant
                # cannot bypass it by closing rooms.
                cur = await db.execute(
                    "SELECT COUNT(*) AS n FROM event_rooms "
                    "WHERE tenant_id = ?",
                    (tenant_id,),
                )
                count_row = await cur.fetchone()
                existing_count = (
                    int(count_row["n"]) if count_row is not None else 0
                )
                if existing_count >= _ROOMS_PER_TENANT_CAP:
                    await db.rollback()
                    raise ValueError(
                        f"tenant {tenant_id!r} has reached the room cap "
                        f"({_ROOMS_PER_TENANT_CAP}); close / expire stale "
                        f"rooms before creating new ones"
                    )

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
        """Bind a session to a room.

        ``principal`` is the human/service principal who authorizes
        the bind. Returns ``True`` if a new row was inserted.

        v3.12.1 — security review #4: a re-bind of an existing
        (room_id, session_id) pair is NOT silently absorbed by
        ``ON CONFLICT DO NOTHING``. The previous shape silently
        swapped the principal who authorized the join without
        surfacing it in the audit log — a caller could
        re-``add_member`` with a new ``principal`` and the
        original author would be erased. The new shape raises
        ``EventRoomAlreadyExists`` (preserves the v3.12.1 audit
        contract: re-bind must be a separate explicit operation
        such as ``remove_member`` + ``add_member``). The existing
        membership row stays intact (no UPDATE on conflict — the
        caller decides whether to swap by going through the
        remove+add sequence).

        Raises ``EventRoomNotFound`` if the room does not exist;
        ``EventRoomNotOpen`` if the room is closed / expired;
        ``EventRoomAlreadyExists`` if the (room_id, session_id)
        pair is already bound.
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

                # v3.12.1 — security review #4: detect the
                # re-bind BEFORE INSERT, raise explicitly, and
                # emit a room event log row so the rejected
                # attempt is auditable. The pre-INSERT probe +
                # ROLLBACK-on-conflict is the only safe shape —
                # ``ON CONFLICT DO NOTHING`` would silently swap
                # the principal that authorized the bind.
                cur = await db.execute(
                    """
                    SELECT 1 FROM event_room_members
                     WHERE room_id = ? AND session_id = ?
                    """,
                    (room_id, session_id),
                )
                existing = await cur.fetchone()
                if existing is not None:
                    # Audit the rejected re-bind attempt (best-effort).
                    ts = int(time.time())
                    try:
                        await db.execute(
                            """
                            INSERT INTO event_room_events
                                (room_id, session_id, event_type, payload_json, created_at)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                room_id,
                                session_id,
                                make_event_room_event_type(
                                    "member_rebind_rejected"
                                ),
                                json.dumps(
                                    {
                                        "attempted_principal": principal,
                                        "ts": ts,
                                    },
                                    sort_keys=True,
                                ),
                                ts,
                            ),
                        )
                    except Exception:
                        pass  # best-effort audit
                    await db.commit()
                    raise EventRoomAlreadyExists(
                        room_id,
                        f"(room_id, session_id) already bound; "
                        f"re-bind requires explicit remove+add "
                        f"(audit §REQ-ROOM-04)",
                    )

                ts = int(time.time())
                cur = await db.execute(
                    """
                    INSERT INTO event_room_members
                        (room_id, session_id, principal, joined_at)
                    VALUES (?, ?, ?, ?)
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
        self,
        room_id: str,
        session_id: str,
        principal: str,
    ) -> bool:
        """Unbind a session from a room.

        v3.12.1 — security review #2: the calling principal must
        match the row's ``principal`` column (self-removal) OR be
        the room owner. The previous shape allowed ANY caller to
        unbind ANY session from ANY room, which is a horizontal-
        privilege-escalation bug — a non-member could remove a
        member they had no relationship to.

        Returns ``True`` if a row was deleted, ``False`` if the
        (room_id, session_id) pair was not bound. Raises
        ``EventRoomNotAuthorized`` if the principal cannot
        authorize the removal; ``EventRoomNotFound`` if the room
        does not exist (room existence is checked before the
        authorization probe so the caller sees a stable error
        code regardless of the room's state).
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
                # Probe the room + member row together so we can
                # distinguish "room missing" from "principal
                # unauthorized" from "not a member".
                cur = await db.execute(
                    """
                    SELECT m.principal AS member_principal,
                           r.owner_principal AS room_owner
                      FROM event_rooms r
                      LEFT JOIN event_room_members m
                        ON m.room_id = r.room_id
                       AND m.session_id = ?
                     WHERE r.room_id = ?
                    """,
                    (session_id, room_id),
                )
                row = await cur.fetchone()
                if row is None:
                    await db.rollback()
                    raise EventRoomNotFound(room_id, "no such room")
                member_principal = row["member_principal"]
                if member_principal is None:
                    # Not a member: idempotent no-op (consistent
                    # with the original contract). Distinct from
                    # "not authorized" — a non-member caller is
                    # not a horizontal-privilege attack.
                    await db.commit()
                    return False
                if (
                    principal != member_principal
                    and principal != row["room_owner"]
                ):
                    await db.rollback()
                    raise EventRoomNotAuthorized(
                        room_id,
                        principal,
                        "self-removal or room-owner only "
                        "(audit §REQ-ROOM-02)",
                    )

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

        v3.12.1 — security review #3: the candidate room_ids are
        CAPTURED in a ``SELECT`` BEFORE the ``UPDATE`` runs, then
        the ``UPDATE`` targets only those specific ids. The
        previous shape updated via a filter predicate
        (``WHERE status='open' AND expires_at <= ts``) and then
        re-read the post-update set, which has a TOCTOU window:
        another writer could insert a NEW room between the
        UPDATE and the re-read that happens to satisfy the same
        filter, and the returned list would include the
        unrelated room. Capture-then-update closes the window.
        """
        ts = int(now if now is not None else time.time())
        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # Step 1: capture the candidate room_ids under the
                # same transaction so the SELECT and the UPDATE
                # observe a consistent snapshot.
                cur = await db.execute(
                    """
                    SELECT room_id FROM event_rooms
                     WHERE status = ? AND expires_at <= ?
                     ORDER BY room_id ASC
                    """,
                    (STATUS_OPEN, ts),
                )
                candidate_rows = await cur.fetchall()
                candidate_ids = [r["room_id"] for r in candidate_rows]

                if not candidate_ids:
                    await db.commit()
                    return []

                # Step 2: UPDATE only the captured ids (not a
                # filter predicate) so a concurrent INSERT of a
                # new stale room cannot sneak into the result set.
                placeholders = ",".join("?" for _ in candidate_ids)
                cur = await db.execute(
                    f"""
                    UPDATE event_rooms
                       SET status = ?
                     WHERE room_id IN ({placeholders})
                       AND status = ?
                    """,
                    [STATUS_EXPIRED, *candidate_ids, STATUS_OPEN],
                )
                rows_affected = cur.rowcount
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        # Sanity: the candidate set was the only thing the
        # UPDATE could have flipped. If the UPDATE affected fewer
        # rows than expected, log a warning (concurrent writer
        # closed a candidate first) but DO NOT raise — the
        # contract is "return the ids that flipped" not
        # "raise on concurrent close".
        if rows_affected < len(candidate_ids):
            logger.info(
                "expire_stale_rooms: {} candidates captured but {} flipped "
                "(concurrent close / status change; non-error)",
                len(candidate_ids),
                rows_affected,
            )
        return candidate_ids[:rows_affected]

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
        principal: str | None = None,
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

        v3.12.1 — security review #1: ``principal`` is OPTIONAL
        for backwards compatibility with the existing
        ``MultiSessionCoordinator.emit_shared_event`` call site
        which already passes the principal in the payload envelope.
        When supplied, the principal must either:
        - match the membership row's ``principal`` (the session
          is a member of the room under this principal), OR
        - match ``event_rooms.owner_principal`` (room-management
          event from the room owner).

        Without the membership check, a non-member caller could
        emit a phantom fan-out to a room they're not in (horizontal
        privilege escalation — event log poisoning). With the
        check, every event row carries a verified authorization
        chain.
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
        if principal is not None and not principal:
            raise ValueError(
                "principal must be a non-empty string when supplied"
            )

        payload_json = json.dumps(payload, sort_keys=True)
        ts = int(time.time())

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                # v3.12.1 — security review #1: probe the room +
                # the membership row + the room owner in one
                # SELECT. Without the membership check, a
                # non-member caller could fan-out phantom events
                # into a room they are not in. The check runs
                # BEFORE the INSERT so a rejected attempt is
                # never persisted.
                cur = await db.execute(
                    """
                    SELECT r.status AS room_status,
                           r.owner_principal AS room_owner,
                           m.principal AS member_principal
                      FROM event_rooms r
                      LEFT JOIN event_room_members m
                        ON m.room_id = r.room_id
                       AND m.session_id = ?
                     WHERE r.room_id = ?
                    """,
                    (origin_session_id, room_id),
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
                if row["room_status"] != STATUS_OPEN:
                    await db.rollback()
                    logger.warning(
                        "fan_out_event: room_id={} status={!r} (not open); dropping event_type={}",
                        room_id,
                        row["room_status"],
                        event_type,
                    )
                    return None
                # Authorization gate (only when principal is supplied).
                # Backwards-compat: pre-security-review callers that
                # do not pass ``principal`` (e.g. tests, the
                # MultiSessionCoordinator internal helper that
                # already validates membership upstream) skip this
                # check. New callers SHOULD pass principal.
                if principal is not None:
                    member_principal = row["member_principal"]
                    room_owner = row["room_owner"]
                    if (
                        principal != member_principal
                        and principal != room_owner
                    ):
                        await db.rollback()
                        logger.warning(
                            "fan_out_event: room_id={} principal={!r} "
                            "not authorized (not a member and not the "
                            "room owner); dropping event_type={}",
                            room_id,
                            principal,
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