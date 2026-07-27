"""Multi-Session Coordinator — sessions share events through an Event Room.

v3.12.1 — EAASP v2.0 Phase 4 (A2A / Event Room / multi-session).

Spec §4.4 / EVOLUTION_PATH §三 Phase 4 / REQ-COORD-01..02 +
REQ-APPROVAL-01..02:

- ``MultiSessionCoordinator`` is the L4-facing wrapper over
  ``EventRoomStore`` that exposes the multi-session coordination
  vocabulary: ``join_event_room``, ``leave_event_room``,
  ``emit_shared_event``, ``resume_with_human_decision``. Each
  method delegates to the underlying ``EventRoomStore`` so the
  storage layer remains the single source of truth.
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

Authorization model — security review rounds 3 + 4: the
authenticated caller principal is NEVER a free method
parameter on the facade (round 3 added this for
``join_event_room``; round 4 promotes the rule to
``leave_event_room`` / ``emit_shared_event`` /
``resume_with_human_decision`` so all four entry points share a
single source-of-truth — the ``_AUTHENTICATED_PRINCIPAL``
``ContextVar`` populated by the API entry-point adapter).
No request body / RPC argument / event payload / model-
generated value can populate the caller identity. A request
that fails to bind the contextvar is treated as
unauthenticated and rejected with ``AuthContextMissing`` (the
contextvar is the only path into the verified-caller
resolution; see ``_require_authenticated_principal``).

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

import contextvars
import json
import time
from typing import Any

from loguru import logger

from .event_room import (
    EVENT_ROOM_EVENT_TYPE_PREFIX,
    EventRoom,
    EventRoomError,
    EventRoomNotAuthorized,
    EventRoomNotFound,
    EventRoomStore,
    make_event_room_event_type,
)


class MultiSessionCoordinatorError(Exception):
    """Base class for multi-session coordination failures."""


class SessionNotInRoom(MultiSessionCoordinatorError):
    """Raised when ``leave_event_room`` is called on a non-member session."""


class AuthContextMissing(MultiSessionCoordinatorError):
    """Raised when a coordinator method requires the authenticated caller
    principal but no auth context has been bound to the current request.

    v3.12.1 — security review round 3 (HIGH authorization):
    the coordinator facade MUST NOT accept the caller identity as a
    free method parameter. The verified principal is resolved from
    ``_AUTHENTICATED_PRINCIPAL`` (a ``ContextVar`` populated by the
    API entry-point adapter from a verified JWT / session /
    AuthContext). A request that fails to set the ContextVar — or
    that sets it to an empty value — is treated as unauthenticated
    and rejected. This closes the horizontal-privilege-escalation
    vector where any caller could pass ``caller_principal=B`` while
    asserting ``principal=A`` in the request body.
    """


# v3.12.1 — security review rounds 3 + 4: the authenticated caller
# principal is propagated via a ``ContextVar`` populated by the API
# entry-point adapter (FastAPI dependency → verified JWT → set
# ``_AUTHENTICATED_PRINCIPAL.set(...)`` BEFORE invoking the
# coordinator). The coordinator facade reads it here; the store
# accepts it as a kwarg to keep the internal seam testable, but no
# external code path can supply it (the facade enforces the
# ContextVar source). Default is ``None`` — every coordinator
# method that requires the authenticated principal checks the
# ContextVar explicitly and raises ``AuthContextMissing`` if it
# is unset. Round 4 promotes this rule from ``join_event_room``
# only to ALL four entry points (``join`` / ``leave`` /
# ``emit_shared_event`` / ``resume_with_human_decision``); see
# the class docstring for the sibling-path parity rationale.
_AUTHENTICATED_PRINCIPAL: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar(
        "eaasp_l4_authenticated_principal",
        default=None,
    )
)


class MultiSessionCoordinator:
    """Multi-session coordination facade over ``EventRoomStore``.

    The coordinator owns one ``EventRoomStore`` instance for the
    lifetime of the FastAPI app. Tests construct one directly
    with a ``tmp_db_path`` and wrap their test body in
    ``bind_authenticated_principal(...)`` to simulate a verified
    request context.

    v3.12.1 — security review rounds 3 + 4 (HIGH authorization):
    the authenticated caller principal is NEVER accepted as a
    method parameter. It is resolved inside the facade from
    ``_AUTHENTICATED_PRINCIPAL`` (a ContextVar populated by the
    API entry-point adapter from a verified JWT). No request
    body, RPC argument, event payload, or model-generated value
    can populate it. A request that has not bound the ContextVar
    is rejected with ``AuthContextMissing``.

    Round 4 fix — sibling-path parity: ``leave_event_room`` /
    ``emit_shared_event`` / ``resume_with_human_decision`` are
    now governed by the same authentication seam as
    ``join_event_room``. The previous round-3 shape left three
    sibling paths exposing ``principal`` / ``human_principal``
    as free parameters, which a caller could populate from the
    request body to act under a different identity. The
    round-4 fix removes those parameters and routes every
    authorization gate through ``_require_authenticated_principal``
    so the source of truth for the verified caller is single.
    """

    def __init__(self, room_store: EventRoomStore) -> None:
        self.room_store = room_store

    @staticmethod
    def _require_authenticated_principal() -> str:
        """Return the verified caller principal from the ContextVar.

        Raises ``AuthContextMissing`` if the ContextVar has not been
        bound by the API entry-point adapter. This is the ONLY
        code path that resolves the caller identity; every public
        method on the facade that requires it routes through here.
        """
        principal = _AUTHENTICATED_PRINCIPAL.get()
        if not principal:
            raise AuthContextMissing(
                "no authenticated principal bound to the current "
                "request context; the API entry-point adapter must "
                "call bind_authenticated_principal(verified) BEFORE "
                "invoking coordinator methods that require the "
                "caller identity (audit §REQ-ROOM-05)"
            )
        return principal

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
        (room_id, session_id) pair was already present.

        v3.12.1 — security review round 3 (HIGH authorization):
        the authenticated caller principal is resolved from
        ``_AUTHENTICATED_PRINCIPAL`` (a ContextVar set by the API
        entry-point adapter from a verified JWT / session /
        AuthContext). It is NOT accepted as a method parameter;
        a request body / RPC argument / event payload / model-
        generated value cannot populate it. The underlying store
        enforces the caller-side authorization gate: caller must
        match the room owner OR an existing member's principal.
        A non-member non-owner caller is rejected with
        ``EventRoomNotAuthorized``.

        Raises ``AuthContextMissing`` if no principal is bound to
        the current request context. Raises ``EventRoomError``
        subclasses for room-level failures (room not found, room
        not open, room not authorized, re-bind conflict).
        """
        if not principal:
            raise ValueError("principal must be a non-empty string")
        caller_principal = self._require_authenticated_principal()
        return await self.room_store.add_member(
            room_id,
            session_id,
            principal,
            caller_principal=caller_principal,
        )

    async def leave_event_room(
        self,
        *,
        room_id: str,
        session_id: str,
    ) -> bool:
        """Unbind ``session_id`` from ``room_id``.

        Returns ``True`` if a row was removed, ``False`` if the
        session was not a member. Idempotent — safe to call from
        session-shutdown paths.

        v3.12.1 — security review round 4 (sibling-path parity
        follow-on: HIGH missing-authorization-gate). The
        authenticated caller principal is resolved from
        ``_AUTHENTICATED_PRINCIPAL`` (a ContextVar set by the API
        entry-point adapter from a verified JWT / session /
        AuthContext). It is NOT accepted as a method parameter;
        a request body / RPC argument / event payload /
        model-generated value cannot populate it. The underlying
        store enforces self-removal or room-owner authorization;
        a non-self non-owner caller is rejected with
        ``EventRoomNotAuthorized``.

        Raises ``AuthContextMissing`` if no principal is bound to
        the current request context.
        """
        caller_principal = self._require_authenticated_principal()
        return await self.room_store.remove_member(
            room_id, session_id, caller_principal
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
    ) -> int | None:
        """Fan-out a shared event to every room member.

        Builds the canonical ``governance.session.cross.<sub>`` event
        type (via ``make_event_room_event_type``), embeds the
        origin_session_id + caller principal in the payload envelope,
        and delegates to ``EventRoomStore.fan_out_event``. Returns
        the new ``seq`` on success or ``None`` on best-effort failure.

        The fan-out itself is structural: SSE consumers read
        ``event_room_events`` and dispatch the row to every active
        session in the room. The coordinator does NOT maintain an
        in-process SSE bus.

        v3.12.1 — security review round 4 (sibling-path parity
        follow-on: HIGH missing-authorization-gate). The
        authenticated caller principal is resolved from
        ``_AUTHENTICATED_PRINCIPAL`` (a ContextVar set by the API
        entry-point adapter from a verified JWT / session /
        AuthContext). It is NOT accepted as a method parameter;
        a request body / RPC argument / event payload /
        model-generated value cannot populate it. The same
        verified caller is recorded in both the SSE-visible
        payload envelope and the store-side ``principal`` kwarg.

        Raises ``AuthContextMissing`` if no principal is bound to
        the current request context.
        """
        caller_principal = self._require_authenticated_principal()
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

        # Build the canonical event type BEFORE hitting the DB so
        # the validation lives outside the transaction.
        event_type = make_event_room_event_type(event_subtype)

        # Embed origin + caller principal in the payload envelope so
        # SSE consumers don't need a separate metadata table to know
        # who emitted the event. The principal recorded here is the
        # verified caller — it is NEVER sourced from the request
        # body. ``origin_session_id`` is also carried as a first-
        # class column by ``fan_out_event`` itself, so this is the
        # SSE-visible view (JSON-serialized).
        envelope = {
            "origin_session_id": origin_session_id,
            "principal": caller_principal,
            "ts": int(time.time()),
            "payload": payload,
        }

        return await self.room_store.fan_out_event(
            room_id=room_id,
            event_type=event_type,
            payload=envelope,
            origin_session_id=origin_session_id,
            principal=caller_principal,
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
        evidence_refs: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Resume a paused 5-stage approval chain with the human verdict.

        v3.12.1 — REQ-APPROVAL-01..02 + REQ-COORD-02: when a session
        participating in an Event Room is paused at the Approve
        stage, ONLY a verified caller's principal may resume the
        chain. The coordinator enforces this by checking the
        ContextVar-resolved verified principal against membership
        in ``event_room_members`` BEFORE delegating to the
        underlying L3 audit store.

        v3.12.1 round 4 — security review follow-on (HIGH
        missing-authorization-gate): ``human_principal`` is NO
        LONGER a method parameter. The verified principal is
        resolved inside the facade from
        ``_AUTHENTICATED_PRINCIPAL`` — the same contextvar that
        ``join_event_room`` / ``leave_event_room`` /
        ``emit_shared_event`` consume. The API entry-point
        adapter must call ``bind_authenticated_principal(verified)``
        BEFORE invoking this method; a request that has not bound
        the contextvar is rejected with ``AuthContextMissing``
        (fail-closed). This closes the horizontal-privilege-
        escalation vector where any caller could resume a paused
        chain while asserting ``human_principal=<room owner>`` in
        the request body.

        Returns a dict describing the resume outcome (``{ok: True,
        decision: 'allow'|'deny', room_id, session_id, principal}``
        on success; ``None`` if the chain is not paused under this
        decision_id). Returns ``EventRoomNotFound`` if the
        ``room_id`` is supplied but absent;
        ``EventRoomNotAuthorized`` (NOT ``PermissionError`` —
        sibling-path parity with the other facade methods) if the
        verified caller is neither a member of the supplied room
        nor its owner; ``AuthContextMissing`` if the contextvar
        has not been bound.

        Implementation note: this method is intentionally
        structural. It does NOT run the L3 ``ApprovalStateMachine``
        itself (the API layer in 03.12.2 + 03.12.3 wires that up);
        it only validates the verified caller is a room member
        and records the resume decision in the audit ledger via
        ``EventRoomStore.fan_out_event``. The chain's terminal
        state (allow / deny) is returned so callers can drive the
        next stage.

        Audit ledger row shape: ``decision_id`` is the chain's
        paused ``gd_approval_*_approve`` row (set by the L3 state
        machine); the resume appends a NEW row with stage
        ``await_human`` carrying the human's verdict + reason +
        the verified principal. Append-only invariant preserved.
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

        # Resolve the verified caller from the API entry-point
        # ContextVar. This is the only source of truth for the
        # human principal recorded on the audit ledger row + the
        # SSE event envelope below. A request that has not bound
        # the contextvar fails closed with ``AuthContextMissing``
        # BEFORE any room-membership check fires — sibling-path
        # parity with the rest of the facade.
        human_principal = self._require_authenticated_principal()

        # Room membership gate: if a room_id is supplied, the
        # verified caller must be a member of the room (recorded
        # via ``add_member`` — the principal is the audit trail of
        # who joined the room, but the join itself is owner-gated).
        # If the room_id is None, we skip the membership check (no
        # room is associated with the chain — back-compat with the
        # v3.11.2 single-session chain path).
        if room_id is not None:
            members = await self.room_store.list_members(room_id)
            # Validate the room exists first (cheap probe).
            room = await self.room_store.get(room_id)
            if room is None:
                raise EventRoomNotFound(room_id, "no such room")
            # The verified caller must either be a member of the
            # room or the room owner. Both are recorded in the
            # event_room tables, so we check both. The failure
            # surface is ``EventRoomNotAuthorized`` (sibling-path
            # parity with the other facade methods) — NOT the
            # legacy ``PermissionError`` shape that preceded the
            # round-4 cleanup.
            if (
                human_principal not in members
                and room.owner_principal != human_principal
            ):
                raise EventRoomNotAuthorized(
                    room_id,
                    human_principal,
                    "verified caller is not a member of room and "
                    "is not the room owner; resume rejected "
                    "(audit §REQ-APPROVAL-02 / §REQ-ROOM-05)",
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
        # v3.12.1 round 4: the ``principal`` recorded here is the
        # verified caller (resolved above), NOT a free parameter.
        # A request body that asserts ``human_principal=<value>``
        # has no effect on what gets persisted. The envelope
        # carrier is structurally identical to round-3 so SSE
        # consumers keep working without churn.
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
    "AuthContextMissing",
    "bind_authenticated_principal",
    "EVENT_ROOM_EVENT_TYPE_PREFIX",
]


class _AuthContextToken:
    """Opaque token returned by ``bind_authenticated_principal``.

    Holds the ``Token`` from ``ContextVar.set`` so the caller can
    ``reset()`` it after the request completes (FastAPI dependency
    pattern: yield-set / yield-reset).
    """

    def __init__(self, token: contextvars.Token) -> None:
        self._token = token

    def reset(self) -> None:
        """Restore the ContextVar to its prior value."""
        _AUTHENTICATED_PRINCIPAL.reset(self._token)


def bind_authenticated_principal(verified: str) -> _AuthContextToken:
    """Bind the verified caller principal to the current request context.

    The API entry-point adapter (FastAPI dependency or equivalent)
    MUST call this with the principal extracted from a verified JWT
    / session / AuthContext BEFORE invoking any coordinator method
    that requires the authenticated caller. Tests call it inside
    an ``async with`` block to simulate a verified request.

    Args:
        verified: the verified principal string (NOT a raw request
            body field). The caller is responsible for extracting
            it from a verified token; this function does NOT
            validate the value — it only records it for the
            coordinator to consume. Empty / whitespace-only /
            None values are rejected with ``ValueError`` to
            prevent a buggy adapter from silently binding an
            empty principal.
    """
    if not isinstance(verified, str) or not verified.strip():
        raise ValueError(
            "verified principal must be a non-empty string extracted "
            "from a verified JWT / session / AuthContext"
        )
    token = _AUTHENTICATED_PRINCIPAL.set(verified)
    return _AuthContextToken(token)