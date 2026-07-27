"""Shared SQLite schema and connection helpers for L4 orchestration.

Mirrors S3.T3 / S3.T2 conventions exactly:
- WAL journal mode for concurrent readers.
- ``foreign_keys`` pragma reapplied on every open (per-connection flag).
- Row factory set so callers can use ``row["col"]`` access.
- Writes must be wrapped in ``BEGIN IMMEDIATE`` (reviewer note C1).
"""

from __future__ import annotations

import os

import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Contract 5 — orchestrated sessions produced by the three-way handshake.
CREATE TABLE IF NOT EXISTS sessions (
    session_id   TEXT PRIMARY KEY,
    intent_id    TEXT,
    skill_id     TEXT,
    runtime_id   TEXT,
    user_id      TEXT,
    status       TEXT NOT NULL
        CHECK(status IN ('created','active','closed','failed')),
    payload_json TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    closed_at    INTEGER
);

CREATE INDEX IF NOT EXISTS idx_sessions_status
    ON sessions(status, created_at DESC);

-- Session event stream — append-only per-session ordered log.
CREATE TABLE IF NOT EXISTS session_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_session_seq
    ON session_events(session_id, seq);

-- v3.12.1 — EVENT-ROOM-01 (EAASP Phase 4 / Event Room + multi-session).
-- Long-lived coordination namespace spanning multiple sessions. Rooms
-- outlive any individual session; members (sessions) join / leave
-- freely; events fan-out across every member. See
-- ``tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_room.py``
-- for the full contract.
--
-- Tables (created idempotently via CREATE TABLE IF NOT EXISTS):
--   event_rooms         — room metadata + status machine (open/closed/expired).
--   event_room_members  — (room_id, session_id) binding + the principal
--                         that authorized the bind (audit trail).
--   event_room_events   — append-only per-room event log; one row per
--                         fan-out dispatch (NOT one per recipient; SSE
--                         consumers fan out per the canonical schema).
--
-- All four tables live in the same L4 SQLite file (WAL) and share the
-- sessions.session_id FK convention used by session_events. Foreign
-- keys are enforced per-connection (PRAGMA foreign_keys=ON).
CREATE TABLE IF NOT EXISTS event_rooms (
    room_id          TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL,
    owner_principal  TEXT NOT NULL,
    status           TEXT NOT NULL
        CHECK(status IN ('open','closed','expired')),
    created_at       INTEGER NOT NULL,
    expires_at       INTEGER NOT NULL,
    closed_at        INTEGER,
    name             TEXT
);

CREATE INDEX IF NOT EXISTS idx_event_rooms_status
    ON event_rooms(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_event_rooms_tenant
    ON event_rooms(tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS event_room_members (
    room_id     TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    principal   TEXT NOT NULL,
    joined_at   INTEGER NOT NULL,
    PRIMARY KEY (room_id, session_id),
    FOREIGN KEY(room_id) REFERENCES event_rooms(room_id)
);

CREATE INDEX IF NOT EXISTS idx_event_room_members_session
    ON event_room_members(session_id);

CREATE TABLE IF NOT EXISTS event_room_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id      TEXT NOT NULL,
    session_id   TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    FOREIGN KEY(room_id) REFERENCES event_rooms(room_id)
);

CREATE INDEX IF NOT EXISTS idx_event_room_events_seq
    ON event_room_events(room_id, seq);
CREATE INDEX IF NOT EXISTS idx_event_room_events_session
    ON event_room_events(room_id, session_id, seq);

-- v3.12.1 round 4 — startup-fail ledger (audit-ledger style).
-- The L4 startup gate (e.g. ADR-V2-028 strict-by-default missing
-- env var) MUST produce a structured record operators can grep /
-- correlate. We persist these into a dedicated append-only
-- table so they survive process restart and end up in the
-- same audit surface as the rest of the L4 event stream.
-- The table is created BEFORE process startup gates fire so a
-- boot probe can write one row before the process exits
-- (persisted via the same WAL discipline as ``session_events``).
CREATE TABLE IF NOT EXISTS l4_startup_failures (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    reason       TEXT NOT NULL,
    env_var      TEXT,
    resolution   TEXT NOT NULL,
    req_id       TEXT,
    adr_id       TEXT,
    created_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_l4_startup_failures_reason
    ON l4_startup_failures(reason, created_at DESC);
"""


# Phase 1 Event Engine columns — idempotent migration via ALTER TABLE ADD COLUMN.
# SQLite silently fails on duplicate column names via try/except.
_V2_COLUMNS = [
    "ALTER TABLE session_events ADD COLUMN event_id TEXT",
    "ALTER TABLE session_events ADD COLUMN source TEXT DEFAULT ''",
    "ALTER TABLE session_events ADD COLUMN metadata_json TEXT DEFAULT '{}'",
    "ALTER TABLE session_events ADD COLUMN cluster_id TEXT",
]

_V2_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS session_events_fts USING fts5(
    event_type, payload_json,
    content='session_events', content_rowid='seq'
);
"""

_V2_FTS_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS session_events_fts_ai
AFTER INSERT ON session_events BEGIN
    INSERT INTO session_events_fts(rowid, event_type, payload_json)
    VALUES (new.seq, new.event_type, new.payload_json);
END;
"""

_V2_INDEX = """
CREATE INDEX IF NOT EXISTS idx_session_events_cluster
    ON session_events(cluster_id) WHERE cluster_id IS NOT NULL;
"""

_V2_EVENT_ID_INDEX = """
CREATE INDEX IF NOT EXISTS idx_session_events_event_id
    ON session_events(event_id) WHERE event_id IS NOT NULL;
"""

# Backfill FTS5 index for rows inserted before migration (Phase 0.5 → Phase 1).
# FTS5 trigger only fires on new INSERT, so pre-existing events would be
# invisible to search() without this backfill. For external-content FTS5
# tables, the 'rebuild' command rebuilds the index from the content table.
# Idempotent: 'rebuild' drops and rebuilds the FTS index from scratch.
_V2_FTS_BACKFILL = """
INSERT INTO session_events_fts(session_events_fts) VALUES('rebuild');
"""


async def init_db(path: str) -> None:
    """Create schema if absent. Ensures the parent directory exists."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()
        # Phase 1 migration — add new columns (idempotent).
        for stmt in _V2_COLUMNS:
            try:
                await db.execute(stmt)
            except Exception:
                pass  # Column already exists
        await db.commit()
        # FTS5 + trigger + indices
        await db.executescript(_V2_FTS)
        await db.executescript(_V2_FTS_TRIGGER)
        await db.executescript(_V2_INDEX)
        await db.executescript(_V2_EVENT_ID_INDEX)
        await db.commit()
        # Backfill FTS5 for pre-migration rows (Phase 0.5 → Phase 1).
        await db.executescript(_V2_FTS_BACKFILL)
        await db.commit()


async def connect(path: str) -> aiosqlite.Connection:
    """Open a connection with row factory set and pragmas applied."""
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    # Defense-in-depth: reapply foreign_keys on every connection (per-conn flag).
    await db.execute("PRAGMA foreign_keys=ON")
    # M4 (reviewer): wait up to 5s on SQLITE_BUSY instead of failing immediately —
    # avoids spurious errors when /sessions/create and /sessions/{id}/message
    # race on WAL write locks. D30 / L2-08 (Phase 7.2 Plan 01) unified the
    # constant in L2 (BUSY_TIMEOUT_MS in eaasp_l2_memory_engine.db). L4
    # retains the literal until the eaasp_common.connect() helper lands
    # (deferred to v3.4+ per CONTEXT D-06 scope ceiling).
    await db.execute("PRAGMA busy_timeout=5000")
    return db
