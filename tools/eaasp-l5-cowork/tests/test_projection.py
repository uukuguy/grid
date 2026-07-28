"""v3.13.0 — Cowork projection tests.

REQ-IDs: CARD-EVENT-01..03 / CARD-EVIDENCE-01..03 /
CARD-ACTION-01..03 / CARD-APPROVAL-01..03 + D-32 (read-only)
+ D-33 (tenant-bound).

Every test populates the per-test tempdir SQLite stores via the
seed_* helpers in conftest.py, then exercises the projection
layer end-to-end. The projection must NEVER mutate the
underlying stores (D-31 / D-32).
"""

from __future__ import annotations

from conftest import (
    seed_event_room,
    seed_l2_anchor,
    seed_l3_decision,
    seed_l4_telemetry,
    seed_room_event,
)

from eaasp_l5_cowork.cards import (
    ActionCard,
    ApprovalCard,
    EvidenceCard,
    EventCard,
)
from eaasp_l5_cowork.projection import CoworkProjection


# ─── EventCard (CARD-EVENT-01..03) ──────────────────────────────────────


async def test_event_card_from_event_room_events(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-EVENT-01 — EventCard projection from event_room_events."""
    await seed_event_room(
        init_l4,
        room_id="er_evt01",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_room_event(
        init_l4,
        room_id="er_evt01",
        session_id="sess_a",
        event_type="governance.approval.plan",
        payload={"stage": "plan", "decision": "allow"},
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_event_cards(
        "sess_a", tenant_id="acme"
    )
    assert len(cards) == 1
    card = cards[0]
    # CARD-EVENT-01 — EventCard has event_seq/room_id/event_type fields.
    assert isinstance(card, EventCard) or hasattr(card, "event_seq")
    assert card.session_id == "sess_a"
    assert card.room_id == "er_evt01"
    assert card.event_type == "governance.approval.plan"
    assert card.tenant_id == "acme"
    assert "decision=allow" in card.summary
    assert "stage=plan" in card.summary


async def test_event_card_keyed_by_seq(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-EVENT-02 — EventCard keyed by (session_id, event_seq)."""
    await seed_event_room(
        init_l4,
        room_id="er_evt02",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_room_event(
        init_l4,
        room_id="er_evt02",
        session_id="sess_a",
        event_type="a2a.request.sent",
        payload={"k": "v"},
    )
    await seed_room_event(
        init_l4,
        room_id="er_evt02",
        session_id="sess_a",
        event_type="a2a.review.submitted",
        payload={"decision": "allow"},
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_event_cards("sess_a", tenant_id="acme")
    assert len(cards) == 2
    # Ordered by seq ASC.
    assert cards[0].event_seq < cards[1].event_seq
    # Each card carries a unique deterministic id.
    assert cards[0].id != cards[1].id


async def test_event_card_by_room(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-EVENT-02 — list_event_cards_by_room returns every event in room."""
    await seed_event_room(
        init_l4,
        room_id="er_evt03",
        tenant_id="acme",
        session_ids=["sess_a", "sess_b"],
    )
    await seed_room_event(
        init_l4,
        room_id="er_evt03",
        session_id="sess_a",
        event_type="a2a.request.sent",
        payload={},
    )
    await seed_room_event(
        init_l4,
        room_id="er_evt03",
        session_id="sess_b",
        event_type="a2a.review.submitted",
        payload={"decision": "needs_revision"},
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_event_cards_by_room(
        "er_evt03", tenant_id="acme"
    )
    assert len(cards) == 2
    sessions = {c.session_id for c in cards}
    assert sessions == {"sess_a", "sess_b"}


async def test_event_card_payload_summary_deterministic(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-EVENT-03 — payload_summary is deterministic 1-line."""
    await seed_event_room(
        init_l4,
        room_id="er_evt04",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_room_event(
        init_l4,
        room_id="er_evt04",
        session_id="sess_a",
        event_type="scada.set_setpoint",
        payload={
            "mode": "enforce",
            "risk": "write_external",
            "room": "r-7",
        },
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_event_cards("sess_a", tenant_id="acme")
    assert len(cards) == 1
    s = cards[0].summary
    # 1-line (no newlines).
    assert "\n" not in s
    # Deterministic sort: a=... m=... r=...
    assert s == "mode=enforce risk=write_external room=r-7"


# ─── EvidenceCard (CARD-EVIDENCE-01..03) ────────────────────────────────


async def test_evidence_card_from_l2_anchor(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-EVIDENCE-01 — EvidenceCard projection from L2 anchors."""
    await seed_event_room(
        init_l4,
        room_id="er_ev01",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_l2_anchor(
        init_l2,
        anchor_id="anc_1",
        event_id="evt_1",
        session_id="sess_a",
        type_="scada_setpoint_history",
        data_ref="/scada/feeder_07/2026-07-15..2026-07-25",
        source_system="scada",
        tool_version="1.0.0",
        metadata={"window": "10d"},
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_evidence_cards("sess_a", tenant_id="acme")
    assert len(cards) == 1
    card = cards[0]
    assert card.anchor_id == "anc_1"
    assert card.evidence_type == "scada_setpoint_history"
    assert card.confirmed is True  # snapshot_hash + tool_version set
    assert "scada" in card.summary.lower()


async def test_evidence_card_unconfirmed_when_missing_snapshot(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-EVIDENCE-01 — anchor without snapshot_hash → confirmed=False."""
    await seed_event_room(
        init_l4,
        room_id="er_ev02",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_l2_anchor(
        init_l2,
        anchor_id="anc_2",
        event_id="evt_2",
        session_id="sess_a",
        type_="tentative",
        snapshot_hash=None,
        tool_version=None,
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_evidence_cards("sess_a", tenant_id="acme")
    assert len(cards) == 1
    assert cards[0].confirmed is False


# ─── ActionCard (CARD-ACTION-01..03) ────────────────────────────────────


async def test_action_card_from_l4_telemetry(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-ACTION-01 — ActionCard projection from L4 telemetry_events."""
    await seed_event_room(
        init_l4,
        room_id="er_act01",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_l4_telemetry(
        init_l4,
        event_id="tev_1",
        session_id="sess_a",
        hook_id="PreToolUse",
        payload={"tool_name": "scada_set_setpoint"},
        tiebreaker=1,
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_action_cards("sess_a", tenant_id="acme")
    assert len(cards) == 1
    card = cards[0]
    assert card.tool_seq == 1
    assert card.tool_name == "scada_set_setpoint"
    # No L3 row joined → risk defaults to "read".
    assert card.risk_level == "read"


async def test_action_card_joins_risk_level_from_l3(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-ACTION-03 — risk_level joins from L3 governance_decisions."""
    await seed_event_room(
        init_l4,
        room_id="er_act02",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_l4_telemetry(
        init_l4,
        event_id="tev_2",
        session_id="sess_a",
        hook_id="PreToolUse",
        payload={"tool_name": "scada_set_setpoint"},
        tiebreaker=1,
    )
    await seed_l3_decision(
        init_l3,
        decision_id="gd_1",
        session_id="sess_a",
        hook_id="PreToolUse",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        decision="gate_request",
        rationale="write_external in enforce mode requires human approval",
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_action_cards("sess_a", tenant_id="acme")
    assert len(cards) == 1
    assert cards[0].risk_level == "write_external"


# ─── ApprovalCard (CARD-APPROVAL-01..03) ────────────────────────────────


async def test_approval_card_5_stage_chain(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-APPROVAL-02 — every 5-stage row surfaces as an ApprovalCard."""
    await seed_event_room(
        init_l4,
        room_id="er_app01",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    # Stamp each stage with a distinct ts so ordering is deterministic.
    stage_ts = {
        "plan": "2026-07-25 10:00:00",
        "check": "2026-07-25 10:01:00",
        "draft": "2026-07-25 10:02:00",
        "approve": "2026-07-25 10:03:00",
        "execute": "2026-07-25 10:04:00",
    }
    for stage, ts in stage_ts.items():
        await seed_l3_decision(
            init_l3,
            decision_id=f"gd_{stage}",
            session_id="sess_a",
            hook_id="PreToolUse",
            tool_name="scada_set_setpoint",
            risk_level="write_external",
            decision="allow",
            rationale=f"{stage}:ok",
            stage=stage,
            ts=ts,
        )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_approval_cards("sess_a", tenant_id="acme")
    assert len(cards) == 5
    stages = [c.stage for c in cards]
    assert stages == ["plan", "check", "draft", "approve", "execute"]


async def test_approval_card_await_human_paused_state(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """CARD-APPROVAL-02 — v3.12.0 await_human rows surface as separate cards."""
    await seed_event_room(
        init_l4,
        room_id="er_app02",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_l3_decision(
        init_l3,
        decision_id="gd_approve_pause",
        session_id="sess_a",
        hook_id="PreToolUse",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        decision="await_human",
        rationale="approve:await_human",
        stage="approve_pause",
        ts="2026-07-25 10:03:00",
    )
    await seed_l3_decision(
        init_l3,
        decision_id="gd_await_human",
        session_id="sess_a",
        hook_id="PreToolUse",
        tool_name="scada_set_setpoint",
        risk_level="write_external",
        decision="await_human",
        rationale="human:人工复议后批准",
        stage="await_human",
        ts="2026-07-25 10:05:00",
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    cards = await proj.list_approval_cards("sess_a", tenant_id="acme")
    assert len(cards) == 2
    pause = next(c for c in cards if c.stage == "approve_pause")
    await_h = next(c for c in cards if c.stage == "await_human")
    assert pause.decision == "await_human"
    assert "approve:await_human" in pause.summary
    assert await_h.decision == "await_human"
    assert "人工复议后批准" in await_h.summary


# ─── D-32 (no mutation) + D-33 (tenant binding) ─────────────────────────


async def test_projection_does_not_mutate_stores(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """D-32 — projection reads but never writes.

    Snapshot the L4 event_room_events count, exercise the
    projection, then re-count: must be unchanged.
    """
    import aiosqlite

    await seed_event_room(
        init_l4,
        room_id="er_imm01",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_room_event(
        init_l4,
        room_id="er_imm01",
        session_id="sess_a",
        event_type="a2a.request.sent",
        payload={"k": "v"},
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    async with aiosqlite.connect(init_l4) as db:
        before = await (await db.execute(
            "SELECT COUNT(*) FROM event_room_events"
        )).fetchone()
        assert before is not None
        before_count = int(before[0])

    # Exercise every projection accessor.
    await proj.list_event_cards("sess_a", tenant_id="acme")
    await proj.list_event_cards_by_room("er_imm01", tenant_id="acme")
    await proj.list_evidence_cards("sess_a", tenant_id="acme")
    await proj.list_action_cards("sess_a", tenant_id="acme")
    await proj.list_approval_cards("sess_a", tenant_id="acme")

    async with aiosqlite.connect(init_l4) as db:
        after = await (await db.execute(
            "SELECT COUNT(*) FROM event_room_events"
        )).fetchone()
        assert after is not None
        after_count = int(after[0])
    assert before_count == after_count


async def test_projection_tenant_filter_excludes_other_tenants(
    init_l2: str, init_l3: str, init_l4: str
) -> None:
    """D-33 — projection filters by tenant_id when supplied."""
    await seed_event_room(
        init_l4,
        room_id="er_tenant_a",
        tenant_id="acme",
        session_ids=["sess_a"],
    )
    await seed_event_room(
        init_l4,
        room_id="er_tenant_b",
        tenant_id="globex",
        session_ids=["sess_b"],
    )
    await seed_room_event(
        init_l4,
        room_id="er_tenant_a",
        session_id="sess_a",
        event_type="a2a.request.sent",
        payload={"tenant": "acme"},
    )
    await seed_room_event(
        init_l4,
        room_id="er_tenant_b",
        session_id="sess_b",
        event_type="a2a.request.sent",
        payload={"tenant": "globex"},
    )
    proj = CoworkProjection(
        l2_db_path=str(init_l2),
        l3_db_path=str(init_l3),
        l4_db_path=str(init_l4),
    )
    # acme tenant sees only acme events.
    acme_cards = await proj.list_event_cards("sess_a", tenant_id="acme")
    assert len(acme_cards) == 1
    assert acme_cards[0].tenant_id == "acme"
    # globex tenant sees only globex events.
    globex_cards = await proj.list_event_cards("sess_b", tenant_id="globex")
    assert len(globex_cards) == 1
    assert globex_cards[0].tenant_id == "globex"
    # Cross-tenant request returns empty.
    cross_cards = await proj.list_event_cards(
        "sess_a", tenant_id="globex"
    )
    assert cross_cards == []
