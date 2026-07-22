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

All write operations are wrapped in ``BEGIN IMMEDIATE`` transactions per
reviewer note C1 (L2 S3.T2 lesson).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel

from .audit import AuditStore
from .db import connect
from .managed_settings import ManagedSettings, ensure_mode, ensure_risk_level


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
    def __init__(self, db_path: str, audit_store: AuditStore | None = None) -> None:
        self.db_path = db_path
        # Optional injection for callers that want gate decisions persisted
        # in the same DB; defaults to a fresh AuditStore on the same path.
        self._audit = audit_store if audit_store is not None else AuditStore(db_path)

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
        )
        return GateDecision(
            decision_id=decision_id,
            decision=decision,
            rationale=rationale,
        )


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
