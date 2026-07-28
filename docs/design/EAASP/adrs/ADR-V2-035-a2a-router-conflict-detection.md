---
adr_id: ADR-V2-035
title: A2A Router conflict-detection algorithm + ReviewSet aggregation rules
status: Accepted
date: 2026-07-28
phase: 4
deciders: Jiangwen Su + Claude
related:
  - ADR-V2-034 (OPA sidecar topology)
  - ADR-V2-024 (Dual-axis model — engine 接入面 / Grid 独立产品)
  - ADR-V2-023 P1 (Shared-core rule)
  - ADR-V2-022 (ADR governance meta-ADR)
  - EVOLUTION_PATH §三 Phase 4
  - EAASP v2.0 spec §14 (multi-agent review coordination)
  - EAASP v2.0 spec §15.9 (deny-always-wins)
  - V310-A2A-01 (DEFERRED_LEDGER, 2026-05-24 baseline)
---

# ADR-V2-035 — A2A Router Conflict-Detection Algorithm + ReviewSet Aggregation Rules

## Context

v3.12.1 SHIPPED the Event Room + MultiSessionCoordinator (long-lived
coordination namespace spanning multiple sessions). v3.12.2 builds on
top to deliver the A2A Router + ReviewSet aggregation engine
(`tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/a2a_router.py`
+ `review_set.py`). The A2A Router lets multiple sessions in a shared
Event Room exchange typed A2A messages through the room's append-only
event log; the ReviewSet is the coordination primitive for multi-reviewer
review flows (one initiator session opens a review, N reviewer sessions
submit independent decisions via A2A, the aggregation engine collects
the decisions, detects contradictions, and produces a final aggregated
decision).

Two candidate aggregation algorithm shapes were on the table:

- **majority-deny + shared-evidence conflict detection** — every
  reviewer's decision is recorded verbatim; the aggregator detects
  shared-evidence contradictions (2+ reviewers citing the same
  `evidence_ref` with different decisions) and applies a
  majority-deny rule (2+ deny + 1+ allow → AGGREGATE_DENY) + a
  review_synthesis escalation (mixed verdict OR conflict_detected
  → AGGREGATE_ESCALATE / `a2a.conflict.detected` SSE event).
- **single-reviewer wins (last-submitter-wins)** — simpler model where
  the last reviewer's decision is the final verdict. Easier to
  implement but does not handle the multi-reviewer case correctly
  (the initiator's review is over-weighted relative to the
  reviewers').

v3.12.2 picks **majority-deny + shared-evidence conflict detection**.
The simpler model fails to surface the spec §15.9 deny-always-wins
invariant (which mandates that ANY deny short-circuits the chain;
the multi-reviewer generalization is "2+ deny + 1+ allow →
AGGREGATE_DENY").

## Decision

EAASP v3.12.2 A2A Router ships with the **majority-deny + shared-evidence
conflict detection** algorithm. The algorithm has three parts:

### 1. Completeness gate (fail-open aggregation)

Before counting decisions, the aggregator compares
``set(self.reviews)`` against ``expected_reviewer_session_ids()``.
If ANY expected reviewer has NOT submitted, the aggregator returns
``AGGREGATE_ESCALATE`` immediately with ``synthesis_required=True``.
A single ``allow`` from one of N expected reviewers is NOT a
unanimous verdict; the aggregation engine refuses to produce a
terminal ``allow``/``deny`` until every reviewer has spoken.

This is the **security review HIGH #1** fix: prior shape treated a
single allow as a unanimous allow, which is a fail-open
authorization vector.

### 2. Conflict detection on shared evidence

The aggregator builds a map of ``evidence_ref`` →
``[(session_id, decision), ...]``. If any single ``evidence_ref``
has 2+ reviews with DIFFERENT decisions:

- ``conflict_detected = True``
- ``conflicting_pairs`` populated with sorted
  ``(session_id_a, session_id_b)`` tuples (deterministic ordering
  so SSE consumers see a stable payload).
- The router emits an ``a2a.conflict.detected`` SSE event from
  both ``aggregate_review_set`` and ``close_review_set``.

Conflict detection is purely structural — the aggregator does not
run any L3 hookup. The ``a2a.conflict.detected`` event is the
cross-session visibility layer; downstream code (the API layer in
03.12.3 live walkthrough) decides how to escalate to human-in-the-
loop arbitration.

### 3. Aggregation rules (5 canonical scenarios + 1 mixed-verdict)

After the completeness gate passes and conflict detection runs, the
aggregator applies the rules in priority order:

1. **Any needs_revision** → ``AGGREGATE_ESCALATE``. Per v3.12.2
   spec §14.4, needs_revision requests human-in-the-loop
   arbitration; a deny that accompanies needs_revision is a
   "deny-with-revision" — still escalation, not deny.
2. **All allow** → ``AGGREGATE_ALLOW``. Unanimous.
3. **All deny** → ``AGGREGATE_DENY``. Unanimous.
4. **2+ deny + 1+ allow** → ``AGGREGATE_DENY`` (majority-deny rule
   per spec §15.9 generalization). 2 denies supersede 1 allow.
5. **1 deny + 1+ allow (no needs_revision)** → ``AGGREGATE_ESCALATE``.
   Mixed verdict; human arbitration required.

The aggregator output ``final_decision`` (``allow`` / ``deny`` /
``escalate``) is consumable by the L3 5-stage approval chain via
``ApprovalStateMachine.resume_with_human_decision(...)`` — ``allow`` /
``deny`` map directly to the human verdict; ``escalate`` routes
through the human-in-the-loop path (the API layer in 03.12.3 wires
this up; v3.12.2 keeps the structural fan-out only per D-25).

### 4. Synthesis flag

``synthesis_required = conflict_detected OR final_decision ==
AGGREGATE_ESCALATE``. Downstream code uses this flag to decide
whether to route the aggregation result through the human-in-the-
loop path.

## Consequences

Positive:

- The deny-always-wins invariant (spec §15.9) is preserved at the
  multi-reviewer layer: 2+ deny + 1+ allow → DENY.
- Shared-evidence contradictions are surfaced explicitly via the
  ``a2a.conflict.detected`` SSE event so SSE consumers can dispatch
  the conflict to downstream handlers.
- The fail-open aggregation gate prevents a single allow from being
  treated as unanimous (security review HIGH #1).

Negative:

- The aggregator is more complex than a simple last-submitter-wins
  model; tests must cover all 5 canonical scenarios + the
  fail-open gate.
- The ``a2a.conflict.detected`` event adds 1 SSE event type to the
  room-scoped stream; SSE consumers must subscribe to it.

## Alternatives considered

- **Single-reviewer wins (last-submitter-wins)**: rejected because
  it does not handle the multi-reviewer case correctly. The
  initiator's review is over-weighted relative to the reviewers';
  the spec §15.9 deny-always-wins invariant is not preserved.

- **Unanimous-only verdict (reject if not unanimous)**:
  rejected because it conflates two distinct failure modes
  ("absent reviewer" vs. "needs_revision" vs. "mixed verdict")
  into a single AGGREGATE_ESCALATE result. The chosen shape
  distinguishes these via the 3-state ``final_decision`` +
  ``conflict_detected`` flag + ``synthesis_required`` flag.

## Implementation

- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/review_set.py`
  — ``ReviewSet.aggregate()`` implements the algorithm. The cached
  ``_expected_sessions_with_principals`` map is built in
  ``__post_init__`` so the completeness-gate lookup is O(1).
- `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/a2a_router.py`
  — ``A2ARouter.aggregate_review_set`` + ``close_review_set`` emit the
  ``a2a.conflict.detected`` + ``a2a.review.closed`` SSE events when
  conflict is detected.
- `tools/eaasp-l4-orchestration/tests/v3_12_2/test_review_set_aggregation.py`
  — 23 tests covering the 5 canonical aggregation scenarios + conflict
  detection + 3 security regression tests (HIGH #1 fail-open +
  HIGH #2 principal mismatch + HIGH #1 missing-reviewer escalates).
- `tools/eaasp-l4-orchestration/tests/v3_12_2/test_a2a_router.py` —
  16 tests covering the A2A Router end-to-end + conflict detection
  emits ``a2a.conflict.detected`` SSE event.
- `tools/eaasp-l4-orchestration/tests/v3_12_2/test_a2a_sse.py` —
  12 tests covering the 5 A2A SSE event types + coexistence with
  the v3.11.2 ``governance.approval.*`` family.

## Implementation status

- v3.12.2 (this ADR + ReviewSet aggregation engine + A2A Router
  + 5 A2A SSE event types + 51 targeted tests) — completed and
  shipped on top of v3.12.1 (`a248d73a`). ADR-V2-035 is Accepted.
  Shared-core preserved (ADR-V2-023 P1): no changes under
  `crates/grid-engine`, `grid-runtime`, `grid-types`,
  `grid-sandbox`, `grid-hook-bridge`. v3.9 RBAC audit (134 routes)
  + v3.10 spec-audit (4 files / 37 rows) still PASS. OPA sidecar
  topology (ADR-V2-034) unchanged.

## References

- EVOLUTION_PATH §三 Phase 4 — A2A Router + Event Room + multi-session
- EAASP v2.0 spec §14 — Multi-agent review coordination
- EAASP v2.0 spec §15.9 — Deny-always-wins
- ADR-V2-023 P1 — Shared-core rule
- ADR-V2-024 — Dual-axis model (engine 接入面 / Grid 独立产品)
- ADR-V2-034 — OPA sidecar deployment topology

- v3.12.3 single-point live walkthrough — `docs/status/PRODUCTION_USABILITY_2026-07-28.md`
  exercises the conflict-detection algorithm end-to-end against a real
  OPA sidecar: Reviewer A submitted `decision=allow` +
  `evidence_refs=["anchor-transformer-spec-v3_12_3"]`; Reviewer B
  submitted `decision=needs_revision` + the same shared
  `anchor-transformer-spec-v3_12_3` evidence ref. `aggregate_review_set`
  returned `final_decision="escalate"` `conflict_detected=True`
  `synthesis_required=True` `conflicting_pairs=[(sess_reviewer_a_v3_12_3, sess_reviewer_b_v3_12_3)]`,
  emitting `a2a.conflict.detected` SSE event. `close_review_set`
  re-emitted the same aggregate. The 5-stage chain resumed via
  `human_decision=ALLOW` to `final_decision="approve"`, exercising the
  end-to-end majority-deny + review-synthesis arbitration paths.
  ADR-V2-035 implementation: **SHIPPED at 2026-07-28**.
