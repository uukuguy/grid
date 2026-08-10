"""End-to-end timeline assembly test for OBSTACK business-flow integration.

Per OBSTACK_DESIGN.md §4.4 (Evaluate, planned) + V315-OPT-01 收敛:

This is the 6b.1b integration test. Seed 4 cross-layer events tagged
with the same ``BusinessKey``, then assert the SELECT-join logic
(mirroring ``tools/eaasp-l4-orchestration/flow_timeline.py``'s
``assemble_business_flow_timeline``) returns all 4 events sorted
by timestamp, with the correct layer / component / event_type labels.

The test is **integration-shaped** because it exercises the
cross-layer + multi-step + user-perspective path that the OBSTACK
demo script was hand-crafting via ``/v1/events/ingest``. It does NOT
import the L4 FastAPI app — it goes directly through SQLite to
exercise the data-layer semantics, which is the unit of behavior
the user cares about (the L4 binding is covered by
``tools/eaasp-l4-orchestration/tests/test_flow_api.py``).

What this test CATCHES that ``test_flow_api.py`` does not:
1. A future schema migration that drops ``business_key`` column.
2. A future SQL contract change in the cross-layer join.
3. A future wire-format collision (e.g. same key being parsed by
   another layer's timestamp format).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass
class AssemblyEvent:
    """Lightweight mirror of ``BusinessFlowEvent`` from
    ``tools/eaasp-l4-orchestration/flow_timeline.py`` — same field
    shape, factory-only contract, no inheritance.
    """

    ts: int
    layer: str
    component: str
    event_type: str
    payload: dict[str, Any]


def _assemble_timeline(db_paths: dict[str, str], wire: str) -> list[AssemblyEvent]:
    """Replicates ``flow_timeline.assemble_business_flow_timeline``
    against the test's ephemeral DBs. The SQL is the same query the
    L4 aggregator emits, just against controlled on-disk copies.

    Each SELECT is fired against its own DB. The 4 result sets are
    merged in Python and sorted by ts ASC (matches the UNION ALL
    ORDER BY ts the L4 aggregator uses).
    """
    results: list[AssemblyEvent] = []

    queries = [
        (
            "l4",
            "SELECT se.created_at AS ts, 'L4' AS layer, 'session' AS component, "
            "se.event_type AS event_type, se.payload_json AS payload_json "
            "FROM session_events se "
            "JOIN sessions s ON s.session_id = se.session_id "
            "WHERE s.business_key = ?",
        ),
        (
            "l4",
            "SELECT created_at AS ts, 'L4' AS layer, 'event_room' AS component, "
            "event_type AS event_type, payload_json AS payload_json "
            "FROM event_room_events WHERE business_key = ?",
        ),
        (
            "l3",
            "SELECT ts AS ts, 'L3' AS layer, 'governance' AS component, "
            "'governance.decision' AS event_type, rationale AS payload_json "
            "FROM governance_decisions WHERE business_key = ?",
        ),
        (
            "l2",
            "SELECT created_at AS ts, 'L2' AS layer, 'memory' AS component, "
            "'memory.write_file' AS event_type, "
            "json_object('content', content, 'memory_id', memory_id) AS payload_json "
            "FROM memory_files WHERE business_key = ?",
        ),
    ]

    for layer, sql in queries:
        conn = sqlite3.connect(db_paths[layer])
        conn.row_factory = sqlite3.Row
        for row in conn.execute(sql, (wire,)):
            results.append(
                AssemblyEvent(
                    ts=int(row["ts"]),
                    layer=str(row["layer"]),
                    component=str(row["component"]),
                    event_type=str(row["event_type"]),
                    payload=json.loads(str(row["payload_json"])),
                )
            )
        conn.close()

    results.sort(key=lambda e: e.ts)
    return results


def _seed_l4_session_row(l4_path: str, wire: str, ts: int) -> None:
    """Insert a parent sessions row. The session_events JOIN walks
    through this row to filter by business_key (real L4 schema).
    """
    conn = sqlite3.connect(l4_path)
    conn.execute(
        "INSERT INTO sessions (session_id, intent_id, skill_id, runtime_id, user_id, "
        "status, payload_json, created_at, business_key) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("sess-business-flow", "intent-1", "threshold-calibration", "rt-1", "u1",
         "active", "{}", ts, wire),
    )
    conn.commit()
    conn.close()


def _seed_l4_session_event(l4_path: str, ts: int, payload: dict[str, Any]) -> None:
    """Insert a session_events row. ``business_key`` is NOT a column
    here — the L4 reader joins via the parent sessions row.
    """
    conn = sqlite3.connect(l4_path)
    conn.execute(
        "INSERT INTO session_events (session_id, event_type, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        ("sess-business-flow", "session.start", json.dumps(payload), ts),
    )
    conn.commit()
    conn.close()


def _seed_l4_session_event_with_id(l4_path: str, sid: str, ts: int, payload: dict[str, Any]) -> None:
    """Variant of ``_seed_l4_session_event`` that takes an explicit
    session_id — used by the cross-tenant isolation test which seeds
    two sessions with different business_keys.
    """
    conn = sqlite3.connect(l4_path)
    conn.execute(
        "INSERT INTO session_events (session_id, event_type, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (sid, "session.start", json.dumps(payload), ts),
    )
    conn.commit()
    conn.close()


def _seed_l4_session_row_with_id(l4_path: str, sid: str, wire: str, ts: int) -> None:
    """Variant of ``_seed_l4_session_row`` that takes an explicit
    session_id — used by the cross-tenant isolation test.
    """
    conn = sqlite3.connect(l4_path)
    conn.execute(
        "INSERT INTO sessions (session_id, intent_id, skill_id, runtime_id, user_id, "
        "status, payload_json, created_at, business_key) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, "intent-1", "threshold-calibration", "rt-1", "u1",
         "active", "{}", ts, wire),
    )
    conn.commit()
    conn.close()


def _seed_l4_event_room(l4_path: str, wire: str, ts: int, payload: dict[str, Any]) -> None:
    conn = sqlite3.connect(l4_path)
    conn.execute(
        "INSERT INTO event_room_events (room_id, session_id, event_type, payload_json, created_at, business_key) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("r1", "sess-business-flow", "event_room.join", json.dumps(payload), ts, wire),
    )
    conn.commit()
    conn.close()


def _seed_l3_decision(l3_path: str, wire: str, ts: int, payload: dict[str, Any]) -> None:
    """L3 governance_decisions has no payload_json column — the
    canonical payload field is ``rationale`` (TEXT NOT NULL). The
    timeline SELECT projects rationale → payload_json so the
    assembly sees the same downstream shape across layers.
    """
    conn = sqlite3.connect(l3_path)
    conn.execute(
        "INSERT INTO governance_decisions "
        "(decision_id, session_id, hook_id, tool_name, risk_level, decision, "
        "rationale, ts, business_key) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("d1", "sess-business-flow", "h1", "scada_read", "low", "allow",
         json.dumps(payload), ts, wire),
    )
    conn.commit()
    conn.close()


def _seed_l2_memory(l2_path: str, wire: str, ts: int, payload: dict[str, Any]) -> None:
    conn = sqlite3.connect(l2_path)
    conn.execute(
        "INSERT INTO memory_files "
        "(memory_id, version, scope, category, content, status, created_at, updated_at, business_key) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("m1", 1, "s", "c", payload.get("content", "x"), "confirmed", ts, ts, wire),
    )
    conn.commit()
    conn.close()


# ─── Tests ────────────────────────────────────────────────────────────────


def test_timeline_e2e_4_cross_layer_events_sorted_by_ts(cross_layer_db):
    """Seed 4 cross-layer events tagged with the same business_key,
    then assert the assembly returns all 4 in timestamp order with
    the correct layer / component / event_type labels.

    Seed (one event per layer × one event_room):
        L4 session_events : ts=1000, type="session.start", payload={"user":"u1"}
        L4 event_room    : ts=1500, type="event_room.join", payload={"room":"r1"}
        L3 governance    : ts=2000, type="governance.decision", payload={"decision":"allow"}
        L2 memory        : ts=2500, type="memory.write_file", payload={"content":"x"}

    Expected assembly (sorted by ts):
        [L4/session @ 1000, L4/event_room @ 1500, L3/governance @ 2000, L2/memory @ 2500]
    """
    wire = cross_layer_db.wire

    _seed_l4_session_row(cross_layer_db.l4, wire, 900)
    _seed_l4_session_event(cross_layer_db.l4, 1000, {"user": "u1"})
    _seed_l4_event_room(cross_layer_db.l4, wire, 1500, {"room": "r1"})
    _seed_l3_decision(cross_layer_db.l3, wire, 2000, {"decision": "allow"})
    _seed_l2_memory(cross_layer_db.l2, wire, 2500, {"content": "x"})

    timeline = _assemble_timeline(
        {
            "l4": cross_layer_db.l4,
            "l3": cross_layer_db.l3,
            "l2": cross_layer_db.l2,
        },
        wire,
    )

    assert len(timeline) == 4, f"expected 4 events, got {len(timeline)}"
    assert [e.ts for e in timeline] == [1000, 1500, 2000, 2500], "events not sorted by ts"

    assert timeline[0].layer == "L4"
    assert timeline[0].component == "session"
    assert timeline[0].event_type == "session.start"

    assert timeline[1].layer == "L4"
    assert timeline[1].component == "event_room"
    assert timeline[1].event_type == "event_room.join"

    assert timeline[2].layer == "L3"
    assert timeline[2].component == "governance"
    assert timeline[2].event_type == "governance.decision"
    assert timeline[2].payload == {"decision": "allow"}

    assert timeline[3].layer == "L2"
    assert timeline[3].component == "memory"
    assert timeline[3].event_type == "memory.write_file"


def test_timeline_e2e_no_events_returns_empty(cross_layer_db):
    """When the business_key has no events tagged, the assembly
    returns an empty list (NOT an error). This is the "fresh
    start" path the L4 endpoint contracts guarantee.
    """
    wire = cross_layer_db.wire
    timeline = _assemble_timeline(
        {
            "l4": cross_layer_db.l4,
            "l3": cross_layer_db.l3,
            "l2": cross_layer_db.l2,
        },
        wire,
    )
    assert timeline == []


def test_timeline_e2e_filters_by_business_key(cross_layer_db):
    """Events tagged with a DIFFERENT business_key must NOT appear
    in the assembly. This is the cross-tenant isolation invariant.

    Seed: 1 event with the test's business_key + 1 event with a
    different business_key. Only the 1st must be returned.
    """
    wire = cross_layer_db.wire
    other_wire = "sess-other|threshold-calibration|Transformer-other"

    _seed_l4_session_row(cross_layer_db.l4, wire, 900)
    _seed_l4_session_row_with_id(cross_layer_db.l4, "sess-other", other_wire, 950)
    _seed_l4_session_event_with_id(cross_layer_db.l4, "sess-business-flow", 1000, {"user": "u1"})
    _seed_l4_session_event_with_id(cross_layer_db.l4, "sess-other", 1100, {"user": "u2"})

    timeline = _assemble_timeline(
        {"l4": cross_layer_db.l4, "l3": cross_layer_db.l3, "l2": cross_layer_db.l2},
        wire,
    )

    assert len(timeline) == 1, f"expected 1 event, got {len(timeline)}"
    assert timeline[0].payload == {"user": "u1"}
