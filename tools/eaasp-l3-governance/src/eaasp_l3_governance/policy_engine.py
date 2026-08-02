"""Policy engine — persistence for managed-settings versions + hook modes.

Contract 1 (Policy Deployment) surface:

- ``deploy()``  — accept a pre-compiled ``ManagedSettings`` and insert a new
  row in ``managed_settings_versions``.
- ``switch_mode()`` — flip an individual hook between ``enforce`` / ``shadow``
  by upserting ``managed_hooks_mode_overrides``. Does **not** bump the
  version number (overrides float above versions — see design note in db.py).
- ``list_versions()`` — newest-first metadata for the UI / CLI ``policy
  versions`` command.
- ``latest_version()`` — most recent version row, used by session validate.
- ``get_mode_override()`` — look up a single hook's override (None if unset).

Contract 5 (Risk Gate — Phase 3.7.3 / REQ-EAASP-03):

- ``evaluate_gate()`` — given a ``session_id``, ``hook_id``, ``tool_name``,
  ``risk_level``, and human-readable ``action_preview``, return a
  ``GateDecision`` describing whether the action may proceed immediately
  (``allow``) or requires synchronous human/CLI approval
  (``gate_request``). Every result is appended to the
  ``governance_decisions`` ledger so the audit trail is complete.

v3.11.2 (5-stage approval chain): ``evaluate_with_opa_and_run_chain()``
extends the OPA path with the 5-stage Plan → Check → Draft → Approve →
Execute state machine. The state machine is OPT-IN: it only runs when
OPA returns ``approval`` (``gate_request`` in the audit ledger). The
return value extends the existing ``GateDecision`` with the chain
result so the API layer can serialize both the OPA decision and the
chain's final state without splitting the wire contract.

All write operations are wrapped in ``BEGIN IMMEDIATE`` transactions per
reviewer note C1 (L2 S3.T2 lesson).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel

from loguru import logger

from .approval_state_machine import (
    APPROVAL_STAGE_APPROVE,
    APPROVAL_STAGE_CHECK,
    APPROVAL_STAGE_DRAFT,
    APPROVAL_STAGE_EXECUTE,
    APPROVAL_STAGE_PLAN,
    ApprovalChainResult,
    ApprovalStagePolicy,
    ApprovalStateMachine,
    DECISION_ALLOW,
    DECISION_APPROVE,
    DECISION_DENY,
)
from .audit import AuditStore
from .db import connect
from .managed_settings import ManagedSettings, ensure_mode, ensure_risk_level
from .opa_backend import (
    DECISION_ALLOW,
    DECISION_APPROVAL,
    DECISION_DENY,
    INFRA_UNAVAILABLE,
    OPABackend,
    OPADecision,
)


class DeployResult(BaseModel):
    version: int
    created_at: str
    hook_count: int
    mode_summary: dict[str, int]


class VersionSummary(BaseModel):
    version: int
    created_at: str
    hook_count: int
    mode_summary: dict[str, int]


class VersionDetail(BaseModel):
    version: int
    created_at: str
    hook_count: int
    mode_summary: dict[str, int]
    payload: dict[str, Any]


class ModeOverride(BaseModel):
    hook_id: str
    mode: str
    updated_at: str


class HookNotFoundError(Exception):
    """Raised when switch_mode() is called for a hook_id not in the latest policy."""

    def __init__(self, hook_id: str) -> None:
        self.hook_id = hook_id
        super().__init__(f"hook_id {hook_id!r} not found in latest policy version")


# REQ-EAASP-03 (Phase 3.7.3): gate decision contract.
# Wire shape is fixed by the audit §5.1 spec; do not rename or remove fields.
GateDecisionValue = Literal["allow", "approve", "deny", "gate_request"]


class GateDecision(BaseModel):
    decision_id: str
    decision: GateDecisionValue
    rationale: str


def _new_gate_id() -> str:
    """Return a fresh ``gd_<uuid4-hex>`` request id.

    Final decisions append ``_final`` at the call site (not here) so the
    request and final rows can be distinguished in the audit ledger while
    sharing a primary-key lineage.
    """
    return f"gd_{uuid.uuid4().hex}"


class PolicyEngine:
    def __init__(
        self,
        db_path: str,
        audit_store: AuditStore | None = None,
        opa_backend: OPABackend | None = None,
    ) -> None:
        self.db_path = db_path
        # Optional injection for callers that want gate decisions persisted
        # in the same DB; defaults to a fresh AuditStore on the same path.
        self._audit = audit_store if audit_store is not None else AuditStore(db_path)
        # Optional OPA backend. When set, evaluate_with_opa() is available;
        # evaluate_gate() still uses the in-process matrix (dev/test path).
        # The API layer is the switch: it reads opa_enabled() and routes
        # to evaluate_with_opa() vs evaluate_gate() per ADR-V2-034 §Decision.
        self._opa_backend = opa_backend

    @property
    def audit(self) -> AuditStore:
        return self._audit

    # ─── Contract 1: PUT /v1/policies/managed-hooks ───────────────────────
    async def deploy(self, settings: ManagedSettings) -> DeployResult:
        """Persist a new managed-settings version.

        The payload is serialized with ``model_dump(mode='json')`` so the
        extras (``ConfigDict(extra="allow")``) round-trip cleanly.
        """
        payload_json = json.dumps(settings.model_dump(mode="json"), sort_keys=True)
        hook_count = len(settings.hooks)
        mode_summary = settings.mode_summary()
        mode_summary_json = json.dumps(mode_summary, sort_keys=True)

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    """
                    INSERT INTO managed_settings_versions
                        (payload_json, hook_count, mode_summary)
                    VALUES (?, ?, ?)
                    RETURNING version, created_at
                    """,
                    (payload_json, hook_count, mode_summary_json),
                )
                row = await cur.fetchone()
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        assert row is not None
        return DeployResult(
            version=int(row["version"]),
            created_at=row["created_at"],
            hook_count=hook_count,
            mode_summary=mode_summary,
        )

    # ─── Contract 1: PUT /v1/policies/{hook_id}/mode ──────────────────────
    async def switch_mode(self, hook_id: str, mode: str) -> ModeOverride:
        """Upsert a mode override. Rejects unknown modes (M4) and unknown hook_ids (D19)."""
        validated = ensure_mode(mode)
        if not hook_id:
            raise ValueError("hook_id must be a non-empty string")

        # D19: Validate hook_id exists in latest policy
        latest = await self.latest_version()
        if latest is None:
            raise HookNotFoundError(hook_id)
        hook_ids = {h.get("hook_id") for h in latest.payload.get("hooks", [])}
        if hook_id not in hook_ids:
            raise HookNotFoundError(hook_id)

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                await db.execute(
                    """
                    INSERT INTO managed_hooks_mode_overrides (hook_id, mode)
                    VALUES (?, ?)
                    ON CONFLICT(hook_id) DO UPDATE SET
                        mode = excluded.mode,
                        updated_at = datetime('now')
                    """,
                    (hook_id, validated),
                )
                cur = await db.execute(
                    "SELECT hook_id, mode, updated_at "
                    "FROM managed_hooks_mode_overrides WHERE hook_id = ?",
                    (hook_id,),
                )
                row = await cur.fetchone()
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        assert row is not None
        return ModeOverride(
            hook_id=row["hook_id"],
            mode=row["mode"],
            updated_at=row["updated_at"],
        )

    async def get_mode_override(self, hook_id: str) -> ModeOverride | None:
        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                "SELECT hook_id, mode, updated_at "
                "FROM managed_hooks_mode_overrides WHERE hook_id = ?",
                (hook_id,),
            )
            row = await cur.fetchone()
        finally:
            await db.close()
        if row is None:
            return None
        return ModeOverride(
            hook_id=row["hook_id"],
            mode=row["mode"],
            updated_at=row["updated_at"],
        )

    # ─── Contract 1: GET /v1/policies/versions ────────────────────────────
    async def list_versions(self, limit: int = 100) -> list[VersionSummary]:
        """Newest-first list of deployed policy versions. Limit clamped (C3)."""
        safe_limit = _clamp_limit(limit, default=100, maximum=500)
        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT version, created_at, hook_count, mode_summary
                FROM managed_settings_versions
                ORDER BY version DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()

        return [
            VersionSummary(
                version=r["version"],
                created_at=r["created_at"],
                hook_count=r["hook_count"],
                mode_summary=_load_mode_summary(r["mode_summary"]),
            )
            for r in rows
        ]

    async def latest_version(self) -> VersionDetail | None:
        """Most-recent version row with full payload (used by validate)."""
        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT version, created_at, hook_count, mode_summary, payload_json
                FROM managed_settings_versions
                ORDER BY version DESC
                LIMIT 1
                """,
            )
            row = await cur.fetchone()
        finally:
            await db.close()
        if row is None:
            return None
        return VersionDetail(
            version=row["version"],
            created_at=row["created_at"],
            hook_count=row["hook_count"],
            mode_summary=_load_mode_summary(row["mode_summary"]),
            payload=json.loads(row["payload_json"]),
        )

    async def get_version(self, version: int) -> VersionDetail | None:
        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT version, created_at, hook_count, mode_summary, payload_json
                FROM managed_settings_versions
                WHERE version = ?
                """,
                (version,),
            )
            row = await cur.fetchone()
        finally:
            await db.close()
        if row is None:
            return None
        return VersionDetail(
            version=row["version"],
            created_at=row["created_at"],
            hook_count=row["hook_count"],
            mode_summary=_load_mode_summary(row["mode_summary"]),
            payload=json.loads(row["payload_json"]),
        )

    # ─── REQ-EAASP-03 — risk-aware gate decision ──────────────────────────
    async def evaluate_gate(
        self,
        session_id: str,
        hook_id: str,
        tool_name: str,
        risk_level: str,
        action_preview: str,
        *,
        business_key: str | None = None,
    ) -> GateDecision:
        """Return a ``GateDecision`` and persist it in the audit ledger.

        Single-line signature is the canonical public contract (audit §5.1).
        Decision matrix (audit §5.2):

        +------------------+----------+-----------------------------+
        | risk_level       | mode     | decision / rationale        |
        +------------------+----------+-----------------------------+
        | read             | any      | allow / (read auto-allowed) |
        | write_local      | shadow   | allow / "shadow mode"       |
        | write_external   | shadow   | allow / "shadow mode"       |
        | write_local      | enforce  | gate_request /              |
        |                  |          | "approval required"         |
        | write_external   | enforce  | gate_request /              |
        |                  |          | "approval required"         |
        +------------------+----------+-----------------------------+

        The mode precedence is: ``managed_hooks_mode_overrides`` (if set) wins
        over the latest version's hook declaration (audit §5.2).

        Every allow and gate_request decision is appended to the
        ``governance_decisions`` ledger with ``approver=None`` (the request
        row does not yet have a human approver; final approve/deny rows use
        ``cli:--yes`` / ``cli:--no`` / ``cli:interactive``).
        """
        # ── 1. Input validation BEFORE any DB open ─────────────────────────
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not hook_id:
            raise ValueError("hook_id must be a non-empty string")
        if not tool_name:
            raise ValueError("tool_name must be a non-empty string")
        if not action_preview:
            raise ValueError("action_preview must be a non-empty string")
        # risk_level: defense-in-depth — Pydantic normally catches this, but
        # raw-string callers (skill metadata) bypass that path.
        validated_risk = ensure_risk_level(risk_level)

        # ── 2. Resolve the hook + effective mode ──────────────────────────
        latest = await self.latest_version()
        if latest is None:
            raise HookNotFoundError(hook_id)

        hook_payload = None
        for hook in latest.payload.get("hooks", []):
            if isinstance(hook, dict) and hook.get("hook_id") == hook_id:
                hook_payload = hook
                break
        if hook_payload is None:
            raise HookNotFoundError(hook_id)

        declared_mode = hook_payload.get("mode", "enforce")
        override = await self.get_mode_override(hook_id)
        effective_mode = override.mode if override is not None else declared_mode

        # ── 3. Decision matrix ─────────────────────────────────────────────
        if validated_risk == "read":
            decision: GateDecisionValue = "allow"
            rationale = "read auto-allowed"
        elif effective_mode == "shadow":
            decision = "allow"
            rationale = "shadow mode"
        else:
            assert effective_mode == "enforce"  # validated by ensure_mode upstream
            decision = "gate_request"
            rationale = "approval required"

        # ── 4. Persist + return ────────────────────────────────────────────
        decision_id = _new_gate_id()
        await self._audit.record_governance_decision(
            decision_id=decision_id,
            session_id=session_id,
            hook_id=hook_id,
            tool_name=tool_name,
            risk_level=validated_risk,
            decision=decision,
            approver=None,
            rationale=rationale,
            business_key=business_key,
        )
        return GateDecision(
            decision_id=decision_id,
            decision=decision,
            rationale=rationale,
        )

    # ─── v3.11.1 — OPA backend path (production) ──────────────────────────

    @property
    def opa_enabled(self) -> bool:
        """True iff an OPA backend has been injected into this engine.

        The API layer reads this flag to decide whether to route a gate
        decision through OPA (production) or through the in-process
        matrix (dev/test). Per ADR-V2-034 the deployment is opt-in:
        ``OPABackend.from_env()`` is the only path that constructs a
        backend, and the API only injects one when ``L3_OPA_ENABLED`` is
        truthy AND the env vars are present.
        """
        return self._opa_backend is not None

    async def evaluate_with_opa(
        self,
        session_id: str,
        hook_id: str,
        tool_name: str,
        risk_level: str,
        action_preview: str,
        *,
        agent_id: str | None = None,
        skill_id: str | None = None,
        principal_scope: str | None = None,
        principal_id: str | None = None,
        tenant_id: str | None = None,
        business_key: str | None = None,
    ) -> GateDecision:
        """Evaluate via OPA and persist the (possibly synthesized) decision.

        Same input contract as :meth:`evaluate_gate`. The OPA backend
        returns a normalized ``OPADecision``; the PolicyEngine converts
        it into the existing ``GateDecision`` shape (so the audit ledger
        and the L4 SSE consumers stay wire-compatible) and writes the
        audit row carrying ``infra_unavailable=True`` on fail-closed.

        The mapping is intentionally narrow:
          - OPA ``allow``     -> ``allow``
          - OPA ``approval``  -> ``approval`` (alias for ``gate_request``)
          - OPA ``deny``      -> ``deny``

        The rationale for the audit row is the OPA ``reason`` string
        (or the fail-closed composite) so operators can pivot on it.
        """
        if self._opa_backend is None:
            raise RuntimeError(
                "OPA backend not configured; construct PolicyEngine with "
                "an OPABackend instance, or use evaluate_gate() for the "
                "in-process fallback path (ADR-V2-034 §Decision)."
            )

        # ── 1. Input validation (same surface as evaluate_gate) ───────────
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not hook_id:
            raise ValueError("hook_id must be a non-empty string")
        if not tool_name:
            raise ValueError("tool_name must be a non-empty string")
        if not action_preview:
            raise ValueError("action_preview must be a non-empty string")
        validated_risk = ensure_risk_level(risk_level)

        # ── 2. Resolve mode (override > declared) ─────────────────────────
        latest = await self.latest_version()
        if latest is None:
            raise HookNotFoundError(hook_id)
        hook_payload = None
        for hook in latest.payload.get("hooks", []):
            if isinstance(hook, dict) and hook.get("hook_id") == hook_id:
                hook_payload = hook
                break
        if hook_payload is None:
            raise HookNotFoundError(hook_id)
        declared_mode = hook_payload.get("mode", "enforce")
        override = await self.get_mode_override(hook_id)
        effective_mode = override.mode if override is not None else declared_mode

        # ── 3. OPA evaluation ──────────────────────────────────────────────
        opa_request = {
            "session_id": session_id,
            "hook_id": hook_id,
            "tool_name": tool_name,
            "risk_level": validated_risk,
            "action_preview": action_preview,
            "mode": effective_mode,
            "agent_id": agent_id,
            "skill_id": skill_id,
            # Security [Issue 1]: principal binding travels into the OPA
            # audit payload so Rego can pivot on it. The authenticated
            # scope is what enforces (a) hook matching and (b) audit
            # traceability — non-HTTP callers must also pass these
            # kwargs explicitly.
            "principal_scope": principal_scope,
            "principal_id": principal_id,
            "tenant_id": tenant_id,
        }
        opa_result = await self._opa_backend.evaluate(opa_request)

        # ── 4. Map OPA -> GateDecision + audit row ─────────────────────────
        decision_id = _new_gate_id()
        decision, rationale = _map_opa_to_gate(opa_result, effective_mode)
        await self._audit.record_governance_decision(
            decision_id=decision_id,
            session_id=session_id,
            hook_id=hook_id,
            tool_name=tool_name,
            risk_level=validated_risk,
            decision=decision,
            approver=None,
            rationale=rationale,
            business_key=business_key,
        )
        if opa_result.infra_unavailable:
            logger.warning(
                "L3 governance OPA fail-closed",
                session_id=session_id,
                hook_id=hook_id,
                cause=opa_result.cause,
            )
        return GateDecision(
            decision_id=decision_id,
            decision=decision,
            rationale=rationale,
        )


def _map_opa_to_gate(opa_result: OPADecision, mode: str) -> tuple[str, str]:
    """Map a normalized OPA decision to a ``GateDecision`` (decision, rationale).

    Authorization gate (security review Issue 2): the runtime MUST NOT
    proceed unless **both** ``opa_result.allow is True`` AND
    ``opa_result.decision == DECISION_ALLOW``. Single-channel truth (only
    ``decision=='allow'`` OR only ``allow=True``) is treated as a fail-closed
    deny; ``infra_unavailable=True`` is preserved upstream so the audit row
    carries the correct cause. This is defense-in-depth on top of the
    bidirectional invariant in ``_parse_opa_response``.
    """
    if opa_result.infra_unavailable:
        # Fail-closed: surface the OPA cause in the rationale so the audit
        # ledger can be filtered by cause in postmortem. decision must be
        # 'deny' per deny-always-wins (spec §15.9).
        return DECISION_DENY, opa_result.reason
    # Belt-and-suspenders: the bidirectional invariant in
    # ``_parse_opa_response`` already guarantees ``decision=='allow'`` iff
    # ``allow is True``, but we re-check here so a future widening of the
    # invariant cannot silently bypass the gate. Any mismatch is fail-closed.
    if opa_result.decision == DECISION_ALLOW and opa_result.allow is True:
        return DECISION_ALLOW, opa_result.reason or f"opa:allow ({mode})"
    if opa_result.decision == DECISION_APPROVAL:
        # OPA emits a 3-state decision (allow / approval / deny). The L3
        # audit ledger is a 4-state value (allow / approve / deny /
        # gate_request) constrained by the DB CHECK. We map OPA's
        # 'approval' to the existing 'gate_request' so the audit row
        # stays within the DB constraint; the rationale carries the OPA
        # reason so the audit trail makes the original intent clear.
        return "gate_request", opa_result.reason or "opa:approval required"
    if opa_result.decision == DECISION_DENY:
        return DECISION_DENY, opa_result.reason or "opa:deny"
    # Defensive — _parse_opa_response already validates this, but keep
    # the guard so a future OPA backend cannot silently widen the enum.
    return DECISION_DENY, f"opa:unknown decision {opa_result.decision!r}"


def _load_mode_summary(raw: str | None) -> dict[str, int]:
    if not raw:
        return {"enforce": 0, "shadow": 0}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"enforce": 0, "shadow": 0}
    return {k: int(v) for k, v in data.items()}


def _clamp_limit(value: int | None, *, default: int, maximum: int) -> int:
    """Clamp a query limit to a safe range. Reviewer note C3 (S3.T2)."""
    if value is None or value <= 0:
        return default
    return min(int(value), maximum)
