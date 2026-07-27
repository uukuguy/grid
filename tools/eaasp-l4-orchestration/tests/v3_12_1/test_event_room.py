"""v3.12.1 — Event Room lifecycle tests.

REQ-IDs: ROOM-01..03 (create / close / add-member / remove-member /
expire sweep + per-tenant cap + room_id pattern validation).

Covers the EventRoomStore (tools/eaasp-l4-orchestration) end-to-end:
- create / close lifecycle
- add / remove member
- expiration sweep (capture-then-update + post-UPDATE re-read)
- room_id pattern allowlist (^[a-zA-Z0-9_-]{1,128}$)
- per-tenant room-count cap (1024)
- principal authorization gate on add/remove (caller-side
  authorization; EventRoomNotAuthorized rejection; security review
  round 2 #1, #2)
- audit row on re-bind rejection (security review round 2 #4)
- fan_out_event best-effort + principal authorization gate
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time

import pytest
import pytest_asyncio

from eaasp_l4_orchestration.db import init_db
from eaasp_l4_orchestration.event_room import (
    EventRoomAlreadyExists,
    EventRoomNotAuthorized,
    EventRoomNotFound,
    EventRoomNotOpen,
    EventRoomNotOwned,
    EventRoomStore,
    STATUS_CLOSED,
    STATUS_EXPIRED,
    STATUS_OPEN,
    make_event_room_event_type,
)


pytestmark = pytest.mark.asyncio


# ─── Fixtures ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def tmp_db_path() -> str:
    """Per-test temp DB so concurrent tests don't share state."""
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
async def store(tmp_db_path: str) -> EventRoomStore:
    """Bare-bones store with a fresh DB."""
    return EventRoomStore(tmp_db_path)


# ─── Lifecycle tests ────────────────────────────────────────────────────────


async def test_create_with_explicit_room_id(store: EventRoomStore) -> None:
    """ROOM-01: explicit room_id is honored + event_room row created."""
    room = await store.create(
        room_id="er_lab01",
        tenant_id="tenant_a",
        owner_principal="alice@example.com",
        name="Lab Room 01",
    )
    assert room.room_id == "er_lab01"
    assert room.tenant_id == "tenant_a"
    assert room.owner_principal == "alice@example.com"
    assert room.status == STATUS_OPEN
    assert room.name == "Lab Room 01"
    assert room.members == []
    assert room.closed_at is None
    # expires_at must be > created_at (TTL applied).
    assert room.expires_at > room.created_at


async def test_create_auto_generates_room_id(store: EventRoomStore) -> None:
    """ROOM-01: room_id defaults to er_<uuid4-hex[:16]> when omitted."""
    room = await store.create(
        tenant_id="tenant_a",
        owner_principal="alice@example.com",
    )
    assert room.room_id.startswith("er_")
    # The auto-generated id must satisfy the pattern.
    import re
    assert re.match(r"^[a-zA-Z0-9_-]{1,128}$", room.room_id)


async def test_create_duplicate_room_id_raises(store: EventRoomStore) -> None:
    """ROOM-01: duplicate room_id raises EventRoomAlreadyExists."""
    await store.create(
        room_id="er_dup",
        tenant_id="tenant_a",
        owner_principal="alice",
    )
    with pytest.raises(EventRoomAlreadyExists):
        await store.create(
            room_id="er_dup",
            tenant_id="tenant_a",
            owner_principal="alice",
        )


async def test_create_invalid_room_id_pattern_rejected(
    store: EventRoomStore,
) -> None:
    """ROOM-01 / security review #5: room_id must match strict pattern."""
    # Path-traversal attempt
    with pytest.raises(ValueError, match="room_id must match"):
        await store.create(
            room_id="../etc/passwd",
            tenant_id="tenant_a",
            owner_principal="alice",
        )
    # SQL-injection attempt
    with pytest.raises(ValueError, match="room_id must match"):
        await store.create(
            room_id="er_lab01'; DROP TABLE event_rooms;--",
            tenant_id="tenant_a",
            owner_principal="alice",
        )
    # Empty string
    with pytest.raises(ValueError, match="room_id must match"):
        await store.create(
            room_id="",
            tenant_id="tenant_a",
            owner_principal="alice",
        )
    # Too long (129 chars)
    with pytest.raises(ValueError, match="room_id must match"):
        await store.create(
            room_id="a" * 129,
            tenant_id="tenant_a",
            owner_principal="alice",
        )


async def test_create_name_max_length_enforced(store: EventRoomStore) -> None:
    """ROOM-01 / security review #5: name <=256 chars."""
    with pytest.raises(ValueError, match="name must be"):
        await store.create(
            room_id="er_long_name",
            tenant_id="tenant_a",
            owner_principal="alice",
            name="x" * 257,
        )


async def test_create_per_tenant_room_count_cap(
    store: EventRoomStore,
) -> None:
    """ROOM-01 / security review #5: per-tenant cap (1024).

    We don't actually create 1024 rows in this test (slow); we
    monkey-patch the cap constant via a re-import so the test
    runs fast. The cap is a module-level constant for fast read;
    verify the check fires at the boundary.
    """
    import eaasp_l4_orchestration.event_room as er_module

    original_cap = er_module._ROOMS_PER_TENANT_CAP
    er_module._ROOMS_PER_TENANT_CAP = 2  # type: ignore[misc]
    try:
        await store.create(
            room_id="er_cap1",
            tenant_id="tenant_cap",
            owner_principal="alice",
        )
        await store.create(
            room_id="er_cap2",
            tenant_id="tenant_cap",
            owner_principal="alice",
        )
        # Third create in the same tenant MUST be rejected.
        with pytest.raises(ValueError, match="room cap"):
            await store.create(
                room_id="er_cap3",
                tenant_id="tenant_cap",
                owner_principal="alice",
            )
        # Different tenant is not affected.
        room_other = await store.create(
            room_id="er_cap_other",
            tenant_id="tenant_other",
            owner_principal="bob",
        )
        assert room_other.room_id == "er_cap_other"
    finally:
        er_module._ROOMS_PER_TENANT_CAP = original_cap  # type: ignore[misc]


async def test_close_by_owner(store: EventRoomStore) -> None:
    """ROOM-01: only owner may close; status flips to closed."""
    room = await store.create(
        room_id="er_close",
        tenant_id="t1",
        owner_principal="alice",
    )
    closed = await store.close(room.room_id, "alice")
    assert closed.status == STATUS_CLOSED
    assert closed.closed_at is not None
    assert closed.closed_at >= closed.created_at


async def test_close_by_non_owner_rejected(store: EventRoomStore) -> None:
    """ROOM-01: non-owner close raises EventRoomNotOwned."""
    room = await store.create(
        room_id="er_close_other",
        tenant_id="t1",
        owner_principal="alice",
    )
    with pytest.raises(EventRoomNotOwned):
        await store.close(room.room_id, "bob")


async def test_close_nonexistent_room_raises(store: EventRoomStore) -> None:
    """ROOM-01: close on missing room raises EventRoomNotFound."""
    with pytest.raises(EventRoomNotFound):
        await store.close("er_missing", "alice")


async def test_close_is_idempotent(store: EventRoomStore) -> None:
    """ROOM-01: closing an already-closed room returns the existing row."""
    room = await store.create(
        room_id="er_idem",
        tenant_id="t1",
        owner_principal="alice",
    )
    first = await store.close(room.room_id, "alice")
    second = await store.close(room.room_id, "alice")
    assert second.status == STATUS_CLOSED
    assert second.closed_at == first.closed_at


# ─── Membership tests ───────────────────────────────────────────────────────


async def test_add_member_then_list(store: EventRoomStore) -> None:
    """ROOM-02: add_member inserts + list_members returns session_id."""
    room = await store.create(
        room_id="er_members",
        tenant_id="t1",
        owner_principal="alice",
    )
    inserted = await store.add_member(
        room.room_id, "sess_001", "alice", caller_principal="alice"
    )
    assert inserted is True
    members = await store.list_members(room.room_id)
    assert members == ["sess_001"]


async def test_add_member_duplicate_raises(store: EventRoomStore) -> None:
    """ROOM-02 + security review #4: re-bind raises EventRoomAlreadyExists.

    The pre-INSERT probe detects the existing (room_id, session_id)
    pair; the new shape raises rather than silently absorbing the
    conflict (which would erase the principal who originally
    authorized the bind).
    """
    room = await store.create(
        room_id="er_rebind",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_001", "alice", caller_principal="alice"
    )
    # Re-bind attempt — must raise.
    with pytest.raises(EventRoomAlreadyExists, match="already bound"):
        await store.add_member(
            room.room_id,
            "sess_001",
            "bob",  # Different principal — must not silently swap.
            caller_principal="alice",
        )
    # The existing membership is preserved (principal column unchanged).
    members = await store.list_members(room.room_id)
    assert members == ["sess_001"]


async def test_add_member_emits_audit_row_on_rebind_rejection(
    store: EventRoomStore,
) -> None:
    """ROOM-02 + security review #4: re-bind rejection emits an audit row."""
    room = await store.create(
        room_id="er_audit",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_001", "alice", caller_principal="alice"
    )
    with pytest.raises(EventRoomAlreadyExists):
        await store.add_member(
            room.room_id,
            "sess_001",
            "mallory",
            caller_principal="alice",
        )
    # The audit row is in event_room_events.
    events = await store.list_room_events(room.room_id)
    audit_events = [
        e for e in events
        if e["event_type"].endswith("member_rebind_rejected")
    ]
    assert len(audit_events) == 1
    payload = audit_events[0]["payload"]
    assert payload["attempted_principal"] == "mallory"
    assert payload["caller_principal"] == "alice"


async def test_add_member_unauthorized_caller_rejected(
    store: EventRoomStore,
) -> None:
    """ROOM-02 + security review round 2 #1 (CRITICAL): non-owner /
    non-member caller cannot bind a session to a room.

    The previous shape allowed ANY caller to bind ANY session to
    ANY open room with ANY principal. The new shape requires the
    caller to be the room owner (or an existing member under the
    same principal — N/A for a fresh bind).
    """
    room = await store.create(
        room_id="er_priv",
        tenant_id="t1",
        owner_principal="alice",
    )
    # Mallory is not the owner and not a member — must be rejected.
    with pytest.raises(EventRoomNotAuthorized):
        await store.add_member(
            room.room_id,
            "sess_mallory",
            "mallory",
            caller_principal="mallory",
        )
    # No membership was created.
    members = await store.list_members(room.room_id)
    assert members == []


async def test_add_member_owner_can_invite_any_session(
    store: EventRoomStore,
) -> None:
    """ROOM-02: the owner CAN bind a session they don't own.

    The owner authorization gate covers room-management events
    (inviting new sessions). This is the legitimate use of the
    "owner bypass" — the owner is responsible for who joins the
    room.
    """
    room = await store.create(
        room_id="er_owner_invite",
        tenant_id="t1",
        owner_principal="alice",
    )
    inserted = await store.add_member(
        room.room_id,
        "sess_bob",
        "bob",
        caller_principal="alice",  # alice is the owner
    )
    assert inserted is True


async def test_remove_member_self_removal(store: EventRoomStore) -> None:
    """ROOM-02: caller can remove themselves."""
    room = await store.create(
        room_id="er_self",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_bob", "bob", caller_principal="alice"
    )
    removed = await store.remove_member(
        room.room_id, "sess_bob", "bob"
    )
    assert removed is True
    members = await store.list_members(room.room_id)
    assert members == []


async def test_remove_member_unauthorized_rejected(
    store: EventRoomStore,
) -> None:
    """ROOM-02 + security review #2: non-self / non-owner removal rejected."""
    room = await store.create(
        room_id="er_unauth",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_bob", "bob", caller_principal="alice"
    )
    # Mallory is neither bob nor the owner — must be rejected.
    with pytest.raises(EventRoomNotAuthorized):
        await store.remove_member(
            room.room_id, "sess_bob", "mallory"
        )
    # The membership is preserved.
    members = await store.list_members(room.room_id)
    assert members == ["sess_bob"]


async def test_remove_member_owner_can_remove_any_session(
    store: EventRoomStore,
) -> None:
    """ROOM-02: the owner CAN remove any session from the room."""
    room = await store.create(
        room_id="er_owner_remove",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_bob", "bob", caller_principal="alice"
    )
    removed = await store.remove_member(
        room.room_id, "sess_bob", "alice"  # owner kicking bob
    )
    assert removed is True


async def test_remove_member_idempotent_for_non_member(
    store: EventRoomStore,
) -> None:
    """ROOM-02: removing a non-member returns False (no error)."""
    room = await store.create(
        room_id="er_nonmember",
        tenant_id="t1",
        owner_principal="alice",
    )
    removed = await store.remove_member(
        room.room_id, "sess_nobody", "alice"
    )
    assert removed is False


async def test_add_member_to_closed_room_rejected(
    store: EventRoomStore,
) -> None:
    """ROOM-02: cannot add a member to a closed room."""
    room = await store.create(
        room_id="er_closed",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.close(room.room_id, "alice")
    with pytest.raises(EventRoomNotOpen):
        await store.add_member(
            room.room_id, "sess_001", "alice", caller_principal="alice"
        )


# ─── Expiry sweep ───────────────────────────────────────────────────────────


async def test_expire_stale_rooms_flips_to_expired(
    store: EventRoomStore,
) -> None:
    """ROOM-03 + security review #3: capture-then-update sweep flips status."""
    # Create a room with a very short TTL (1 second).
    room = await store.create(
        room_id="er_short",
        tenant_id="t1",
        owner_principal="alice",
        ttl_seconds=1,
    )
    # Expire sweep BEFORE the TTL — nothing flips.
    flipped = await store.expire_stale_rooms()
    assert flipped == []
    # Advance virtual time past the TTL.
    future_ts = room.expires_at + 1
    flipped = await store.expire_stale_rooms(now=future_ts)
    assert flipped == ["er_short"]
    # Verify the DB state.
    refreshed = await store.get("er_short")
    assert refreshed is not None
    assert refreshed.status == STATUS_EXPIRED


async def test_expire_stale_rooms_idempotent(store: EventRoomStore) -> None:
    """ROOM-03: a second sweep returns an empty list."""
    room = await store.create(
        room_id="er_idem_expire",
        tenant_id="t1",
        owner_principal="alice",
        ttl_seconds=1,
    )
    future_ts = room.expires_at + 1
    first = await store.expire_stale_rooms(now=future_ts)
    second = await store.expire_stale_rooms(now=future_ts)
    assert first == ["er_idem_expire"]
    assert second == []


async def test_expire_stale_rooms_no_toctou_window(
    store: EventRoomStore,
) -> None:
    """ROOM-03 + security review round 1 #3 + round 2 #3:

    Capture-then-update closes the TOCTOU window. We can't
    actually inject a concurrent writer in a single-threaded
    test, but we can verify the returned list is derived from
    the post-UPDATE state (not from a slice of the candidate
    set). Create 5 rooms with mixed TTLs, sweep, verify the
    flipped list comes from the post-UPDATE ``status='expired'``
    SELECT.
    """
    rooms = []
    for i in range(5):
        r = await store.create(
            room_id=f"er_mixed_{i}",
            tenant_id="t1",
            owner_principal="alice",
            ttl_seconds=1 if i < 3 else 3600,
        )
        rooms.append(r)
    future_ts = rooms[2].expires_at + 1  # only first 3 are stale
    flipped = await store.expire_stale_rooms(now=future_ts)
    assert sorted(flipped) == sorted(
        ["er_mixed_0", "er_mixed_1", "er_mixed_2"]
    )


# ─── list_active ────────────────────────────────────────────────────────────


async def test_list_active_returns_only_open_unexpired(
    store: EventRoomStore,
) -> None:
    """ROOM-01: list_active filters by status='open' AND expires_at>now."""
    open_room = await store.create(
        room_id="er_alive",
        tenant_id="t1",
        owner_principal="alice",
        ttl_seconds=3600,
    )
    short_room = await store.create(
        room_id="er_shortlist",
        tenant_id="t1",
        owner_principal="alice",
        ttl_seconds=1,
    )
    # Wait for the short room to expire, then sweep.
    future_ts = short_room.expires_at + 1
    await store.expire_stale_rooms(now=future_ts)

    active = await store.list_active()
    ids = sorted(r.room_id for r in active)
    assert ids == ["er_alive"]
    # Tenant filter.
    active_t1 = await store.list_active(tenant_id="t1")
    assert sorted(r.room_id for r in active_t1) == ["er_alive"]
    active_t2 = await store.list_active(tenant_id="t2")
    assert active_t2 == []


# ─── fan_out_event ──────────────────────────────────────────────────────────


async def test_fan_out_event_happy_path(store: EventRoomStore) -> None:
    """ROOM-03: fan_out_event appends to event_room_events; member allowed."""
    room = await store.create(
        room_id="er_fan",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_alice", "alice", caller_principal="alice"
    )
    seq = await store.fan_out_event(
        room_id=room.room_id,
        event_type=make_event_room_event_type("user_message"),
        payload={"content": "hello"},
        origin_session_id="sess_alice",
        principal="alice",
    )
    assert seq is not None and seq >= 1
    events = await store.list_room_events(room.room_id)
    assert len(events) == 1
    assert events[0]["event_type"].endswith("user_message")
    assert events[0]["payload"] == {"content": "hello"}


async def test_fan_out_event_principal_required(
    store: EventRoomStore,
) -> None:
    """ROUND 2 #2: principal is required (no default)."""
    room = await store.create(
        room_id="er_req_principal",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_alice", "alice", caller_principal="alice"
    )
    with pytest.raises(ValueError, match="principal must be"):
        await store.fan_out_event(
            room_id=room.room_id,
            event_type="governance.session.cross.user_message",
            payload={},
            origin_session_id="sess_alice",
            principal="",
        )


async def test_fan_out_event_rejects_non_member(
    store: EventRoomStore,
) -> None:
    """ROUND 1 #1: fan-out by non-member non-owner is dropped (returns None)."""
    room = await store.create(
        room_id="er_no_fan",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_alice", "alice", caller_principal="alice"
    )
    # Mallory is not a member and not the owner.
    seq = await store.fan_out_event(
        room_id=room.room_id,
        event_type=make_event_room_event_type("user_message"),
        payload={"content": "evil"},
        origin_session_id="sess_mallory",
        principal="mallory",
    )
    assert seq is None
    # No event was persisted.
    events = await store.list_room_events(room.room_id)
    assert events == []


async def test_fan_out_event_owner_can_emit_room_management(
    store: EventRoomStore,
) -> None:
    """ROOM-03: the owner can emit room-management events (special case)."""
    room = await store.create(
        room_id="er_owner_emit",
        tenant_id="t1",
        owner_principal="alice",
    )
    seq = await store.fan_out_event(
        room_id=room.room_id,
        event_type=make_event_room_event_type("room_announce"),
        payload={"announcement": "welcome"},
        origin_session_id="sess_alice",
        principal="alice",
    )
    assert seq is not None


async def test_fan_out_event_to_closed_room_dropped(
    store: EventRoomStore,
) -> None:
    """ROOM-03: fan-out into a closed/expired room is dropped."""
    room = await store.create(
        room_id="er_drop",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_alice", "alice", caller_principal="alice"
    )
    await store.close(room.room_id, "alice")
    seq = await store.fan_out_event(
        room_id=room.room_id,
        event_type=make_event_room_event_type("user_message"),
        payload={"content": "after-close"},
        origin_session_id="sess_alice",
        principal="alice",
    )
    assert seq is None
    events = await store.list_room_events(room.room_id)
    assert events == []


# ─── list_room_events clamping ──────────────────────────────────────────────


async def test_list_room_events_clamps_limit(
    store: EventRoomStore,
) -> None:
    """ROOM-03: limit is clamped to [1..500]."""
    room = await store.create(
        room_id="er_clamp",
        tenant_id="t1",
        owner_principal="alice",
    )
    await store.add_member(
        room.room_id, "sess_alice", "alice", caller_principal="alice"
    )
    for i in range(5):
        await store.fan_out_event(
            room_id=room.room_id,
            event_type=make_event_room_event_type("user_message"),
            payload={"i": i},
            origin_session_id="sess_alice",
            principal="alice",
        )
    # limit too small is ignored; 0/negative use the default 500.
    events = await store.list_room_events(room.room_id, limit=2)
    assert len(events) == 2
    # out-of-range to_seq raises
    with pytest.raises(ValueError, match="to_seq"):
        await store.list_room_events(room.room_id, from_seq=5, to_seq=2)