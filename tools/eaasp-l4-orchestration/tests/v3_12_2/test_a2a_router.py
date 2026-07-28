"""v3.12.2 — A2A Router tests.

REQ-IDs: A2A-01..03 + SSE-01..05.

Covers the A2A Router end-to-end against a real EventRoomStore +
MultiSessionCoordinator:
- Single-reviewer path (route a single message to one session).
- Multi-reviewer consistent-decision path (all allow / all deny).
- Conflict detection path (multi-reviewer contradict on shared
  evidence).
- Cross-session routing + ContextVar authorization.
- Source principal parity check (request body vs ContextVar).
- Target principal probe (server-side lookup rejects mismatches).
- ReviewSet lifecycle (open + submit + close).
- Aggregation output emits a2a.review.closed +
  a2a.conflict.detected events.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time

import pytest
import pytest_asyncio

from eaasp_l4_orchestration.a2a_protocol import (
    A2AMessageEnvelope,
    A2A_KIND_GENERIC,
    A2A_KIND_REVIEW_REQUEST,
    RiskMetadata,
    A2A_REQUEST_SENT,
    A2A_REQUEST_ACKNOWLEDGED,
    A2A_REVIEW_SUBMITTED,
    A2A_REVIEW_CLOSED,
    A2A_CONFLICT_DETECTED,
)
from eaasp_l4_orchestration.a2a_router import (
    A2AMessageNotAccepted,
    A2ARouter,
    A2ARouterError,
)
from eaasp_l4_orchestration.db import init_db
from eaasp_l4_orchestration.event_room import EventRoomStore
from eaasp_l4_orchestration.review_set import (
    AGGREGATE_ALLOW,
    AGGREGATE_DENY,
    AGGREGATE_ESCALATE,
    REVIEW_DECISION_ALLOW,
    REVIEW_DECISION_DENY,
    REVIEW_DECISION_NEEDS_REVISION,
)
from eaasp_l4_orchestration.session_orchestrator_room import (
    AuthContextMissing,
    MultiSessionCoordinator,
    _AUTHENTICATED_PRINCIPAL,
    bind_authenticated_principal,
)


pytestmark = pytest.mark.asyncio


# ─── Round 4 env-var fixture (HMAC-SHA256 subject hash) ──────────────────────


_TEST_SALT_VALUE = "round4-test-salt-32-bytes-min-aaaaaa"


@pytest.fixture(autouse=True)
def _l4_subject_hash_salt_env(monkeypatch: pytest.MonkeyPatch):
    """Set ``EAASP_L4_SUBJECT_HASH_SALT`` for every test (autouse)."""
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
    """Yield (store, coordinator, router, room) with a 3-session room.

    Sessions: sess_alice (alice, owner), sess_bob (bob), sess_carol (carol).
    """
    store = EventRoomStore(tmp_db_path)
    coord = MultiSessionCoordinator(store)
    router = A2ARouter(store, coord)

    # Defensive: clear any leaked principal from a prior test.
    _AUTHENTICATED_PRINCIPAL.set(None)

    room = await store.create(
        room_id="er_router01",
        tenant_id="tenant_a",
        owner_principal="alice",
    )

    token = bind_authenticated_principal("alice")
    try:
            await coord.join_event_room(
                room_id="er_router01",
                session_id="sess_alice",
                principal="alice",
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            await coord.join_event_room(
                room_id="er_router01",
                session_id="sess_bob",
                principal="bob",
            )
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            await coord.join_event_room(
                room_id="er_router01",
                session_id="sess_carol",
                principal="carol",
            )
    
    finally:
        token.reset()
    yield store, coord, router, room

    _AUTHENTICATED_PRINCIPAL.set(None)


# ─── Single-reviewer path tests ──────────────────────────────────────────────


async def test_route_message_to_single_target_emits_request_sent(
    setup,
) -> None:
    """A2A-01: route_message to a single target emits a2a.request.sent."""
    store, coord, router, _room = setup
    env = A2AMessageEnvelope(
        room_id="er_router01",
        source_session_id="sess_alice",
        source_principal="alice",
        target_session_ids=["sess_bob"],
        target_principals=["bob"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "hello bob"},
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("alice")
    try:
            seq = await router.route_message(env)
    finally:
        token.reset()
    assert seq is not None

    events = await store.list_room_events("er_router01")
    sent_events = [
        e for e in events if e["event_type"] == A2A_REQUEST_SENT
    ]
    assert len(sent_events) == 1
    payload = sent_events[0]["payload"]
    assert payload["source_session_id"] == "sess_alice"
    assert payload["target_session_ids"] == ["sess_bob"]
    assert payload["payload_kind"] == "generic"


async def test_route_message_requires_authenticated_principal(
    setup,
) -> None:
    """A2A-02: route_message without ContextVar raises AuthContextMissing."""
    store, coord, router, _room = setup
    env = A2AMessageEnvelope(
        room_id="er_router01",
        source_session_id="sess_alice",
        source_principal="alice",
        target_session_ids=["sess_bob"],
        target_principals=["bob"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "x"},
        created_at=int(time.time()),
    )
    # No bind_authenticated_principal → must raise.
    with pytest.raises(AuthContextMissing):
        await router.route_message(env)


async def test_route_message_rejects_source_principal_mismatch(
    setup,
) -> None:
    """A2A-02: envelope.source_principal ≠ ContextVar → A2AMessageNotAccepted."""
    store, coord, router, _room = setup
    env = A2AMessageEnvelope(
        room_id="er_router01",
        source_session_id="sess_alice",
        source_principal="alice",
        target_session_ids=["sess_bob"],
        target_principals=["bob"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "x"},
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("bob")  # bob is not alice
    try:
            with pytest.raises(A2AMessageNotAccepted):
                await router.route_message(env)
    finally:
        token.reset()


async def test_route_message_rejects_target_not_in_room(setup) -> None:
    """A2A-02: target session not in room → A2AMessageNotAccepted."""
    store, coord, router, _room = setup
    env = A2AMessageEnvelope(
        room_id="er_router01",
        source_session_id="sess_alice",
        source_principal="alice",
        target_session_ids=["sess_nonexistent"],
        target_principals=["bob"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "x"},
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("alice")
    try:
            with pytest.raises(A2AMessageNotAccepted):
                await router.route_message(env)
    
    
    finally:
        token.reset()
async def test_route_message_rejects_target_principal_mismatch(
    setup,
) -> None:
    """A2A-02: target_session_id is in room but target_principal is wrong
    → A2AMessageNotAccepted."""
    store, coord, router, _room = setup
    env = A2AMessageEnvelope(
        room_id="er_router01",
        source_session_id="sess_alice",
        source_principal="alice",
        target_session_ids=["sess_bob"],
        target_principals=["eve"],  # wrong principal for sess_bob
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "x"},
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("alice")
    try:
            with pytest.raises(A2AMessageNotAccepted):
                await router.route_message(env)
    
    
    finally:
        token.reset()
async def test_route_message_rejects_source_session_not_in_room(
    setup,
) -> None:
    """A2A-02: source session not in room → A2AMessageNotAccepted."""
    store, coord, router, _room = setup
    env = A2AMessageEnvelope(
        room_id="er_router01",
        source_session_id="sess_nonexistent",
        source_principal="alice",
        target_session_ids=["sess_bob"],
        target_principals=["bob"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "x"},
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("alice")
    try:
            with pytest.raises(A2AMessageNotAccepted):
                await router.route_message(env)
    
    
    finally:
        token.reset()
async def test_route_message_rejects_source_principal_bound_to_other(
    setup,
) -> None:
    """A2A-02: source session is in room but bound to a DIFFERENT principal
    than the verified caller → A2AMessageNotAccepted.

    Stops alice from sending a message under bob's identity from
    bob's session.
    """
    store, coord, router, _room = setup
    # sess_bob is bound to bob; alice cannot send as bob.
    env = A2AMessageEnvelope(
        room_id="er_router01",
        source_session_id="sess_bob",
        source_principal="bob",
        target_session_ids=["sess_carol"],
        target_principals=["carol"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "x"},
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("alice")
    try:
            with pytest.raises(A2AMessageNotAccepted):
                await router.route_message(env)
    
    
    finally:
        token.reset()
# ─── ReviewSet lifecycle tests ────────────────────────────────────────────────


async def test_request_review_creates_reviewset_and_emits_request_sent(
    setup,
) -> None:
    """A2A-01: request_review emits a2a.request.sent per reviewer + creates
    a ReviewSet keyed on set_id in router.review_sets."""
    store, coord, router, _room = setup
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_router01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob", "sess_carol"],
                payload={"artifact": "spreadsheet.csv"},
                ttl_seconds=3600,
            )
    finally:
        token.reset()
    assert rs.set_id is not None
    assert rs.status == "open"
    assert rs.room_id == "er_router01"
    assert router.review_sets.get(rs.set_id) is rs

    events = await store.list_room_events("er_router01")
    sent_events = [
        e for e in events if e["event_type"] == A2A_REQUEST_SENT
    ]
    assert len(sent_events) == 1  # single fan-out row covering both reviewers


async def test_request_review_emits_request_acknowledged(
    setup,
) -> None:
    """SSE-02: review_request also emits a2a.request.acknowledged (structural)."""
    store, coord, router, _room = setup
    token = bind_authenticated_principal("alice")
    try:
            await router.request_review(
                room_id="er_router01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob", "sess_carol"],
                payload={"artifact": "x"},
                ttl_seconds=3600,
            )
    finally:
        token.reset()
    events = await store.list_room_events("er_router01")
    ack_events = [
        e for e in events if e["event_type"] == A2A_REQUEST_ACKNOWLEDGED
    ]
    assert len(ack_events) == 1


async def test_route_review_submission_emits_review_submitted(
    setup,
) -> None:
    """SSE-03: each reviewer submission emits a2a.review.submitted."""
    store, coord, router, _room = setup
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_router01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob", "sess_carol"],
                payload={"artifact": "x"},
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
    events = await store.list_room_events("er_router01")
    submitted = [
        e for e in events if e["event_type"] == A2A_REVIEW_SUBMITTED
    ]
    assert len(submitted) == 1
    payload = submitted[0]["payload"]
    assert payload["reviewer_session_id"] == "sess_bob"
    assert payload["decision"] == REVIEW_DECISION_ALLOW


async def test_route_review_submission_rejects_principal_mismatch(
    setup,
) -> None:
    """A2A-02: caller-supplied reviewer_principal disagrees with ContextVar
    → A2AMessageNotAccepted."""
    store, coord, router, _room = setup
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_router01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob"],
                payload={"artifact": "x"},
                ttl_seconds=3600,
            )
    
    finally:
        token.reset()
    token = bind_authenticated_principal("bob")
    try:
            with pytest.raises(A2AMessageNotAccepted):
                await router.route_review_submission(
                    set_id=rs.set_id,
                    reviewer_principal="eve",  # wrong principal
                    reviewer_session_id="sess_bob",
                    decision=REVIEW_DECISION_ALLOW,
                )
    
    
    finally:
        token.reset()
# ─── Aggregation + close event tests ─────────────────────────────────────────


async def test_close_review_set_emits_review_closed(setup) -> None:
    """SSE-04: close_review_set emits a2a.review.closed + the AggregationResult
    is the audit-visible final decision."""
    store, coord, router, _room = setup
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_router01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob", "sess_carol"],
                payload={"artifact": "x"},
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
    token = bind_authenticated_principal("carol")
    try:
            await router.route_review_submission(
                set_id=rs.set_id,
                reviewer_principal="carol",
                reviewer_session_id="sess_carol",
                decision=REVIEW_DECISION_ALLOW,
                evidence_refs=["a1"],
            )
    
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            result = await router.close_review_set(rs.set_id)
    
    finally:
        token.reset()
    assert result is not None
    assert result.final_decision == AGGREGATE_ALLOW
    events = await store.list_room_events("er_router01")
    closed_events = [
        e for e in events if e["event_type"] == A2A_REVIEW_CLOSED
    ]
    assert len(closed_events) == 1
    payload = closed_events[0]["payload"]
    assert payload["final_decision"] == AGGREGATE_ALLOW
    assert payload["set_id"] == rs.set_id


async def test_close_review_set_with_conflict_emits_conflict_detected(
    setup,
) -> None:
    """SSE-05: aggregation detects conflict → a2a.conflict.detected emitted."""
    store, coord, router, _room = setup
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_router01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob", "sess_carol"],
                payload={"artifact": "x"},
                ttl_seconds=3600,
            )
    
    finally:
        token.reset()
    # Both reviewers cite the SAME evidence with contradictory
    # decisions.
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
    token = bind_authenticated_principal("carol")
    try:
            await router.route_review_submission(
                set_id=rs.set_id,
                reviewer_principal="carol",
                reviewer_session_id="sess_carol",
                decision=REVIEW_DECISION_DENY,
                evidence_refs=["shared_anchor"],
            )
    
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            result = await router.close_review_set(rs.set_id)
    
    finally:
        token.reset()
    assert result is not None
    assert result.conflict_detected is True
    events = await store.list_room_events("er_router01")
    conflict_events = [
        e for e in events if e["event_type"] == A2A_CONFLICT_DETECTED
    ]
    assert len(conflict_events) == 1


async def test_close_review_set_missing_reviewers_escalates(
    setup,
) -> None:
    """REVIEW-03 / HIGH #1: missing reviewers → AGGREGATE_ESCALATE."""
    store, coord, router, _room = setup
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_router01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob", "sess_carol"],
                payload={"artifact": "x"},
                ttl_seconds=3600,
            )
    
    finally:
        token.reset()
    # Only bob submits; carol is silent.
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
            result = await router.close_review_set(rs.set_id)
    
    finally:
        token.reset()
    assert result is not None
    assert result.final_decision == AGGREGATE_ESCALATE
    assert result.synthesis_required is True


# ─── Cross-session routing + ContextVar auth ─────────────────────────────────


async def test_cross_session_principal_can_message_via_room(
    setup,
) -> None:
    """A2A-02: alice (principal) can message bob via sess_bob
    (cross-session, cross-principal) — the room membership +
    principal probes authorize it."""
    store, coord, router, _room = setup
    env = A2AMessageEnvelope(
        room_id="er_router01",
        source_session_id="sess_alice",
        source_principal="alice",
        target_session_ids=["sess_bob"],
        target_principals=["bob"],
        payload_kind=A2A_KIND_GENERIC,
        payload={"msg": "hello from alice"},
        created_at=int(time.time()),
    )
    token = bind_authenticated_principal("alice")
    try:
            seq = await router.route_message(env)
    finally:
        token.reset()
    assert seq is not None


async def test_aggregate_then_close_emits_both_review_closed_and_conflict(
    setup,
) -> None:
    """SSE-04 + SSE-05: aggregate_review_set emits conflict_detected
    AND close_review_set emits review_closed."""
    store, coord, router, _room = setup
    token = bind_authenticated_principal("alice")
    try:
            rs = await router.request_review(
                room_id="er_router01",
                initiator_session_id="sess_alice",
                reviewer_session_ids=["sess_bob", "sess_carol"],
                payload={"artifact": "x"},
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
                evidence_refs=["x"],
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
                evidence_refs=["x"],
            )
    
    finally:
        token.reset()
    token = bind_authenticated_principal("alice")
    try:
            # First, aggregate (emits conflict_detected).
            agg_result = await router.aggregate_review_set(rs.set_id)
            assert agg_result is not None
            assert agg_result.conflict_detected is True
    
            # Then close (emits review_closed).
            close_result = await router.close_review_set(rs.set_id)
            assert close_result is not None
    
    finally:
        token.reset()
    events = await store.list_room_events("er_router01")
    event_types = [e["event_type"] for e in events]
    # Both conflict_detected (from aggregate) + review_closed (from close) emitted.
    assert A2A_CONFLICT_DETECTED in event_types
    assert A2A_REVIEW_CLOSED in event_types