"""Shared fixtures for v3.14.0 ecosystem ontology tests.

Mirrors the v3.7.3 NEW-A1 pre-test fixture isolation pattern:
every test gets its own tempdir for L2 / L3 / L4 SQLite stores,
the schemas are initialised once per session, and tests populate
the stores directly so the projection layer is exercised end-to-end.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from eaasp_ecosystem.ontology import OntologyService


# ─── Schemas (mirror the L2 / L3 / L4 / L5 stores) ──────────────────────

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

L3_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS governance_decisions (
    decision_id TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    hook_id     TEXT NOT NULL,
    tool_name   TEXT NOT NULL,
    risk_level  TEXT NOT NULL CHECK(risk_level IN ('read','write_local','write_external')),
    decision    TEXT NOT NULL,
    approver    TEXT,
    rationale   TEXT NOT NULL,
    stage       TEXT,
    ts          TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

L4_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS event_rooms (
    room_id          TEXT PRIMARY KEY,
    tenant_id        TEXT NOT NULL,
    owner_principal  TEXT NOT NULL,
    status           TEXT NOT NULL,
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
    PRIMARY KEY (room_id, session_id)
);

CREATE TABLE IF NOT EXISTS event_room_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id      TEXT NOT NULL,
    session_id   TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   INTEGER NOT NULL
);
"""

L5_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS l5_cards (
    card_id     TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    card_type   TEXT NOT NULL,
    tenant_id   TEXT NOT NULL,
    summary     TEXT,
    payload_json TEXT NOT NULL,
    created_at  INTEGER NOT NULL
);
"""


def _init_schema(db_path: Path, schema_sql: str) -> None:
    """Apply a schema to a fresh SQLite database."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()


# ─── Per-test tempdirs ───────────────────────────────────────────────────


@pytest.fixture
def tmp_db_dir(tmp_path: Path) -> Path:
    """Per-test tempdir for SQLite stores (NEW-A1 pattern)."""
    d = tmp_path / "ecosystem-dbs"
    d.mkdir()
    return d


@pytest.fixture
def l2_db(tmp_db_dir: Path) -> Path:
    p = tmp_db_dir / "l2.db"
    _init_schema(p, L2_SCHEMA)
    return p


@pytest.fixture
def l3_db(tmp_db_dir: Path) -> Path:
    p = tmp_db_dir / "l3.db"
    _init_schema(p, L3_SCHEMA)
    return p


@pytest.fixture
def l4_db(tmp_db_dir: Path) -> Path:
    p = tmp_db_dir / "l4.db"
    _init_schema(p, L4_SCHEMA)
    return p


@pytest.fixture
def l5_db(tmp_db_dir: Path) -> Path:
    p = tmp_db_dir / "l5.db"
    _init_schema(p, L5_SCHEMA)
    return p


@pytest.fixture
def ontology_service(
    l2_db: Path, l3_db: Path, l4_db: Path, l5_db: Path
) -> OntologyService:
    """Build an OntologyService backed by the per-test SQLite stores."""
    return OntologyService(
        l2_db_path=str(l2_db),
        l3_db_path=str(l3_db),
        l4_db_path=str(l4_db),
        l5_db_path=str(l5_db),
        default_tenant="default",
        root_layer="l2_type",
    )


# ─── Seeding helpers ─────────────────────────────────────────────────────


def seed_l2_anchor(
    db_path: Path,
    *,
    anchor_id: str,
    event_id: str,
    session_id: str,
    type_value: str,
) -> None:
    """Insert a row into the L2 anchors table."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO anchors (
                anchor_id, event_id, session_id, type,
                data_ref, snapshot_hash, source_system, tool_version,
                model_version, rule_version, created_at, metadata
            ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, 0, NULL)
            """,
            (anchor_id, event_id, session_id, type_value),
        )
        conn.commit()


def seed_l3_decision(
    db_path: Path,
    *,
    decision_id: str,
    session_id: str,
    hook_id: str,
    tool_name: str,
    risk_level: str,
    decision_value: str = "allow",
    rationale: str = "test",
    stage: str | None = None,
) -> None:
    """Insert a row into the L3 governance_decisions table."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO governance_decisions (
                decision_id, session_id, hook_id, tool_name, risk_level,
                decision, approver, rationale, stage
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (decision_id, session_id, hook_id, tool_name, risk_level,
             decision_value, rationale, stage),
        )
        conn.commit()


def seed_l4_event(
    db_path: Path,
    *,
    room_id: str,
    session_id: str,
    event_type: str,
    payload_json: str = "{}",
) -> int:
    """Insert a row into the L4 event_room_events table. Returns seq."""
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO event_room_events (
                room_id, session_id, event_type, payload_json, created_at
            ) VALUES (?, ?, ?, ?, 0)
            """,
            (room_id, session_id, event_type, payload_json),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def seed_l4_room(
    db_path: Path,
    *,
    room_id: str,
    tenant_id: str,
    owner_principal: str = "tester",
    status: str = "open",
    name: str | None = None,
) -> None:
    """Insert a row into the L4 event_rooms table (for tenant filtering)."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO event_rooms (
                room_id, tenant_id, owner_principal, status,
                created_at, expires_at, closed_at, name
            ) VALUES (?, ?, ?, ?, 0, 0, NULL, ?)
            """,
            (room_id, tenant_id, owner_principal, status, name),
        )
        conn.commit()


def seed_l5_card(
    db_path: Path,
    *,
    card_id: str,
    session_id: str,
    card_type: str,
    tenant_id: str = "default",
    summary: str = "",
    payload_json: str = "{}",
) -> None:
    """Insert a row into the L5 l5_cards table."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO l5_cards (
                card_id, session_id, card_type, tenant_id, summary,
                payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (card_id, session_id, card_type, tenant_id, summary, payload_json),
        )
        conn.commit()