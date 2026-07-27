"""v3.11.2 — 5-stage approval state machine tests.

REQ-IDs: STAGE-01..05, SSE-01..05, AUDIT-01..02, DENY-01..02.

Covers:
- Happy path: 5 audit rows (plan/check/draft/approve/execute) for a
  successful chain; each stage emits one governance.approval.<stage>
  event through the L4 SSE sink.
- Deny-always-wins: a deny in any one of the first 3 stages
  short-circuits the remaining stages (no further audit rows, no
  further SSE events).
- Approve-stage pause: awaits_human flag pauses at approve; calling
  resume_with_human_decision(allow) runs the execute stage; calling
  resume_with_human_decision(deny) terminates with deny.
- Input validation: empty caller_principal / missing evidence_refs /
  wrong-stage policy / unsupported stage decision surface as ValueError
  BEFORE any DB open.
- Stage column persistence: the new ``stage`` column on
  governance_decisions carries the per-stage name; defaults to NULL
  for backwards compat rows.
"""

from __future__ import annotations

import pytest

from eaasp_l3_governance.approval_state_machine import (
    APPROVAL_STAGE_APPROVE,
    APPROVAL_STAGE_EXECUTE,
    APPROVAL_STAGE_PLAN,
    DECISION_ALLOW,
    DECISION_APPROVE,
    DECISION_AWAIT_HUMAN,
    DECISION_DENY,
    STAGE_ORDER,
    ApprovalEventSink,
    ApprovalStagePolicy,
    ApprovalStateMachine,
)
from eaasp_l3_governance.audit import AuditStore, GovernanceDecisionOut
from eaasp_l3_governance.db import connect, init_db


pytestmark = pytest.mark.asyncio


# ─── Test fixtures ───────────────────────────────────────────────────────────


class _RecordingSink:
    """In-process sink that records every emitted event for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(
        self, session_id: str, event_type: str, payload: dict,
    ) -> int:
        self.events.append((event_type, dict(payload)))
        return len(self.events)


def _allow_policy(stage: str, *, evidence: list[str] | None = None) -> ApprovalStagePolicy:
    return ApprovalStagePolicy(
        stage_name=stage,
        decision=DECISION_ALLOW,
        reason=f"{stage}:policy-allow",
        evidence_refs=list(evidence or []),
        awaits_human=False,
    )


def _deny_policy(stage: str, *, reason: str = "policy-deny") -> ApprovalStagePolicy:
    return ApprovalStagePolicy(
        stage_name=stage,
        decision=DECISION_DENY,
        reason=reason,
        evidence_refs=[],
        awaits_human=False,
    )


def _evaluator_for(policies: dict[str, ApprovalStagePolicy]):
    """Build a stage evaluator that dispatches from a per-stage policy dict."""
    def _eval(stage: str, policy_input, **kwargs) -> ApprovalStagePolicy:
        if stage not in policies:
            pytest.fail(f"unexpected stage call: {stage}")
        return policies[stage]
    return _eval


async def _stage_records_for(
    audit_store: AuditStore, decision_id: str,
) -> list[GovernanceDecisionOut]:
    """Return all rows for a single approval chain (decision_id prefix).

    Sort by canonical STAGE_ORDER so ordering is deterministic across
    rows that share the same ``datetime('now')`` timestamp.
    """
    db = await connect(audit_store.db_path)
    try:
        cur = await db.execute(
            """
            SELECT decision_id, session_id, hook_id, tool_name,
                   risk_level, decision, approver, rationale, stage, ts
            FROM governance_decisions
            WHERE decision_id LIKE ?
            """,
            (f"{decision_id}_%",),
        )
        rows = [dict(r) async for r in cur]
    finally:
        await db.close()

    out = [
        GovernanceDecisionOut(
            decision_id=r["decision_id"],
            session_id=r["session_id"],
            hook_id=r["hook_id"],
            tool_name=r["tool_name"],
            risk_level=r["risk_level"],
            decision=r["decision"],
            approver=r["approver"],
            rationale=r["rationale"],
            stage=r["stage"],
            ts=r["ts"],
        )
        for r in rows
    ]

    order = {stage: i for i, stage in enumerate(STAGE_ORDER)}
    # Place rows with stage=None at the end (backwards-compat / migration).
    out.sort(key=lambda r: (order.get(r.stage, 999), r.decision_id))
    return out


async def test_stage_order_is_canonical_five_stages() -> None:
    """The state-machine stage order is frozen (audit §6.4)."""
    assert STAGE_ORDER == ("plan", "check", "draft", "approve", "execute")


async def test_happy_path_persists_five_audit_rows_and_emits_five_events(
    db_path: str,
) -> None:
    """STAGE-01..05 happy path: all 5 stages run; 5 audit rows; 5 SSE events."""
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)

    machine = ApprovalStateMachine(
        policy_input={"action": "set_setpoint", "value": 70.0},
        session_id="sess_happy",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )
    result = await machine.run(
        _evaluator_for({
            APPROVAL_STAGE_PLAN: ApprovalStagePolicy(
                stage_name=APPROVAL_STAGE_PLAN, decision=DECISION_ALLOW,
                reason="plan:ok", evidence_refs=["anchor-plan-1"], awaits_human=False,
            ),
            "check": ApprovalStagePolicy(
                stage_name="check", decision=DECISION_ALLOW,
                reason="check:ok", evidence_refs=[], awaits_human=False,
            ),
            "draft": ApprovalStagePolicy(
                stage_name="draft", decision=DECISION_ALLOW,
                reason="draft:ok", evidence_refs=["doc-draft-42"], awaits_human=False,
            ),
            "approve": ApprovalStagePolicy(
                stage_name="approve", decision=DECISION_APPROVE,
                reason="approve:ok", evidence_refs=[], awaits_human=False,
            ),
            "execute": ApprovalStagePolicy(
                stage_name="execute", decision=DECISION_APPROVE,
                reason="execute:ok", evidence_refs=[], awaits_human=False,
            ),
        })
    )

    # 1. Final aggregate is approve (5 stages completed).
    assert result.final_decision == "approve"
    assert result.stages_completed == 5
    assert result.paused_at_stage is None
    assert len(result.records) == 5

    # 2. Append-only ledger carries exactly 5 rows for this request.
    rows = await _stage_records_for(audit_store, result.decision_id)
    assert len(rows) == 5
    stage_seq = [r.stage for r in rows]
    assert stage_seq == ["plan", "check", "draft", "approve", "execute"]

    # 3. The new ``stage`` column on each row matches the per-stage name.
    assert all(r.stage == s for r, s in zip(rows, stage_seq))

    # 4. Evidence refs round-trip from policy → ledger row.
    plan_row = next(r for r in rows if r.stage == "plan")
    assert "anchor-plan-1" in plan_row.rationale or "plan:ok" in plan_row.rationale

    # 5. SSE sink received exactly 5 events, one per stage.
    assert len(sink.events) == 5
    suffix_seq = [evt[0].rsplit(".", 1)[-1] for evt in sink.events]
    assert suffix_seq == ["plan", "check", "draft", "approve", "execute"]

    # 6. Each SSE event carries the canonical 8-field payload.
    expected_keys = {
        "stage", "decision_id", "request_id", "session_id", "hook_id",
        "decision", "reason", "caller_principal", "evidence_refs", "ts",
    }
    for _evt_type, payload in sink.events:
        assert expected_keys.issubset(set(payload.keys()))


async def test_deny_in_first_stage_short_circuits_remaining_stages(
    db_path: str,
) -> None:
    """DENY-01: deny in plan → only 1 audit row, 1 event, final=deny."""
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)

    machine = ApprovalStateMachine(
        policy_input={"action": "dangerous_write"},
        session_id="sess_deny1",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )
    result = await machine.run(
        _evaluator_for({APPROVAL_STAGE_PLAN: _deny_policy(APPROVAL_STAGE_PLAN, reason="plan:policy denied")})
    )

    assert result.final_decision == "deny"
    assert result.final_reason == "plan:policy denied"
    assert result.stages_completed == 1
    assert len(result.records) == 1
    assert result.records[0].stage == "plan"

    rows = await _stage_records_for(audit_store, result.decision_id)
    assert len(rows) == 1
    assert rows[0].decision == "deny"
    assert rows[0].stage == "plan"

    assert len(sink.events) == 1
    assert sink.events[0][0] == "governance.approval.plan"


async def test_deny_in_middle_stage_short_circuits_remaining_stages(
    db_path: str,
) -> None:
    """DENY-02: deny in draft → only 3 audit rows, 3 events, final=deny."""
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)

    machine = ApprovalStateMachine(
        policy_input={},
        session_id="sess_deny2",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )
    result = await machine.run(
        _evaluator_for({
            APPROVAL_STAGE_PLAN: _allow_policy(APPROVAL_STAGE_PLAN, evidence=["p"]),
            "check": _allow_policy("check"),
            "draft": _deny_policy("draft", reason="draft:rejected by policy"),
            "approve": _allow_policy("approve"),
            "execute": _allow_policy("execute"),
        })
    )

    assert result.final_decision == "deny"
    assert result.stages_completed == 3
    assert result.final_reason == "draft:rejected by policy"

    rows = await _stage_records_for(audit_store, result.decision_id)
    assert [r.stage for r in rows] == ["plan", "check", "draft"]
    assert rows[2].decision == "deny"

    assert len(sink.events) == 3
    assert [evt[0] for evt in sink.events] == [
        "governance.approval.plan",
        "governance.approval.check",
        "governance.approval.draft",
    ]


async def test_approve_stage_can_pause_then_resume_with_human_allow(
    db_path: str,
) -> None:
    """Approve stage with awaits_human=True pauses; resume(allow) runs execute."""
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)

    machine = ApprovalStateMachine(
        policy_input={"action": "human_review_required"},
        session_id="sess_pause",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )
    pause_policies = {
        APPROVAL_STAGE_PLAN: _allow_policy(APPROVAL_STAGE_PLAN),
        "check": _allow_policy("check"),
        "draft": _allow_policy("draft"),
        "approve": ApprovalStagePolicy(
            stage_name="approve",
            decision="approve",
            reason="approve:await human",
            evidence_refs=["approval-pending"],
            awaits_human=True,
        ),
        "execute": _allow_policy("execute"),
    }
    result = await machine.run(_evaluator_for(pause_policies))

    assert machine.paused is True
    assert result.paused_at_stage == "approve"
    assert result.final_decision == "await_human"
    assert result.stages_completed == 4
    assert len(sink.events) == 4

    # Human signs off → resume runs the execute stage and emits the
    # 5th event.
    final = await machine.resume_with_human_decision(
        human_decision="allow",
        human_reason="human: cli --yes",
        evidence_refs=["ticket-123"],
    )
    assert final.final_decision == "approve"
    # 4 stages + await_human row + execute row = 6 ledger entries.
    assert final.stages_completed == 6
    assert len(sink.events) == 5
    assert sink.events[-1][0] == "governance.approval.execute"

    rows = await _stage_records_for(audit_store, result.decision_id)
    # Rows share the same datetime('now') timestamp; sorted by canonical
    # stage order. The two resume-time rows are ``await_human`` (human
    # verdict record) and ``execute`` (final step).
    assert [r.stage for r in rows] == [
        "plan", "check", "draft", "approve", "execute", "await_human",
    ]


async def test_approve_pause_then_human_deny_terminates(
    db_path: str,
) -> None:
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)

    machine = ApprovalStateMachine(
        policy_input={},
        session_id="sess_deny_h",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )
    result = await machine.run(_evaluator_for({
        APPROVAL_STAGE_PLAN: _allow_policy(APPROVAL_STAGE_PLAN),
        "check": _allow_policy("check"),
        "draft": _allow_policy("draft"),
        "approve": ApprovalStagePolicy(
            stage_name="approve", decision="approve",
            reason="pause", evidence_refs=[], awaits_human=True,
        ),
        "execute": _allow_policy("execute"),
    }))
    assert result.final_decision == "await_human"

    final = await machine.resume_with_human_decision(
        human_decision="deny",
        human_reason="human: cli --no",
    )
    assert final.final_decision == "deny"
    assert final.stages_completed == 5  # 4 stages + await_human row
    assert len(sink.events) == 4  # no execute event after human deny

    rows = await _stage_records_for(
        audit_store, machine.request_id
    )
    assert [r.stage for r in rows] == [
        "plan", "check", "draft", "approve", "await_human",
    ]
    assert rows[-1].decision == "deny"


async def test_empty_caller_principal_raises_before_db_open(
    db_path: str,
) -> None:
    audit_store = AuditStore(db_path)
    with pytest.raises(ValueError, match="caller_principal"):
        ApprovalStateMachine(
            policy_input={},
            session_id="s1",
            hook_id="h",
            caller_principal="",
            audit_store=audit_store,
        )


async def test_missing_session_id_raises() -> None:
    audit_store = AuditStore("placeholder.db")
    with pytest.raises(ValueError, match="session_id"):
        ApprovalStateMachine(
            policy_input={},
            session_id="",
            hook_id="h",
            caller_principal="caller",
            audit_store=audit_store,
        )


async def test_missing_hook_id_raises() -> None:
    audit_store = AuditStore("placeholder.db")
    with pytest.raises(ValueError, match="hook_id"):
        ApprovalStateMachine(
            policy_input={},
            session_id="s1",
            hook_id="",
            caller_principal="caller",
            audit_store=audit_store,
        )


async def test_policy_with_wrong_stage_name_raises(db_path: str) -> None:
    """Stage mismatch: evaluator returns a policy for a different stage."""
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)
    machine = ApprovalStateMachine(
        policy_input={},
        session_id="s1",
        hook_id="h",
        caller_principal="caller",
        audit_store=audit_store,
        event_sink=sink,
    )

    def _bad_eval(stage, _input, **_kwargs):
        # Always claim to be plan regardless of the requested stage.
        return ApprovalStagePolicy(
            stage_name=APPROVAL_STAGE_PLAN,
            decision=DECISION_ALLOW,
            reason="wrong",
            evidence_refs=[],
        )

    with pytest.raises(ValueError, match="stage mismatch"):
        await machine.run(_bad_eval)


async def test_awaits_human_outside_approve_stage_raises(db_path: str) -> None:
    """Only the approve stage is allowed to set awaits_human."""
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)
    machine = ApprovalStateMachine(
        policy_input={},
        session_id="s1",
        hook_id="h",
        caller_principal="caller",
        audit_store=audit_store,
        event_sink=sink,
    )

    def _bad_eval(stage, _input, **_kwargs):
        return ApprovalStagePolicy(
            stage_name=stage,
            decision=DECISION_ALLOW,
            reason="pause",
            evidence_refs=[],
            awaits_human=True,  # only valid on the approve stage
        )

    with pytest.raises(ValueError, match="only the 'approve' stage can pause"):
        await machine.run(_bad_eval)


async def test_unsupported_stage_decision_raises(db_path: str) -> None:
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)
    machine = ApprovalStateMachine(
        policy_input={},
        session_id="s1",
        hook_id="h",
        caller_principal="caller",
        audit_store=audit_store,
        event_sink=sink,
    )

    def _bad_eval(stage, _input, **_kwargs):
        return ApprovalStagePolicy(
            stage_name=stage,
            decision="bogus_decision",
            reason="r",
            evidence_refs=[],
        )

    with pytest.raises(ValueError, match="unsupported stage decision"):
        await machine.run(_bad_eval)


async def test_resume_without_pause_raises(db_path: str) -> None:
    audit_store = AuditStore(db_path)
    machine = ApprovalStateMachine(
        policy_input={},
        session_id="s1",
        hook_id="h",
        caller_principal="caller",
        audit_store=audit_store,
    )
    with pytest.raises(RuntimeError, match="not paused"):
        await machine.resume_with_human_decision(
            human_decision="allow", human_reason="r"
        )


async def test_resume_with_invalid_human_decision_raises(db_path: str) -> None:
    audit_store = AuditStore(db_path)
    machine = ApprovalStateMachine(
        policy_input={},
        session_id="s1",
        hook_id="h",
        caller_principal="caller",
        audit_store=audit_store,
    )
    # Force paused state without running the chain.
    machine.paused = True
    machine.paused_at_stage = "approve"
    with pytest.raises(ValueError, match="human_decision"):
        await machine.resume_with_human_decision(
            human_decision="bogus", human_reason="r"
        )


async def test_run_after_pause_raises(db_path: str) -> None:
    """A paused machine cannot be re-run; must resume instead."""
    audit_store = AuditStore(db_path)
    machine = ApprovalStateMachine(
        policy_input={},
        session_id="s1",
        hook_id="h",
        caller_principal="caller",
        audit_store=audit_store,
    )
    machine.paused = True
    with pytest.raises(RuntimeError, match="already paused"):
        await machine.run(lambda *a, **kw: _allow_policy(a[0]))


async def test_evidence_refs_round_trip_through_ledger(db_path: str) -> None:
    """AUDIT-01: evidence_refs in the policy reach the ledger row's rationale
    and the SSE event payload."""
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)
    machine = ApprovalStateMachine(
        policy_input={},
        session_id="sess_evref",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )

    await machine.run(_evaluator_for({
        APPROVAL_STAGE_PLAN: ApprovalStagePolicy(
            stage_name=APPROVAL_STAGE_PLAN, decision=DECISION_ALLOW,
            reason="plan-with-evidence",
            evidence_refs=["anchor:a", "anchor:b"],
            awaits_human=False,
        ),
        "check": _allow_policy("check"),
        "draft": _allow_policy("draft"),
        "approve": _allow_policy("approve"),
        "execute": _allow_policy("execute"),
    }))

    rows = await _stage_records_for(audit_store, machine.request_id)
    plan_row = next(r for r in rows if r.stage == "plan")
    assert "plan-with-evidence" in plan_row.rationale

    plan_event_payload = next(
        p for evt, p in sink.events if evt == "governance.approval.plan"
    )
    assert plan_event_payload["evidence_refs"] == ["anchor:a", "anchor:b"]


async def test_deny_reason_propagates_to_ledger_rationale(db_path: str) -> None:
    sink = _RecordingSink()
    audit_store = AuditStore(db_path)
    machine = ApprovalStateMachine(
        policy_input={},
        session_id="sess_reason",
        hook_id="h_pre",
        caller_principal="caller@scopes",
        audit_store=audit_store,
        event_sink=sink,
    )
    await machine.run(_evaluator_for({
        APPROVAL_STAGE_PLAN: _allow_policy(APPROVAL_STAGE_PLAN),
        "check": _deny_policy("check", reason="check:too-late-write-window"),
    }))

    rows = await _stage_records_for(audit_store, machine.request_id)
    assert len(rows) == 2
    assert "check:too-late-write-window" in rows[1].rationale
    assert rows[1].decision == "deny"
