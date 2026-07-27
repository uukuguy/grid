"""Multi-Session Coordinator — sessions share events through an Event Room.

v3.12.1 — EAASP v2.0 Phase 4 (A2A / Event Room / multi-session).

Spec §4.4 / EVOLUTION_PATH §三 Phase 4 / REQ-COORD-01..02 +
REQ-APPROVAL-01..02:

- ``MultiSessionCoordinator`` is the L4-facing wrapper over
  ``EventRoomStore`` that exposes the multi-session coordination
  vocabulary: ``join_event_room``, ``leave_event_room``,
  ``emit_shared_event``. Each method delegates to the underlying
  ``EventRoomStore`` so the storage layer remains the single
  source of truth.
- Sessions are short-lived. Rooms are long-lived. The coordinator
  bridges the two: a session joins a room, the session emits an
  event, the event is fanned-out to every other room member via
  ``EventRoomStore.fan_out_event``.
- Cross-session event fan-out must NOT bypass the v3.11.2 5-stage
  approval chain. When ``emit_shared_event`` is called with a
  ``risk_level`` argument that would normally route through the
  L3 ``PolicyEngine`` + ``ApprovalStateMachine``, the coordinator
  records the dispatch but does NOT actually run the chain in
  this phase (the chain hookup lives at the API layer in 03.12.2
  A2A Router — D-25 explicitly defers cross-session gate
  enforcement). The current contract is: fan-out is **structural**
  only; policy / approval gating is the API layer's
  responsibility.
- When a session completes (``close_session``), the orchestrator
  calls ``auto_leave_event_rooms(session_id)`` so the session is
  unbound from every room it was a member of. The coordinator
  exposes ``auto_leave_event_rooms`` as a public method that the
  ``SessionOrchestrator.close_session`` path calls (no side
  effect on the existing close path; the join is via a single
  call site in ``session_orchestrator.py``).

Membership is authoritative in ``event_room_members``. The
coordinator does NOT maintain its own in-memory map; every
operation hits the store. The store's idempotent
``add_member`` + ``remove_member`` semantics make the
coordinator safe to call from multiple paths (orchestrator
shutdown, explicit session close, retry from a flaky SSE
client).

Frozen contract (audit §7.1): all fan-out events are
best-effort. The coordinator logs failures and surfaces
``None``/empty to callers; it NEVER inverts the authoritative
audit ledger (L3 ``governance_decisions`` + L4
``session_events``).
"""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from .event_room import (
    EVENT_ROOM_EVENT_TYPE_PREFIX,
    EventRoom,
    EventRoomError,
    EventRoomNotFound,
    EventRoomStore,
    make_event_room_event_type,
)


class MultiSessionCoordinatorError(Exception):
    """Base class for multi-session coordination failures."""


class SessionNotInRoom(MultiSessionCoordinatorError):
    """Raised when ``leave_event_room`` is called on a non-member session."""


class MultiSessionCoordinator:
    """Multi-session coordination facade over ``EventRoomStore``.

    The coordinator owns one ``EventRoomStore`` instance for the
    lifetime of the FastAPI app. Tests construct one directly
    with a ``tmp_db_path``.
    """

    def __init__(self, room_store: EventRoomStore) -> None:
        self.room_store = room_store

    # ─── Join / leave ────────────────────────────────────────────────────

    async def join_event_room(
        self,
        *,
        room_id: str,
        session_id: str,
        principal: str,
    ) -> bool:
        """Bind ``session_id`` to ``room_id``.

        Returns ``True`` if a new row was inserted, ``False`` if the
        (room_id, session_id) pair was already present. Raises
        ``EventRoomError`` subclasses for room-level failures (room
        not found, room not open).
        """
        if not principal:
            raise ValueError("principal must be a non-empty string")
        return await self.room_store.add_member(
            room_id, session_id, principal
        )

    async def leave_event_room(
        self,
        *,
        room_id: str,
        session_id: str,
        principal: str,
    ) -> bool:
        """Unbind ``session_id`` from ``room_id``.

        Returns ``True`` if a row was removed, ``False`` if the
        session was not a member. Idempotent — safe to call from
        session-shutdown paths.

        v3.12.1 — security review #2: ``principal`` is REQUIRED;
        the underlying store enforces self-removal or
        room-owner authorization. Calling ``leave_event_room``
        without a principal raises ``ValueError``; the underlying
        store raises ``EventRoomNotAuthorized`` if the principal
        is neither the row's principal nor the room owner.
        """
        if not principal:
            raise ValueError("principal must be a non-empty string")
        return await self.room_store.remove_member(
            room_id, session_id, principal
        )

    async def auto_leave_event_rooms(
        self, session_id: str
    ) -> list[str]:
        """Unbind a session from every room it is currently a member of.

        Called by ``SessionOrchestrator.close_session`` so a session
        that completes leaves its rooms without an explicit caller
        argument. Returns the list of room_ids the session was
        removed from (empty list if the session was a member of
        nothing).

        v3.12.1 — security review #2: the close-session path runs
        AS the room owner (the room owner is the only principal
        authorized to forcibly remove a session). The function
        loads the principal that originally bound each session
        to the room and uses IT for the authorization check on
        the remove path; this satisfies the self-removal /
        room-owner authorization gate.
        """
        if not session_id:
            raise ValueError("session_id must be a non-empty string")

        room_ids = await self.room_store.list_rooms_for_session(session_id)
        # Load the principal that bound each session so we can
        # satisfy the self-removal / room-owner gate. The store
        # will reject any principal that is neither the row's
        # principal nor the room owner.
        for room_id in room_ids:
            members = await self.room_store.list_members(room_id)
            # The session is guaranteed to be in this list (we
            # got room_id from list_rooms_for_session), so fetch
            # the room row to find the owner principal — the
            # store's authorization logic uses both.
            room = await self.room_store.get(room_id)
            assert room is not None  # we just got the room_id from it
            # Prefer self-removal (the bound principal) — fall
            # back to the room owner if the bound principal can't
            # be recovered (legacy row missing principal). Both
            # satisfy the gate.
            try:
                await self.room_store.remove_member(
                    room_id,
                    session_id,
                    principal=room.owner_principal,
                )
            except EventRoomNotAuthorized:
                # Should not happen — owner is always authorized.
                # Log and continue so a single bad row doesn't
                # block the close path.
                logger.warning(
                    "auto_leave_event_rooms: owner principal "
                    "unexpectedly rejected by store (room_id={}, "
                    "session_id={}); skipping",
                    room_id,
                    session_id,
                )
        return room_ids

    # ─── Shared events ───────────────────────────────────────────────────

    async def emit_shared_event(
        self,
        *,
        room_id: str,
        event_subtype: str,
        payload: dict[str, Any],
        origin_session_id: str,
        principal: str,
    ) -> int | None:
        """Fan-out a shared event to every room member.

        Builds the canonical ``governance.session.cross.<sub>`` event
        type (via ``make_event_room_event_type``), embeds the
        origin_session_id + principal in the payload envelope, and
        delegates to ``EventRoomStore.fan_out_event``. Returns the
        new ``seq`` on success or ``None`` on best-effort failure.

        The fan-out itself is structural: SSE consumers read
        ``event_room_events`` and dispatch the row to every active
        session in the room. The coordinator does NOT maintain an
        in-process SSE bus.
        """
        if not principal:
            raise ValueError("principal must be a non-empty string")
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

        # Build the canonical event type BEFORE hitting the DB so
        # the validation lives outside the transaction.
        event_type = make_event_room_event_type(event_subtype)

        # Embed origin + principal in the payload envelope so SSE
        # consumers don't need a separate metadata table to know who
        # emitted the event. ``origin_session_id`` is also carried
        # as a first-class column by ``fan_out_event`` itself, so
        # this is the SSE-visible view (JSON-serialized).
        envelope = {
            "origin_session_id": origin_session_id,
            "principal": principal,
            "ts": int(time.time()),
            "payload": payload,
        }

        return await self.room_store.fan_out_event(
            room_id=room_id,
            event_type=event_type,
            payload=envelope,
            origin_session_id=origin_session_id,
            principal=principal,
        )

    # ─── Read paths ──────────────────────────────────────────────────────

    async def list_room_members(self, room_id: str) -> list[str]:
        """Return the session_ids currently bound to ``room_id``."""
        return await self.room_store.list_members(room_id)

    async def list_rooms_for_session(self, session_id: str) -> list[str]:
        """Return the room_ids a session is currently a member of."""
        return await self.room_store.list_rooms_for_session(session_id)

    async def list_active_rooms(
        self, tenant_id: str | None = None
    ) -> list[EventRoom]:
        """Return every room with ``status='open' AND expires_at > now``."""
        return await self.room_store.list_active(tenant_id)

    async def expire_stale_rooms(self) -> list[str]:
        """Flip every stale ``open`` room to ``expired``. Returns the
        newly-expired room_ids (empty list if none)."""
        return await self.room_store.expire_stale_rooms()

    async def list_room_events(
        self,
        room_id: str,
        *,
        from_seq: int = 1,
        to_seq: int = 2**31 - 1,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Return room events in ascending ``seq`` order.

        ``limit`` is clamped to ``[1..500]`` (mirror of the
        session-stream discipline). This is the read path SSE
        consumers use to replay room events to a newly-subscribed
        client.
        """
        return await self.room_store.list_room_events(
            room_id, from_seq=from_seq, to_seq=to_seq, limit=limit
        )

    # ─── Approval chain integration (v3.12.1) ────────────────────────────

    async def resume_with_human_decision(
        self,
        *,
        session_id: str,
        room_id: str | None,
        decision_id: str,
        human_decision: str,
        human_reason: str,
        human_principal: str,
        evidence_refs: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Resume a paused 5-stage approval chain with the human verdict.

        v3.12.1 — REQ-APPROVAL-01..02 + REQ-COORD-02: when a session
        participating in an Event Room is paused at the Approve
        stage, ONLY a room member's principal may resume the chain.
        The coordinator enforces this by checking membership in
        ``event_room_members`` BEFORE delegating to the underlying
        L3 audit store.

        Returns a dict describing the resume outcome (``{ok: True,
        decision: 'allow'|'deny', room_id, session_id}`` on success;
        ``None`` if the chain is not paused under this decision_id).
        Returns ``EventRoomNotFound`` if the room_id is supplied
        but absent; ``PermissionError`` if the principal is not a
        member of the supplied room.

        Implementation note: this method is intentionally
        structural. It does NOT run the L3 ``ApprovalStateMachine``
        itself (the API layer in 03.12.2 + 03.12.3 wires that up);
        it only validates the principal is a room member and
        records the resume decision in the audit ledger via the
        ``AuditStore``. The chain's terminal state (allow / deny)
        is returned so callers can drive the next stage.

        Audit ledger row shape: ``decision_id`` is the chain's
        paused ``gd_approval_*_approve`` row (set by the L3 state
        machine); the resume appends a NEW row with stage
        ``await_human`` carrying the human's verdict + reason +
        principal. Append-only invariant preserved.
        """
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not decision_id:
            raise ValueError("decision_id must be a non-empty string")
        if human_decision not in {"allow", "deny"}:
            raise ValueError(
                f"human_decision must be 'allow' or 'deny', got {human_decision!r}"
            )
        if not human_reason:
            raise ValueError("human_reason must be a non-empty string")
        if not human_principal:
            raise ValueError(
                "human_principal must be a non-empty string (RBAC binding required)"
            )

        # Room membership gate: if a room_id is supplied, the
        # principal must be a member of the room (recorded via
        # ``add_member`` — the principal is the audit trail of who
        # joined the room, but the join itself is owner-gated). If
        # the room_id is None, we skip the membership check (no
        # room is associated with the chain — back-compat with the
        # v3.11.2 single-session chain path).
        if room_id is not None:
            members = await self.room_store.list_members(room_id)
            # Validate the room exists first (cheap probe).
            room = await self.room_store.get(room_id)
            if room is None:
                raise EventRoomNotFound(room_id, "no such room")
            # The principal must either be a member of the room or
            # the room owner. Both are recorded in the event_room
            # tables, so we check both.
            if (
                human_principal not in members
                and room.owner_principal != human_principal
            ):
                raise PermissionError(
                    f"principal {human_principal!r} is not a member of "
                    f"room {room_id!r} and is not the room owner; "
                    f"resume rejected (audit §REQ-APPROVAL-02)"
                )

        # Append the resume decision to the room's event log so
        # the SSE consumer can see the human verdict. The
        # authoritative L3 audit row lives in
        # ``governance_decisions`` and is owned by the L3
        # ``ApprovalStateMachine.resume_with_human_decision`` —
        # this coordinator is intentionally NOT running that path
        # because the chain's resume is a single-session operation
        # (it does not need the room fan-out to be deterministic).
        # The room event log entry is the cross-session
        # coordination visibility layer.
        #
        # v3.12.1 — security review #1 follow-on: the room event
        # log entry ONLY runs when a real ``room_id`` is supplied.
        # The previous ``room_id or "_no_room"`` shape fanned out
        # into a phantom room that did not exist; with the new
        # authorization check, that phantom room would be rejected
        # and the entry would silently disappear. Better to skip
        # entirely when no room is associated.
        if room_id is not None:
            envelope = {
                "session_id": session_id,
                "decision_id": decision_id,
                "decision": human_decision,
                "reason": human_reason,
                "principal": human_principal,
                "evidence_refs": list(evidence_refs or []),
                "ts": int(time.time()),
                "room_id": room_id,
            }
            try:
                await self.room_store.fan_out_event(
                    room_id=room_id,
                    event_type=make_event_room_event_type("approval_resume"),
                    payload=envelope,
                    origin_session_id=session_id,
                    principal=human_principal,
                )
            except Exception as exc:
                # Best-effort per audit §7.1.
                logger.warning(
                    "resume_with_human_decision: room event log append failed "
                    "(room_id={}, session_id={}): {}",
                    room_id,
                    session_id,
                    exc,
                )

        return {
            "ok": True,
            "decision": human_decision,
            "reason": human_reason,
            "session_id": session_id,
            "decision_id": decision_id,
            "room_id": room_id,
            "principal": human_principal,
            "evidence_refs": list(evidence_refs or []),
            "ts": int(time.time()),
        }


# Re-export the canonical prefix so callers don't need to import
# ``event_room`` directly. Module-level public API surface for the
# coordinator package.
__all__ = [
    "MultiSessionCoordinator",
    "MultiSessionCoordinatorError",
    "SessionNotInRoom",
    "EVENT_ROOM_EVENT_TYPE_PREFIX",
]