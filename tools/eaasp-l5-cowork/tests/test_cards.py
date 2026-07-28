"""v3.13.0 — Four-card data model tests.

REQ-IDs: CARD-EVENT-01..03 / CARD-EVIDENCE-01..03 /
CARD-ACTION-01..03 / CARD-APPROVAL-01..03.

Covers the dataclass shape, deterministic summary, and keying
rules — the projection-level tests live in test_projection.py.
"""

from __future__ import annotations

from eaasp_l5_cowork.cards import (
    ActionCard,
    ApprovalCard,
    EvidenceCard,
    EventCard,
    SUMMARY_MAX_LEN,
    _make_card_id,
    _truncate_summary,
    make_payload_summary,
)


def test_make_payload_summary_empty_dict() -> None:
    """Empty dict still produces a deterministic summary (sha prefix)."""
    s = make_payload_summary({})
    assert s.startswith("<empty payload sha=")
    assert len(s) <= SUMMARY_MAX_LEN


def test_make_payload_summary_none() -> None:
    assert make_payload_summary(None) == "<empty>"


def test_make_payload_summary_string() -> None:
    assert make_payload_summary("hello world") == "hello world"


def test_make_payload_summary_producer_supplied() -> None:
    """Producer-supplied ``summary`` field wins over auto-rendering."""
    s = make_payload_summary(
        {"summary": "scada_set_setpoint mode=enforce risk=write_external"}
    )
    assert s == "scada_set_setpoint mode=enforce risk=write_external"


def test_make_payload_summary_deterministic() -> None:
    """Same payload → same summary (sorted keys)."""
    a = make_payload_summary({"b": 2, "a": 1})
    b = make_payload_summary({"a": 1, "b": 2})
    assert a == b
    assert a == "a=1 b=2"


def test_make_payload_summary_collapses_nested() -> None:
    """Nested dicts become '{Nkeys}' so the summary stays 1 line."""
    s = make_payload_summary({"payload": {"a": 1, "b": 2, "c": 3}})
    assert "payload={3keys}" in s


def test_make_payload_summary_collapses_list() -> None:
    s = make_payload_summary({"items": [1, 2, 3, 4]})
    assert "items=[4]" in s


def test_truncate_summary_short_passthrough() -> None:
    assert _truncate_summary("hi") == "hi"


def test_truncate_summary_long_truncates_with_ellipsis() -> None:
    long_text = "x" * (SUMMARY_MAX_LEN + 50)
    out = _truncate_summary(long_text)
    assert len(out) == SUMMARY_MAX_LEN
    assert out.endswith("...")


def test_make_card_id_deterministic() -> None:
    """Same key parts → same id (idempotent projection)."""
    a = _make_card_id("event", "sess_1", 7, "a2a.request.sent")
    b = _make_card_id("event", "sess_1", 7, "a2a.request.sent")
    assert a == b
    assert a.startswith("event_")


def test_make_card_id_distinguishes_card_types() -> None:
    a = _make_card_id("event", "sess_1", 7)
    b = _make_card_id("action", "sess_1", 7)
    assert a != b


def test_event_card_to_dict_shape() -> None:
    """CARD-EVENT-01 — EventCard.to_dict carries session/room/event_type."""
    card = EventCard(
        id="event_abc",
        session_id="sess_1",
        tenant_id="acme",
        created_at="2026-07-25T00:00:00Z",
        summary="a2a.request.sent",
        event_seq=10,
        room_id="er_test01",
        event_type="a2a.request.sent",
    )
    out = card.to_dict()
    assert out["card_type"] == "event"
    assert out["session_id"] == "sess_1"
    assert out["room_id"] == "er_test01"
    assert out["event_seq"] == 10
    assert out["event_type"] == "a2a.request.sent"
    assert out["tenant_id"] == "acme"


def test_evidence_card_to_dict_shape() -> None:
    """CARD-EVIDENCE-01 — EvidenceCard.to_dict carries anchor_id + confirmed."""
    card = EvidenceCard(
        id="evidence_abc",
        session_id="sess_1",
        tenant_id="acme",
        created_at="2026-07-25T00:00:00Z",
        summary="scada_reading data_ref=/scada/feeder_07",
        anchor_id="anc_1",
        evidence_type="scada_reading",
        confirmed=True,
    )
    out = card.to_dict()
    assert out["card_type"] == "evidence"
    assert out["anchor_id"] == "anc_1"
    assert out["evidence_type"] == "scada_reading"
    assert out["confirmed"] is True


def test_action_card_to_dict_shape() -> None:
    """CARD-ACTION-01..03 — ActionCard carries tool_name + risk_level."""
    card = ActionCard(
        id="action_abc",
        session_id="sess_1",
        tenant_id="acme",
        created_at="2026-07-25T00:00:00Z",
        summary="scada_set_setpoint mode=enforce",
        tool_seq=3,
        tool_name="scada_set_setpoint",
        risk_level="write_external",
    )
    out = card.to_dict()
    assert out["card_type"] == "action"
    assert out["tool_seq"] == 3
    assert out["tool_name"] == "scada_set_setpoint"
    assert out["risk_level"] == "write_external"


def test_approval_card_to_dict_shape_canonical_5_state() -> None:
    """CARD-APPROVAL-03 — ApprovalCard carries decision from extended allowlist."""
    for decision in (
        "allow",
        "approve",
        "deny",
        "gate_request",
        "await_human",
    ):
        card = ApprovalCard(
            id=f"approval_{decision}",
            session_id="sess_1",
            tenant_id="acme",
            created_at="2026-07-25T00:00:00Z",
            summary=f"decision={decision}",
            decision_id=f"gd_{decision}",
            stage="approve" if decision == "await_human" else "plan",
            decision=decision,
            approver=None,
            risk_level="write_external",
            tool_name="scada_set_setpoint",
        )
        out = card.to_dict()
        assert out["card_type"] == "approval"
        assert out["decision"] == decision
        # Stage position badge (5-stage + approve_pause + await_human).
        assert out["stage"] in {
            "plan",
            "check",
            "draft",
            "approve",
            "execute",
            "approve_pause",
            "await_human",
            None,
        }
