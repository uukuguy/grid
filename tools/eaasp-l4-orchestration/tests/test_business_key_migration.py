"""Test v3.15 business_key column migration (OBSTACK §3.4).

Pre-v3.15 L4 DB schema has no ``business_key`` column on
``sessions`` or ``event_room_events``. After upgrade, both columns
must exist (idempotent ALTER), and both partial indices must be
present, so the flow_timeline aggregator can JOIN cross-table.

This test mirrors the FTS5 migration test pattern:
1. Simulate pre-migration DB (no business_key columns).
2. Call init_db() — must add the columns + indices without breaking
   legacy rows.
3. Verify pre-existing rows are still readable AND new rows can be
   inserted with a business_key value.
"""

from __future__ import annotations

import os
import tempfile

import aiosqlite

from eaasp_l4_orchestration.db import init_db


async def test_v315_business_key_columns_added_to_legacy_db() -> None:
    """Pre-v3.15 DB (no business_key) gets the columns after init_db."""
    db_path = tempfile.mktemp(suffix=".db")
    try:
        # Simulate pre-v3.15: full schema, no business_key columns.
        async with aiosqlite.connect(db_path) as db:
            await db.executescript(
                """
                CREATE TABLE sessions (
                    session_id  TEXT PRIMARY KEY,
                    status      TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at  INTEGER NOT NULL,
                    closed_at   INTEGER
                );
                CREATE TABLE event_room_events (
                    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id      TEXT NOT NULL,
                    session_id   TEXT NOT NULL,
                    event_type   TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at   INTEGER NOT NULL
                );
                INSERT INTO sessions
                    (session_id, status, payload_json, created_at)
                    VALUES ('legacy-001', 'closed', '{}', 1000);
                INSERT INTO event_room_events
                    (room_id, session_id, event_type, payload_json, created_at)
                    VALUES ('legacy-room', 'legacy-001', 'STOP', '{}', 1000);
                """
            )
            await db.commit()

        # Run the v3.15 migration (no-op on the new columns; idempotent
        # ALTERs + indices create).
        await init_db(db_path)

        # Verify the columns are now present on both tables.
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row

            sessions_rows = await (
                await db.execute("PRAGMA table_info(sessions)")
            ).fetchall()
            sessions_cols = {row[1] for row in sessions_rows}
            assert "business_key" in sessions_cols, (
                f"sessions.business_key missing after init_db; "
                f"got columns {sorted(sessions_cols)}"
            )

            room_rows = await (
                await db.execute("PRAGMA table_info(event_room_events)")
            ).fetchall()
            room_cols = {row[1] for row in room_rows}
            assert "business_key" in room_cols, (
                f"event_room_events.business_key missing after init_db; "
                f"got columns {sorted(room_cols)}"
            )

            # Pre-existing rows are still readable (legacy NULL business_key).
            legacy = await (
                await db.execute(
                    "SELECT session_id, business_key FROM sessions "
                    "WHERE session_id = 'legacy-001'"
                )
            ).fetchone()
            assert legacy is not None
            assert legacy["session_id"] == "legacy-001"
            assert legacy["business_key"] is None  # legacy column → NULL
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


async def test_v315_business_key_insertion_and_index_round_trip() -> None:
    """New rows can be inserted with business_key and indexed."""
    db_path = tempfile.mktemp(suffix=".db")
    try:
        await init_db(db_path)

        # Insert a session with a populated business_key.
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO sessions "
                "(session_id, status, payload_json, created_at, business_key) "
                "VALUES (?, ?, ?, ?, ?)",
                ("sess-A", "active", "{}", 2000,
                 "sess-A|skill-thr|Transformer-001"),
            )
            await db.execute(
                "INSERT INTO event_room_events "
                "(room_id, session_id, event_type, payload_json, "
                "created_at, business_key) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("room-A", "sess-A", "STOP", "{}", 2001,
                 "sess-A|skill-thr|Transformer-001"),
            )
            await db.commit()

        # Verify the values round-trip AND the partial index is used.
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            sess = await (
                await db.execute(
                    "SELECT business_key FROM sessions WHERE session_id = 'sess-A'"
                )
            ).fetchone()
            assert sess is not None and sess["business_key"] == (
                "sess-A|skill-thr|Transformer-001"
            )

            ev = await (
                await db.execute(
                    "SELECT business_key FROM event_room_events "
                    "WHERE session_id = 'sess-A'"
                )
            ).fetchone()
            assert ev is not None and ev["business_key"] == (
                "sess-A|skill-thr|Transformer-001"
            )

            # Index must exist on both tables.
            for idx in (
                "idx_sessions_business_key",
                "idx_event_room_events_business_key",
            ):
                present = await (
                    await db.execute(
                        "SELECT 1 FROM sqlite_master "
                        "WHERE type='index' AND name=?",
                        (idx,),
                    )
                ).fetchone()
                assert present is not None, f"missing index {idx}"
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass
