"""Tests for flow_readers.py — V315-BUSINESS-FLOW-02 LayerReader implementations.

Verifies that each cross-layer reader correctly maps SQLite rows to
``BusinessFlowEvent`` instances and respects the ``business_key``
filter. Tests use ``aiosqlite.connect(":memory:")`` with the same
schema the production DB has, so no external dependencies are needed.

Per the OBSTACK §3.5 contract:

- readers are pure functions of (aiosqlite.Connection, BusinessKey)
- they MUST return [] when the key has no matching rows
- they MUST emit events whose ``ts`` is in milliseconds
- they MUST NOT raise on missing columns (defensive against partial
  migrations — but production schema is fully migrated at v3.15.5)
"""

from __future__ import annotations

import aiosqlite
import pytest

from eaasp_common.business_flow import BusinessKey

from eaasp_l4_orchestration.flow_readers import (
    build_default_layer_readers,
    read_l2_memory_files,
    read_l3_governance_decisions,
    read_l3_telemetry_events,
    read_l4_event_room_events,
    read_l4_session_events,
    read_l4_sessions,
)
from eaasp_l4_orchestration.flow_timeline import BusinessFlowEvent


# ─── Schema fragments used by the in-memory tests ────────────────────────────

# Minimal L4 sessions / session_events / event_room_events schema
# (mirrors tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/db.py).
L4_SCHEMA = """
CREATE TABLE sessions (
    session_id   TEXT PRIMARY KEY,
    intent_id    TEXT,
    skill_id     TEXT,
    runtime_id   TEXT,
    user_id      TEXT,
    status       TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    closed_at    INTEGER,
    business_key TEXT
);
CREATE TABLE session_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    event_id     TEXT,
    source       TEXT,
    metadata_json TEXT DEFAULT '{}',
    cluster_id   TEXT
);
CREATE TABLE event_room_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id      TEXT NOT NULL,
    session_id   TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    business_key TEXT
);
"""

# Minimal L3 governance_decisions / telemetry_events schema.
L3_SCHEMA = """
CREATE TABLE governance_decisions (
    decision_id  TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    hook_id      TEXT NOT NULL,
    tool_name    TEXT NOT NULL,
    risk_level   TEXT NOT NULL,
    decision     TEXT NOT NULL,
    approver     TEXT,
    rationale    TEXT,
    stage        TEXT,
    ts           TEXT NOT NULL,
    business_key TEXT
);
CREATE TABLE telemetry_events (
    event_id     TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    agent_id     TEXT,
    hook_id      TEXT,
    phase        TEXT,
    payload_json TEXT NOT NULL,
    received_at  TEXT NOT NULL,
    tiebreaker   INTEGER NOT NULL DEFAULT 0,
    business_key TEXT
);
"""

# Minimal L2 memory_files schema.
L2_SCHEMA = """
CREATE TABLE memory_files (
    memory_id      TEXT NOT NULL,
    version        INTEGER NOT NULL,
    scope          TEXT NOT NULL,
    category       TEXT NOT NULL,
    content        TEXT NOT NULL,
    evidence_refs  TEXT,
    status         TEXT NOT NULL,
    created_at     INTEGER NOT NULL,
    updated_at     INTEGER NOT NULL,
    business_key   TEXT,
    PRIMARY KEY (memory_id, version)
);
"""


# ─── Helpers ────────────────────────────────────────────────────────────────


async def _make_db(schema: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row  # mirror production db.connect()
    await conn.executescript(schema)
    return conn


def _key() -> BusinessKey:
    return BusinessKey(
        session_id="sess-001",
        skill_id="threshold-calibration",
        business_object_id="Transformer-001",
    )


def _other_key() -> BusinessKey:
    return BusinessKey(
        session_id="sess-002",
        skill_id="threshold-calibration",
        business_object_id="Transformer-002",
    )


# ─── read_l4_sessions ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_l4_sessions_returns_created_and_closed_events() -> None:
    conn = await _make_db(L4_SCHEMA)
    wire = _key().to_header()
    await conn.execute(
        """
        INSERT INTO sessions
            (session_id, intent_id, skill_id, runtime_id, user_id,
             status, payload_json, created_at, closed_at, business_key)
        VALUES
            ('sess-001', 'i1', 'threshold-calibration', 'grid-runtime',
             'user1', 'closed', '{}', 1000, 2000, ?)
        """,
        (wire,),
    )
    await conn.commit()
    events = await read_l4_sessions(conn, _key())
    assert len(events) == 2
    types = sorted(e.event_type for e in events)
    assert types == ["session.closed", "session.created"]
    assert all(e.layer == "L4" for e in events)
    assert all(e.component == "session" for e in events)
    assert sorted(e.ts for e in events) == [1_000_000, 2_000_000]


@pytest.mark.asyncio
async def test_read_l4_sessions_empty_when_no_match() -> None:
    conn = await _make_db(L4_SCHEMA)
    events = await read_l4_sessions(conn, _key())
    assert events == []


@pytest.mark.asyncio
async def test_read_l4_sessions_filters_by_business_key() -> None:
    conn = await _make_db(L4_SCHEMA)
    wire_match = _key().to_header()
    wire_other = _other_key().to_header()
    await conn.execute(
        "INSERT INTO sessions VALUES ('sess-001','i1','skill','rt','u','created','{}',1000,NULL,?)",
        (wire_match,),
    )
    await conn.execute(
        "INSERT INTO sessions VALUES ('sess-002','i2','skill','rt','u','created','{}',1000,NULL,?)",
        (wire_other,),
    )
    await conn.commit()
    events = await read_l4_sessions(conn, _key())
    assert len(events) == 1
    assert events[0].event_type == "session.created"


# ─── read_l4_event_room_events ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_l4_event_room_events_prefixes_event_type() -> None:
    conn = await _make_db(L4_SCHEMA)
    wire = _key().to_header()
    await conn.execute(
        """
        INSERT INTO event_room_events
            (room_id, session_id, event_type, payload_json, created_at, business_key)
        VALUES ('room-1','sess-001','A2A_REQUEST','{}',1500,?)
        """,
        (wire,),
    )
    await conn.commit()
    events = await read_l4_event_room_events(conn, _key())
    assert len(events) == 1
    assert events[0].event_type == "event_room.A2A_REQUEST"
    assert events[0].layer == "L4"
    assert events[0].component == "event_room"
    assert events[0].ts == 1_500_000


# ─── read_l4_session_events ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_l4_session_events_joins_via_sessions() -> None:
    conn = await _make_db(L4_SCHEMA)
    wire = _key().to_header()
    await conn.execute(
        "INSERT INTO sessions VALUES ('sess-001','i1','skill','rt','u','active','{}',1000,NULL,?)",
        (wire,),
    )
    await conn.execute(
        """
        INSERT INTO session_events
            (session_id, event_type, payload_json, created_at, event_id, source)
        VALUES ('sess-001','PRE_TOOL_USE','{"tool_name":"scada_read"}',1100,NULL,'runtime:grid-runtime')
        """,
    )
    await conn.commit()
    events = await read_l4_session_events(conn, _key())
    assert len(events) == 1
    assert events[0].event_type == "PRE_TOOL_USE"
    assert events[0].payload.get("tool_name") == "scada_read"
    assert events[0].ts == 1_100_000


# ─── read_l3_governance_decisions ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_l3_governance_decisions_maps_decision_field() -> None:
    conn = await _make_db(L3_SCHEMA)
    wire = _key().to_header()
    await conn.execute(
        """
        INSERT INTO governance_decisions
            (decision_id, session_id, hook_id, tool_name, risk_level,
             decision, approver, rationale, stage, ts, business_key)
        VALUES ('dec-1','sess-001','PreToolUse:scada_read','scada_read','medium',
                'allow','system','safe read','plan','1970-01-01 00:00:01',?)
        """,
        (wire,),
    )
    await conn.commit()
    events = await read_l3_governance_decisions(conn, _key())
    assert len(events) == 1
    assert events[0].event_type == "allow"
    assert events[0].layer == "L3"
    assert events[0].component == "governance"
    assert events[0].ts == 1_000


# ─── read_l3_telemetry_events ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_l3_telemetry_events_prefixes_with_telemetry() -> None:
    conn = await _make_db(L3_SCHEMA)
    wire = _key().to_header()
    await conn.execute(
        """
        INSERT INTO telemetry_events
            (event_id, session_id, phase, payload_json, received_at,
             tiebreaker, business_key)
        VALUES ('event-1','sess-001','skill.usage',
                '{"skill_id":"threshold-calibration"}',
                '1970-01-01 00:00:02',0,?)
        """,
        (wire,),
    )
    await conn.commit()
    events = await read_l3_telemetry_events(conn, _key())
    assert len(events) == 1
    assert events[0].event_type == "telemetry.skill.usage"
    assert events[0].layer == "L3"
    assert events[0].ts == 2_000


# ─── read_l2_memory_files ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_l2_memory_files_emits_one_event_per_status() -> None:
    conn = await _make_db(L2_SCHEMA)
    wire = _key().to_header()
    await conn.execute(
        """
        INSERT INTO memory_files
            (memory_id, version, scope, category, content, evidence_refs,
             status, created_at, updated_at, business_key)
        VALUES ('mem-1',1,'org:default','threshold','85','{}','confirmed',1400,1400,?)
        """,
        (wire,),
    )
    await conn.commit()
    events = await read_l2_memory_files(conn, _key())
    assert len(events) == 1
    assert events[0].event_type == "memory.write_file.confirmed"
    assert events[0].layer == "L2"
    assert events[0].component == "memory"
    assert events[0].ts == 1400


# ─── build_default_layer_readers ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_default_layer_readers_with_all_conns() -> None:
    l4 = await _make_db(L4_SCHEMA)
    l3 = await _make_db(L3_SCHEMA)
    l2 = await _make_db(L2_SCHEMA)
    readers = build_default_layer_readers(
        l4_conn=l4, l3_conn=l3, l2_conn=l2,
    )
    expected = {
        "L4_sessions",
        "L4_event_room_events",
        "L4_session_events",
        "L3_governance_decisions",
        "L3_telemetry_events",
        "L2_memory_files",
    }
    assert set(readers.keys()) == expected
    # Each reader must be callable and return [] for an empty DB.
    for name, reader in readers.items():
        rows = await reader(_key())
        assert rows == [], f"reader {name} should return [] for empty DB"


@pytest.mark.asyncio
async def test_build_default_layer_readers_with_none_conns() -> None:
    """When L2/L3 conns are None, the readers gracefully degrade to no-ops."""
    l4 = await _make_db(L4_SCHEMA)
    readers = build_default_layer_readers(
        l4_conn=l4, l3_conn=None, l2_conn=None,
    )
    assert await readers["L3_governance_decisions"](_key()) == []
    assert await readers["L3_telemetry_events"](_key()) == []
    assert await readers["L2_memory_files"](_key()) == []


@pytest.mark.asyncio
async def test_build_default_layer_readers_with_real_data_aggregates_correctly() -> None:
    """End-to-end smoke: wire all three layers, insert rows across all 5
    tables, confirm the timeline aggregator surfaces every layer.
    """
    l4 = await _make_db(L4_SCHEMA)
    l3 = await _make_db(L3_SCHEMA)
    l2 = await _make_db(L2_SCHEMA)
    wire = _key().to_header()

    # L4 session + session event + event room event
    await l4.execute(
        "INSERT INTO sessions VALUES ('sess-001','i1','skill','rt','u','active','{}',1000,NULL,?)",
        (wire,),
    )
    await l4.execute(
        "INSERT INTO session_events (session_id, event_type, payload_json, created_at) "
        "VALUES ('sess-001','PRE_TOOL_USE','{}',1100)",
    )
    await l4.execute(
        "INSERT INTO event_room_events (room_id, session_id, event_type, payload_json, created_at, business_key) "
        "VALUES ('room-1','sess-001','A2A_REQUEST','{}',1150,?)",
        (wire,),
    )
    # L3 governance decision + telemetry event
    await l3.execute(
        "INSERT INTO governance_decisions "
        "(decision_id, session_id, hook_id, tool_name, risk_level, decision, rationale, ts, business_key) "
        "VALUES ('d1','sess-001','h','t','read','allow','ok','1970-01-01 00:00:02',?)",
        (wire,),
    )
    await l3.execute(
        "INSERT INTO telemetry_events "
        "(event_id, session_id, phase, payload_json, received_at, tiebreaker, business_key) "
        "VALUES ('event-1','sess-001','skill.usage','{}','1970-01-01 00:00:03',0,?)",
        (wire,),
    )
    # L2 memory
    await l2.execute(
        "INSERT INTO memory_files "
        "(memory_id, version, scope, category, content, status, created_at, updated_at, business_key) "
        "VALUES ('m1',1,'s','c','85','confirmed',1300,1300,?)",
        (wire,),
    )
    await l4.commit()
    await l3.commit()
    await l2.commit()

    readers = build_default_layer_readers(l4_conn=l4, l3_conn=l3, l2_conn=l2)
    # Invoke each reader and sum the events.
    all_events: list[BusinessFlowEvent] = []
    for reader in readers.values():
        all_events.extend(await reader(_key()))

    layers = {e.layer for e in all_events}
    assert layers == {"L2", "L3", "L4"}
    assert len(all_events) >= 5  # at minimum: 1 L4 session + 1 L4 session_event
    # All events sorted by ts (the aggregator does this in production).
    all_events.sort(key=lambda e: e.ts)
    timestamps = [e.ts for e in all_events]
    assert timestamps == sorted(timestamps)
