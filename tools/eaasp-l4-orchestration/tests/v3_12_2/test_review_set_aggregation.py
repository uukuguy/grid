"""v3.12.2 — ReviewSet aggregation engine tests.

REQ-IDs: REVIEW-01..03 + CONFLICT-01..02 + SSE (a2a.review.closed).

Covers the ReviewSet aggregation engine + the 5-stage approval
integration shape end-to-end:
- 5 canonical aggregation scenarios (all allow / all deny / any
  needs_revision / multiple deny / mixed verdict).
- Conflict detection on shared evidence_ref.
- 5-stage approval integration: aggregator output is shaped to
  feed ``ApprovalStateMachine.resume_with_human_decision``.
- TTL expiry + post-close submission rejection.
- Reviewer-not-expected + principal-mismatch rejection.
- Security review HIGH #1: fail-open aggregation when expected
  reviewers are missing (single allow does NOT become
  unanimous allow).
- Security review HIGH #2: principal mismatch gate.
- Security review HIGH #3: principal-mismatch-vs-not-in-list
  distinction (companion to fix #2).
"""

from __future__ import annotations

import time

import pytest

from eaasp_l4_orchestration.review_set import (
    AGGREGATE_ALLOW,
    AGGREGATE_DENY,
    AGGREGATE_ESCALATE,
    Review,
    ReviewerNotExpected,
    ReviewerPrincipalMismatch,
    ReviewSet,
    ReviewSetClosed,
    ReviewSetExpired,
    REVIEW_DECISION_ALLOW,
    REVIEW_DECISION_DENY,
    REVIEW_DECISION_NEEDS_REVISION,
)

pytestmark = pytest.mark.asyncio


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _build_review_set(
    *,
    set_id: str,
    reviewer_sessions: list[tuple[str, str]],
    ttl_seconds: int = 3600,
) -> ReviewSet:
    """Build a fresh ``ReviewSet`` with the given reviewers."""
    return ReviewSet(
        set_id=set_id,
        room_id="er_lab01",
        initiator_principal="alice@example.com",
        initiator_session_id="sess_alice",
        reviewers=reviewer_sessions,
        ttl_seconds=ttl_seconds,
    )


def _submit(
    review_set: ReviewSet,
    *,
    principal: str,
    session_id: str,
    decision: str,
    evidence_refs: list[str] | None = None,
    payload: dict | None = None,
) -> bool:
    """Helper to submit a review via the ReviewSet API."""
    return review_set.submit_review(
        Review(
            reviewer_principal=principal,
            reviewer_session_id=session_id,
            decision=decision,
            payload=payload or {},
            evidence_refs=evidence_refs or [],
        )
    )


# ─── Aggregation scenario tests (5 canonical) ────────────────────────────────


async def test_aggregation_all_allow_yields_allow() -> None:
    """REVIEW-01: all reviewers decide allow → AGGREGATE_ALLOW."""
    rs = _build_review_set(
        set_id="rs_all_allow",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(rs, principal="bob", session_id="sess_bob", decision=REVIEW_DECISION_ALLOW)
    _submit(rs, principal="carol", session_id="sess_carol", decision=REVIEW_DECISION_ALLOW)
    result = rs.aggregate()
    assert result.final_decision == AGGREGATE_ALLOW
    assert result.conflict_detected is False
    assert result.conflicting_pairs == []
    assert result.synthesis_required is False
    assert "unanimous" in result.aggregate_reason or "all" in result.aggregate_reason


async def test_aggregation_all_deny_yields_deny() -> None:
    """REVIEW-01: all reviewers decide deny → AGGREGATE_DENY."""
    rs = _build_review_set(
        set_id="rs_all_deny",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(rs, principal="bob", session_id="sess_bob", decision=REVIEW_DECISION_DENY)
    _submit(rs, principal="carol", session_id="sess_carol", decision=REVIEW_DECISION_DENY)
    result = rs.aggregate()
    assert result.final_decision == AGGREGATE_DENY
    assert result.conflict_detected is False
    assert result.conflicting_pairs == []
    assert result.synthesis_required is False


async def test_aggregation_any_needs_revision_yields_escalate() -> None:
    """REVIEW-01: any needs_revision → AGGREGATE_ESCALATE (wins over allow/deny)."""
    rs = _build_review_set(
        set_id="rs_needs_revision",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(rs, principal="bob", session_id="sess_bob", decision=REVIEW_DECISION_ALLOW)
    _submit(
        rs,
        principal="carol",
        session_id="sess_carol",
        decision=REVIEW_DECISION_NEEDS_REVISION,
    )
    result = rs.aggregate()
    assert result.final_decision == AGGREGATE_ESCALATE
    assert result.synthesis_required is True


async def test_aggregation_multiple_deny_supersedes_single_allow() -> None:
    """REVIEW-01 / ADR-V2-035: 2+ deny + 1+ allow → AGGREGATE_DENY."""
    rs = _build_review_set(
        set_id="rs_multi_deny",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
            ("sess_dave", "dave"),
        ],
    )
    _submit(rs, principal="bob", session_id="sess_bob", decision=REVIEW_DECISION_ALLOW)
    _submit(rs, principal="carol", session_id="sess_carol", decision=REVIEW_DECISION_DENY)
    _submit(rs, principal="dave", session_id="sess_dave", decision=REVIEW_DECISION_DENY)
    result = rs.aggregate()
    assert result.final_decision == AGGREGATE_DENY
    assert result.synthesis_required is False
    assert "majority-deny" in result.aggregate_reason


async def test_aggregation_mixed_allow_deny_yields_escalate() -> None:
    """REVIEW-01: 1 deny + 1+ allow (no needs_revision) → AGGREGATE_ESCALATE."""
    rs = _build_review_set(
        set_id="rs_mixed",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(rs, principal="bob", session_id="sess_bob", decision=REVIEW_DECISION_ALLOW)
    _submit(rs, principal="carol", session_id="sess_carol", decision=REVIEW_DECISION_DENY)
    result = rs.aggregate()
    assert result.final_decision == AGGREGATE_ESCALATE
    assert result.synthesis_required is True
    assert "mixed" in result.aggregate_reason


# ─── Conflict detection tests ────────────────────────────────────────────────


async def test_aggregation_conflict_detected_on_shared_evidence() -> None:
    """CONFLICT-01: 2+ reviewers cite same evidence with different decisions
    → conflict_detected=True + conflicting_pairs populated."""
    rs = _build_review_set(
        set_id="rs_conflict",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(
        rs,
        principal="bob",
        session_id="sess_bob",
        decision=REVIEW_DECISION_ALLOW,
        evidence_refs=["shared_anchor"],
    )
    _submit(
        rs,
        principal="carol",
        session_id="sess_carol",
        decision=REVIEW_DECISION_DENY,
        evidence_refs=["shared_anchor"],
    )
    result = rs.aggregate()
    assert result.conflict_detected is True
    assert ("sess_bob", "sess_carol") in result.conflicting_pairs
    assert result.synthesis_required is True


async def test_aggregation_no_conflict_on_distinct_evidence() -> None:
    """CONFLICT-02: distinct evidence_refs → no conflict detected."""
    rs = _build_review_set(
        set_id="rs_no_conflict",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(
        rs,
        principal="bob",
        session_id="sess_bob",
        decision=REVIEW_DECISION_ALLOW,
        evidence_refs=["bob_anchor"],
    )
    _submit(
        rs,
        principal="carol",
        session_id="sess_carol",
        decision=REVIEW_DECISION_DENY,
        evidence_refs=["carol_anchor"],
    )
    result = rs.aggregate()
    assert result.conflict_detected is False
    assert result.conflicting_pairs == []


async def test_aggregation_conflict_pairs_sorted() -> None:
    """CONFLICT-01: conflicting_pairs are returned sorted for deterministic
    downstream consumption."""
    rs = _build_review_set(
        set_id="rs_conflict_sorted",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(
        rs,
        principal="bob",
        session_id="sess_bob",
        decision=REVIEW_DECISION_ALLOW,
        evidence_refs=["shared"],
    )
    _submit(
        rs,
        principal="carol",
        session_id="sess_carol",
        decision=REVIEW_DECISION_DENY,
        evidence_refs=["shared"],
    )
    result = rs.aggregate()
    # conflicting_pairs should be sorted ascending by session_id.
    assert result.conflicting_pairs == sorted(result.conflicting_pairs)


# ─── Status lifecycle tests ──────────────────────────────────────────────────


async def test_close_persists_aggregation() -> None:
    """REVIEW-02: close() flips status to closed + stores AggregationResult."""
    rs = _build_review_set(
        set_id="rs_close",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(rs, principal="bob", session_id="sess_bob", decision=REVIEW_DECISION_ALLOW)
    _submit(rs, principal="carol", session_id="sess_carol", decision=REVIEW_DECISION_ALLOW)
    result = rs.close()
    assert rs.status == "closed"
    assert rs.closed_at is not None
    assert rs.aggregation is result
    assert result.final_decision == AGGREGATE_ALLOW


async def test_close_after_close_raises() -> None:
    """REVIEW-02: closing a closed ReviewSet raises ReviewSetClosed."""
    rs = _build_review_set(
        set_id="rs_close_again",
        reviewer_sessions=[("sess_bob", "bob")],
    )
    _submit(rs, principal="bob", session_id="sess_bob", decision=REVIEW_DECISION_ALLOW)
    rs.close()
    with pytest.raises(ReviewSetClosed):
        rs.close()


async def test_submit_after_close_raises() -> None:
    """REVIEW-01: submit_review on a closed set raises ReviewSetClosed."""
    rs = _build_review_set(
        set_id="rs_submit_closed",
        reviewer_sessions=[("sess_bob", "bob")],
    )
    _submit(rs, principal="bob", session_id="sess_bob", decision=REVIEW_DECISION_ALLOW)
    rs.close()
    with pytest.raises(ReviewSetClosed):
        _submit(
            rs,
            principal="bob",
            session_id="sess_bob",
            decision=REVIEW_DECISION_DENY,
        )


async def test_submit_after_expiry_raises() -> None:
    """REVIEW-01: submit_review on a TTL-expired set raises ReviewSetExpired."""
    rs = _build_review_set(
        set_id="rs_submit_expired",
        reviewer_sessions=[("sess_bob", "bob")],
        ttl_seconds=1,
    )
    # Force expiry by advancing wall clock.
    time.sleep(1.1)
    with pytest.raises(ReviewSetExpired):
        _submit(
            rs,
            principal="bob",
            session_id="sess_bob",
            decision=REVIEW_DECISION_ALLOW,
        )


async def test_expire_flips_status_on_ttl_breach() -> None:
    """REVIEW-01: expire() flips status to expired after TTL."""
    rs = _build_review_set(
        set_id="rs_expire",
        reviewer_sessions=[("sess_bob", "bob")],
        ttl_seconds=1,
    )
    assert rs.status == "open"
    time.sleep(1.1)
    flipped = rs.expire()
    assert flipped is True
    assert rs.status == "expired"


async def test_expire_is_idempotent_on_already_expired() -> None:
    """REVIEW-01: expire() returns False on an already-expired set."""
    rs = _build_review_set(
        set_id="rs_expire_idem",
        reviewer_sessions=[("sess_bob", "bob")],
        ttl_seconds=1,
    )
    time.sleep(1.1)
    assert rs.expire() is True
    assert rs.expire() is False


async def test_close_after_expiry_raises() -> None:
    """REVIEW-02: close() on an expired set raises ReviewSetExpired."""
    rs = _build_review_set(
        set_id="rs_close_expired",
        reviewer_sessions=[("sess_bob", "bob")],
        ttl_seconds=1,
    )
    _submit(rs, principal="bob", session_id="sess_bob", decision=REVIEW_DECISION_ALLOW)
    time.sleep(1.1)
    with pytest.raises(ReviewSetExpired):
        rs.close()


# ─── Reviewer authorization tests ─────────────────────────────────────────────


async def test_submit_reviewer_not_in_list_raises() -> None:
    """REVIEW-01: session_id not in reviewers → ReviewerNotExpected."""
    rs = _build_review_set(
        set_id="rs_unexpected",
        reviewer_sessions=[("sess_bob", "bob")],
    )
    with pytest.raises(ReviewerNotExpected):
        _submit(
            rs,
            principal="carol",
            session_id="sess_carol",
            decision=REVIEW_DECISION_ALLOW,
        )


async def test_submit_principal_mismatch_raises() -> None:
    """REVIEW-01 + security review HIGH #2: caller-supplied principal
    disagrees with bound principal → ReviewerPrincipalMismatch."""
    rs = _build_review_set(
        set_id="rs_principal_mismatch",
        reviewer_sessions=[("sess_bob", "bob")],
    )
    with pytest.raises(ReviewerPrincipalMismatch):
        _submit(
            rs,
            principal="eve",  # wrong principal; session is bound to bob
            session_id="sess_bob",
            decision=REVIEW_DECISION_ALLOW,
        )


async def test_submit_replacement_is_latest_wins() -> None:
    """REVIEW-01: same session resubmits → latest decision wins (returns False)."""
    rs = _build_review_set(
        set_id="rs_latest_wins",
        reviewer_sessions=[("sess_bob", "bob")],
    )
    is_new1 = _submit(
        rs,
        principal="bob",
        session_id="sess_bob",
        decision=REVIEW_DECISION_ALLOW,
    )
    assert is_new1 is True
    is_new2 = _submit(
        rs,
        principal="bob",
        session_id="sess_bob",
        decision=REVIEW_DECISION_DENY,
    )
    assert is_new2 is False
    assert rs.reviews["sess_bob"].decision == REVIEW_DECISION_DENY


# ─── Security regression tests (3 required) ──────────────────────────────────


async def test_security_regression_fail_open_aggregation_single_allow() -> None:
    """REVIEW-03 / security review HIGH #1 — fail-open aggregation.

    Regression test: a single allow from one of three expected
    reviewers must NOT produce AGGREGATE_ALLOW. The aggregator
    must return AGGREGATE_ESCALATE because unanimity requires
    every expected reviewer's input.
    """
    rs = _build_review_set(
        set_id="rs_regression_fail_open",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
            ("sess_dave", "dave"),
        ],
    )
    # Only bob submits.
    _submit(
        rs,
        principal="bob",
        session_id="sess_bob",
        decision=REVIEW_DECISION_ALLOW,
        evidence_refs=["a1"],
    )
    result = rs.aggregate()
    assert result.final_decision == AGGREGATE_ESCALATE, (
        f"expected ESCALATE (missing reviewers), got "
        f"{result.final_decision!r}"
    )
    assert result.synthesis_required is True
    assert "have not submitted" in result.aggregate_reason
    assert "sess_carol" in result.aggregate_reason
    assert "sess_dave" in result.aggregate_reason


async def test_security_regression_principal_mismatch_rejected() -> None:
    """REVIEW-01 / security review HIGH #2 — principal mismatch.

    Regression test: a session that IS in the reviewers list
    but supplies a principal that disagrees with the bound
    principal must be rejected with ReviewerPrincipalMismatch
    BEFORE the review is written to self.reviews.
    """
    rs = _build_review_set(
        set_id="rs_regression_principal",
        reviewer_sessions=[("sess_bob", "bob")],
    )
    with pytest.raises(ReviewerPrincipalMismatch) as exc_info:
        _submit(
            rs,
            principal="eve",
            session_id="sess_bob",
            decision=REVIEW_DECISION_ALLOW,
        )
    # The review must NOT have been written.
    assert "sess_bob" not in rs.reviews
    # The exception message must name both principals for
    # operator diagnostics.
    msg = str(exc_info.value)
    assert "sess_bob" in msg
    assert "eve" in msg
    assert "bob" in msg


async def test_security_regression_missing_reviewer_escalates() -> None:
    """REVIEW-03 / security review HIGH #1 — missing reviewer escalates.

    Regression test: when 1 of 2 expected reviewers submits
    deny and the other has not submitted, the aggregator must
    return AGGREGATE_ESCALATE (not AGGREGATE_DENY) because
    unanimity is not decidable.
    """
    rs = _build_review_set(
        set_id="rs_regression_missing",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(
        rs,
        principal="bob",
        session_id="sess_bob",
        decision=REVIEW_DECISION_DENY,
        evidence_refs=["a1"],
    )
    # carol has not submitted.
    result = rs.aggregate()
    assert result.final_decision == AGGREGATE_ESCALATE, (
        f"expected ESCALATE (carol missing), got "
        f"{result.final_decision!r}"
    )
    assert result.synthesis_required is True
    assert "sess_carol" in result.aggregate_reason


# ─── 5-stage approval integration shape ──────────────────────────────────────


async def test_aggregation_output_feeds_approval_resume() -> None:
    """REVIEW-03 / SSE: aggregator output is shaped to feed
    ``ApprovalStateMachine.resume_with_human_decision``.

    The aggregator returns one of {allow, deny, escalate} —
    the v3.11.2 resume_with_human_decision accepts {allow, deny}.
    escalate maps to the human-in-the-loop resume decision
    (the aggregator's escalate result indicates that a human
    must arbitrate the chain).
    """
    rs = _build_review_set(
        set_id="rs_approval_resume",
        reviewer_sessions=[
            ("sess_bob", "bob"),
            ("sess_carol", "carol"),
        ],
    )
    _submit(
        rs,
        principal="bob",
        session_id="sess_bob",
        decision=REVIEW_DECISION_ALLOW,
        evidence_refs=["evidence_x"],
    )
    _submit(
        rs,
        principal="carol",
        session_id="sess_carol",
        decision=REVIEW_DECISION_ALLOW,
        evidence_refs=["evidence_x"],
    )
    result = rs.aggregate()
    # The aggregator's allow/deny is consumable by the L3
    # approval resume; escalate signals the API layer to
    # route through the human-in-the-loop path.
    assert result.final_decision in {"allow", "deny", "escalate"}
    assert result.set_id == "rs_approval_resume"
    assert result.aggregated_at > 0