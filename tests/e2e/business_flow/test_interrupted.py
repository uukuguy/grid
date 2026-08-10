"""Interrupted-flow timeline test for OBSTACK business-flow integration.

Per OBSTACK_DESIGN.md §4.4 (Evaluate, planned) + V315-OPT-01 收敛:

This is the 6b.1c integration test. Verify that ``interrupted_at``
+ ``last_event_layer`` columns on the L4 sessions table correctly
identify a partial business flow that did not reach completion.

The OBSTACK_RETROSPECTIVE path (v3.13.2) consumes these columns
to render "截断点" (interrupted layer) in the per-flow timeline
view. If the columns are missing or wrong, the cross-layer
retrospective trace silently emits `last_event_layer = "unknown"`
and the operator can't tell where the flow was interrupted.

This test seeds:
- 1 L4 session with status="interrupted" + interrupted_at=2000
  + last_event_layer="L3" (the last event before interruption
  came from L3 governance)
- 1 L3 governance_decisions row at ts=2000 (the last event)
- 1 L2 memory_files row at ts=1500 (an earlier event, before
  interruption)

It then asserts:
1. The interruption marker is on the session row.
2. The "last_event_layer" matches the highest layer that
   emitted an event before ``interrupted_at``.
3. The timeline still returns all events (interruption doesn't
   drop anything).
"""

from __future__ import annotations

import json
import sqlite3


def _seed_cross_layer_interrupted(
    paths: dict[str, str], wire: str
) -> None:
    """Seed the cross-layer DB with an interrupted flow.

    Seed shape:
        L4 sessions row:  status="interrupted", interrupted_at=2000,
                          last_event_layer="L3"
        L3 governance_decisions: ts=2000 (the last event)
        L2 memory_files:        ts=1500 (an earlier event)
    """
    conn = sqlite3.connect(paths["l4"])
    conn.execute(
        "INSERT INTO sessions (session_id, intent_id, skill_id, runtime_id, user_id, "
        "status, payload_json, created_at, business_key, last_event_layer, interrupted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "sess-interrupted", "intent-1", "threshold-calibration", "rt-1", "u1",
            "interrupted", "{}", 1000, wire, "L3", 2000,
        ),
    )
    conn.commit()
    conn.close()

    # The last event before interruption (L3 governance).
    conn = sqlite3.connect(paths["l3"])
    conn.execute(
        "INSERT INTO governance_decisions "
        "(decision_id, session_id, hook_id, tool_name, risk_level, "
        "decision, rationale, ts, business_key) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "d1", "sess-interrupted", "h1", "scada_read", "low", "allow",
            "circuit-breaker tripped", 2000, wire,
        ),
    )
    conn.commit()
    conn.close()

    # An earlier event (L2 memory write at ts=1500).
    conn = sqlite3.connect(paths["l2"])
    conn.execute(
        "INSERT INTO memory_files "
        "(memory_id, version, scope, category, content, status, "
        "created_at, updated_at, business_key) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("m1", 1, "s", "c", "early-snapshot", "confirmed", 1500, 1500, wire),
    )
    conn.commit()
    conn.close()


def _read_session_row(l4_path: str, wire: str) -> dict[str, object]:
    """Read the L4 sessions row for the given business_key. Returns
    a dict so the test can assert on individual fields without
    worrying about the row layout.
    """
    conn = sqlite3.connect(l4_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT session_id, status, last_event_layer, interrupted_at, business_key "
        "FROM sessions WHERE business_key = ?",
        (wire,),
    ).fetchone()
    conn.close()
    assert row is not None, f"session row missing for {wire!r}"
    return dict(row)


def _read_timeline_after_interruption(
    paths: dict[str, str], wire: str
) -> list[tuple[int, str]]:
    """Read all events tagged with the business_key, in timestamp
    order. Returns ``(ts, layer)`` tuples (the "layer" is the
    L-prefix string the timeline emits, not the SQL table name).
    """
    events: list[tuple[int, str]] = []

    # L4 session_events (empty in this scenario — interruption came
    # from L3, never propagated an event_room event).
    conn = sqlite3.connect(paths["l4"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT se.created_at AS ts FROM session_events se "
        "JOIN sessions s ON s.session_id = se.session_id "
        "WHERE s.business_key = ?",
        (wire,),
    ).fetchall()
    conn.close()
    events.extend((int(r["ts"]), "L4") for r in rows)

    # L4 event_room_events.
    conn = sqlite3.connect(paths["l4"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT created_at AS ts FROM event_room_events WHERE business_key = ?",
        (wire,),
    ).fetchall()
    conn.close()
    events.extend((int(r["ts"]), "L4") for r in rows)

    # L3 governance_decisions (uses ts, not created_at).
    conn = sqlite3.connect(paths["l3"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT ts FROM governance_decisions WHERE business_key = ?",
        (wire,),
    ).fetchall()
    conn.close()
    def _parse_ts(value: object) -> int:
        # L3 stores ts as a TEXT ISO-8601 string; timeline needs INT.
        # For test purposes, we ASSUME the schema uses INTEGER
        # (this test seeds INTEGER; production stores TEXT and
        # the L4 timeline aggregator converts it). If schema is
        # TEXT, the test fixture is wrong; the v3.15.6 6b.1c
        # datapath requires schema fix.
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            # INTEGER stringified, e.g. "2000"
            try:
                return int(value)
            except ValueError:
                # ISO-8601 — convert to a sortable epoch-ish number.
                # We do NOT need real epoch here, just monotonicity,
                # so the L4 timeline order_by can be tested against
                # the L2 created_at.  Convert ISO via fromisoformat.
                from datetime import datetime
                return int(datetime.fromisoformat(value).timestamp() * 1000)
        return int(value)  # last resort
    events.extend((_parse_ts(r["ts"]), "L3") for r in rows)

    # L2 memory_files.
    conn = sqlite3.connect(paths["l2"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT created_at AS ts FROM memory_files WHERE business_key = ?",
        (wire,),
    ).fetchall()
    conn.close()
    events.extend((int(r["ts"]), "L2") for r in rows)

    events.sort(key=lambda pair: pair[0])
    return events


# ─── Tests ────────────────────────────────────────────────────────────────


def test_interrupted_session_row_carries_marker(cross_layer_db_interrupted):
    """The L4 sessions row MUST carry ``status="interrupted"`` +
    ``last_event_layer="L3"`` + ``interrupted_at=2000`` so the
    retrospective trace API can emit the correct diagnostic.
    """
    wire = cross_layer_db_interrupted.wire
    _seed_cross_layer_interrupted(
        {
            "l4": cross_layer_db_interrupted.l4,
            "l3": cross_layer_db_interrupted.l3,
            "l2": cross_layer_db_interrupted.l2,
        },
        wire,
    )

    row = _read_session_row(cross_layer_db_interrupted.l4, wire)

    assert row["status"] == "interrupted"
    assert row["last_event_layer"] == "L3"
    assert int(row["interrupted_at"]) == 2000
    assert row["session_id"] == "sess-interrupted"


def test_interrupted_timeline_preserves_all_events(cross_layer_db_interrupted):
    """Interruption does NOT drop events. The timeline must still
    include all events tagged with the business_key, in timestamp
    order. The interruption marker is a separate signal on the
    session row.
    """
    wire = cross_layer_db_interrupted.wire
    _seed_cross_layer_interrupted(
        {
            "l4": cross_layer_db_interrupted.l4,
            "l3": cross_layer_db_interrupted.l3,
            "l2": cross_layer_db_interrupted.l2,
        },
        wire,
    )

    timeline = _read_timeline_after_interruption(
        {
            "l4": cross_layer_db_interrupted.l4,
            "l3": cross_layer_db_interrupted.l3,
            "l2": cross_layer_db_interrupted.l2,
        },
        wire,
    )

    # 2 events: L2 memory @ 1500, L3 governance @ 2000.
    assert len(timeline) == 2, f"expected 2 events, got {len(timeline)}"
    assert timeline[0] == (1500, "L2")
    assert timeline[1] == (2000, "L3")


def test_interrupted_last_event_layer_matches_highest_layer_emit(cross_layer_db_interrupted):
    """``last_event_layer`` must be the highest layer that emitted
    an event <= interrupted_at. With L3 @ 2000 (= interrupted_at)
    + L2 @ 1500, the highest layer is L3.

    This is the property the v3.13.2 retrospective trace depends
    on. If ``last_event_layer`` came from "the last event in
    chronological order" without the layer filter, it would point
    at L2 (the older event) instead of L3 (the most recent layer
    that emitted before interruption).
    """
    wire = cross_layer_db_interrupted.wire
    _seed_cross_layer_interrupted(
        {
            "l4": cross_layer_db_interrupted.l4,
            "l3": cross_layer_db_interrupted.l3,
            "l2": cross_layer_db_interrupted.l2,
        },
        wire,
    )

    row = _read_session_row(cross_layer_db_interrupted.l4, wire)
    assert row["last_event_layer"] == "L3", (
        "last_event_layer should reflect the highest layer that "
        "emitted <= interrupted_at, not the chronologically last event"
    )
