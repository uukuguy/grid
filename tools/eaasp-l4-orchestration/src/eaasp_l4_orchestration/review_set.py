"""ReviewSet — multi-reviewer aggregation engine for A2A review flows.

v3.12.2 — EAASP v2.0 Phase 4 (A2A Router + Event Room + multi-session
coordination). Spec §14 / ADR-V2-024 (engine 接入面) / ADR-V2-035
(conflict-detection algorithm).

The ReviewSet is a coordination primitive on top of the v3.12.1
Event Room: one initiator session opens a review, N reviewer
sessions submit independent decisions via A2A messages, the
aggregation engine collects the decisions, detects contradictions,
and produces a final aggregated decision that downstream code can
feed back into the v3.11.2 5-stage approval chain via
``ApprovalStateMachine.resume_with_human_decision``.

This module is **purely in-process** (no SQLite writes) — the
authoritative audit row lives in the L3 ``governance_decisions``
ledger + the L4 ``event_room_events`` log. The ReviewSet data
structure is the in-memory bookkeeping that drives the
aggregation engine; per audit §7.1 the engine's output is
best-effort and NEVER inverts the authoritative ledger.

Aggregation rules (v3.12.2 — REQ-REVIEW-01..03 + REQ-CONFLICT-01..02):

- ``allow`` wins when ALL reviewers decide ``allow`` (unanimous).
- ``deny`` wins when ALL reviewers decide ``deny`` (unanimous).
- ``escalate`` when ANY reviewer decides ``needs_revision`` OR
  when there is at least one ``allow`` and one ``deny`` with no
  ``needs_revision`` (mixed-but-not-all-deny).
- ``deny`` wins when there are MULTIPLE ``deny`` decisions
  (majority-deny supersedes single allow).
- Conflict: two reviewers decided differently against the SAME
  evidence_ref → ``conflict_detected=True`` triggers
  ``review_synthesis`` (a downstream hook that the API layer can
  implement; the engine flags it but does not run it).

Status lifecycle (v3.12.2 — REQ-REVIEW-01):

- ``open`` — created, awaiting reviewer submissions.
- ``closed`` — aggregated decision delivered; no more submissions
  accepted.
- ``expired`` — TTL exceeded; aggregation engine rejects
  post-expiry submissions.

Aggregation output (REQ-REVIEW-02 + REQ-REVIEW-03):

- ``final_decision``: ``allow`` / ``deny`` / ``escalate``.
- ``conflict_detected``: bool — True iff two reviewers contradict
  on the same evidence.
- ``conflicting_pairs``: list of ``(session_id_a, session_id_b)``
  tuples representing the contradiction(s).
- ``synthesis_required``: bool — True iff ``conflict_detected`` is
  True OR mixed-decision aggregation requires escalation.
- ``aggregate_reason``: human-readable string explaining the
  aggregation result.

Frozen contract (audit §7.1): the ReviewSet data structure is
in-process and does not touch the audit ledger. A reviewer's
decision is recorded as an A2A ``a2a.review.submitted`` room event
(via the A2A Router); the aggregator's final output is recorded
as a single ``a2a.review.closed`` (or ``a2a.conflict.detected``)
room event. The two writes are independent — failure of either
does not roll back the other.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# ─── Review decision enum (v3.12.2) ──────────────────────────────────────────
#
# Distinct from the v3.11.2 ``DECISION_ALLOW`` / ``DECISION_DENY`` /
# ``DECISION_AWAIT_HUMAN`` L3 constants because a Review decision is
# an A2A coordination primitive (between sessions), not a single
# policy verdict (between caller and gate). Mapping from A2A review
# decision → L3 decision happens at the API layer when the
# aggregated ReviewSet result is fed into the approval chain.
REVIEW_DECISION_ALLOW = "allow"
REVIEW_DECISION_DENY = "deny"
REVIEW_DECISION_NEEDS_REVISION = "needs_revision"

VALID_REVIEW_DECISIONS: frozenset[str] = frozenset(
    {
        REVIEW_DECISION_ALLOW,
        REVIEW_DECISION_DENY,
        REVIEW_DECISION_NEEDS_REVISION,
    }
)

# ─── ReviewSet status lifecycle ──────────────────────────────────────────────
STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
STATUS_EXPIRED = "expired"
VALID_REVIEW_SET_STATUSES: frozenset[str] = frozenset(
    {STATUS_OPEN, STATUS_CLOSED, STATUS_EXPIRED}
)

# ─── Aggregation result enum ────────────────────────────────────────────────
#
# The aggregation engine never returns ``await_human`` — that is
# the L3 ApprovalStateMachine's signal. The engine returns
# ``escalate`` to flag the chain needs human-in-the-loop
# arbitration (e.g. via ``resume_with_human_decision``).
AGGREGATE_ALLOW = "allow"
AGGREGATE_DENY = "deny"
AGGREGATE_ESCALATE = "escalate"
VALID_AGGREGATE_DECISIONS: frozenset[str] = frozenset(
    {AGGREGATE_ALLOW, AGGREGATE_DENY, AGGREGATE_ESCALATE}
)


@dataclass
class Review:
    """A single reviewer's decision in a ReviewSet.

    Fields:
        reviewer_principal: the principal that submitted the
            decision (verified at A2A submission time).
        reviewer_session_id: the session that submitted the
            decision (a member of the ReviewSet's room).
        decision: one of ``allow`` / ``deny`` / ``needs_revision``.
        payload: opaque body for downstream consumption (free-form).
        evidence_refs: list of opaque refs (memory anchors, run
            ids, ticket ids). Two reviewers citing the same
            evidence_ref with contradictory decisions triggers a
            conflict.
        submitted_at: unix epoch seconds when the review was
            submitted.
    """

    reviewer_principal: str
    reviewer_session_id: str
    decision: str
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    submitted_at: int = 0

    def __post_init__(self) -> None:
        if not self.reviewer_principal:
            raise ValueError("reviewer_principal must be a non-empty string")
        if not self.reviewer_session_id:
            raise ValueError(
                "reviewer_session_id must be a non-empty string"
            )
        if self.decision not in VALID_REVIEW_DECISIONS:
            raise ValueError(
                f"decision must be one of {sorted(VALID_REVIEW_DECISIONS)!r}, "
                f"got {self.decision!r}"
            )
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dict")
        for ref in self.evidence_refs:
            if not isinstance(ref, str) or not ref:
                raise ValueError(
                    "evidence_refs entries must be non-empty strings"
                )
        if not self.submitted_at:
            self.submitted_at = int(time.time())


@dataclass
class AggregationResult:
    """The aggregation engine's output for a closed ReviewSet.

    Fields:
        set_id: the ReviewSet this result belongs to.
        final_decision: one of ``allow`` / ``deny`` / ``escalate``.
        conflict_detected: True iff two reviewers contradicted on
            the same evidence_ref.
        conflicting_pairs: list of ``(session_id_a, session_id_b)``
            tuples representing the contradictions.
        synthesis_required: True iff conflict_detected OR the
            aggregation requires human-in-the-loop escalation.
        aggregate_reason: human-readable explanation.
        aggregated_at: unix epoch seconds when the aggregation ran.
    """

    set_id: str
    final_decision: str
    conflict_detected: bool
    conflicting_pairs: list[tuple[str, str]]
    synthesis_required: bool
    aggregate_reason: str
    aggregated_at: int = 0

    def __post_init__(self) -> None:
        if not self.set_id:
            raise ValueError("set_id must be a non-empty string")
        if self.final_decision not in VALID_AGGREGATE_DECISIONS:
            raise ValueError(
                f"final_decision must be one of "
                f"{sorted(VALID_AGGREGATE_DECISIONS)!r}, "
                f"got {self.final_decision!r}"
            )
        if not isinstance(self.conflicting_pairs, list):
            raise ValueError("conflicting_pairs must be a list of tuples")
        if not self.aggregated_at:
            self.aggregated_at = int(time.time())


@dataclass
class ReviewSet:
    """A multi-reviewer review collection opened against an Event Room.

    Fields:
        set_id: server-issued ULID-ish UUID hex (``rs_<uuid4hex>``).
        room_id: the Event Room the review is scoped to.
        initiator_principal: the principal that opened the review.
        initiator_session_id: the session that opened the review.
        reviewers: list of (session_id, principal) pairs that are
            expected to submit reviews. The aggregator validates
            every submitted review is from a session in this list
            and refuses submissions from non-reviewers.
        reviews: dict[reviewer_session_id, Review] populated as
            reviewers submit. Idempotent on (set_id, session_id):
            a reviewer that submits twice has the latest decision
            win (the prior one is replaced).
        status: ``open`` / ``closed`` / ``expired``.
        ttl_seconds: how long the review stays open before
            ``expire()`` flips status to ``expired``. Clamped to
            ``[1..86400]`` (1 second .. 1 day) so a malformed
            caller cannot pin an indefinite review.
        created_at: unix epoch seconds.
        closed_at: unix epoch seconds when ``close()`` ran;
            None while ``status == open``.
        aggregation: the ``AggregationResult`` populated by
            ``aggregate()`` / ``close()``; None while
            ``status == open``.
    """

    set_id: str
    room_id: str
    initiator_principal: str
    initiator_session_id: str
    reviewers: list[tuple[str, str]] = field(default_factory=list)
    reviews: dict[str, Review] = field(default_factory=dict)
    status: str = STATUS_OPEN
    ttl_seconds: int = 3600
    created_at: int = 0
    closed_at: int | None = None
    aggregation: AggregationResult | None = None

    # Cached ``{session_id: principal}`` map built once in
    # ``__post_init__`` so ``submit_review`` / ``aggregate`` do
    # NOT rebuild it on every call. Used to authorize the
    # session→principal binding in ``submit_review`` (security
    # review HIGH #2: refuse caller-supplied reviewer_principal
    # when it disagrees with the expected principal).
    _expected_sessions_with_principals: dict[str, str] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        if not self.set_id:
            raise ValueError("set_id must be a non-empty string")
        if not self.room_id:
            raise ValueError("room_id must be a non-empty string")
        if not self.initiator_principal:
            raise ValueError(
                "initiator_principal must be a non-empty string"
            )
        if not self.initiator_session_id:
            raise ValueError(
                "initiator_session_id must be a non-empty string"
            )
        if self.status not in VALID_REVIEW_SET_STATUSES:
            raise ValueError(
                f"status must be one of "
                f"{sorted(VALID_REVIEW_SET_STATUSES)!r}, "
                f"got {self.status!r}"
            )
        # Clamp ttl to [1..86400].
        if self.ttl_seconds is None or self.ttl_seconds <= 0:
            self.ttl_seconds = 3600
        elif self.ttl_seconds > 86400:
            self.ttl_seconds = 86400
        if not self.created_at:
            self.created_at = int(time.time())
        # Build the canonical session_id → principal map ONCE so
        # subsequent operations (submit_review / aggregate) can
        # look up the bound principal in O(1). Defensive: reviewers
        # must be unique on session_id; every principal must be a
        # non-empty string.
        cache: dict[str, str] = {}
        for sid, principal in self.reviewers:
            if sid in cache:
                raise ValueError(
                    f"duplicate reviewer session_id {sid!r} in reviewers"
                )
            if not principal:
                raise ValueError(
                    f"reviewer ({sid!r}) has empty principal"
                )
            cache[sid] = principal
        self._expected_sessions_with_principals = cache

    # ─── Lifecycle helpers ──────────────────────────────────────────────────

    def is_open(self) -> bool:
        """True iff status is ``open`` AND not past TTL."""
        if self.status != STATUS_OPEN:
            return False
        return (int(time.time()) - self.created_at) < self.ttl_seconds

    def is_expired(self, *, now: int | None = None) -> bool:
        """True iff past TTL regardless of status."""
        ts = int(now if now is not None else time.time())
        return (ts - self.created_at) >= self.ttl_seconds

    def expected_reviewer_session_ids(self) -> set[str]:
        """Return the session_ids this ReviewSet expects reviews from."""
        return set(self._expected_sessions_with_principals.keys())

    def submit_review(self, review: Review) -> bool:
        """Record a reviewer's decision. Returns True if a new review
        was recorded, False if it replaced a prior submission from
        the same session (latest-wins).

        Refuses submissions after ``close()`` / after TTL expiry.
        Refuses submissions from sessions that are not in the
        expected reviewers list (REQ-REVIEW-01).

        Security review HIGH #2 — principal mismatch: after the
        session-membership check, the function looks up the
        expected principal for that session from the cached
        ``_expected_sessions_with_principals`` map and requires
        exact match with ``review.reviewer_principal``. A
        caller-supplied principal that disagrees with the
        expected one is rejected with
        ``ReviewerPrincipalMismatch`` BEFORE the review is
        written to ``self.reviews``. This closes the
        horizontal-privilege-escalation vector where a session
        bound to principal=A could submit a review attributed
        to principal=B by populating the request-body field.
        """
        if self.status == STATUS_CLOSED:
            raise ReviewSetClosed(
                self.set_id, f"set {self.set_id!r} is closed"
            )
        if self.status == STATUS_EXPIRED or self.is_expired():
            self.status = STATUS_EXPIRED
            raise ReviewSetExpired(
                self.set_id, f"set {self.set_id!r} has expired"
            )

        # Security review HIGH #2 — verify the (session_id,
        # principal) pair matches the configured reviewer. The
        # cached map is built in ``__post_init__`` so this lookup
        # is O(1) and the principal is sourced from the trusted
        # ReviewSet configuration (request_review probe), NOT
        # from the caller-supplied field.
        expected_principal = self._expected_sessions_with_principals.get(
            review.reviewer_session_id
        )
        if expected_principal is None:
            raise ReviewerNotExpected(
                self.set_id,
                review.reviewer_session_id,
                review.reviewer_principal,
                f"session {review.reviewer_session_id!r} is not in the "
                f"ReviewSet's reviewers list",
            )
        if review.reviewer_principal != expected_principal:
            raise ReviewerPrincipalMismatch(
                self.set_id,
                review.reviewer_session_id,
                review.reviewer_principal,
                f"session {review.reviewer_session_id!r} is bound "
                f"to principal {expected_principal!r}, not "
                f"{review.reviewer_principal!r}; refusing the "
                f"submission (audit §REQ-REVIEW-01 / "
                f"security review HIGH #2)",
            )

        replaced = review.reviewer_session_id in self.reviews
        self.reviews[review.reviewer_session_id] = review
        return not replaced

    def aggregate(self, *, now: int | None = None) -> AggregationResult:
        """Run the aggregation engine over the recorded reviews.

        The aggregator produces an ``AggregationResult`` but does
        NOT mutate ``status`` or ``closed_at`` — the caller is
        expected to invoke ``close()`` (or ``expire()``)
        separately. ``aggregate()`` is idempotent; calling it
        twice produces the same result.

        Aggregation algorithm (v3.12.2 — ADR-V2-035):

        1. Completeness gate (security review HIGH #1 — fail-open
           aggregation): compute the set of expected reviewer
           session_ids (``_expected_sessions_with_principals``)
           and the set of recorded reviewer session_ids
           (``self.reviews``). If ANY expected reviewer has NOT
           submitted, return ``AGGREGATE_ESCALATE`` immediately
           with ``synthesis_required=True`` — unanimity is NOT
           decidable without every reviewer's input. A
           single ``allow`` from one of N expected reviewers is
           NOT a unanimous verdict; the aggregation engine
           refuses to produce a terminal allow/deny until every
           reviewer has spoken.
        2. Conflict detection: build a map of ``evidence_ref`` →
           ``[(session_id, decision), ...]``. If any single
           ``evidence_ref`` has 2+ reviews with DIFFERENT decisions,
           mark ``conflict_detected=True`` and record the
           contradicting ``(session_id_a, session_id_b)`` pairs.
        3. Decision counting: count allow / deny / needs_revision
           in the recorded reviews.
        4. Apply aggregation rules:
           - all allow → AGGREGATE_ALLOW.
           - any needs_revision → AGGREGATE_ESCALATE
             (needs_revision wins over allow; deny that
             accompanies needs_revision means "deny-with-revision"
             which is still escalation).
           - multiple deny (>= 2) → AGGREGATE_DENY
             (majority-deny supersedes single allow).
           - single deny + at least one allow → AGGREGATE_ESCALATE
             (mixed-but-not-all-deny).
           - all deny → AGGREGATE_DENY.
        5. Synthesis flag: True iff conflict_detected OR the
           aggregation result is AGGREGATE_ESCALATE.

        The aggregator is deterministic and free of side effects;
        tests assert against fixed inputs (deterministic decisions
        + timestamps).
        """
        expected_sids = set(self._expected_sessions_with_principals.keys())
        recorded_sids = set(self.reviews.keys())
        missing_sids = expected_sids - recorded_sids

        if missing_sids:
            # Security review HIGH #1 — fail-open aggregation:
            # missing reviewers means unanimity is not decidable.
            # Even if every recorded reviewer voted ``allow``,
            # the absent reviewer's verdict is unknown — escalate
            # rather than produce a terminal allow/deny verdict.
            return AggregationResult(
                set_id=self.set_id,
                final_decision=AGGREGATE_ESCALATE,
                conflict_detected=False,
                conflicting_pairs=[],
                synthesis_required=True,
                aggregate_reason=(
                    f"escalate: {len(missing_sids)} of "
                    f"{len(expected_sids)} expected reviewer(s) have "
                    f"not submitted; unanimity is not decidable; "
                    f"missing session_ids = {sorted(missing_sids)} "
                    f"(audit §REQ-REVIEW-01 / security review "
                    f"HIGH #1 — fail-open aggregation)"
                ),
                aggregated_at=int(now if now is not None else time.time()),
            )

        if not self.reviews:
            # No reviews yet → escalate (cannot decide without input).
            return AggregationResult(
                set_id=self.set_id,
                final_decision=AGGREGATE_ESCALATE,
                conflict_detected=False,
                conflicting_pairs=[],
                synthesis_required=True,
                aggregate_reason=(
                    "no reviews submitted; aggregator escalates "
                    "the decision to a human reviewer "
                    "(REQ-REVIEW-01)"
                ),
                aggregated_at=int(now if now is not None else time.time()),
            )

        # Step 1: conflict detection on evidence_refs.
        evidence_to_reviews: dict[str, list[tuple[str, str]]] = {}
        for sid, review in self.reviews.items():
            for ref in review.evidence_refs:
                evidence_to_reviews.setdefault(ref, []).append(
                    (sid, review.decision)
                )

        conflict_detected = False
        conflicting_pairs_set: set[tuple[str, str]] = set()
        for ref, reviews_with_ref in evidence_to_reviews.items():
            decisions_for_ref = {decision for _sid, decision in reviews_with_ref}
            if len(decisions_for_ref) <= 1:
                continue
            # At least two reviewers cited this evidence with
            # different decisions. Mark conflict + record pairs.
            conflict_detected = True
            # Record every (a, b) pair where a < b on session_id
            # so the same pair is not added twice.
            sorted_sessions = sorted({sid for sid, _d in reviews_with_ref})
            for i in range(len(sorted_sessions)):
                for j in range(i + 1, len(sorted_sessions)):
                    conflicting_pairs_set.add(
                        (sorted_sessions[i], sorted_sessions[j])
                    )

        # Step 2: decision counting.
        decisions = [review.decision for review in self.reviews.values()]
        allow_count = decisions.count(REVIEW_DECISION_ALLOW)
        deny_count = decisions.count(REVIEW_DECISION_DENY)
        needs_revision_count = decisions.count(REVIEW_DECISION_NEEDS_REVISION)

        # Step 3: aggregation rules (ordered by specificity).
        final_decision: str
        aggregate_reason: str

        if needs_revision_count > 0:
            # any needs_revision → escalate. Per v3.12.2 spec §14.4,
            # needs_revision requests human-in-the-loop arbitration;
            # a deny that accompanies needs_revision is a
            # "deny-with-revision" — still escalation, not deny.
            final_decision = AGGREGATE_ESCALATE
            aggregate_reason = (
                f"escalate: {needs_revision_count} reviewer(s) "
                f"requested needs_revision"
            )
        elif allow_count == len(decisions):
            # all allow → allow (unanimous).
            final_decision = AGGREGATE_ALLOW
            aggregate_reason = (
                f"allow: all {allow_count} reviewer(s) submitted allow"
            )
        elif deny_count == len(decisions):
            # all deny → deny (unanimous).
            final_decision = AGGREGATE_DENY
            aggregate_reason = (
                f"deny: all {deny_count} reviewer(s) submitted deny"
            )
        elif deny_count >= 2:
            # multiple deny → deny (majority-deny supersedes
            # single allow). 2+ denies with 1+ allows → deny.
            final_decision = AGGREGATE_DENY
            aggregate_reason = (
                f"deny: {deny_count} deny votes supersede "
                f"{allow_count} allow vote(s) "
                f"(majority-deny rule, ADR-V2-035)"
            )
        else:
            # mixed but not all-deny and no needs_revision:
            # one deny + one+ allow → escalate (mixed verdict).
            final_decision = AGGREGATE_ESCALATE
            aggregate_reason = (
                f"escalate: mixed verdict — {allow_count} allow, "
                f"{deny_count} deny (no needs_revision); "
                f"human arbitration required"
            )

        # Step 4: synthesis flag — conflict_detected OR final is escalate.
        synthesis_required = bool(
            conflict_detected or final_decision == AGGREGATE_ESCALATE
        )

        return AggregationResult(
            set_id=self.set_id,
            final_decision=final_decision,
            conflict_detected=conflict_detected,
            conflicting_pairs=sorted(conflicting_pairs_set),
            synthesis_required=synthesis_required,
            aggregate_reason=aggregate_reason,
            aggregated_at=int(now if now is not None else time.time()),
        )

    def close(
        self, final_decision: str | None = None, *, now: int | None = None
    ) -> AggregationResult:
        """Close the ReviewSet and produce the final aggregation.

        If ``final_decision`` is None, the aggregation engine runs
        over the recorded reviews. If non-None, it MUST match what
        the engine produces — a mismatch raises ``ValueError``
        (caller-side override is not allowed; the engine is the
        single source of truth).

        Refuses to close an already-closed ReviewSet. Marks the
        set closed and stores the aggregation result on the
        instance.
        """
        if self.status == STATUS_CLOSED:
            raise ReviewSetClosed(
                self.set_id, f"set {self.set_id!r} is already closed"
            )

        # Apply TTL expiry before aggregation so a stale open set
        # surfaces as expired rather than producing a stale verdict.
        if self.status == STATUS_EXPIRED or self.is_expired(now=now):
            self.status = STATUS_EXPIRED
            raise ReviewSetExpired(
                self.set_id, f"set {self.set_id!r} has expired"
            )

        result = self.aggregate(now=now)
        if final_decision is not None:
            if final_decision != result.final_decision:
                raise ValueError(
                    f"caller-supplied final_decision {final_decision!r} "
                    f"disagrees with aggregator output "
                    f"{result.final_decision!r}; caller override is "
                    f"not allowed (audit §REQ-REVIEW-02)"
                )

        self.status = STATUS_CLOSED
        self.closed_at = int(now if now is not None else time.time())
        self.aggregation = result
        return result

    def expire(self, *, now: int | None = None) -> bool:
        """Flip status to ``expired`` if past TTL.

        Returns True iff the set was flipped (i.e. was previously
        ``open`` and is now ``expired``). Idempotent — calling
        twice on an already-expired set returns False without
        raising.
        """
        if self.status == STATUS_CLOSED:
            return False
        if self.status == STATUS_EXPIRED:
            return False
        if not self.is_expired(now=now):
            return False
        self.status = STATUS_EXPIRED
        return True


# ─── Exceptions (v3.12.2 — REQ-REVIEW-01..03) ────────────────────────────────


class ReviewSetError(Exception):
    """Base class for ReviewSet failures."""


class ReviewSetClosed(ReviewSetError):
    """Raised when an operation requires an open ReviewSet but it
    is already closed."""


class ReviewSetExpired(ReviewSetError):
    """Raised when an operation requires an open ReviewSet but it
    is past its TTL."""


class ReviewerNotExpected(ReviewSetError):
    """Raised when a session that is not in the reviewers list
    tries to submit a review.

    v3.12.2 — security review HIGH #2: now carries BOTH the
    session_id and the caller-supplied principal so operators
    can distinguish "session not in reviewers list" from
    "session is in the list but supplied a wrong principal"
    (which is the companion ``ReviewerPrincipalMismatch``).
    """

    def __init__(
        self,
        set_id: str,
        session_id: str,
        principal: str,
        detail: str = "",
    ) -> None:
        self.set_id = set_id
        self.session_id = session_id
        self.principal = principal
        super().__init__(
            f"reviewer {session_id!r} (principal={principal!r}) "
            f"not in ReviewSet {set_id!r} reviewers list: "
            f"{detail}".strip()
        )


class ReviewerPrincipalMismatch(ReviewSetError):
    """Raised when a reviewer's session_id IS in the expected
    reviewers list but the caller-supplied ``reviewer_principal``
    disagrees with the bound principal in
    ``_expected_sessions_with_principals``.

    v3.12.2 — security review HIGH #2: closes the horizontal-
    privilege-escalation vector where a session bound to
    principal=A could submit a review attributed to principal=B
    by populating the request-body field. The ReviewSet looks
    up the expected principal from the trusted configuration
    (NOT from the caller-supplied field) and rejects mismatches
    BEFORE the review is written to ``self.reviews``.
    """

    def __init__(
        self,
        set_id: str,
        session_id: str,
        supplied_principal: str,
        detail: str = "",
    ) -> None:
        self.set_id = set_id
        self.session_id = session_id
        self.supplied_principal = supplied_principal
        super().__init__(
            f"ReviewSet {set_id!r}: reviewer {session_id!r} "
            f"supplied principal {supplied_principal!r} which "
            f"does not match the bound principal; {detail}".strip()
        )


def make_review_set_id() -> str:
    """Server-issued ULID-ish UUID hex (``rs_<uuid4hex>``)."""
    return f"rs_{uuid.uuid4().hex[:16]}"


__all__ = [
    "REVIEW_DECISION_ALLOW",
    "REVIEW_DECISION_DENY",
    "REVIEW_DECISION_NEEDS_REVISION",
    "VALID_REVIEW_DECISIONS",
    "STATUS_OPEN",
    "STATUS_CLOSED",
    "STATUS_EXPIRED",
    "VALID_REVIEW_SET_STATUSES",
    "AGGREGATE_ALLOW",
    "AGGREGATE_DENY",
    "AGGREGATE_ESCALATE",
    "VALID_AGGREGATE_DECISIONS",
    "Review",
    "AggregationResult",
    "ReviewSet",
    "ReviewSetError",
    "ReviewSetClosed",
    "ReviewSetExpired",
    "ReviewerNotExpected",
    "ReviewerPrincipalMismatch",
    "make_review_set_id",
]