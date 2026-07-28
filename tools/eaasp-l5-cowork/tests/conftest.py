"""Shared fixtures for v3.13.0 Cowork projection tests.

v3.13.0 — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action /
Approval) + 回溯闭环 (retrospective cycle).

The fixtures mirror the v3.7.3 NEW-A1 pre-test fixture
isolation pattern: every test gets its own tempdir for L2 / L3
/ L4 SQLite stores, the schemas are initialised once per
session, and tests populate the stores directly so the
projection layer is exercised end-to-end.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import pytest

from eaasp_l5_cowork.projection import CoworkProjection


# ─── L2 memory engine — anchors schema (mirrors L2 db.py) ──────────────

L2_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS anchors (
    anchor_id      TEXT PRIMARY KEY,
    event_id       TEXT NOT NULL,
    session_id     TEXT NOT NULL,
    type           TEXT NOT NULL,
    data_ref       TEXT,
    snapshot_hash  TEXT,
    source_system  TEXT,
    tool_version   TEXT,
    model_version  TEXT,
    rule_version   TEXT,
    created_at     INTEGER NOT NULL,
    metadata       TEXT
);
"""

# ─── L3 governance — governance_decisions + telemetry_events (mirrors L3 db.py) ─

L3_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id     TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    agent_id     TEXT,
    hook_id      TEXT,
    phase        TEXT,
    payload_json TEXT NOT NULL,
    received_at  TEXT NOT NULL DEFAULT (datetime('now')),
    tiebreaker   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS governance_decisions (
    decision_id TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    hook_id     TEXT NOT NULL,
    tool_name   TEXT NOT NULL,
    risk_level  TEXT NOT NULL CHECK(risk_level IN ('read','write_local','write_external')),
    decision    TEXT NOT NULL CHECK(decision IN ('allow','approve','deny','gate_request','await_human')),
    approver    TEXT,
    rationale   TEXT NOT NULL,
    stage       TEXT,
    ts          TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# ─── L4 orchestration — event_rooms + event_room_members + event_room_events (mirrors L4 db.py) ─

L4_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

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

CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id     TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    agent_id     TEXT,
    hook_id      TEXT,
    phase        TEXT,
    payload_json TEXT NOT NULL,
    received_at  TEXT NOT NULL DEFAULT (datetime('now')),
    tiebreaker   INTEGER NOT NULL DEFAULT 0
);
"""


# ─── Per-test tempdirs (NEW-A1 + v3.7.3 isolation pattern) ──────────────


@pytest.fixture
def tmp_db_dir(tmp_path: Path) -> Path:
    """Per-test tempdir with subdirs for L2 / L3 / L4 DBs."""
    (tmp_path / "l2").mkdir()
    (tmp_path / "l3").mkdir()
    (tmp_path / "l4").mkdir()
    return tmp_path


@pytest.fixture
def l2_db(tmp_db_dir: Path) -> Path:
    return tmp_db_dir / "l2" / "memory.db"


@pytest.fixture
def l3_db(tmp_db_dir: Path) -> Path:
    return tmp_db_dir / "l3" / "governance.db"


@pytest.fixture
def l4_db(tmp_db_dir: Path) -> Path:
    return tmp_db_dir / "l4" / "orchestration.db"


@pytest.fixture
async def init_l2(l2_db: Path) -> AsyncIterator[Path]:
    async with aiosqlite.connect(l2_db) as db:
        await db.executescript(L2_SCHEMA)
        await db.commit()
    yield l2_db


@pytest.fixture
async def init_l3(l3_db: Path) -> AsyncIterator[Path]:
    async with aiosqlite.connect(l3_db) as db:
        await db.executescript(L3_SCHEMA)
        await db.commit()
    yield l3_db


@pytest.fixture
async def init_l4(l4_db: Path) -> AsyncIterator[Path]:
    async with aiosqlite.connect(l4_db) as db:
        await db.executescript(L4_SCHEMA)
        await db.commit()
    yield l4_db


@pytest.fixture
def projection(
    init_l2: Path, init_l3: Path, init_l4: Path
) -> CoworkProjection:
    """CoworkProjection wired to the per-test tempdirs."""
    return CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )


# ─── High-level seeders ─────────────────────────────────────────────────


async def seed_event_room(
    l4_db: Path,
    *,
    room_id: str = "er_test01",
    tenant_id: str = "acme",
    owner_principal: str = "alice@acme",
    session_ids: list[str] | None = None,
    expires_at: int | None = None,
) -> None:
    """Insert a row in event_rooms + one membership per session."""
    import time

    now = int(time.time())
    expires = expires_at if expires_at is not None else now + 3600
    async with aiosqlite.connect(l4_db) as db:
        await db.execute(
            """
            INSERT INTO event_rooms
                (room_id, tenant_id, owner_principal, status,
                 created_at, expires_at, name)
            VALUES (?, ?, ?, 'open', ?, ?, ?)
            """,
            (room_id, tenant_id, owner_principal, now, expires, "test room"),
        )
        for sid in session_ids or []:
            await db.execute(
                """
                INSERT INTO event_room_members
                    (room_id, session_id, principal, joined_at)
                VALUES (?, ?, ?, ?)
                """,
                (room_id, sid, owner_principal, now),
            )
        await db.commit()


async def seed_room_event(
    l4_db: Path,
    *,
    room_id: str,
    session_id: str,
    event_type: str,
    payload: dict,
    created_at: int | None = None,
) -> int:
    """Insert a row in event_room_events and return its seq."""
    import json
    import time

    now = int(time.time())
    ts = created_at if created_at is not None else now
    async with aiosqlite.connect(l4_db) as db:
        cur = await db.execute(
            """
            INSERT INTO event_room_events
                (room_id, session_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (room_id, session_id, event_type, json.dumps(payload), ts),
        )
        await db.commit()
        return int(cur.lastrowid or 0)


async def seed_l2_anchor(
    l2_db: Path,
    *,
    anchor_id: str,
    event_id: str,
    session_id: str,
    type_: str = "scada_reading",
    data_ref: str = "/scada/feeder_07/2026-07-25",
    snapshot_hash: str | None = "sha256:deadbeef",
    source_system: str = "scada",
    tool_version: str = "1.0.0",
    metadata: dict | None = None,
    created_at: int | None = None,
) -> None:
    import json
    import time

    now = int(time.time())
    ts = created_at if created_at is not None else now
    async with aiosqlite.connect(l2_db) as db:
        await db.execute(
            """
            INSERT INTO anchors
                (anchor_id, event_id, session_id, type, data_ref,
                 snapshot_hash, source_system, tool_version,
                 model_version, rule_version, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (
                anchor_id,
                event_id,
                session_id,
                type_,
                data_ref,
                snapshot_hash,
                source_system,
                tool_version,
                ts,
                json.dumps(metadata or {}),
            ),
        )
        await db.commit()


async def seed_l4_telemetry(
    l4_db: Path,
    *,
    event_id: str,
    session_id: str,
    hook_id: str | None = "PreToolUse",
    phase: str | None = "PreToolUse",
    payload: dict | None = None,
    received_at: str | None = None,
    tiebreaker: int = 0,
) -> None:
    import json

    received = received_at or "2026-07-25 12:00:00"
    async with aiosqlite.connect(l4_db) as db:
        await db.execute(
            """
            INSERT INTO telemetry_events
                (event_id, session_id, agent_id, hook_id, phase,
                 payload_json, received_at, tiebreaker)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                session_id,
                hook_id,
                phase,
                json.dumps(payload or {}),
                received,
                tiebreaker,
            ),
        )
        await db.commit()


async def seed_l3_decision(
    l3_db: Path,
    *,
    decision_id: str,
    session_id: str,
    hook_id: str,
    tool_name: str,
    risk_level: str = "write_external",
    decision: str = "allow",
    approver: str | None = None,
    rationale: str = "test",
    stage: str | None = None,
    ts: str | None = None,
) -> None:
    async with aiosqlite.connect(l3_db) as db:
        await db.execute(
            """
            INSERT INTO governance_decisions
                (decision_id, session_id, hook_id, tool_name, risk_level,
                 decision, approver, rationale, stage, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                session_id,
                hook_id,
                tool_name,
                risk_level,
                decision,
                approver,
                rationale,
                stage,
                ts or "2026-07-25 12:00:00",
            ),
        )
        await db.commit()
