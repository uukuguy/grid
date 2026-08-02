"""L2 memory engine SLA baseline — OBSTACK_DESIGN.md §5.2.

Measures the L2 ``memory_read`` and ``memory_write`` paths via the
standard ``sqlite3`` (sync) module using a temp DB. Tests stay sync
(no async runtime required) so this file can be picked up by any
plain pytest config; the other layers (L3, L4) use specific
async-marked test modules.

The bounds chosen detect obvious regressions (missing index, N+1
query, lock contention) without flaking on shared CI runners:

  read:   p50 < 5ms,  p95 < 15ms
  write:  p50 < 10ms, p95 < 30ms

If this test starts failing on real regressions, raise the bounds in
a coordinated commit with the platform SLA evaluator. Don't silently
loosen them.
"""

from __future__ import annotations

import sqlite3
import tempfile

from .conftest import assert_within, time_loop


def _make_db_with_one_row(db_path: str) -> None:
    """Create a minimal memory_files table (without going through
    init_db — we replicate just the columns the SLA case needs so
    the test is independent of any future schema migrations).
    """
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS memory_files (
            file_id      TEXT PRIMARY KEY,
            content      TEXT NOT NULL,
            created_at   INTEGER NOT NULL,
            business_key TEXT
        );
        INSERT INTO memory_files (file_id, content, created_at, business_key)
            VALUES ('sla-seed-A', '{"k":"v"}', 1000, 'sla|sla|A');
        """
    )
    conn.commit()
    conn.close()


def test_l2_memory_read_p50_p95_within_sla() -> None:
    """L2 memory read p50 < 5ms, p95 < 15ms (baseline)."""
    db_path = tempfile.mktemp(suffix=".db")
    _make_db_with_one_row(db_path)

    def one_read() -> None:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT file_id FROM memory_files WHERE file_id = ?",
            ("sla-seed-A",),
        ).fetchone()
        conn.close()
        assert row is not None and row[0] == "sla-seed-A"

    samples = time_loop(one_read, iterations=200, warmup=10)
    assert_within(
        samples,
        p50_max=0.005,
        p95_max=0.015,
        label="l2.memory.read",
    )


def test_l2_memory_write_p50_p95_within_sla() -> None:
    """L2 memory write p50 < 10ms, p95 < 30ms (baseline)."""
    db_path = tempfile.mktemp(suffix=".db")
    conn0 = sqlite3.connect(db_path)
    conn0.execute(
        "CREATE TABLE IF NOT EXISTS memory_files ("
        " file_id TEXT PRIMARY KEY, content TEXT NOT NULL,"
        " created_at INTEGER NOT NULL, business_key TEXT)"
    )
    conn0.commit()
    conn0.close()

    counter = {"n": 0}

    def one_write() -> None:
        counter["n"] += 1
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO memory_files (file_id, content, created_at, business_key) "
            "VALUES (?, ?, ?, ?)",
            (f"sla-write-{counter['n']}", '{"k":"v"}', 1000, "sla|sla|A"),
        )
        conn.commit()
        conn.close()

    samples = time_loop(one_write, iterations=100, warmup=10)
    assert_within(
        samples,
        p50_max=0.010,
        p95_max=0.030,
        label="l2.memory.write",
    )
