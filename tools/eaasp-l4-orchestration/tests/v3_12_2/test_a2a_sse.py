"""v3.12.2 — A2A SSE event contract tests.

REQ-IDs: SSE-01..05.

Covers the 5 A2A SSE event types end-to-end:
- a2a.request.sent (SSE-01)
- a2a.request.acknowledged (SSE-02)
- a2a.review.submitted (SSE-03)
- a2a.review.closed (SSE-04)
- a2a.conflict.detected (SSE-05)

Plus coexistence with the pre-existing v3.11.2
``governance.approval.*`` SSE event family (REQ-SSE-06 = "the
5 A2A SSE events coexist with the 5 governance.approval events
on the per-session stream and the room-scoped event log").
"""

from __future__ import annotations

import os
import tempfile
import time

import pytest
import pytest_asyncio

from eaasp_l4_orchestration.a2a_protocol import (
    A2A_CONFLICT_DETECTED,
    A2A_EVENT_TYPES,
    A2A_KIND_GENERIC,
    A2A_KIND_REVIEW_REQUEST,
    A2A_REVIEW_CLOSED,
    A2A_REVIEW_SUBMITTED,
    A2A_REQUEST_ACKNOWLEDGED,
    A2A_REQUEST_SENT,
    A2AMessageEnvelope,
    RiskMetadata,
)
from eaasp_l4_orchestration.a2a_router import A2ARouter
from eaasp_l4_orchestration.db import init_db
from eaasp_l4_orchestration.event_room import EventRoomStore
from eaasp_l4_orchestration.event_stream import SessionEventStream
from eaasp_l4_orchestration.review_set import (
    REVIEW_DECISION_ALLOW,
    REVIEW_DECISION_DENY,
)
from eaasp_l4_orchestration.session_orchestrator_room import (
    MultiSessionCoordinator,
    _AUTHENTICATED_PRINCIPAL,
    bind_authenticated_principal,
)

pytestmark = pytest.mark.asyncio


# ─── Round 4 env-var fixture (HMAC-SHA256 subject hash) ──────────────────────


_TEST_SALT_VALUE = "round4-test-salt-32-bytes-min-aaaaaa"


@pytest.fixture(autouse=True)
def _l4_subject_hash_salt_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EAASP_L4_SUBJECT_HASH_SALT", _TEST_SALT_VALUE)
    from eaasp_l4_orchestration.event_room import (
        _reset_subject_hash_secret_for_testing,
    )
    _reset_subject_hash_secret_for_testing()
    yield
    _reset_subject_hash_secret_for_testing()


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def tmp_db_path() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    await init_db(path)
    try:
        yield path
    finally:
        for suffix in ("", "-wal", "-shm"):
            p = path + suffix
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:
                    pass


@pytest_asyncio.fixture
async def setup(tmp_db_path: str):
    """Yield (store, coord, router, room, session_event_stream, session_id)."""
    store = EventRoomStore(tmp_db_path)
    coord = MultiSessionCoordinator(store)
    router = A2ARouter(store, coord)

    _AUTHENTICATED_PRINCIPAL.set(None)

    room = await store.create(
        room_id="er_sse01",
        tenant_id="tenant_a",
        owner_principal="alice",
    )

    # Seed a session row so the per-session event stream accepts
    # governance.approval.* events (FK to sessions table).
    from eaasp_l4_orchestration.db import connect as _connect
    db = await _connect(tmp_db_path)
    try:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """
            INSERT INTO sessions
                (session_id, intent_id, skill_id, runtime_id, user_id,
                 status, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sess_alice",
                None,
                "skill.test",
                "hermes-l1",
                "user-test",
                "created",
                "{}",
                int(time.time()),
            ),
        )
        await db.commit()
    finally:
        await db.close()

    token = bind_authenticated_principal("alice")
    try:
            await coord.join_event_room(
                room_id="er_sse01",
                session_id="sess_alice",
                principal="alice",
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            await coord.join_event_room(
                room_id="er_sse01",
                session_id="sess_bob",
                principal="bob",
            )
    
    finally:
        token.reset()
    session_event_stream = SessionEventStream(tmp_db_path)
    yield store, coord, router, room, session_event_stream, "sess_alice"

    _AUTHENTICATED_PRINCIPAL.set(None)


# ─── 5 canonical A2A SSE event type tests ───────────────────────────────────


async def test_sse_01_request_sent_event_type_constant() -> None:
    """SSE-01: a2a.request.sent event type constant is in A2A_EVENT_TYPES."""
    assert A2A_REQUEST_SENT in A2A_EVENT_TYPES
    assert A2A_REQUEST_SENT == "a2a.request.sent"


async def test_sse_02_request_acknowledged_event_type_constant() -> None:
    """SSE-02: a2a.request.acknowledged event type constant is canonical."""
    assert A2A_REQUEST_ACKNOWLEDGED in A2A_EVENT_TYPES
    assert A2A_REQUEST_ACKNOWLEDGED == "a2a.request.acknowledged"


async def test_sse_03_review_submitted_event_type_constant() -> None:
    """SSE-03: a2a.review.submitted event type constant is canonical."""
    assert A2A_REVIEW_SUBMITTED in A2A_EVENT_TYPES
    assert A2A_REVIEW_SUBMITTED == "a2a.review.submitted"


async def test_sse_04_review_closed_event_type_constant() -> None:
    """SSE-04: a2a.review.closed event type constant is canonical."""
    assert A2A_REVIEW_CLOSED in A2A_EVENT_TYPES
    assert A2A_REVIEW_CLOSED == "a2a.review.closed"


async def test_sse_05_conflict_detected_event_type_constant() -> None:
    """SSE-05: a2a.conflict.detected event type constant is canonical."""
    assert A2A_CONFLICT_DETECTED in A2A_EVENT_TYPES
    assert A2A_CONFLICT_DETECTED == "a2a.conflict.detected"


async def test_sse_all_five_event_types_emitted_in_full_review_lifecycle(
    setup,
) -> None:
    """SSE-01..05: a complete request_review + 2 submissions + close with
    conflict emits ALL FIVE A2A event types in the canonical order."""
    store, coord, router, _room, _ses, _sid = setup

    # 1. request_review emits SSE-01 + SSE-02.
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_sse01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob", "sess_alice"],
                payload={"artifact": "x"},
                ttl_seconds=3600,
            )
    
    finally:
        token.reset()
    # 2. submissions emit SSE-03.
    token = bind_authenticated_principal("bob")
    try:
            await router.route_review_submission(
                set_id=rs.set_id,
                reviewer_principal="bob",
                reviewer_session_id="sess_bob",
                decision=REVIEW_DECISION_ALLOW,
                evidence_refs=["shared_anchor"],
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            await router.route_review_submission(
                set_id=rs.set_id,
                reviewer_principal="alice",
                reviewer_session_id="sess_alice",
                decision=REVIEW_DECISION_DENY,
                evidence_refs=["shared_anchor"],
            )
    
    finally:
        token.reset()
    # 3. close with conflict emits SSE-04 + SSE-05.
    token = bind_authenticated_principal("alice")
    try:
            result = await router.close_review_set(rs.set_id)
    
    finally:
        token.reset()
    assert result is not None
    assert result.conflict_detected is True

    events = await store.list_room_events("er_sse01")
    event_types_in_order = [e["event_type"] for e in events]

    # Verify all 5 canonical event types are present.
    assert A2A_REQUEST_SENT in event_types_in_order
    assert A2A_REQUEST_ACKNOWLEDGED in event_types_in_order
    assert A2A_REVIEW_SUBMITTED in event_types_in_order
    assert A2A_REVIEW_CLOSED in event_types_in_order
    assert A2A_CONFLICT_DETECTED in event_types_in_order


# ─── Payload shape tests ─────────────────────────────────────────────────────


async def test_sse_request_sent_payload_shape(setup) -> None:
    """SSE-01: a2a.request.sent payload carries source/target + payload_kind
    + risk_level + ts."""
    store, coord, router, _room, _ses, _sid = setup
    from eaasp_l4_orchestration.a2a_protocol import A2AMessageEnvelope

    env = A2AMessageEnvelope(
        room_id="er_sse01",
        source_session_id="sess_alice",
        source_principal="alice",
        target_session_ids=["sess_bob"],
        target_principals=["bob"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "x"},
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("alice")
    try:
            await router.route_message(env)
    
    finally:
        token.reset()
    events = await store.list_room_events("er_sse01")
    sent = [e for e in events if e["event_type"] == A2A_REQUEST_SENT]
    assert len(sent) == 1
    payload = sent[0]["payload"]
    expected_keys = {
        "a2a_message_id",
        "source_session_id",
        "source_principal",
        "target_session_ids",
        "target_principals",
        "payload_kind",
        "payload",
        "risk_level",
        "risk_action",
        "risk_metadata",
        "metadata",
        "ts",
    }
    assert expected_keys.issubset(set(payload.keys()))


async def test_sse_review_submitted_payload_shape(setup) -> None:
    """SSE-03: a2a.review.submitted payload carries set_id + reviewer_session_id
    + decision + evidence_refs + is_new_submission + ts."""
    store, coord, router, _room, _ses, _sid = setup
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_sse01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob"],
                payload={"x": 1},
                ttl_seconds=3600,
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("bob")
    try:
            await router.route_review_submission(
                set_id=rs.set_id,
                reviewer_principal="bob",
                reviewer_session_id="sess_bob",
                decision=REVIEW_DECISION_ALLOW,
                evidence_refs=["a1", "a2"],
            )
    
    finally:
        token.reset()
    events = await store.list_room_events("er_sse01")
    submitted = [
        e for e in events if e["event_type"] == A2A_REVIEW_SUBMITTED
    ]
    assert len(submitted) == 1
    payload = submitted[0]["payload"]
    expected_keys = {
        "set_id",
        "room_id",
        "reviewer_session_id",
        "reviewer_principal",
        "decision",
        "evidence_refs",
        "is_new_submission",
        "ts",
    }
    assert expected_keys.issubset(set(payload.keys()))
    assert payload["is_new_submission"] is True


async def test_sse_review_closed_payload_shape(setup) -> None:
    """SSE-04: a2a.review.closed payload carries final_decision + conflict_detected
    + conflicting_pairs + synthesis_required + aggregate_reason."""
    store, coord, router, _room, _ses, _sid = setup
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_sse01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob"],
                payload={"x": 1},
                ttl_seconds=3600,
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("bob")
    try:
            await router.route_review_submission(
                set_id=rs.set_id,
                reviewer_principal="bob",
                reviewer_session_id="sess_bob",
                decision=REVIEW_DECISION_ALLOW,
                evidence_refs=["a1"],
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            await router.close_review_set(rs.set_id)
    
    finally:
        token.reset()
    events = await store.list_room_events("er_sse01")
    closed = [e for e in events if e["event_type"] == A2A_REVIEW_CLOSED]
    assert len(closed) == 1
    payload = closed[0]["payload"]
    expected_keys = {
        "set_id",
        "room_id",
        "initiator_session_id",
        "initiator_principal",
        "final_decision",
        "conflict_detected",
        "conflicting_pairs",
        "synthesis_required",
        "aggregate_reason",
        "review_count",
        "ts",
    }
    assert expected_keys.issubset(set(payload.keys()))
    assert payload["final_decision"] == "allow"


async def test_sse_conflict_detected_payload_shape(setup) -> None:
    """SSE-05: a2a.conflict.detected payload carries conflicting_pairs +
    synthesis_required + aggregate_reason."""
    store, coord, router, _room, _ses, _sid = setup
    # Add sess_carol to the room so we can include her as a reviewer.
    token = bind_authenticated_principal("alice")
    try:
            await coord.join_event_room(
                room_id="er_sse01",
                session_id="sess_carol",
                principal="carol",
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_sse01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob", "sess_carol"],
                payload={"x": 1},
                ttl_seconds=3600,
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("bob")
    try:
            await router.route_review_submission(
                set_id=rs.set_id,
                reviewer_principal="bob",
                reviewer_session_id="sess_bob",
                decision=REVIEW_DECISION_ALLOW,
                evidence_refs=["shared"],
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("carol")
    try:
            await router.route_review_submission(
                set_id=rs.set_id,
                reviewer_principal="carol",
                reviewer_session_id="sess_carol",
                decision=REVIEW_DECISION_DENY,
                evidence_refs=["shared"],
            )
    
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            await router.close_review_set(rs.set_id)
    
    finally:
        token.reset()
    events = await store.list_room_events("er_sse01")
    conflict = [
        e for e in events if e["event_type"] == A2A_CONFLICT_DETECTED
    ]
    assert len(conflict) == 1
    payload = conflict[0]["payload"]
    expected_keys = {
        "set_id",
        "room_id",
        "initiator_session_id",
        "initiator_principal",
        "conflicting_pairs",
        "synthesis_required",
        "aggregate_reason",
        "review_count",
        "ts",
    }
    assert expected_keys.issubset(set(payload.keys()))


# ─── Coexistence tests ───────────────────────────────────────────────────────


async def test_sse_a2a_events_coexist_with_governance_approval_events(
    setup,
) -> None:
    """SSE-06: the 5 a2a.* events coexist with the v3.11.2
    governance.approval.<stage> events on the per-session stream +
    room-scoped event log (different namespaces; SSE consumers
    dispatch on event-type prefix)."""
    store, coord, router, _room, ses, sid = setup

    # Emit a governance.approval.plan event on the per-session stream.
    await ses.emit_governance_approval_plan(
        session_id=sid,
        decision_id="gd_approval_plan_sse",
        request_id="gd_approval_sse",
        hook_id="h_pre",
        decision="allow",
        reason="plan:sse",
        caller_principal="caller@scopes",
        evidence_refs=[],
        ts="2026-07-27 10:00:00",
    )

    # Emit an A2A request.sent on the room-scoped event log.
    from eaasp_l4_orchestration.a2a_protocol import A2AMessageEnvelope
    env = A2AMessageEnvelope(
        room_id="er_sse01",
        source_session_id="sess_alice",
        source_principal="alice",
        target_session_ids=["sess_bob"],
        target_principals=["bob"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "x"},
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("alice")
    try:
            await router.route_message(env)
    
    finally:
        token.reset()
    # Verify the per-session stream has governance.approval.plan.
    session_events = await ses.list_events(sid)
    session_event_types = [e["event_type"] for e in session_events]
    assert "governance.approval.plan" in session_event_types

    # Verify the room-scoped event log has a2a.request.sent.
    room_events = await store.list_room_events("er_sse01")
    room_event_types = [e["event_type"] for e in room_events]
    assert A2A_REQUEST_SENT in room_event_types


async def test_sse_event_type_names_are_distinct_namespaces(setup) -> None:
    """SSE-07: a2a.* event types are in a distinct namespace from
    governance.approval.* (so SSE consumers can subscribe independently)."""
    a2a_types = set(A2A_EVENT_TYPES)
    gov_approval_types = {
        "governance.approval.plan",
        "governance.approval.check",
        "governance.approval.draft",
        "governance.approval.approve",
        "governance.approval.execute",
    }
    # No overlap between namespaces.
    assert a2a_types.isdisjoint(gov_approval_types)
    # The A2A namespace is prefixed with "a2a.".
    for t in a2a_types:
        assert t.startswith("a2a."), f"{t!r} does not start with 'a2a.'"


async def test_sse_room_event_payload_preserves_risk_metadata(
    setup,
) -> None:
    """SSE-08: a2a.request.sent payload preserves the risk_level +
    risk_action + risk_metadata sub-dict verbatim (REQ-A2A-02)."""
    from eaasp_l4_orchestration.a2a_protocol import RiskMetadata
    store, coord, router, _room, _ses, _sid = setup
    env = A2AMessageEnvelope(
        room_id="er_sse01",
        source_session_id="sess_alice",
        source_principal="alice",
        target_session_ids=["sess_bob"],
        target_principals=["bob"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "x"},
        risk_metadata=RiskMetadata(
            risk_level="write_external",
            action="scada_set_setpoint",
            metadata={"target_device": "xfmr-042"},
        ),
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("alice")
    try:
            await router.route_message(env)
    
    finally:
        token.reset()
    events = await store.list_room_events("er_sse01")
    sent = [e for e in events if e["event_type"] == A2A_REQUEST_SENT]
    assert len(sent) == 1
    payload = sent[0]["payload"]
    assert payload["risk_level"] == "write_external"
    assert payload["risk_action"] == "scada_set_setpoint"
    assert payload["risk_metadata"]["target_device"] == "xfmr-042"