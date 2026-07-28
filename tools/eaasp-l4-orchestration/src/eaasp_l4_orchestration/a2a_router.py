"""A2A Router — session-to-session coordination protocol layer.

v3.12.2 — EAASP v2.0 Phase 4 (A2A Router + Event Room + multi-session
coordination). Spec §14 / ADR-V2-024 (engine 接入面) / ADR-V2-035
(conflict-detection algorithm).

The A2A Router is the L4 protocol layer that lets two or more
sessions (in the same Event Room) coordinate by exchanging typed
A2A messages through the room's append-only event log. It is the
*coordination* surface; the L3 ``ApprovalStateMachine`` is the
*authorization* surface — the router is purely structural and
NEVER inverts an authoritative L3 decision.

Construction (v3.12.2 — REQ-A2A-01..03):

- ``A2ARouter`` is constructed with three dependencies:
  - ``room_store`` (v3.12.1 ``EventRoomStore``) — the
    authoritative storage layer for rooms + members + room event
    log. The router delegates membership checks + fan-out to it.
  - ``coordinator`` (v3.12.1 ``MultiSessionCoordinator``) — the
    facade the API layer uses to resolve the verified caller
    principal (via ``_AUTHENTICATED_PRINCIPAL`` ContextVar). The
    router reads the same ContextVar so a hostile caller cannot
    inject ``source_principal`` from the request body.
  - ``risk_classifier`` — an OPTIONAL dependency on the L3 risk
    classification surface (``PolicyEngine.evaluate_gate`` or
    equivalent). The router uses it to record the
    ``RiskMetadata`` envelope on the room event so SSE consumers
    can dispatch inbound A2A to the L3 ``PolicyEngine`` for the
    gated path. ``None`` is acceptable for tests + structural-only
    deployments (REQ-A2A-03 / D-25 defers the L3 hookup to 03.12.3).

Routing model (v3.12.2 — REQ-A2A-02):

- ``route_message(room_id, source_session_id, envelope)`` fans out
  the canonical envelope to every ``target_session_ids`` member
  of the room. The router authorizes the source principal
  (verified via ContextVar vs. envelope.source_principal parity)
  and validates every target is a current room member under the
  supplied ``target_principals``. On success, the router records
  ONE row in ``event_room_events`` with event_type
  ``a2a.request.sent`` and returns the new seq.
- ``request_review(room_id, initiator_session_id,
  reviewer_session_ids, payload)`` creates a fresh ``ReviewSet``
  and fans out review requests to each reviewer. Each reviewer
  receives an ``a2a.request.sent`` event with ``payload_kind =
  review_request``; their submissions are routed back via
  ``route_review_submission``. The router records the
  ``ReviewSet`` in the in-memory ``self.review_sets`` dict keyed
  on ``set_id``; the aggregation engine runs on demand via
  ``aggregate_review_set`` / ``close_review_set``.
- ``route_review_submission(set_id, review)`` records the
  reviewer's decision in the ``ReviewSet`` + emits an
  ``a2a.review.submitted`` room event. Refuses submissions to
  closed / expired sets and from non-reviewer sessions.
- ``aggregate_review_set(set_id)`` runs the aggregation engine
  and returns the ``AggregationResult``. If the result has
  ``conflict_detected``, the router also emits an
  ``a2a.conflict.detected`` room event.
- ``close_review_set(set_id)`` runs aggregation + emits
  ``a2a.review.closed`` (or ``a2a.conflict.detected`` when
  conflict was detected) and flips the set's status to closed.

Frozen contract (audit §7.1): the router is best-effort. Every
fan-out / aggregation call wraps the underlying store call in a
try/except and logs failures. Per the v3.12.1 fan-out contract,
failures NEVER inverts an authoritative audit decision; they
surface as ``None`` to the caller.

SSE events emitted (v3.12.2 — REQ-SSE-01..05):

- ``a2a.request.sent`` — every room-scoped A2A message (route +
  review_request).
- ``a2a.request.acknowledged`` — emitted when a reviewer
  acknowledges receipt (currently structural: emitted alongside
  the ``a2a.request.sent`` for review requests; future phases
  can extend to a real ack handshake).
- ``a2a.review.submitted`` — emitted per reviewer submission.
- ``a2a.review.closed`` — emitted when the ReviewSet closes.
- ``a2a.conflict.detected`` — emitted when the aggregation engine
  detects contradictory decisions on shared evidence.
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol

from loguru import logger

from .a2a_protocol import (
    A2A_CONFLICT_DETECTED,
    A2A_EVENT_TYPES,
    A2A_KIND_GENERIC,
    A2A_KIND_REVIEW_REQUEST,
    A2A_KIND_REVIEW_RESPONSE,
    A2A_REVIEW_CLOSED,
    A2A_REVIEW_SUBMITTED,
    A2A_REQUEST_ACKNOWLEDGED,
    A2A_REQUEST_SENT,
    A2AMessageEnvelope,
    RiskMetadata,
    make_a2a_event_type,
)
from .event_room import (
    EVENT_ROOM_EVENT_TYPE_PREFIX,
    EventRoomNotAuthorized,
    EventRoomNotFound,
    EventRoomStore,
    make_event_room_event_type,
)
from .review_set import (
    AGGREGATE_ESCALATE,
    AggregationResult,
    Review,
    ReviewSet,
    ReviewSetClosed,
    ReviewSetError,
    ReviewSetExpired,
    ReviewerNotExpected,
    make_review_set_id,
)
from .session_orchestrator_room import (
    AuthContextMissing,
    MultiSessionCoordinator,
    _AUTHENTICATED_PRINCIPAL,
)


# ─── L3 risk classifier interface (v3.12.2 — REQ-A2A-03) ─────────────────────
#
# The router records the L3 ``RiskMetadata`` envelope on the room
# event so SSE consumers can dispatch inbound A2A to the L3
# ``PolicyEngine`` for the gated path. The router itself does NOT
# invoke L3; the L3 hookup lives at the API layer per the v3.12.2
# plan (D-25 defers cross-session gate enforcement). The protocol
# is declared here so a future deployment can wire
# ``L3RiskClassifier.evaluate(actor, action, context)`` without
# changing the router's public surface.
class L3RiskClassifier(Protocol):
    """L3 risk-classification dependency (structural — optional).

    The router does NOT call any method on this protocol in
    v3.12.2; it merely stores a reference so the API layer can
    pull it from the router for the gated path. Implementations
    typically wrap ``PolicyEngine.evaluate_gate`` or a
    ``RiskClassifier.classify`` helper.

    The presence of this attribute on the router is the API
    layer's signal that an L3-classifier-aware deployment is in
    use; the attribute is None for structural-only deployments
    and tests.
    """

    def classify(
        self,
        *,
        actor: str,
        action: str,
        context: dict[str, Any],
    ) -> str:
        """Return a risk_level (``read`` / ``write_local`` /
        ``write_external``) for the (actor, action, context)
        triple. The router does NOT call this in v3.12.2; the
        API layer may invoke it during request_review to set
        the ``RiskMetadata`` envelope before fan-out."""
        ...


class A2ARouterError(Exception):
    """Base class for A2A Router failures."""


class A2AMessageNotAccepted(A2ARouterError):
    """Raised when the router refuses to fan out a message.

    Causes: room not found, source principal mismatch with the
    ContextVar, target session not a current room member,
    room not open, etc.
    """

    def __init__(self, message_id: str, detail: str) -> None:
        self.message_id = message_id
        super().__init__(
            f"a2a message {message_id!r} not accepted: {detail}"
        )


class A2ARouter:
    """A2A Router facade — coordinates sessions through Event Room.

    Construction takes the v3.12.1 ``EventRoomStore`` (authoritative
    storage) + the v3.12.1 ``MultiSessionCoordinator`` facade (which
    owns the ``_AUTHENTICATED_PRINCIPAL`` ContextVar) + an OPTIONAL
    ``L3RiskClassifier``. The router is purely structural; the
    authoritative L3 ``governance_decisions`` ledger + the L4
    ``event_room_events`` log are NEVER inverted by the router.
    """

    def __init__(
        self,
        room_store: EventRoomStore,
        coordinator: MultiSessionCoordinator,
        risk_classifier: L3RiskClassifier | None = None,
    ) -> None:
        self.room_store = room_store
        self.coordinator = coordinator
        self.risk_classifier = risk_classifier
        # In-memory registry of ReviewSets created via
        # ``request_review``. Keyed on ``set_id``. The authoritative
        # audit trail lives in ``event_room_events`` (a2a.* events);
        # this dict is the in-process bookkeeping that drives the
        # aggregation engine. Per audit §7.1, losing this dict
        # (e.g. process restart) does NOT inverts any audit
        # decision — the SSE consumer can still replay the
        # ``a2a.review.submitted`` events to rebuild the set.
        self.review_sets: dict[str, ReviewSet] = {}

    # ─── Verified-caller resolution ────────────────────────────────────────

    @staticmethod
    def _require_authenticated_principal() -> str:
        """Resolve the verified caller principal from the ContextVar.

        Sibling-path parity with the v3.12.1
        ``MultiSessionCoordinator._require_authenticated_principal``:
        the principal is NEVER accepted as a method parameter. It
        is resolved inside the router from the same ContextVar
        that ``join_event_room`` / ``emit_shared_event`` /
        ``resume_with_human_decision`` consume. A request that
        has not bound the ContextVar is rejected with
        ``AuthContextMissing`` (fail-closed).
        """
        principal = _AUTHENTICATED_PRINCIPAL.get()
        if not principal:
            raise AuthContextMissing(
                "no authenticated principal bound to the current "
                "request context; the API entry-point adapter must "
                "call bind_authenticated_principal(verified) BEFORE "
                "invoking A2ARouter methods (audit §REQ-A2A-02)"
            )
        return principal

    # ─── Authorize envelope ────────────────────────────────────────────────

    async def _authorize_envelope(
        self, envelope: A2AMessageEnvelope
    ) -> str:
        """Validate the envelope and return the verified caller principal.

        Authorization chain (v3.12.2 — REQ-A2A-02):

        1. Resolve the verified caller principal from the
           ContextVar (``_AUTHENTICATED_PRINCIPAL``). Fail closed
           with ``AuthContextMissing`` if not bound.
        2. Verify ``envelope.source_principal`` matches the
           ContextVar principal. This closes the horizontal-
           privilege-escalation vector where a caller could
           populate ``source_principal`` from the request body
           while the ContextVar is bound to a different principal.
        3. Probe the room via ``EventRoomStore.get(room_id)`` so
           the room must exist + be ``open``. ``EventRoomNotFound``
           or ``EventRoomNotOpen`` surfaces as
           ``A2AMessageNotAccepted`` with a stable reason.
        4. Verify the source session is a current member of the
           room under the verified caller principal via the
           v3.12.1 ``is_session_in_room`` probe + a
           principal-binding probe. Reject with
           ``A2AMessageNotAccepted`` if either probe fails.
        5. Verify every (target_session_id, target_principal)
           pair is a current room member via the same probe +
           a principal-binding probe. Reject with
           ``A2AMessageNotAccepted`` if any pair fails. The
           router deliberately does NOT trust the request-body
           ``target_principals`` — the store's authoritative
           principal column is the single source of truth.

        Returns the verified principal (== ``envelope.source_principal``
        after the parity check) on success.
        """
        caller_principal = self._require_authenticated_principal()

        # Parity check.
        if envelope.source_principal != caller_principal:
            raise A2AMessageNotAccepted(
                envelope.message_id,
                f"envelope.source_principal {envelope.source_principal!r} "
                f"disagrees with verified caller principal "
                f"{caller_principal!r}; refusing to honor the "
                f"envelope (audit §REQ-A2A-02)",
            )

        room = await self.room_store.get(envelope.room_id)
        if room is None:
            raise A2AMessageNotAccepted(
                envelope.message_id,
                f"room {envelope.room_id!r} does not exist",
            )
        if not room.is_open():
            raise A2AMessageNotAccepted(
                envelope.message_id,
                f"room {envelope.room_id!r} is not open "
                f"(status={room.status!r})",
            )

        # Source session probe.
        if not await self.room_store.is_session_in_room(
            envelope.room_id, envelope.source_session_id
        ):
            raise A2AMessageNotAccepted(
                envelope.message_id,
                f"source session {envelope.source_session_id!r} is "
                f"not a member of room {envelope.room_id!r}",
            )

        # Source principal probe: the (room_id, session_id) row's
        # principal must match the verified caller. This stops
        # alice from sending a message under bob's identity from
        # bob's session (a principal-spoof attempt that survives
        # the parity check above).
        db_path = self.room_store.db_path
        from .db import connect as _connect

        db = await _connect(db_path)
        try:
            cur = await db.execute(
                """
                SELECT principal FROM event_room_members
                 WHERE room_id = ? AND session_id = ?
                """,
                (envelope.room_id, envelope.source_session_id),
            )
            row = await cur.fetchone()
        finally:
            await db.close()

        if row is None or row["principal"] != caller_principal:
            raise A2AMessageNotAccepted(
                envelope.message_id,
                f"source session {envelope.source_session_id!r} is "
                f"not bound under the verified caller principal "
                f"{caller_principal!r} in room "
                f"{envelope.room_id!r}",
            )

        # Target probe — every (target_session_id, target_principal)
        # pair must be a current member under the stated principal.
        for target_sid, target_principal in envelope.matched_target_pairs():
            if not await self.room_store.is_session_in_room(
                envelope.room_id, target_sid
            ):
                raise A2AMessageNotAccepted(
                    envelope.message_id,
                    f"target session {target_sid!r} is not a "
                    f"member of room {envelope.room_id!r}",
                )

            db = await _connect(db_path)
            try:
                cur = await db.execute(
                    """
                    SELECT principal FROM event_room_members
                     WHERE room_id = ? AND session_id = ?
                    """,
                    (envelope.room_id, target_sid),
                )
                row = await cur.fetchone()
            finally:
                await db.close()

            if row is None or row["principal"] != target_principal:
                raise A2AMessageNotAccepted(
                    envelope.message_id,
                    f"target session {target_sid!r} is not bound "
                    f"under principal {target_principal!r} in room "
                    f"{envelope.room_id!r}",
                )

        return caller_principal

    # ─── Public: route a single A2A message ─────────────────────────────────

    async def route_message(
        self, envelope: A2AMessageEnvelope
    ) -> int | None:
        """Fan-out a single A2A message to its target sessions.

        Validates the envelope + authorizes the source + probes
        every target session before delegating to
        ``EventRoomStore.fan_out_event``. Records ONE row in
        ``event_room_events`` with event_type ``a2a.request.sent``
        (or ``a2a.request.acknowledged`` for review_request
        acknowledgements).

        Returns the new ``seq`` on success, ``None`` on
        best-effort failure (per audit §7.1).
        """
        caller_principal = await self._authorize_envelope(envelope)

        # Embed source / target info + risk metadata + envelope
        # metadata into the room event payload envelope so SSE
        # consumers can dispatch without consulting the
        # ``event_room_members`` table.
        fan_out_envelope = {
            "a2a_message_id": envelope.message_id,
            "source_session_id": envelope.source_session_id,
            "source_principal": caller_principal,
            "target_session_ids": list(envelope.target_session_ids),
            "target_principals": list(envelope.target_principals),
            "payload_kind": envelope.payload_kind,
            "payload": envelope.payload,
            "risk_level": envelope.risk_metadata.risk_level,
            "risk_action": envelope.risk_metadata.action,
            "risk_metadata": envelope.risk_metadata.metadata,
            "metadata": envelope.metadata,
            "ts": int(time.time()),
        }

        # Append the request.sent event.
        seq = await self.room_store.fan_out_event(
            room_id=envelope.room_id,
            event_type=A2A_REQUEST_SENT,
            payload=fan_out_envelope,
            origin_session_id=envelope.source_session_id,
            principal=caller_principal,
        )
        if seq is None:
            logger.warning(
                "A2ARouter.route_message: fan_out_event returned None "
                "(room_id={}, message_id={}); best-effort per audit §7.1",
                envelope.room_id,
                envelope.message_id,
            )

        # For review_request payloads, also emit a structural
        # ``a2a.request.acknowledged`` so the SSE consumer can
        # distinguish "request sent" from "request acknowledged
        # by the room fan-out". The actual reviewer ack handshake
        # is deferred to v3.12.3 / Phase 5 (D-25).
        if envelope.payload_kind == A2A_KIND_REVIEW_REQUEST:
            ack_envelope = {
                "a2a_message_id": envelope.message_id,
                "source_session_id": envelope.source_session_id,
                "source_principal": caller_principal,
                "target_session_ids": list(envelope.target_session_ids),
                "ts": int(time.time()),
            }
            ack_seq = await self.room_store.fan_out_event(
                room_id=envelope.room_id,
                event_type=A2A_REQUEST_ACKNOWLEDGED,
                payload=ack_envelope,
                origin_session_id=envelope.source_session_id,
                principal=caller_principal,
            )
            if ack_seq is None:
                logger.warning(
                    "A2ARouter.route_message: review ack fan_out_event "
                    "returned None (room_id={}, message_id={})",
                    envelope.room_id,
                    envelope.message_id,
                )

        return seq

    # ─── Public: open a ReviewSet ───────────────────────────────────────────

    async def request_review(
        self,
        *,
        room_id: str,
        initiator_session_id: str,
        reviewer_session_ids: list[str],
        payload: dict[str, Any],
        risk_metadata: RiskMetadata | None = None,
        ttl_seconds: int = 3600,
    ) -> ReviewSet:
        """Open a new ReviewSet and fan-out review requests.

        Resolves the verified caller principal from the
        ContextVar (the initiator). Validates the room + the
        initiator session is a current member. Probes every
        reviewer session + its bound principal; the
        ``ReviewSet`` carries ``[(session_id, principal), ...]``
        pairs so the aggregation engine can authorize
        submissions later.

        On success, creates a fresh ``ReviewSet`` keyed on
        ``set_id`` in ``self.review_sets`` AND fans out one
        ``a2a.request.sent`` room event per reviewer (with
        ``payload_kind = review_request`` carrying the set_id).
        """
        caller_principal = self._require_authenticated_principal()
        if not room_id:
            raise ValueError("room_id must be a non-empty string")
        if not initiator_session_id:
            raise ValueError(
                "initiator_session_id must be a non-empty string"
            )
        if not reviewer_session_ids:
            raise ValueError(
                "reviewer_session_ids must be a non-empty list"
            )
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

        # Probe room + initiator membership.
        room = await self.room_store.get(room_id)
        if room is None:
            raise A2ARouterError(
                f"room {room_id!r} does not exist"
            )
        if not room.is_open():
            raise A2ARouterError(
                f"room {room_id!r} is not open (status={room.status!r})"
            )

        if not await self.room_store.is_session_in_room(
            room_id, initiator_session_id
        ):
            raise A2ARouterError(
                f"initiator session {initiator_session_id!r} is not "
                f"a member of room {room_id!r}"
            )

        # Probe every reviewer session + its principal.
        reviewer_pairs: list[tuple[str, str]] = []
        db_path = self.room_store.db_path
        from .db import connect as _connect

        for reviewer_sid in reviewer_session_ids:
            if not await self.room_store.is_session_in_room(
                room_id, reviewer_sid
            ):
                raise A2ARouterError(
                    f"reviewer session {reviewer_sid!r} is not a "
                    f"member of room {room_id!r}"
                )
            db = await _connect(db_path)
            try:
                cur = await db.execute(
                    """
                    SELECT principal FROM event_room_members
                     WHERE room_id = ? AND session_id = ?
                    """,
                    (room_id, reviewer_sid),
                )
                row = await cur.fetchone()
            finally:
                await db.close()
            if row is None:
                raise A2ARouterError(
                    f"reviewer session {reviewer_sid!r} has no "
                    f"principal row in event_room_members"
                )
            reviewer_pairs.append((reviewer_sid, row["principal"]))

        # Create the ReviewSet + record in self.review_sets.
        set_id = make_review_set_id()
        review_set = ReviewSet(
            set_id=set_id,
            room_id=room_id,
            initiator_principal=caller_principal,
            initiator_session_id=initiator_session_id,
            reviewers=reviewer_pairs,
            ttl_seconds=ttl_seconds,
        )
        self.review_sets[set_id] = review_set

        # Build the canonical review-request envelope.
        target_principals = [principal for _sid, principal in reviewer_pairs]
        risk = risk_metadata or RiskMetadata()
        envelope = A2AMessageEnvelope(
            message_id=f"a2a_{set_id}",
            room_id=room_id,
            source_session_id=initiator_session_id,
            source_principal=caller_principal,
            target_session_ids=[sid for sid, _p in reviewer_pairs],
            target_principals=target_principals,
            payload_kind=A2A_KIND_REVIEW_REQUEST,
            payload={**payload, "review_set_id": set_id},
            risk_metadata=risk,
            metadata={"a2a_message_kind": "review_request"},
        )

        # Reuse ``route_message`` so the audit row is identical
        # to a regular route_message call (single event_type
        # ``a2a.request.sent`` per fan-out + structural
        # ``a2a.request.acknowledged``).
        await self.route_message(envelope)

        return review_set

    # ─── Public: route a reviewer's submission ─────────────────────────────

    async def route_review_submission(
        self,
        *,
        set_id: str,
        reviewer_principal: str,
        reviewer_session_id: str,
        decision: str,
        payload: dict[str, Any] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> bool:
        """Record a reviewer's decision in the ReviewSet + emit
        ``a2a.review.submitted``.

        The reviewer principal MUST be the verified caller
        principal (resolved from the ContextVar). The router
        refuses the submission if the principal parity check
        fails (REQ-A2A-02). The reviewer session MUST be in
        the ReviewSet's reviewers list.

        Returns True if a new review was recorded, False if it
        replaced a prior submission (latest-wins).
        """
        caller_principal = self._require_authenticated_principal()
        if reviewer_principal != caller_principal:
            raise A2AMessageNotAccepted(
                set_id,
                f"reviewer_principal {reviewer_principal!r} disagrees "
                f"with verified caller principal {caller_principal!r}; "
                f"refusing the submission (audit §REQ-A2A-02)",
            )

        review_set = self.review_sets.get(set_id)
        if review_set is None:
            raise A2ARouterError(
                f"ReviewSet {set_id!r} not found in router registry; "
                f"create it via request_review() first"
            )

        review = Review(
            reviewer_principal=reviewer_principal,
            reviewer_session_id=reviewer_session_id,
            decision=decision,
            payload=payload or {},
            evidence_refs=evidence_refs or [],
        )

        is_new = review_set.submit_review(review)

        # Emit a2a.review.submitted so the SSE consumer can see
        # the submission cross-session.
        envelope = {
            "set_id": set_id,
            "room_id": review_set.room_id,
            "reviewer_session_id": reviewer_session_id,
            "reviewer_principal": reviewer_principal,
            "decision": decision,
            "evidence_refs": list(evidence_refs or []),
            "is_new_submission": is_new,
            "ts": int(time.time()),
        }
        seq = await self.room_store.fan_out_event(
            room_id=review_set.room_id,
            event_type=A2A_REVIEW_SUBMITTED,
            payload=envelope,
            origin_session_id=reviewer_session_id,
            principal=caller_principal,
        )
        if seq is None:
            logger.warning(
                "A2ARouter.route_review_submission: fan_out_event "
                "returned None (set_id={}, reviewer_session_id={})",
                set_id,
                reviewer_session_id,
            )

        return is_new

    # ─── Public: aggregate + close a ReviewSet ──────────────────────────────

    async def aggregate_review_set(
        self, set_id: str
    ) -> AggregationResult | None:
        """Run the aggregation engine on the ReviewSet.

        Returns the ``AggregationResult`` if the set exists.
        Returns ``None`` if the set is not in the router registry.
        Does NOT close the set — call ``close_review_set`` for
        that. If the result has ``conflict_detected``, also emits
        an ``a2a.conflict.detected`` room event.
        """
        review_set = self.review_sets.get(set_id)
        if review_set is None:
            return None

        result = review_set.aggregate()

        if result.conflict_detected:
            await self._emit_conflict_detected(review_set, result)

        return result

    async def close_review_set(
        self, set_id: str
    ) -> AggregationResult | None:
        """Run aggregation + flip status to closed + emit
        ``a2a.review.closed`` (or ``a2a.conflict.detected`` when
        conflict was detected).

        Returns the ``AggregationResult`` if the set exists and
        closes successfully. Returns ``None`` if the set is not
        in the router registry. Raises ``ReviewSetClosed`` /
        ``ReviewSetExpired`` if the set is in a terminal state.
        """
        review_set = self.review_sets.get(set_id)
        if review_set is None:
            return None

        result = review_set.close()
        await self._emit_review_closed(review_set, result)
        if result.conflict_detected:
            await self._emit_conflict_detected(review_set, result)
        return result

    # ─── Private: emit closing + conflict events ─────────────────────────────

    async def _emit_review_closed(
        self,
        review_set: ReviewSet,
        result: AggregationResult,
    ) -> int | None:
        envelope = {
            "set_id": review_set.set_id,
            "room_id": review_set.room_id,
            "initiator_session_id": review_set.initiator_session_id,
            "initiator_principal": review_set.initiator_principal,
            "final_decision": result.final_decision,
            "conflict_detected": result.conflict_detected,
            "conflicting_pairs": [
                list(pair) for pair in result.conflicting_pairs
            ],
            "synthesis_required": result.synthesis_required,
            "aggregate_reason": result.aggregate_reason,
            "review_count": len(review_set.reviews),
            "ts": int(time.time()),
        }
        return await self.room_store.fan_out_event(
            room_id=review_set.room_id,
            event_type=A2A_REVIEW_CLOSED,
            payload=envelope,
            origin_session_id=review_set.initiator_session_id,
            principal=review_set.initiator_principal,
        )

    async def _emit_conflict_detected(
        self,
        review_set: ReviewSet,
        result: AggregationResult,
    ) -> int | None:
        envelope = {
            "set_id": review_set.set_id,
            "room_id": review_set.room_id,
            "initiator_session_id": review_set.initiator_session_id,
            "initiator_principal": review_set.initiator_principal,
            "conflicting_pairs": [
                list(pair) for pair in result.conflicting_pairs
            ],
            "synthesis_required": result.synthesis_required,
            "aggregate_reason": result.aggregate_reason,
            "review_count": len(review_set.reviews),
            "ts": int(time.time()),
        }
        return await self.room_store.fan_out_event(
            room_id=review_set.room_id,
            event_type=A2A_CONFLICT_DETECTED,
            payload=envelope,
            origin_session_id=review_set.initiator_session_id,
            principal=review_set.initiator_principal,
        )


__all__ = [
    "L3RiskClassifier",
    "A2ARouterError",
    "A2AMessageNotAccepted",
    "A2ARouter",
]