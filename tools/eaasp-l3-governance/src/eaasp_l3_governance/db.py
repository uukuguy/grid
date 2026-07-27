"""Shared SQLite schema and connection helpers for L3 governance.

Mirrors the conventions locked in S3.T2 (L2 memory engine):
- WAL journal mode for concurrent readers.
- ``foreign_keys`` pragma on every open (defense-in-depth).
- Row factory set so callers can use ``row["col"]`` access.
- Writes must be wrapped in ``BEGIN IMMEDIATE`` (enforced at call sites — C1).
"""

from __future__ import annotations

import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Contract 1 — versioned managed-settings.json snapshots.
-- Append-only: a policy "deploy" is always a new row.
CREATE TABLE IF NOT EXISTS managed_settings_versions (
    version       INTEGER PRIMARY KEY AUTOINCREMENT,
    payload_json  TEXT NOT NULL,
    hook_count    INTEGER NOT NULL,
    mode_summary  TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_managed_settings_created_at
    ON managed_settings_versions(created_at DESC);

-- Contract 1 — per-hook mode overrides that float above the version rows.
-- One row per hook_id; updated in place (kept separate so mode flips do not
-- bump the policy version number — aligns with §3.3 "thin L3" semantics).
CREATE TABLE IF NOT EXISTS managed_hooks_mode_overrides (
    hook_id    TEXT PRIMARY KEY,
    mode       TEXT NOT NULL CHECK(mode IN ('enforce','shadow')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Contract 4 — async PostToolUse telemetry ingest.
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

CREATE INDEX IF NOT EXISTS idx_telemetry_session
    ON telemetry_events(session_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_received_at
    ON telemetry_events(received_at DESC);

-- REQ-EAASP-02 (Phase 3.7.3): append-only governance decision ledger.
-- Captures both the initial gate_request and the final approve/deny decision
-- as separate rows (different decision_id values) — see audit §6.3.
-- v3.11.2: the optional ``stage`` column carries the 5-stage approval
-- chain stage name (plan/check/draft/approve/execute). Default NULL
-- preserves v3.11.0 / v3.11.1 rows; the column is always present in
-- fresh schemas so the audit query does not need a column-presence
-- probe.
-- v3.12.0 — V311-AUDIT-01 / SCHEMA-01..03: the ``decision`` CHECK
-- allowlist now includes ``await_human`` (the 5-stage state machine's
-- pause-on-Approve sentinel). Fresh schemas carry the widened
-- constraint inline; existing v3.11.x DBs are upgraded via the
-- idempotent ``migrate_decision_await_human`` migration below.
--
-- Note: indexes on ``governance_decisions`` are NOT created here
-- because the ``stage`` column is added conditionally below; the
-- indexes are created in ``init_db`` AFTER the conditional column
-- add so legacy v3.11.0 / v3.11.1 DBs (which lack ``stage``) don't
-- fail the CREATE INDEX with ``no such column: stage``. ``init_db``
-- also runs the indexes again after ``migrate_decision_await_human``
-- in case the migration's table-rebuild dropped them.
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


# Indexes on governance_decisions are created AFTER the table exists
# (and after the v3.11.2 ``stage`` column migration runs). See
# ``_create_governance_decisions_indexes`` for the helper.
_GOVERNANCE_DECISIONS_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_governance_decisions_session_ts "
    "ON governance_decisions(session_id, ts DESC)",
    "CREATE INDEX IF NOT EXISTS idx_governance_decisions_stage "
    "ON governance_decisions(stage) WHERE stage IS NOT NULL",
)


async def _create_governance_decisions_indexes(path: str) -> None:
    """Create governance_decisions indexes idempotently.

    Called from ``init_db`` after the conditional ``stage`` column
    add and again after ``migrate_decision_await_human`` (which
    rebuilds the table and drops indexes).
    """
    async with aiosqlite.connect(path) as db:
        for ddl in _GOVERNANCE_DECISIONS_INDEXES:
            await db.execute(ddl)
        await db.commit()


async def init_db(path: str) -> None:
    """Create schema if absent, then apply idempotent migrations."""
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()

    # D26 / L3-08 — add tiebreaker column (idempotent via PRAGMA table_info probe)
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("PRAGMA table_info(telemetry_events)")
        columns = [row[1] async for row in cur]
        if "tiebreaker" not in columns:
            await db.execute(
                "ALTER TABLE telemetry_events ADD COLUMN tiebreaker INTEGER NOT NULL DEFAULT 0"
            )
            await db.commit()

    # v3.11.2 — add stage column to the governance decision ledger
    # (idempotent via PRAGMA table_info probe). Old v3.11.0 / v3.11.1
    # databases get a NULL default for the column; the AuditStore
    # SELECT queries select NULL as Python None.
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("PRAGMA table_info(governance_decisions)")
        columns = [row[1] async for row in cur]
        if "stage" not in columns:
            await db.execute(
                "ALTER TABLE governance_decisions ADD COLUMN stage TEXT"
            )
            await db.commit()

    # Indexes that depend on ``stage`` are created after the column
    # add so legacy v3.11.0 / v3.11.1 DBs (no ``stage`` column yet)
    # don't fail with ``no such column: stage``.
    await _create_governance_decisions_indexes(path)

    # v3.12.0 — V311-AUDIT-01 / SCHEMA-02 — widen the CHECK constraint on
    # ``governance_decisions.decision`` to include ``await_human``
    # (idempotent: detects a pre-migration CHECK that lacks the sentinel
    # and rebuilds the table; no-op on fresh schemas that already include
    # it inline). The migration preserves all existing rows.
    migrated = await migrate_decision_await_human(path)
    if migrated:
        # The migration rebuilds the table and recreates the indexes
        # itself; but if the legacy DB did not have the ``stage``
        # column (v3.11.0 / v3.11.1), the migration's
        # ``idx_governance_decisions_stage`` CREATE would have failed
        # the same way the inline SCHEMA did. Run the indexes again
        # defensively.
        await _create_governance_decisions_indexes(path)


async def migrate_decision_await_human(path: str) -> bool:
    """Idempotently widen the CHECK constraint on governance_decisions.decision.

    v3.12.0 — V311-AUDIT-01 / SCHEMA-02:

    - Fresh schemas (v3.12.0+ CREATE TABLE) carry the widened allowlist
      inline (see ``SCHEMA``); this function is a NO-OP for those.
    - v3.11.x databases carry the legacy 4-value CHECK
      (``allow, approve, deny, gate_request``). The 5-stage state
      machine emits ``await_human`` at the Approve stage pause; without
      this migration, ``record_governance_decision`` would fail with an
      ``aiosqlite.IntegrityError`` on the paused chain and the human
      verdict would never reach the audit ledger.

    Migration strategy: SQLite does not support ``ALTER TABLE ... DROP
    CONSTRAINT`` or ``ALTER TABLE ... ALTER COLUMN``, so we:

    1. Probe the current CHECK clause via ``sqlite_master``.
    2. If it already contains ``await_human``, return ``False`` (NO-OP).
    3. Otherwise, rename the old table to ``governance_decisions__legacy_v3_11``,
       create the new table with the widened allowlist, copy every row
       across (column-for-column), and drop the legacy table. Existing
       rows keep their original ``decision`` values (they are all in
       the 4-value legacy set, which is a subset of the widened one).

    Returns ``True`` if a migration ran, ``False`` if the DB was already
    up-to-date. Idempotent: calling twice in a row converges (the second
    call finds ``await_human`` already in the CHECK clause and returns
    ``False``).
    """
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='governance_decisions'"
        )
        row = await cur.fetchone()
        if row is None:
            # Fresh DB without the table — init_db() will create it with
            # the widened allowlist inline. Nothing to migrate.
            return False
        existing_sql = row["sql"] or ""
        # The CHECK allowlist is the token list after ``CHECK(decision IN (``.
        if "await_human" in existing_sql:
            return False  # already migrated

        # Run the table-rebuild inside BEGIN IMMEDIATE so concurrent
        # writers (per C1 convention) serialize. Same atomicity shape
        # as the v3.11.2 ``stage`` column add — although SQLite's
        # rename+create+copy+drop is intrinsically transactional in
        # autocommit mode, BEGIN IMMEDIATE matches the project-wide
        # write-path convention (audit §C1).
        await db.execute("BEGIN IMMEDIATE")
        try:
            # Probe the legacy column list. v3.11.0 / v3.11.1 had no
            # ``stage`` column; v3.11.2 added it via ALTER TABLE; we
            # copy only the columns the legacy row actually carries,
            # defaulting ``stage`` to NULL for pre-v3.11.2 rows.
            cur = await db.execute(
                "PRAGMA table_info(governance_decisions)"
            )
            legacy_cols = [row[1] async for row in cur]
            await db.execute(
                "ALTER TABLE governance_decisions "
                "RENAME TO governance_decisions__legacy_v3_11"
            )
            # Recreate with the widened CHECK. Identical to the inline
            # ``SCHEMA`` definition above — kept inline here so the
            # migration is self-contained.
            await db.execute(
                """
                CREATE TABLE governance_decisions (
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
                )
                """
            )
            # Copy every row across, projecting only the columns the
            # legacy table carries. ``stage`` defaults to NULL when
            # missing on the legacy row (pre-v3.11.2).
            col_list = ", ".join(legacy_cols)
            await db.execute(
                f"INSERT INTO governance_decisions ({col_list}) "
                f"SELECT {col_list} FROM governance_decisions__legacy_v3_11"
            )
            await db.execute(
                "DROP TABLE governance_decisions__legacy_v3_11"
            )
            # Rebuild the dependent indexes (the CREATE TABLE didn't
            # recreate them — only the column-level constraints carried
            # over). Match the inline ``SCHEMA`` definitions.
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_governance_decisions_session_ts "
                "ON governance_decisions(session_id, ts DESC)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_governance_decisions_stage "
                "ON governance_decisions(stage) WHERE stage IS NOT NULL"
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return True


async def connect(path: str) -> aiosqlite.Connection:
    """Open a connection with row factory set and pragmas applied."""
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    # Defense-in-depth: reapply pragmas on every connection. WAL is persistent
    # (set on the file) but foreign_keys is a per-connection flag.
    await db.execute("PRAGMA foreign_keys=ON")
    return db
