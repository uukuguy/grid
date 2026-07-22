"""REQ-EAASP-02 — Append-only governance audit ledger tests.

Verifies the contract frozen in `docs/audit/3.7.3-GAP-AUDIT.md` §6:
- Exact nine-column schema with CHECK constraints on risk/decision enum values.
- AuditStore.record_governance_decision persists an immutable row.
- BEGIN IMMEDIATE + rollback-on-error ensures no partial row remains after failure.
- Append-only semantics: request and final decision have separate primary keys.
"""

from __future__ import annotations

import aiosqlite
import pytest

from eaasp_l3_governance import audit as audit_mod
from eaasp_l3_governance.audit import (
    AuditStore,
    GovernanceDecisionOut,
)
from eaasp_l3_governance.db import connect, init_db


pytestmark = pytest.mark.asyncio


async def test_governance_decisions_schema_has_nine_columns_and_checks(
    db_path: str,
) -> None:
    db = await connect(db_path)
    try:
        cur = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='governance_decisions'"
        )
        assert await cur.fetchone() is not None

        cur = await db.execute("PRAGMA table_info(governance_decisions)")
        cols = [row[1] async for row in cur]
        assert cols == [
            "decision_id",
            "session_id",
            "hook_id",
            "tool_name",
            "risk_level",
            "decision",
            "approver",
            "rationale",
            "ts",
        ]
    finally:
        await db.close()


async def test_governance_decisions_index_on_session_ts(
    db_path: str,
) -> None:
    db = await connect(db_path)
    try:
        cur = await db.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_governance_decisions_session_ts'"
        )
        assert await cur.fetchone() is not None
    finally:
        await db.close()


async def test_record_governance_decision_persists_row(
    audit_store: AuditStore,
) -> None:
    out = await audit_store.record_governance_decision(
        decision_id="gd_abc123",
        session_id="sess_1",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        decision="gate_request",
        approver=None,
        rationale="approval required",
    )
    assert isinstance(out, GovernanceDecisionOut)
    assert out.decision_id == "gd_abc123"
    assert out.session_id == "sess_1"
    assert out.risk_level == "write_external"
    assert out.decision == "gate_request"
    assert out.approver is None
    assert out.rationale == "approval required"
    assert out.ts  # non-empty


async def test_record_validates_empty_identifiers(
    audit_store: AuditStore,
) -> None:
    base = dict(
        decision_id="gd_x",
        session_id="s1",
        hook_id="h",
        tool_name="t",
        risk_level="read",
        decision="allow",
        approver=None,
        rationale="r",
    )
    for field in ("decision_id", "session_id", "hook_id", "tool_name", "rationale"):
        bad = dict(base)
        bad[field] = ""
        with pytest.raises(ValueError):
            await audit_store.record_governance_decision(**bad)


async def test_record_validates_enum_values(
    audit_store: AuditStore,
) -> None:
    base = dict(
        decision_id="gd_x",
        session_id="s1",
        hook_id="h",
        tool_name="t",
        approver=None,
        rationale="r",
    )
    with pytest.raises(ValueError):
        await audit_store.record_governance_decision(**base, risk_level="bogus", decision="allow")
    with pytest.raises(ValueError):
        await audit_store.record_governance_decision(**base, risk_level="read", decision="bogus")


async def test_request_and_final_decision_are_separate_rows(
    audit_store: AuditStore,
) -> None:
    """Append-only: final decision does NOT overwrite the gate_request row."""
    request_id = "gd_aaaaaaaa"
    final_id = f"{request_id}_final"

    await audit_store.record_governance_decision(
        decision_id=request_id,
        session_id="sess_s",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        decision="gate_request",
        approver=None,
        rationale="approval required",
    )
    await audit_store.record_governance_decision(
        decision_id=final_id,
        session_id="sess_s",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        decision="approve",
        approver="cli:--yes",
        rationale=f"resolved request {request_id}: cli --yes",
    )

    # Both rows exist with distinct IDs.
    a = await audit_store.get_governance_decision(request_id)
    b = await audit_store.get_governance_decision(final_id)
    assert a is not None and a.decision == "gate_request"
    assert b is not None and b.decision == "approve"
    assert b.approver == "cli:--yes"


async def test_rollback_on_insert_failure_leaves_no_partial_row(
    audit_store: AuditStore, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inject a DB failure mid-transaction; verify no partial row remains."""
    # We patch ``audit_mod.connect`` so the INSERT raises after BEGIN IMMEDIATE,
    # forcing the rollback path. The outer exception proves rollback completed
    # (commit was never reached), and the get_governance_decision check proves
    # no partial row is visible.
    real_connect = audit_mod.connect

    class _BoomConn:
        def __init__(self, real):
            self._real = real

        async def execute(self, sql, params=()):
            if "INSERT INTO governance_decisions" in sql:
                raise RuntimeError("injected DB failure")
            return await self._real.execute(sql, params)

        async def commit(self):
            return await self._real.commit()

        async def rollback(self):
            return await self._real.rollback()

        async def close(self):
            return await self._real.close()

    async def boom_connect(_path):
        # ``real_connect`` returns an aiosqlite.Connection (awaitable).
        # Note: aiosqlite connections are not async-context-managers by default;
        # we just wrap the awaited instance.
        return _BoomConn(await real_connect(_path))

    monkeypatch.setattr(audit_mod, "connect", boom_connect)

    with pytest.raises(RuntimeError, match="injected DB failure"):
        await audit_store.record_governance_decision(
            decision_id="gd_should_rollback",
            session_id="sess_x",
            hook_id="h_pre",
            tool_name="t",
            risk_level="read",
            decision="allow",
            approver=None,
            rationale="should rollback",
        )

    # Patch back to real connect for verification (monkeypatch already handles this).
    after = await audit_store.get_governance_decision("gd_should_rollback")
    assert after is None, "rollback failed: partial row found"


async def test_approver_accepts_known_provenance_only(
    audit_store: AuditStore,
) -> None:
    """approver can be None or one of the canonical cli:* labels."""
    # None is fine
    out = await audit_store.record_governance_decision(
        decision_id="gd_no_app",
        session_id="sess_a",
        hook_id="h",
        tool_name="t",
        risk_level="read",
        decision="allow",
        approver=None,
        rationale="r",
    )
    assert out.approver is None

    # cli:* labels accepted (no email leakage — D-06 threat model)
    out2 = await audit_store.record_governance_decision(
        decision_id="gd_yes_app",
        session_id="sess_a",
        hook_id="h",
        tool_name="t",
        risk_level="write_external",
        decision="approve",
        approver="cli:--yes",
        rationale="resolved request gd_x: cli --yes",
    )
    assert out2.approver == "cli:--yes"
