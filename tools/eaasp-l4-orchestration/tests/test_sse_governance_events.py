"""REQ-EAASP-04 — L4 governance event helpers.

Verifies the contract frozen in `docs/audit/3.7.3-GAP-AUDIT.md` §7.1:
- ``SessionEventStream.emit_governance_request(session_id, decision_id,
  hook_id, tool_name, risk_level, action_preview)`` appends a
  ``governance.request`` event with exactly those payload keys.
- ``SessionEventStream.emit_governance_decision(session_id, decision_id,
  decision, approver)`` appends a ``governance.decision`` event.
- Event append is best-effort — when ``append()`` raises, the helper logs
  and returns ``None`` without inverting the gate decision.
"""

from __future__ import annotations

import pytest

from eaasp_l4_orchestration.event_stream import SessionEventStream


async def test_emit_governance_request_writes_correct_payload(
    tmp_db_path: str, seed_session,
) -> None:
    sid = await seed_session("sess_req")
    stream = SessionEventStream(tmp_db_path)

    seq = await stream.emit_governance_request(
        session_id=sid,
        decision_id="gd_abc",
        hook_id="h_pre",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        action_preview="xfmr-042/temperature_limit_c=70.0",
    )
    assert seq is not None

    events = await stream.list_events(sid)
    matches = [e for e in events if e["event_type"] == "governance.request"]
    assert len(matches) == 1
    payload = matches[0]["payload"]
    assert payload == {
        "decision_id": "gd_abc",
        "hook_id": "h_pre",
        "tool_name": "scada_set_setpoint",
        "risk_level": "write_external",
        "action_preview": "xfmr-042/temperature_limit_c=70.0",
    }


async def test_emit_governance_decision_writes_correct_payload(
    tmp_db_path: str, seed_session,
) -> None:
    sid = await seed_session("sess_dec")
    stream = SessionEventStream(tmp_db_path)

    seq = await stream.emit_governance_decision(
        session_id=sid,
        decision_id="gd_abc_final",
        decision="approve",
        approver="cli:--yes",
    )
    assert seq is not None

    events = await stream.list_events(sid)
    matches = [e for e in events if e["event_type"] == "governance.decision"]
    assert len(matches) == 1
    payload = matches[0]["payload"]
    assert payload == {
        "decision_id": "gd_abc_final",
        "decision": "approve",
        "approver": "cli:--yes",
    }


async def test_emit_governance_request_validates_inputs(
    tmp_db_path: str, seed_session,
) -> None:
    sid = await seed_session("sess_val")
    stream = SessionEventStream(tmp_db_path)

    # Empty session_id → ValueError (preserves existing append() contract).
    with pytest.raises(ValueError):
        await stream.emit_governance_request(
            session_id="",
            decision_id="gd_x",
            hook_id="h",
            tool_name="t",
            risk_level="read",
            action_preview="a",
        )


async def test_emit_governance_decision_validates_decision(
    tmp_db_path: str, seed_session,
) -> None:
    sid = await seed_session("sess_vdec")
    stream = SessionEventStream(tmp_db_path)

    with pytest.raises(ValueError):
        await stream.emit_governance_decision(
            session_id=sid,
            decision_id="gd_x",
            decision="totally_invented",
            approver="cli:--yes",
        )


async def test_emit_governance_request_best_effort_on_append_failure(
    tmp_db_path: str, seed_session, monkeypatch,
) -> None:
    """When ``append()`` raises, helper logs and returns ``None`` instead of bubbling."""
    sid = await seed_session("sess_boom")
    stream = SessionEventStream(tmp_db_path)

    async def boom_append(*_args, **_kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(stream, "append", boom_append)

    # Should NOT raise — event append is best-effort by audit §7.1.
    result = await stream.emit_governance_request(
        session_id=sid,
        decision_id="gd_x",
        hook_id="h",
        tool_name="t",
        risk_level="read",
        action_preview="a",
    )
    assert result is None


async def test_emit_governance_decision_best_effort_on_append_failure(
    tmp_db_path: str, seed_session, monkeypatch,
) -> None:
    sid = await seed_session("sess_boom_dec")
    stream = SessionEventStream(tmp_db_path)

    async def boom_append(*_args, **_kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(stream, "append", boom_append)
    result = await stream.emit_governance_decision(
        session_id=sid,
        decision_id="gd_x_final",
        decision="approve",
        approver="cli:--yes",
    )
    assert result is None
