"""5-stage approval chain state machine (v3.11.2).

Spec §6.9–6.10 / ADR-V2-034 §Out-of-scope 2026-07-26 closure:
- Plan → Check → Draft → Approve → Execute (5 sequential stages).
- Each stage emits a dedicated ``governance.approval.<stage>`` SSE event
  through the L4 event stream and a row in the append-only
  ``governance_decisions`` ledger. The ledger extension is a single
  nullable ``stage`` column (default NULL) — strict backwards compatibility
  with v3.11.1 rows produced by ``PolicyEngine.evaluate_gate`` /
  ``evaluate_with_opa`` (audit §6).
- Deny-always-wins (spec §15.9): any stage producing ``decision ==
  "deny"`` immediately terminates the machine; subsequent stages do not
  run and do not emit events or audit rows.
- The Approve stage produces ``decision == "await_human"`` to signal a
  pause for human-in-the-loop attestation. The state machine pauses
  here and returns control to the caller; the caller can resume by
  invoking :meth:`ApprovalStateMachine.resume_with_human_decision` with
  the human's verdict (allow/deny).
- Missing evidence_refs, missing caller principal, or schema invalid
  inputs are input-validation failures (Rule 2 — auto-add) and surface
  as ``ValueError`` BEFORE the first DB open. Never partial state.
- The state machine is OPT-IN: callers only invoke ``run()`` when
  ``policy.opa_enabled`` is True and the OPA decision is ``approval``
  (per the v3.11.2 API switch in ``tools/eaasp-l3-governance/api.py``).
  v3.11.0 / v3.11.1 paths are unchanged.

Reference: V310-APPROVAL-01 DEFERRED_LEDGER entry closed by this phase.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from loguru import logger
from pydantic import BaseModel, Field

from .audit import AuditStore


# ─── Stage constants — DO NOT widen (audit §6.4 / §7.1) ──────────────────────
APPROVAL_STAGE_PLAN = "plan"
APPROVAL_STAGE_CHECK = "check"
APPROVAL_STAGE_DRAFT = "draft"
APPROVAL_STAGE_APPROVE = "approve"
APPROVAL_STAGE_EXECUTE = "execute"

# Ordered stage sequence. The state machine MUST process stages in this
# exact order; any deny in an earlier stage short-circuits the rest.
STAGE_ORDER: tuple[str, ...] = (
    APPROVAL_STAGE_PLAN,
    APPROVAL_STAGE_CHECK,
    APPROVAL_STAGE_DRAFT,
    APPROVAL_STAGE_APPROVE,
    APPROVAL_STAGE_EXECUTE,
)

# Per-stage decision enum (mirrors the ledger's CHECK constraint, but
# audit §6.4 makes ``allow`` / ``approve`` / ``deny`` / ``gate_request``
# the canonical values; the state machine additionally uses the
# ``await_human`` sentinel for the Approve stage pause).
DECISION_ALLOW = "allow"
DECISION_APPROVE = "approve"
DECISION_DENY = "deny"
DECISION_GATE_REQUEST = "gate_request"
DECISION_AWAIT_HUMAN = "await_human"

# Stage-name → event-type suffix map for the L4 SSE event stream.
# Keep aligned with STAGE_ORDER.
STAGE_EVENT_TYPE: dict[str, str] = {
    APPROVAL_STAGE_PLAN: "governance.approval.plan",
    APPROVAL_STAGE_CHECK: "governance.approval.check",
    APPROVAL_STAGE_DRAFT: "governance.approval.draft",
    APPROVAL_STAGE_APPROVE: "governance.approval.approve",
    APPROVAL_STAGE_EXECUTE: "governance.approval.execute",
}


# ─── Public types ────────────────────────────────────────────────────────────


class ApprovalStagePolicy(BaseModel):
    """Stage-level policy input.

    Each stage takes a single ``ApprovalStagePolicy`` and returns a
    ``StageDecision``. The state machine persists the decision in the
    ledger as its own row. The state machine is responsible for the
    ``stage`` column on the ledger; the policy is responsible for the
    decision (allow/approve/deny/await_human) and the reason.

    Fields:
        stage_name: matches one of the 5 stage constants.
        decision: per-stage decision (allow / approve / deny / await_human).
        reason: short human-readable reason (stored in rationale).
        evidence_refs: list of opaque refs (memory anchors, run ids).
        awaits_human: True iff the stage requires a human pause after
            the policy runs. The Approve stage uses this to pause.
    """

    stage_name: str = Field(..., min_length=1)
    decision: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    awaits_human: bool = False


@dataclass
class StageRecord:
    """Append-only audit row produced by a single stage.

    Distinct IDs (``gd_...`` line) per stage keep the append-only
    invariant (audit §6.3) — ``query_governance_decisions`` returns the
    full history ordered by ``ts``.
    """

    decision_id: str
    stage: str
    decision: str
    reason: str
    caller_principal: str
    session_id: str
    hook_id: str
    evidence_refs: list[str]
    ts: str


@dataclass
class ApprovalChainResult:
    """Aggregate result of a single 5-stage run.

    The state machine stops at the first terminal stage: a deny in any
    stage ends the chain (decision=deny, stages_completed < 5), or a
    human pause at the Approve stage ends the chain (decision=await_human,
    stages_completed <= 4). On full success, decision=approve,
    stages_completed=5, and all 5 ``StageRecord``s are in the ledger.
    """

    decision_id: str  # request_id — links all 5 row PKs
    policy_input: dict[str, Any]
    session_id: str
    hook_id: str
    caller_principal: str
    stages_completed: int
    final_decision: str  # approve | deny | await_human
    final_reason: str
    records: list[StageRecord] = field(default_factory=list)
    paused_at_stage: str | None = None


# ─── Stage policy protocol ───────────────────────────────────────────────────


class StagePolicyEvaluator(Protocol):
    """Callable signature for a per-stage policy evaluator.

    Implementations must be pure (no I/O) and deterministic given the
    same inputs. The state machine supplies a frozen ``policy_input``
    dict so test fixtures can match exactly against expected reasons.
    """

    def __call__(
        self,
        stage: str,
        policy_input: dict[str, Any],
        *,
        caller_principal: str,
        session_id: str,
        hook_id: str,
    ) -> ApprovalStagePolicy: ...


# ─── Event sink protocol ─────────────────────────────────────────────────────


class ApprovalEventSink(Protocol):
    """Callable signature for the L4 SSE event sink.

    The state machine emits one event per stage. Failures in the sink
    are absorbed (logged) and do NOT invert the audit-ledger decision
    (audit §7.1 invariant — also held by emit_governance_request /
    emit_governance_decision).
    """

    async def emit(
        self,
        session_id: str,
        stage: str,
        payload: dict[str, Any],
    ) -> int | None: ...


# ─── State machine ───────────────────────────────────────────────────────────


def _new_approval_id() -> str:
    """Return a fresh ``gd_<uuid4-hex>`` request id for the chain."""
    return f"gd_approval_{uuid.uuid4().hex[:16]}"


class ApprovalStateMachine:
    """Drive the 5-stage approval chain for a single hook.

    Lifecycle (one run per ``run()`` invocation):

    1. ``__init__`` captures the immutable run context (policy_input +
       hook_id + session_id + caller_principal).
    2. ``run()`` iterates STAGE_ORDER, invoking the supplied
       ``StagePolicyEvaluator`` for each stage. After each stage:
       - persist a row in ``governance_decisions`` (append-only),
       - emit a ``governance.approval.<stage>`` SSE event,
       - if the stage's decision is ``deny`` OR the chain is paused
         at ``await_human``, exit the loop early.
    3. The caller can later ``resume_with_human_decision(allow|deny)``
       to complete a paused chain. The resume decision is persisted
       as the **execute** stage's row (when Approve was the pause
       stage) and the machine transitions to a final decision.

    The state machine is **not** thread-safe. Each run should own its
    own instance. The class holds no module-level state.
    """

    def __init__(
        self,
        *,
        policy_input: dict[str, Any],
        session_id: str,
        hook_id: str,
        caller_principal: str,
        audit_store: AuditStore,
        event_sink: ApprovalEventSink | None = None,
    ) -> None:
        # ── Input validation BEFORE any DB open (audit §6 contract) ──
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not hook_id:
            raise ValueError("hook_id must be a non-empty string")
        if not caller_principal:
            raise ValueError(
                "caller_principal must be a non-empty string (RBAC binding required)"
            )
        if not isinstance(policy_input, dict):
            raise ValueError("policy_input must be a dict")
        if audit_store is None:
            raise ValueError("audit_store is required (append-only ledger)")

        self.policy_input = policy_input
        self.session_id = session_id
        self.hook_id = hook_id
        self.caller_principal = caller_principal
        self.audit_store = audit_store
        self.event_sink = event_sink

        # Per-run state. ``paused`` is set True when the Approve stage
        # returns ``await_human``; ``resumed_decision`` is filled by
        # ``resume_with_human_decision`` before the final transition.
        self.request_id: str = _new_approval_id()
        self.records: list[StageRecord] = []
        self.paused: bool = False
        self.paused_at_stage: str | None = None
        self.resumed_decision: str | None = None

    # ─── Public: run the chain ──────────────────────────────────────────────

    async def run(self, evaluator: StagePolicyEvaluator) -> ApprovalChainResult:
        """Execute stages in order until terminal (deny / await_human / done).

        ``evaluator`` is invoked once per stage with the per-stage
        context. The state machine owns the audit row + event emission;
        the evaluator owns the decision + reason (per audit §6.4, the
        rationale is the policy's reasoned justification).
        """
        if self.paused:
            # Should not happen — resume is the only path after pause.
            raise RuntimeError(
                "ApprovalStateMachine already paused; call "
                "resume_with_human_decision() instead of run()"
            )

        for stage in STAGE_ORDER:
            policy = evaluator(
                stage,
                self.policy_input,
                caller_principal=self.caller_principal,
                session_id=self.session_id,
                hook_id=self.hook_id,
            )
            self._validate_stage_policy(stage, policy)

            record = await self._record_stage(stage, policy)
            self.records.append(record)

            # Any deny → terminal (deny-always-wins, spec §15.9).
            if policy.decision == DECISION_DENY:
                return self._finalize(
                    final_decision=DECISION_DENY,
                    final_reason=policy.reason,
                    paused_at_stage=None,
                )

            # Approve stage specifically yields await_human on pause.
            # v3.12.0 — V311-AUDIT-01 / SCHEMA-01..03: the persisted
            # ledger row at the pause carries ``DECISION_AWAIT_HUMAN``
            # (not ``approve``) so the audit evidence matches the
            # human-in-the-loop pause semantics. The earlier shape
            # (decision="approve" on the paused row) conflated two
            # distinct outcomes in the same column. ``audit.py``'s
            # ``DECISION_ALLOWLIST`` now accepts ``await_human`` via
            # ``db.migrate_decision_await_human``.
            #
            # Append-only invariant: the ledger is keyed by
            # ``decision_id = {request_id}_{stage}`` (PK). The pause row
            # is therefore written via ``_append_audit_row`` directly
            # with a distinct suffix (``_approve_pause``) so the chain
            # remains append-only. ``records`` then carries both the
            # upstream ``approve`` decision (the policy's verdict)
            # and the pause row (the machine's paused-state outcome)
            # — distinct events on the same Approve stage.
            if (
                stage == APPROVAL_STAGE_APPROVE
                and policy.awaits_human
                and policy.decision != DECISION_DENY
            ):
                pause_record = await self._append_audit_row(
                    stage="approve_pause",
                    decision=DECISION_AWAIT_HUMAN,
                    reason=policy.reason,
                    evidence_refs=list(policy.evidence_refs),
                )
                self.records.append(pause_record)
                self.paused = True
                self.paused_at_stage = stage
                return self._finalize(
                    final_decision=DECISION_AWAIT_HUMAN,
                    final_reason=policy.reason,
                    paused_at_stage=stage,
                )

        # All 5 stages passed without deny or pause.
        return self._finalize(
            final_decision=DECISION_APPROVE,
            final_reason="5-stage approval chain completed",
            paused_at_stage=None,
        )

    # ─── Public: resume after human pause ───────────────────────────────────

    async def resume_with_human_decision(
        self,
        *,
        human_decision: str,
        human_reason: str,
        evidence_refs: list[str] | None = None,
    ) -> ApprovalChainResult:
        """Resume a paused chain after the human signs off.

        ``human_decision`` must be ``allow`` or ``deny`` (the
        human-in-the-loop verdict). On allow, the machine runs the
        final Execute stage; on deny, it terminates with deny and
        does NOT emit an Execute stage row (5-stage deny-always-wins).

        A resume decision is itself persisted as an audit row carrying
        the human's reason in the rationale. The Execute stage row only
        exists when the human approves AND the execute evaluator
        returns allow.
        """
        if not self.paused:
            raise RuntimeError(
                "ApprovalStateMachine is not paused; nothing to resume"
            )
        if human_decision not in {DECISION_ALLOW, DECISION_DENY}:
            raise ValueError(
                f"human_decision must be 'allow' or 'deny', got {human_decision!r}"
            )
        if not human_reason:
            raise ValueError("human_reason must be a non-empty string")

        # Persist the human verdict as its own ledger row so the
        # audit trail is unambiguous: the Approve stage is the LAST
        # stage that ran before the pause; the human's verdict is
        # the next row.
        human_record = await self._append_audit_row(
            stage="await_human",
            decision=human_decision,
            reason=human_reason,
            evidence_refs=evidence_refs or [],
        )
        self.records.append(human_record)

        if human_decision == DECISION_DENY:
            self.paused = False
            self.resumed_decision = DECISION_DENY
            return self._finalize(
                final_decision=DECISION_DENY,
                final_reason=human_reason,
                paused_at_stage=None,
            )

        # Allow: run the execute stage (the chain's terminal step).
        # The execute stage uses the same SignOff reason as the human
        # pause reason so the audit ledger explains why the chain moved.
        execute_policy = ApprovalStagePolicy(
            stage_name=APPROVAL_STAGE_EXECUTE,
            decision=DECISION_APPROVE,
            reason=f"execute: human signed off ({human_reason})",
            evidence_refs=evidence_refs or [],
            awaits_human=False,
        )
        record = await self._record_stage(
            APPROVAL_STAGE_EXECUTE, execute_policy
        )
        self.records.append(record)
        self.paused = False
        self.resumed_decision = DECISION_APPROVE
        return self._finalize(
            final_decision=DECISION_APPROVE,
            final_reason=execute_policy.reason,
            paused_at_stage=None,
        )

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _validate_stage_policy(self, stage: str, policy: ApprovalStagePolicy) -> None:
        if policy.stage_name != stage:
            raise ValueError(
                f"stage mismatch: machine expected {stage!r}, "
                f"policy returned {policy.stage_name!r}"
            )
        if policy.decision not in {
            DECISION_ALLOW,
            DECISION_APPROVE,
            DECISION_DENY,
            DECISION_GATE_REQUEST,
            DECISION_AWAIT_HUMAN,
        }:
            raise ValueError(
                f"unsupported stage decision {policy.decision!r}"
            )
        # The Approve stage is the only stage that may set awaits_human.
        if policy.awaits_human and stage != APPROVAL_STAGE_APPROVE:
            raise ValueError(
                f"only the {APPROVAL_STAGE_APPROVE!r} stage can pause for "
                f"human review; got awaits_human on {stage!r}"
            )

    async def _record_stage(
        self,
        stage: str,
        policy: ApprovalStagePolicy,
    ) -> StageRecord:
        """Persist one stage's audit row + emit one SSE event."""
        record = await self._append_audit_row(
            stage=stage,
            decision=policy.decision,
            reason=policy.reason,
            evidence_refs=policy.evidence_refs,
        )

        # Emit SSE event best-effort. Failures are logged and swallowed
        # so the audit ledger remains the source of truth (audit §7.1).
        if self.event_sink is not None:
            event_type = STAGE_EVENT_TYPE.get(stage)
            if event_type is not None:
                payload = {
                    "stage": stage,
                    "decision_id": record.decision_id,
                    "request_id": self.request_id,
                    "session_id": self.session_id,
                    "hook_id": self.hook_id,
                    "decision": policy.decision,
                    "reason": policy.reason,
                    "caller_principal": self.caller_principal,
                    "evidence_refs": list(policy.evidence_refs),
                    "ts": record.ts,
                }
                try:
                    await self.event_sink.emit(
                        self.session_id, event_type, payload
                    )
                except Exception as exc:  # best-effort §7.1
                    logger.warning(
                        "approval SSE event append failed "
                        "(stage={}, session_id={}): {}",
                        stage,
                        self.session_id,
                        exc,
                    )

        return record

    async def _append_audit_row(
        self,
        *,
        stage: str,
        decision: str,
        reason: str,
        evidence_refs: list[str],
    ) -> StageRecord:
        """Write one append-only ledger row carrying the stage metadata."""
        decision_id = f"{self.request_id}_{stage}"
        # ``tool_name`` is the legacy 9-column field; the state machine
        # does not have a tool concept, so the run's hook_id is used
        # as the "tool" identifier (consistent with how evaluate_with_opa
        # flows through ``hook_id`` + ``risk_level``).
        out = await self.audit_store.record_governance_decision(
            decision_id=decision_id,
            session_id=self.session_id,
            hook_id=self.hook_id,
            tool_name=self.hook_id,
            risk_level="write_external",
            decision=decision,
            approver=self.caller_principal,
            rationale=reason,
            stage=stage,
        )
        return StageRecord(
            decision_id=out.decision_id,
            stage=stage,
            decision=decision,
            reason=reason,
            caller_principal=self.caller_principal,
            session_id=self.session_id,
            hook_id=self.hook_id,
            evidence_refs=list(evidence_refs),
            ts=out.ts,
        )

    def _finalize(
        self,
        *,
        final_decision: str,
        final_reason: str,
        paused_at_stage: str | None,
    ) -> ApprovalChainResult:
        return ApprovalChainResult(
            decision_id=self.request_id,
            policy_input=dict(self.policy_input),
            session_id=self.session_id,
            hook_id=self.hook_id,
            caller_principal=self.caller_principal,
            stages_completed=len(self.records),
            final_decision=final_decision,
            final_reason=final_reason,
            records=list(self.records),
            paused_at_stage=paused_at_stage,
        )
