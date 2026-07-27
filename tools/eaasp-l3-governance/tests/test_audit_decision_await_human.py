"""v3.12.0 — V311-AUDIT-01 / AWAIT-HUMAN-01..02: audit.py + state machine
contract tests for the ``DECISION_AWAIT_HUMAN`` sentinel.

REQ-IDs: AWAIT-HUMAN-01 (audit.py CHECK constraint + enum allowlist
accepts ``await_human``) and AWAIT-HUMAN-02 (5-stage state machine
routes ``DECISION_AWAIT_HUMAN`` through the full
``record_governance_decision`` flow and the row lands in the ledger).

Covers:
- ``record_governance_decision`` accepts ``await_human`` after the
  migration runs (no ``ValueError`` / no ``aiosqlite.IntegrityError``).
- The migration applied to an existing v3.11.x DB allows the new
  sentinel value while preserving the historical rows.
- 5-stage state machine: an Approve-stage pause writes a
  ``DECISION_AWAIT_HUMAN`` row in the ledger (no silent swallowing).
- After the human signs off, the resume path writes the human
  verdict (``allow`` / ``deny``) as a follow-on row.
"""

from __future__ import annotations

import pytest

from eaasp_l3_governance.approval_state_machine import (
    APPROVAL_STAGE_APPROVE,
    APPROVAL_STAGE_PLAN,
    DECISION_ALLOW,
    DECISION_AWAIT_HUMAN,
    DECISION_DENY,
    ApprovalStagePolicy,
    ApprovalStateMachine,
)
from eaasp_l3_governance.audit import (
    DECISION_ALLOWLIST,
    AuditStore,
    GovernanceDecisionOut,
)
from eaasp_l3_governance.db import (
    connect,
    init_db,
    migrate_decision_await_human,
)


pytestmark = pytest.mark.asyncio


# ─── In-process enum validation ──────────────────────────────────────────────


async def test_decision_allowlist_includes_await_human() -> None:
    """AWAIT-HUMAN-01: the in-process enum allowlist is widened.

    Mirrors the DB CHECK allowlist so callers see a clean
    ``ValueError`` (not an ``aiosqlite.IntegrityError``) on every
    code path.
    """
    assert "await_human" in DECISION_ALLOWLIST
    # Backwards-compat — all v3.11.x values still in the set.
    for legacy in ("allow", "approve", "deny", "gate_request"):
        assert legacy in DECISION_ALLOWLIST


async def test_record_governance_decision_accepts_await_human(
    audit_store: AuditStore,
) -> None:
    """AWAIT-HUMAN-01: ``record_governance_decision`` accepts
    ``await_human`` and persists the row.
    """
    out = await audit_store.record_governance_decision(
        decision_id="gd_await_1",
        session_id="sess_await",
        hook_id="h_pre",
        tool_name="t",
        risk_level="write_external",
        decision=DECISION_AWAIT_HUMAN,
        approver="caller",
        rationale="human-in-the-loop pause",
        stage="approve_pause",
    )
    assert isinstance(out, GovernanceDecisionOut)
    assert out.decision == "await_human"
    assert out.stage == "approve_pause"


async def test_record_governance_decision_rejects_unknown_decision(
    audit_store: AuditStore,
) -> None:
    """The in-process enum still rejects unknown decision values."""
    with pytest.raises(ValueError, match="decision must be one of"):
        await audit_store.record_governance_decision(
            decision_id="gd_bogus",
            session_id="s1",
            hook_id="h",
            tool_name="t",
            risk_level="read",
            decision="bogus_value",
            approver=None,
            rationale="r",
        )


# ─── Migration on a pre-existing v3.11.x ledger ──────────────────────────────


async def test_audit_allowlist_after_migrate_on_existing_db(tmp_path) -> None:
    """AWAIT-HUMAN-01 + AWAIT-HUMAN-02: the migration is idempotent
    and unlocks the new sentinel on pre-existing DBs without losing
    history.

    Hand-constructs a v3.11.0-style ledger (4-value CHECK allowlist,
    no ``stage`` column, no ``await_human``), inserts a legacy row,
    runs the migration, and verifies:

    - the legacy row is preserved,
    - the new CHECK allowlist includes ``await_human``,
    - a fresh ``record_governance_decision(..., decision="await_human")``
      succeeds.
    """
    import aiosqlite

    db_path = tmp_path / "v311x.db"
    # Hand-construct a v3.11.0-style ledger: 4-value CHECK, no
    # ``stage`` column. This is the schema shape ``audit.py`` shipped
    # at v3.11.0 / v3.11.1; v3.11.2 added the ``stage`` column on
    # top via an idempotent ``ALTER TABLE`` migration. We strip the
    # ``stage`` column too so the test exercises a true pre-v3.11.2
    # DB (the migration logic does not depend on the ``stage``
    # column's presence).
    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(
            """
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
        )
        # Insert a legacy row so the migration has something to preserve.
        await db.execute(
            """
            INSERT INTO governance_decisions
                (decision_id, session_id, hook_id, tool_name,
                 risk_level, decision, approver, rationale, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "gd_legacy_1",
                "sess_legacy",
                "h_pre",
                "scada_set_setpoint",
                "write_external",
                "approve",
                "cli:--yes",
                "v3.11.0-era row",
                "2026-07-26 12:00:00",
            ),
        )
        await db.commit()

    # Migration should report it ran.
    migrated = await migrate_decision_await_human(str(db_path))
    assert migrated is True

    # Second call should be a NO-OP.
    migrated_again = await migrate_decision_await_human(str(db_path))
    assert migrated_again is False

    # Schema now carries the widened allowlist.
    db = await connect(str(db_path))
    try:
        cur = await db.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='governance_decisions'"
        )
        row = await cur.fetchone()
        assert "await_human" in (row["sql"] or "")

        # Legacy row preserved.
        cur = await db.execute(
            "SELECT decision, approver FROM governance_decisions "
            "WHERE decision_id = ?",
            ("gd_legacy_1",),
        )
        legacy = await cur.fetchone()
        assert legacy is not None
        assert legacy["decision"] == "approve"
        assert legacy["approver"] == "cli:--yes"
    finally:
        await db.close()

    # Fresh row with ``await_human`` now succeeds via the AuditStore.
    audit_store = AuditStore(str(db_path))
    # init_db() should be a NO-OP on a migrated DB (it re-applies
    # the migration idempotently and finds the CHECK already widened).
    await init_db(str(db_path))
    out = await audit_store.record_governance_decision(
        decision_id="gd_await_post_migrate",
        session_id="sess_post",
        hook_id="h_pre",
        tool_name="t",
        risk_level="write_external",
        decision=DECISION_AWAIT_HUMAN,
        approver="caller",
        rationale="post-migration await_human",
    )
    assert out.decision == "await_human"


# ─── 5-stage state machine: paused Approve stage writes await_human ──────────


async def test_5stage_approve_pause_writes_await_human_audit_row(
    db_path: str,
) -> None:
    """AWAIT-HUMAN-02: the paused Approve stage writes a
    ``DECISION_AWAIT_HUMAN`` row in the ledger. Pre-v3.12.0 the row
    was silently swallowed (audit.py rejected ``await_human``).
    """
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)

    machine = ApprovalStateMachine(
        policy_input={"action": "human_review_required"},
        session_id="sess_pause_test",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )
    pause_policies = {
        APPROVAL_STAGE_PLAN: ApprovalStagePolicy(
            stage_name=APPROVAL_STAGE_PLAN, decision=DECISION_ALLOW,
            reason="plan:ok", evidence_refs=[], awaits_human=False,
        ),
        "check": ApprovalStagePolicy(
            stage_name="check", decision=DECISION_ALLOW,
            reason="check:ok", evidence_refs=[], awaits_human=False,
        ),
        "draft": ApprovalStagePolicy(
            stage_name="draft", decision=DECISION_ALLOW,
            reason="draft:ok", evidence_refs=[], awaits_human=False,
        ),
        APPROVAL_STAGE_APPROVE: ApprovalStagePolicy(
            stage_name=APPROVAL_STAGE_APPROVE,
            decision=DECISION_AWAIT_HUMAN,
            reason="approve:OPA decision=approval ⇒ human-in-the-loop",
            evidence_refs=["ticket-pending"],
            awaits_human=True,
        ),
        "execute": ApprovalStagePolicy(
            stage_name="execute", decision=DECISION_ALLOW,
            reason="execute:ok", evidence_refs=[], awaits_human=False,
        ),
    }
    result = await machine.run(_evaluator_for(pause_policies))

    assert result.final_decision == DECISION_AWAIT_HUMAN
    assert result.paused_at_stage == "approve"

    # The pause row carries DECISION_AWAIT_HUMAN (not silently
    # swallowed). This is the assertion the v3.11.3 walkthrough
    # §7 finding was after — ``await_human`` MUST reach the ledger.
    pause_records = [
        r for r in result.records
        if r.stage == "approve_pause" and r.decision == "await_human"
    ]
    assert len(pause_records) == 1, (
        "AWAIT-HUMAN-02: the paused Approve stage must write a row "
        "with stage='approve_pause' and decision='await_human'."
    )
    assert pause_records[0].reason == (
        "approve:OPA decision=approval ⇒ human-in-the-loop"
    )


async def test_5stage_pause_then_human_allow_writes_resume_rows(
    db_path: str,
) -> None:
    """AWAIT-HUMAN-02: after the human signs off with allow, the
    state machine writes the human verdict as a follow-on row AND
    the execute-stage row.
    """
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)

    machine = ApprovalStateMachine(
        policy_input={"action": "human_review_required"},
        session_id="sess_resume_test",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )
    pause_policies = {
        APPROVAL_STAGE_PLAN: ApprovalStagePolicy(
            stage_name=APPROVAL_STAGE_PLAN, decision=DECISION_ALLOW,
            reason="plan:ok", evidence_refs=[], awaits_human=False,
        ),
        "check": ApprovalStagePolicy(
            stage_name="check", decision=DECISION_ALLOW,
            reason="check:ok", evidence_refs=[], awaits_human=False,
        ),
        "draft": ApprovalStagePolicy(
            stage_name="draft", decision=DECISION_ALLOW,
            reason="draft:ok", evidence_refs=[], awaits_human=False,
        ),
        APPROVAL_STAGE_APPROVE: ApprovalStagePolicy(
            stage_name=APPROVAL_STAGE_APPROVE,
            decision=DECISION_AWAIT_HUMAN,
            reason="approve:await human",
            evidence_refs=["ticket-123"],
            awaits_human=True,
        ),
        "execute": ApprovalStagePolicy(
            stage_name="execute", decision=DECISION_ALLOW,
            reason="execute:ok", evidence_refs=[], awaits_human=False,
        ),
    }
    result = await machine.run(_evaluator_for(pause_policies))
    assert result.final_decision == DECISION_AWAIT_HUMAN

    final = await machine.resume_with_human_decision(
        human_decision=DECISION_ALLOW,
        human_reason="human: cli --yes",
        evidence_refs=["ticket-123"],
    )
    assert final.final_decision == "approve"

    # The ledger now carries: 4 stages + approve_pause + execute +
    # human verdict (await_human resume row). 7 rows total.
    rows = await _all_records_for(audit_store, machine.request_id)
    assert len(rows) == 7

    stage_decisions = [(r["stage"], r["decision"]) for r in rows]
    assert stage_decisions == [
        ("plan", "allow"),
        ("check", "allow"),
        ("draft", "allow"),
        ("approve", DECISION_AWAIT_HUMAN),  # upstream policy verdict
        ("approve_pause", DECISION_AWAIT_HUMAN),  # paused-state row
        ("execute", "approve"),
        ("await_human", "allow"),  # human verdict (resume-time row)
    ]


async def test_5stage_pause_then_human_deny_writes_deny_row(
    db_path: str,
) -> None:
    """AWAIT-HUMAN-02: human deny writes a deny row after the
    approve_pause row and skips the execute stage.
    """
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)

    machine = ApprovalStateMachine(
        policy_input={"action": "human_review_required"},
        session_id="sess_deny_test",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )
    pause_policies = {
        APPROVAL_STAGE_PLAN: ApprovalStagePolicy(
            stage_name=APPROVAL_STAGE_PLAN, decision=DECISION_ALLOW,
            reason="plan:ok", evidence_refs=[], awaits_human=False,
        ),
        "check": ApprovalStagePolicy(
            stage_name="check", decision=DECISION_ALLOW,
            reason="check:ok", evidence_refs=[], awaits_human=False,
        ),
        "draft": ApprovalStagePolicy(
            stage_name="draft", decision=DECISION_ALLOW,
            reason="draft:ok", evidence_refs=[], awaits_human=False,
        ),
        APPROVAL_STAGE_APPROVE: ApprovalStagePolicy(
            stage_name=APPROVAL_STAGE_APPROVE,
            decision=DECISION_AWAIT_HUMAN,
            reason="approve:await human",
            evidence_refs=[],
            awaits_human=True,
        ),
        "execute": ApprovalStagePolicy(
            stage_name="execute", decision=DECISION_ALLOW,
            reason="execute:ok", evidence_refs=[], awaits_human=False,
        ),
    }
    result = await machine.run(_evaluator_for(pause_policies))
    assert result.final_decision == DECISION_AWAIT_HUMAN

    final = await machine.resume_with_human_decision(
        human_decision=DECISION_DENY,
        human_reason="human: cli --no",
    )
    assert final.final_decision == DECISION_DENY

    # 4 stages + approve_pause + human verdict (deny). No execute row.
    rows = await _all_records_for(audit_store, machine.request_id)
    assert len(rows) == 6
    stage_decisions = [(r["stage"], r["decision"]) for r in rows]
    assert stage_decisions == [
        ("plan", "allow"),
        ("check", "allow"),
        ("draft", "allow"),
        ("approve", DECISION_AWAIT_HUMAN),
        ("approve_pause", DECISION_AWAIT_HUMAN),
        ("await_human", DECISION_DENY),
    ]


# ─── Helpers ─────────────────────────────────────────────────────────────────


class _RecordingSink:
    """In-process sink that records every emitted event for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(
        self, session_id: str, event_type: str, payload: dict,
    ) -> int:
        self.events.append((event_type, dict(payload)))
        return len(self.events)


def _evaluator_for(policies: dict[str, ApprovalStagePolicy]):
    """Build a stage evaluator that dispatches from a per-stage policy dict."""
    def _eval(stage: str, policy_input, **kwargs) -> ApprovalStagePolicy:
        if stage not in policies:
            pytest.fail(f"unexpected stage call: {stage}")
        return policies[stage]
    return _eval


async def _all_records_for(
    audit_store: AuditStore, request_id: str,
) -> list[dict]:
    """Return all ledger rows for ``request_id`` ordered by canonical
    stage sequence (plan → check → draft → approve → approve_pause
    → execute → await_human) so the assertion list is stable across
    rows that share the same ``datetime('now')`` timestamp.

    v3.12.0: ``approve_pause`` sits between the upstream ``approve``
    row and the resume-time ``execute`` / ``await_human`` rows so
    the audit timeline is linear.
    """
    db = await connect(audit_store.db_path)
    try:
        cur = await db.execute(
            """
            SELECT decision_id, stage, decision, rationale, ts
            FROM governance_decisions
            WHERE decision_id LIKE ?
            """,
            (f"{request_id}_%",),
        )
        rows = [dict(r) async for r in cur]
    finally:
        await db.close()

    # Canonical stage order (same convention as
    # ``test_approval_state_machine._stage_records_for``).
    order = {
        "plan": 0,
        "check": 1,
        "draft": 2,
        "approve": 3,
        "approve_pause": 4,
        "execute": 5,
        "await_human": 6,
    }
    rows.sort(key=lambda r: (order.get(r["stage"], 999), r["decision_id"]))
    return rows