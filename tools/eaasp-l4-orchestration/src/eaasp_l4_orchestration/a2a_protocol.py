"""A2A (Agent-to-Agent) protocol envelope — v3.12.2.

Spec §14 / EAASP_v2_0_EVOLUTION_PATH.md §三 Phase 4 / ADR-V2-024 (engine
接入面) — A2A Router protocol layer. Sessions coordinate through a shared
Event Room by exchanging typed A2A messages; the protocol envelope is
the canonical shape that crosses every A2A boundary in this layer.

v3.12.2 — REQ-A2A-01..03 + REQ-SSE-01..05:

- ``A2AMessageEnvelope`` is a pydantic ``BaseModel`` so every entry
  point (FastAPI request body, room event payload, in-memory builder)
  uses the same parser / validator. The Pydantic model rejects
  malformed payloads BEFORE the route / fan-out path opens the DB.
- ``RiskMetadata`` carries the L3 ``risk_level`` value (``read`` /
  ``write_local`` / ``write_external``) so the L3 ``PolicyEngine``
  can classify the inbound A2A request without re-deriving it from
  the payload. The shape mirrors the v3.11.2 ``governance.request``
  payload's ``risk_level`` field (event_stream.py).
- The 5 A2A SSE event types (``a2a.request.sent`` /
  ``a2a.request.acknowledged`` / ``a2a.review.submitted`` /
  ``a2a.review.closed`` / ``a2a.conflict.detected``) coexist with
  the 5 ``governance.approval.<stage>`` events emitted by the
  v3.11.2 5-stage approval chain — distinct namespace so SSE
  consumers can subscribe to the A2A family independently. The
  ``a2a.*`` family lives in the room-scoped event stream (Event
  Room, long-lived) while ``governance.approval.*`` lives in the
  per-session stream (single session, short-lived).

Frozen contract (audit §7.1): the envelope is best-effort and
NEVER inverts the authoritative audit ledger. Fan-out failures
log + return ``None``; the L3 ``governance_decisions`` ledger +
the L4 ``session_events`` ledger are the only sources of truth.

v3.12.2 — REQ-A2A-02 (principal-keyed routing): ``source_principal``
and ``target_principals`` are first-class fields so the router can
authorize the source + validate every target is a current room
member without re-reading the payload body. The source principal
is set by the API entry-point adapter (verified JWT) and the
router refuses to honor a request where it disagrees with the
``_AUTHENTICATED_PRINCIPAL`` ContextVar (sibling-path parity with
the v3.12.1 ``MultiSessionCoordinator`` facade).
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ─── A2A SSE event types (v3.12.2 — REQ-SSE-01..05) ──────────────────────────
#
# Distinct namespace from ``governance.approval.*`` so SSE consumers can
# subscribe to A2A events independently. The names follow the
# established convention: ``a2a.<verb>.<past_participle>`` so the SSE
# consumer can dispatch on the event-type suffix.
A2A_REQUEST_SENT = "a2a.request.sent"
A2A_REQUEST_ACKNOWLEDGED = "a2a.request.acknowledged"
A2A_REVIEW_SUBMITTED = "a2a.review.submitted"
A2A_REVIEW_CLOSED = "a2a.review.closed"
A2A_CONFLICT_DETECTED = "a2a.conflict.detected"

# Set-of-valid A2A SSE event types. The router / aggregation engine
# accept only these as room-scoped A2A events; any other event_type
# is forwarded as-is via ``EventRoomStore.fan_out_event`` but is NOT
# considered an A2A event (the room has its own pre-existing
# ``governance.session.cross.*`` family from v3.12.1).
A2A_EVENT_TYPES: frozenset[str] = frozenset(
    {
        A2A_REQUEST_SENT,
        A2A_REQUEST_ACKNOWLEDGED,
        A2A_REVIEW_SUBMITTED,
        A2A_REVIEW_CLOSED,
        A2A_CONFLICT_DETECTED,
    }
)

# v3.12.2 — REQ-A2A-01: A2A message ``payload_kind`` enum. The router
# accepts only these values; any other kind is rejected with a
# ``ValueError`` BEFORE the DB open. Future expansion (e.g.
# ``artifact_handoff``) requires updating this enum + the router
# dispatch.
A2A_KIND_REVIEW_REQUEST = "review_request"
A2A_KIND_REVIEW_RESPONSE = "review_response"
A2A_KIND_GENERIC = "generic"
A2A_PAYLOAD_KINDS: frozenset[str] = frozenset(
    {A2A_KIND_REVIEW_REQUEST, A2A_KIND_REVIEW_RESPONSE, A2A_KIND_GENERIC}
)

# v3.12.2 — REQ-A2A-02 / risk metadata. Mirrors the v3.11.2
# governance request shape (event_stream.py ``emit_governance_request``).
# The router forwards this to the L3 ``PolicyEngine`` /
# ``RiskClassifier`` for the gated path (audit-style; v3.12.2 keeps
# the structural fan-out only — the L3 hookup is the API layer's
# responsibility per the v3.12.2 plan).
RISK_READ = "read"
RISK_WRITE_LOCAL = "write_local"
RISK_WRITE_EXTERNAL = "write_external"
RISK_LEVELS: frozenset[str] = frozenset(
    {RISK_READ, RISK_WRITE_LOCAL, RISK_WRITE_EXTERNAL}
)

# v3.12.2 — REQ-A2A-02: principal / session_id / room_id format
# allowlist. The id fields are URL path segments + SSE event log keys
# + FTS5 tokens; a strict pattern prevents injection / corruption.
# Identical to the v3.12.1 ``_ROOM_ID_PATTERN`` shape — kept here so
# the A2A module is decoupled from ``event_room`` module load order.
_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")


def _validate_id_field(value: str, *, field_name: str) -> str:
    """Validate a principal / session_id / room_id shape.

    Empty / None / non-string values raise ``ValueError``. The
    pattern is identical to the v3.12.1 ``_ROOM_ID_PATTERN`` —
    ``[a-zA-Z0-9_.-]{1,128}`` — so a hostile caller cannot inject
    quotes / control chars / unbounded strings.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    if not _ID_PATTERN.match(value):
        raise ValueError(
            f"{field_name} must match {_ID_PATTERN.pattern!r}, "
            f"got {value!r}"
        )
    return value


class RiskMetadata(BaseModel):
    """L3 risk-classification metadata carried by every A2A message.

    Mirrors the v3.11.2 ``emit_governance_request`` shape. The
    router records this in the room event payload so SSE consumers
    can dispatch the inbound A2A to the L3 ``PolicyEngine`` /
    ``RiskClassifier`` for the gated path without re-deriving it
    from the payload body.

    Fields:
        risk_level: one of ``read`` / ``write_local`` / ``write_external``.
        action: optional human-readable action name (e.g.
            ``scada_set_setpoint``); used by the L3 ``PolicyEngine``
            to look up the action-specific policy.
        metadata: free-form bag for action-specific data (e.g.
            target device, ticket id). Caller-controlled.
    """

    risk_level: str = "read"
    action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("risk_level")
    @classmethod
    def _check_risk_level(cls, value: str) -> str:
        if value not in RISK_LEVELS:
            raise ValueError(
                f"risk_level must be one of {sorted(RISK_LEVELS)!r}, "
                f"got {value!r}"
            )
        return value


class A2AMessageEnvelope(BaseModel):
    """Canonical A2A message envelope (v3.12.2 — REQ-A2A-01).

    Pydantic ``BaseModel`` so every entry point (FastAPI request
    body, room event payload, in-memory builder) uses the same
    parser / validator. Validation rejects malformed payloads
    BEFORE the route / fan-out path opens the DB.

    Fields:
        message_id: server-issued ULID-ish UUID hex (``a2a_<uuid4hex>``).
            Auto-generated if omitted by the caller.
        room_id: target Event Room id (required).
        source_session_id: emitting session (required).
        source_principal: emitting principal (verified). The
            router refuses to honor a request where this
            disagrees with the API ContextVar (sibling-path
            parity with v3.12.1 ``MultiSessionCoordinator``).
        target_session_ids: explicit list of receiving sessions
            (required, non-empty). The router validates every
            target is a current room member under the supplied
            target_principals before fan-out.
        target_principals: parallel list of principals bound to
            each ``target_session_ids`` entry. Length must
            match ``target_session_ids``. The router uses
            these to authorize the cross-principal send
            (e.g. alice can message bob even though alice
            and bob have different principals).
        payload_kind: one of ``review_request`` /
            ``review_response`` / ``generic``.
        payload: opaque body for the receiving session(s).
            Pydantic does not constrain its shape.
        risk_metadata: L3 risk classification (read /
            write_local / write_external). The router records
            this verbatim in the room event payload.
        metadata: free-form bag for caller-specific data (e.g.
            trace id, ticket id). Not interpreted by the
            router.
        created_at: unix epoch seconds. Defaults to ``int(time.time())``
            when omitted. The router records this in the room
            event payload.
    """

    message_id: str = ""
    room_id: str
    source_session_id: str
    source_principal: str
    target_session_ids: list[str] = Field(default_factory=list)
    target_principals: list[str] = Field(default_factory=list)
    payload_kind: str = A2A_KIND_GENERIC
    payload: dict[str, Any] = Field(default_factory=dict)
    risk_metadata: RiskMetadata = Field(default_factory=RiskMetadata)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: int = 0

    @field_validator("room_id")
    @classmethod
    def _check_room_id(cls, value: str) -> str:
        return _validate_id_field(value, field_name="room_id")

    @field_validator("source_session_id")
    @classmethod
    def _check_source_session_id(cls, value: str) -> str:
        return _validate_id_field(value, field_name="source_session_id")

    @field_validator("source_principal")
    @classmethod
    def _check_source_principal(cls, value: str) -> str:
        return _validate_id_field(value, field_name="source_principal")

    @field_validator("target_session_ids")
    @classmethod
    def _check_target_session_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("target_session_ids must be a non-empty list")
        for idx, sid in enumerate(value):
            _validate_id_field(sid, field_name=f"target_session_ids[{idx}]")
        return value

    @field_validator("target_principals")
    @classmethod
    def _check_target_principals(cls, value: list[str]) -> list[str]:
        for idx, principal in enumerate(value):
            _validate_id_field(
                principal, field_name=f"target_principals[{idx}]"
            )
        return value

    @field_validator("payload_kind")
    @classmethod
    def _check_payload_kind(cls, value: str) -> str:
        if value not in A2A_PAYLOAD_KINDS:
            raise ValueError(
                f"payload_kind must be one of {sorted(A2A_PAYLOAD_KINDS)!r}, "
                f"got {value!r}"
            )
        return value

    def model_post_init(self, __context: Any) -> None:
        """Auto-fill ``message_id`` + ``created_at`` if the caller
        did not supply them.

        Pydantic v2 ``model_post_init`` is invoked after field
        validation; both auto-fills are deterministic but the
        timestamps shift on every call. Tests that need stable
        values MUST set both fields explicitly.
        """
        if not self.message_id:
            object.__setattr__(
                self, "message_id", f"a2a_{uuid.uuid4().hex[:16]}"
            )
        if not self.created_at:
            object.__setattr__(self, "created_at", int(time.time()))

    def matched_target_pairs(self) -> list[tuple[str, str]]:
        """Return ``[(session_id, principal), ...]`` parallel arrays.

        The router uses this to authorize the cross-principal send
        + to write the room event payload. Raises ``ValueError`` if
        the parallel-array invariant is violated (lengths differ).
        """
        if len(self.target_session_ids) != len(self.target_principals):
            raise ValueError(
                "target_session_ids and target_principals must have "
                "the same length; got "
                f"{len(self.target_session_ids)} session_ids and "
                f"{len(self.target_principals)} principals"
            )
        return list(zip(self.target_session_ids, self.target_principals))


def make_a2a_event_type(subtype: str) -> str:
    """Build a canonical A2A SSE event type (``a2a.<subtype>``).

    Accepts the 5 canonical subtype strings (``request.sent`` /
    ``request.acknowledged`` / ``review.submitted`` /
    ``review.closed`` / ``conflict.detected``) and any caller-
    defined subtype that satisfies the strict pattern. The
    function does NOT validate that the subtype is in
    ``A2A_EVENT_TYPES`` — the canonical 5 are enforced at the
    router / aggregation-engine dispatch layer, not at the
    envelope-builder layer.
    """
    if not subtype:
        raise ValueError("subtype must be a non-empty string")
    if not _ID_PATTERN.match(subtype.replace(".", "a")):
        # ``replace(".", "a")`` lets dotted subtypes pass while
        # still rejecting control chars / quotes / spaces.
        raise ValueError(
            f"subtype must match {_ID_PATTERN.pattern!r}, "
            f"got {subtype!r}"
        )
    return f"a2a.{subtype}"


__all__ = [
    "A2A_REQUEST_SENT",
    "A2A_REQUEST_ACKNOWLEDGED",
    "A2A_REVIEW_SUBMITTED",
    "A2A_REVIEW_CLOSED",
    "A2A_CONFLICT_DETECTED",
    "A2A_EVENT_TYPES",
    "A2A_KIND_REVIEW_REQUEST",
    "A2A_KIND_REVIEW_RESPONSE",
    "A2A_KIND_GENERIC",
    "A2A_PAYLOAD_KINDS",
    "RISK_READ",
    "RISK_WRITE_LOCAL",
    "RISK_WRITE_EXTERNAL",
    "RISK_LEVELS",
    "RiskMetadata",
    "A2AMessageEnvelope",
    "make_a2a_event_type",
]