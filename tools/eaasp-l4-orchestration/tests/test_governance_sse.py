"""v3.11.2 — L4 governance.approval.* SSE event helpers tests.

REQ-IDs: SSE-01..05, STAGE-01..05.

Verifies:
- All 5 ``emit_governance_approval_<stage>`` helpers write the
  canonical payload shape for governance.approval.{plan,check,draft,
  approve,execute}.
- The 5 approval helpers coexist with the pre-existing
  ``governance.request`` / ``governance.decision`` event types.
- Event append is best-effort (failure swallowed, audit §7.1).
- Stage allowlist validation: unknown stage names raise ValueError
  BEFORE any DB open.
"""

from __future__ import annotations

import pytest

from eaasp_l4_orchestration.event_stream import SessionEventStream


EXPECTED_PAYLOAD_KEYS = {
    "stage",
    "decision_id",
    "request_id",
    "hook_id",
    "decision",
    "reason",
    "caller_principal",
    "evidence_refs",
    "ts",
}


async def test_emit_governance_approval_plan_writes_correct_payload(
    tmp_db_path: str, seed_session,
) -> None:
    """SSE-01: governance.approval.plan payload contract."""
    sid = await seed_session("sess_aplan")
    stream = SessionEventStream(tmp_db_path)
    seq = await stream.emit_governance_approval_plan(
        session_id=sid,
        decision_id="gd_approval_plan_x",
        request_id="gd_approval_x",
        hook_id="h_pre",
        decision="allow",
        reason="plan:policy-allow",
        caller_principal="caller@scopes",
        evidence_refs=["anchor-1"],
        ts="2026-07-27 10:00:00",
    )
    assert seq is not None

    events = await stream.list_events(sid)
    matches = [e for e in events if e["event_type"] == "governance.approval.plan"]
    assert len(matches) == 1
    payload = matches[0]["payload"]
    assert EXPECTED_PAYLOAD_KEYS.issubset(set(payload.keys()))
    assert payload["stage"] == "plan"
    assert payload["decision_id"] == "gd_approval_plan_x"
    assert payload["request_id"] == "gd_approval_x"
    assert payload["hook_id"] == "h_pre"
    assert payload["decision"] == "allow"
    assert payload["reason"] == "plan:policy-allow"
    assert payload["caller_principal"] == "caller@scopes"
    assert payload["evidence_refs"] == ["anchor-1"]
    assert payload["ts"] == "2026-07-27 10:00:00"


@pytest.mark.parametrize(
    "stage,helper",
    [
        ("plan", "emit_governance_approval_plan"),
        ("check", "emit_governance_approval_check"),
        ("draft", "emit_governance_approval_draft"),
        ("approve", "emit_governance_approval_approve"),
        ("execute", "emit_governance_approval_execute"),
    ],
)
async def test_all_five_stage_helpers_emit_canonical_event_types(
    tmp_db_path: str, seed_session, stage, helper,
) -> None:
    """SSE-01..05: every helper writes governance.approval.<stage>."""
    sid = await seed_session(f"sess_a{stage}")
    stream = SessionEventStream(tmp_db_path)
    fn = getattr(stream, helper)
    seq = await fn(
        session_id=sid,
        decision_id=f"gd_approval_{stage}",
        request_id="gd_approval_y",
        hook_id="h_pre",
        decision="allow",
        reason=f"{stage}:ok",
        caller_principal="caller@scopes",
        evidence_refs=[],
        ts="2026-07-27 10:00:01",
    )
    assert seq is not None

    events = await stream.list_events(sid)
    matches = [
        e for e in events
        if e["event_type"] == f"governance.approval.{stage}"
    ]
    assert len(matches) == 1
    payload = matches[0]["payload"]
    assert payload["stage"] == stage
    assert EXPECTED_PAYLOAD_KEYS.issubset(set(payload.keys()))


async def test_emit_governance_approval_unknown_stage_raises(
    tmp_db_path: str,
) -> None:
    """Stage allowlist: only plan/check/draft/approve/execute accepted."""
    stream = SessionEventStream(tmp_db_path)
    with pytest.raises(ValueError, match="stage must be one of"):
        await stream.emit_governance_approval(
            session_id="sess_x",
            stage="bogus",
            decision_id="d",
            request_id="r",
            hook_id="h",
            decision="allow",
            reason="r",
            caller_principal="caller",
            evidence_refs=[],
            ts="2026-07-27 10:00:02",
        )


async def test_approval_events_coexist_with_request_and_decision(
    tmp_db_path: str, seed_session,
) -> None:
    """All 3 governance event families coexist on the same session stream."""
    sid = await seed_session("sess_coexist")
    stream = SessionEventStream(tmp_db_path)

    await stream.emit_governance_request(
        session_id=sid,
        decision_id="gd_req",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="xfmr-042/temperature_limit_c=70.0",
    )
    await stream.emit_governance_approval_plan(
        session_id=sid,
        decision_id="gd_approval_plan_co",
        request_id="gd_approval_co",
        hook_id="h_pre",
        decision="allow",
        reason="plan:co",
        caller_principal="caller@scopes",
        evidence_refs=[],
        ts="2026-07-27 10:00:03",
    )
    await stream.emit_governance_approval_execute(
        session_id=sid,
        decision_id="gd_approval_execute_co",
        request_id="gd_approval_co",
        hook_id="h_pre",
        decision="approve",
        reason="execute:co",
        caller_principal="caller@scopes",
        evidence_refs=["ticket-co"],
        ts="2026-07-27 10:00:04",
    )
    await stream.emit_governance_decision(
        session_id=sid,
        decision_id="gd_dec",
        decision="approve",
        approver="cli:--yes",
    )

    events = await stream.list_events(sid)
    types_in_order = [e["event_type"] for e in events]
    assert "governance.request" in types_in_order
    assert "governance.approval.plan" in types_in_order
    assert "governance.approval.execute" in types_in_order
    assert "governance.decision" in types_in_order


async def test_emit_governance_approval_best_effort_on_append_failure(
    tmp_db_path: str, seed_session, monkeypatch,
) -> None:
    sink = SessionEventStream(tmp_db_path)

    async def boom_append(*_args, **_kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(sink, "append", boom_append)

    result = await sink.emit_governance_approval_plan(
        session_id="any",
        decision_id="d",
        request_id="r",
        hook_id="h",
        decision="allow",
        reason="r",
        caller_principal="caller",
        evidence_refs=[],
        ts="t",
    )
    # Best-effort: returns None instead of crashing.
    assert result is None


async def test_evidence_refs_normalized_to_strings(
    tmp_db_path: str, seed_session,
) -> None:
    """evidence_refs is normalized to a list of strings for downstream consumers."""
    sid = await seed_session("sess_norm")
    stream = SessionEventStream(tmp_db_path)
    await stream.emit_governance_approval_check(
        session_id=sid,
        decision_id="gd_chk_norm",
        request_id="gd_chk_norm_r",
        hook_id="h_pre",
        decision="allow",
        reason="check:norm",
        caller_principal="caller",
        evidence_refs=["a", "b"],
        ts="t",
    )

    events = await stream.list_events(sid)
    payload = next(
        e["payload"] for e in events
        if e["event_type"] == "governance.approval.check"
    )
    assert payload["evidence_refs"] == ["a", "b"]
    assert all(isinstance(r, str) for r in payload["evidence_refs"])
