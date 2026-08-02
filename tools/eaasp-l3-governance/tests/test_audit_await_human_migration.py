"""v3.12.0 — V311-AUDIT-01 / MIGRATION-01..02: targeted tests for the
idempotent ``migrate_decision_await_human`` ALTER TABLE migration.

REQ-IDs: MIGRATION-01 (idempotent migration widens CHECK constraint
on ``governance_decisions.decision`` from the v3.11.x 4-value
allowlist to the v3.12.0 5-value allowlist including ``await_human``)
and MIGRATION-02 (no data loss — pre-existing rows preserved through
the migration).

Covers:
- Hand-construct a v3.11-style DB schema (4-value CHECK, no
  ``await_human``) and run the migration; assert the schema now
  carries the widened allowlist.
- Repeat the migration call; assert it is a NO-OP (idempotency).
- Migration preserves all pre-existing rows.
- Migration preserves the ``stage`` column and its partial index
  when present (v3.11.2 backward-compat).
- ``init_db`` applies the migration on a freshly-created v3.11-style
  DB and the resulting schema accepts ``await_human`` inserts.
"""

from __future__ import annotations

import aiosqlite
import pytest

from eaasp_l3_governance.audit import AuditStore
from eaasp_l3_governance.db import (
    connect,
    init_db,
    migrate_decision_await_human,
)


pytestmark = pytest.mark.asyncio


V311_LEGACY_SCHEMA = """
CREATE TABLE governance_decisions (
    decision_id TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    hook_id     TEXT NOT NULL,
    tool_name   TEXT NOT NULL,
    risk_level  TEXT NOT NULL CHECK(risk_level IN ('read','write_local','write_external')),
    decision    TEXT NOT NULL CHECK(decision IN ('allow','approve','deny','gate_request')),
    approver    TEXT,
    rationale   TEXT NOT NULL,
    ts          TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

V3112_LEGACY_SCHEMA = """
CREATE TABLE governance_decisions (
    decision_id TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    hook_id     TEXT NOT NULL,
    tool_name   TEXT NOT NULL,
    risk_level  TEXT NOT NULL CHECK(risk_level IN ('read','write_local','write_external')),
    decision    TEXT NOT NULL CHECK(decision IN ('allow','approve','deny','gate_request')),
    approver    TEXT,
    rationale   TEXT NOT NULL,
    stage       TEXT,
    ts          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_governance_decisions_session_ts
    ON governance_decisions(session_id, ts DESC);
CREATE INDEX idx_governance_decisions_stage
    ON governance_decisions(stage) WHERE stage IS NOT NULL;
"""


async def _create_legacy_db(
    db_path: str, schema_sql: str, legacy_rows: list[tuple],
) -> None:
    """Hand-construct a v3.11-style ledger at ``db_path`` with
    optional pre-existing rows.

    The ``legacy_rows`` tuple order matches the column order in the
    schema_sql CREATE TABLE statement (decision_id, session_id,
    hook_id, tool_name, risk_level, decision, approver, rationale,
    [stage,] ts). The helper probes ``PRAGMA table_info`` to derive
    the column list, then issues a positional ``INSERT ... VALUES
    (?, ?, ...)`` that matches. Row tuples MUST match the legacy
    column order; the ``stage`` column is included when present.
    """
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(schema_sql)
        # Discover the column order so the INSERT binds the right
        # number of placeholders (9 for v3.11.0/1, 10 for v3.11.2).
        cur = await db.execute(
            "PRAGMA table_info(governance_decisions)"
        )
        cols = [row[1] async for row in cur]
        col_list = ", ".join(cols)
        placeholder = ", ".join(["?"] * len(cols))
        for row in legacy_rows:
            assert len(row) == len(cols), (
                f"legacy row has {len(row)} fields but the schema "
                f"defines {len(cols)} columns: {cols}"
            )
            await db.execute(
                f"INSERT INTO governance_decisions ({col_list}) "
                f"VALUES ({placeholder})",
                row,
            )
        await db.commit()


async def _get_schema_sql(db_path: str) -> str:
    db = await connect(db_path)
    try:
        cur = await db.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='governance_decisions'"
        )
        row = await cur.fetchone()
        return row["sql"] if row else ""
    finally:
        await db.close()


async def _count_rows(db_path: str, where: str = "", params: tuple = ()) -> int:
    sql = f"SELECT COUNT(*) AS n FROM governance_decisions {where}"
    db = await connect(db_path)
    try:
        cur = await db.execute(sql, params)
        row = await cur.fetchone()
        return int(row["n"])
    finally:
        await db.close()


# ─── MIGRATION-01: idempotent CHECK constraint widening ──────────────────────


async def test_migrate_decision_await_human_widens_v3_11_schema(
    tmp_path,
) -> None:
    """MIGRATION-01: a v3.11.0 DB (4-value CHECK) is upgraded to the
    v3.12.0 5-value CHECK including ``await_human``.
    """
    db_path = str(tmp_path / "v3110.db")
    await _create_legacy_db(db_path, V311_LEGACY_SCHEMA, [])

    migrated = await migrate_decision_await_human(db_path)
    assert migrated is True

    schema = await _get_schema_sql(db_path)
    assert "await_human" in schema


async def test_migrate_decision_await_human_is_idempotent_on_legacy_db(
    tmp_path,
) -> None:
    """MIGRATION-01: running the migration twice in a row converges
    to a single widened schema (no double-rewrite, no error).
    """
    db_path = str(tmp_path / "v3110_idem.db")
    await _create_legacy_db(db_path, V311_LEGACY_SCHEMA, [])

    first = await migrate_decision_await_human(db_path)
    second = await migrate_decision_await_human(db_path)
    third = await migrate_decision_await_human(db_path)
    assert first is True
    assert second is False
    assert third is False

    schema = await _get_schema_sql(db_path)
    # ``await_human`` appears exactly once in the widened CHECK.
    assert schema.count("'await_human'") == 1


async def test_migrate_decision_await_human_no_op_on_fresh_db(
    tmp_path,
) -> None:
    """MIGRATION-01: a fresh DB created by ``init_db`` already carries
    the widened allowlist inline; the migration is a NO-OP.
    """
    db_path = str(tmp_path / "v3120_fresh.db")
    await init_db(db_path)

    migrated = await migrate_decision_await_human(db_path)
    assert migrated is False

    schema = await _get_schema_sql(db_path)
    assert "await_human" in schema


# ─── MIGRATION-02: no data loss ──────────────────────────────────────────────


async def test_migrate_preserves_existing_rows_on_v3_11_schema(
    tmp_path,
) -> None:
    """MIGRATION-02: legacy rows survive the migration verbatim.
    Each v3.11.x decision value (allow / approve / deny / gate_request)
    lands unchanged in the widened table.
    """
    db_path = str(tmp_path / "v3110_preserve.db")
    legacy_rows = [
        (
            "gd_legacy_allow",
            "sess_a",
            "h_pre",
            "t",
            "read",
            "allow",
            None,
            "v3.11.0 legacy allow row",
            "2026-07-26 12:00:00",
        ),
        (
            "gd_legacy_approve",
            "sess_b",
            "h_pre",
            "t",
            "write_external",
            "approve",
            "cli:--yes",
            "v3.11.0 legacy approve row",
            "2026-07-26 12:01:00",
        ),
        (
            "gd_legacy_deny",
            "sess_c",
            "h_pre",
            "t",
            "write_external",
            "deny",
            "policy:drop",
            "v3.11.0 legacy deny row",
            "2026-07-26 12:02:00",
        ),
        (
            "gd_legacy_gate",
            "sess_d",
            "h_pre",
            "t",
            "write_external",
            "gate_request",
            None,
            "v3.11.0 legacy gate_request row",
            "2026-07-26 12:03:00",
        ),
    ]
    await _create_legacy_db(db_path, V311_LEGACY_SCHEMA, legacy_rows)

    migrated = await migrate_decision_await_human(db_path)
    assert migrated is True

    n = await _count_rows(db_path)
    assert n == 4

    db = await connect(db_path)
    try:
        for decision_id, expected_decision in [
            ("gd_legacy_allow", "allow"),
            ("gd_legacy_approve", "approve"),
            ("gd_legacy_deny", "deny"),
            ("gd_legacy_gate", "gate_request"),
        ]:
            cur = await db.execute(
                "SELECT decision, approver, rationale FROM governance_decisions "
                "WHERE decision_id = ?",
                (decision_id,),
            )
            row = await cur.fetchone()
            assert row is not None
            assert row["decision"] == expected_decision
    finally:
        await db.close()


async def test_migrate_preserves_stage_column_on_v3_11_2_schema(
    tmp_path,
) -> None:
    """MIGRATION-02: the v3.11.2 ``stage`` column and its partial
    index survive the migration. Backwards compatibility with
    v3.11.2 / v3.11.3 rows is preserved.
    """
    db_path = str(tmp_path / "v3112_preserve.db")
    legacy_rows = [
        (
            "gd_v3112_approve",
            "sess_e",
            "h_pre",
            "t",
            "write_external",
            "approve",
            "cli:--yes",
            "v3.11.2-era row with stage column",
            "approve",  # stage column value
            "2026-07-27 09:00:00",
        ),
    ]
    await _create_legacy_db(db_path, V3112_LEGACY_SCHEMA, legacy_rows)

    migrated = await migrate_decision_await_human(db_path)
    assert migrated is True

    # The ``stage`` column is still present (PRAGMA table_info).
    db = await connect(db_path)
    try:
        cur = await db.execute("PRAGMA table_info(governance_decisions)")
        cols = [row[1] async for row in cur]
        assert "stage" in cols

        # The legacy row's ``stage`` value survived.
        cur = await db.execute(
            "SELECT stage, decision FROM governance_decisions "
            "WHERE decision_id = ?",
            ("gd_v3112_approve",),
        )
        row = await cur.fetchone()
        assert row is not None
        assert row["stage"] == "approve"
        assert row["decision"] == "approve"
    finally:
        await db.close()


# ─── MIGRATION-01 + 02: round-trip on real AuditStore ────────────────────────


async def test_migrated_legacy_db_accepts_await_human_via_audit_store(
    tmp_path,
) -> None:
    """MIGRATION-01 + MIGRATION-02 end-to-end: a v3.11.x ledger is
    migrated, then ``AuditStore.record_governance_decision`` accepts
    ``await_human`` without IntegrityError.
    """
    db_path = str(tmp_path / "v3110_e2e.db")
    await _create_legacy_db(
        db_path,
        V311_LEGACY_SCHEMA,
        [
            (
                "gd_v3110_e2e",
                "sess_pre",
                "h_pre",
                "t",
                "write_external",
                "approve",
                None,
                "pre-migration row",
                "2026-07-26 12:00:00",
            ),
        ],
    )

    await migrate_decision_await_human(db_path)

    # v3.15.5 — V315-BUSINESS-FLOW-02 — production brings DB to current
    # state via init_db() which adds business_key idempotently. The legacy
    # v3.11.x schema here only has 9 columns, so we run init_db after the
    # migration to layer on the v3.15.x business_key column without
    # touching the migrated decision CHECK constraint.
    await init_db(db_path)

    audit_store = AuditStore(db_path)
    out = await audit_store.record_governance_decision(
        decision_id="gd_v3120_e2e",
        session_id="sess_post",
        hook_id="h_pre",
        tool_name="t",
        risk_level="write_external",
        decision="await_human",
        approver="caller",
        rationale="post-migration await_human row",
    )
    assert out.decision == "await_human"

    # Pre-migration row is preserved.
    db = await connect(db_path)
    try:
        cur = await db.execute(
            "SELECT decision, approver FROM governance_decisions "
            "WHERE decision_id = ?",
            ("gd_v3110_e2e",),
        )
        row = await cur.fetchone()
        assert row is not None
        assert row["decision"] == "approve"
    finally:
        await db.close()


async def test_init_db_applies_migration_on_legacy_schema(
    tmp_path,
) -> None:
    """MIGRATION-01 + MIGRATION-02: ``init_db`` invokes the migration
    on a pre-existing v3.11.x ledger; calling ``init_db`` again on
    the same file is a NO-OP.
    """
    db_path = str(tmp_path / "v3110_init.db")
    await _create_legacy_db(db_path, V311_LEGACY_SCHEMA, [])

    # ``init_db`` runs the SCHEMA (CREATE IF NOT EXISTS — no-op on
    # pre-existing tables) + the migration (which widens the CHECK).
    await init_db(db_path)

    schema = await _get_schema_sql(db_path)
    assert "await_human" in schema

    # Second ``init_db`` call converges (idempotent).
    await init_db(db_path)
    schema_again = await _get_schema_sql(db_path)
    assert schema_again == schema

    # New ``await_human`` inserts land.
    audit_store = AuditStore(db_path)
    out = await audit_store.record_governance_decision(
        decision_id="gd_after_init",
        session_id="sess_post",
        hook_id="h_pre",
        tool_name="t",
        risk_level="read",
        decision="await_human",
        approver=None,
        rationale="post-init_db await_human row",
    )
    assert out.decision == "await_human"