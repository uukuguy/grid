"""Telemetry audit store — Contract 4 (async PostToolUse ingest).

Append-only table of PostToolUse events sent by L1 runtimes over HTTP. MVP
writes land in ``telemetry_events`` with a minimal metadata envelope; the
full payload is preserved verbatim as JSON so future phases can backfill
richer schemas without a migration.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
from pydantic import BaseModel, Field

from .db import connect


class TelemetryEventIn(BaseModel):
    """Incoming event envelope.

    ``payload`` is free-form — the whole hook POST body is stashed here so
    evidence-chain consumers can reconstruct the original signal.

    ``_tiebreaker`` (D26) is a monotonic counter for deterministic test
    ordering. Default 0 — production code never sets it; two events with
    same tiebreaker fall back to ``received_at`` ordering.
    """

    session_id: str = Field(..., min_length=1)
    agent_id: str | None = None
    hook_id: str | None = None
    phase: str | None = None  # "PreToolUse" | "PostToolUse" | "Stop" | ...
    payload: dict[str, Any] = Field(default_factory=dict)
    tiebreaker: int = Field(default=0, alias="_tiebreaker")


class TelemetryEventOut(BaseModel):
    event_id: str
    session_id: str
    agent_id: str | None
    hook_id: str | None
    phase: str | None
    payload: dict[str, Any]
    received_at: str
    tiebreaker: int


# REQ-EAASP-02 (Phase 3.7.3): row shape for `governance_decisions` table.
# Mirrors the DDL column order in `db.py`.
class GovernanceDecisionOut(BaseModel):
    decision_id: str
    session_id: str
    hook_id: str
    tool_name: str
    risk_level: str
    decision: str
    approver: str | None
    rationale: str
    ts: str


class AuditStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def ingest(self, event: TelemetryEventIn) -> TelemetryEventOut:
        """Insert a telemetry event.

        Wrapped in ``BEGIN IMMEDIATE`` to serialize concurrent writers (C1),
        even though the primary key is client-unique — WAL + SQLite still
        benefits from explicit ordering on high-churn hosts.
        """
        event_id = f"tel_{uuid.uuid4().hex[:16]}"
        payload_json = json.dumps(event.payload)

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                await db.execute(
                    """
                    INSERT INTO telemetry_events
                        (event_id, session_id, agent_id, hook_id, phase, payload_json, tiebreaker)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        event.session_id,
                        event.agent_id,
                        event.hook_id,
                        event.phase,
                        payload_json,
                        event.tiebreaker,
                    ),
                )
                cur = await db.execute(
                    "SELECT received_at, tiebreaker FROM telemetry_events WHERE event_id = ?",
                    (event_id,),
                )
                row = await cur.fetchone()
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        assert row is not None
        return TelemetryEventOut(
            event_id=event_id,
            session_id=event.session_id,
            agent_id=event.agent_id,
            hook_id=event.hook_id,
            phase=event.phase,
            payload=event.payload,
            received_at=row["received_at"],
            tiebreaker=row["tiebreaker"],
        )

    async def query(
        self,
        session_id: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[TelemetryEventOut]:
        """Return newest-first events matching filters. Limit is clamped (C3).

        ``since`` is an ISO-8601 timestamp (SQLite ``datetime('now')`` format
        compatible, e.g. ``2026-04-12 12:34:56``); events with
        ``received_at > since`` are returned.
        """
        safe_limit = _clamp_limit(limit, default=100, maximum=500)

        where: list[str] = []
        params: list[Any] = []
        if session_id is not None:
            where.append("session_id = ?")
            params.append(session_id)
        if since is not None:
            where.append("received_at > ?")
            params.append(since)
        where_clause = ("WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
            SELECT event_id, session_id, agent_id, hook_id, phase,
                   payload_json, received_at, tiebreaker
            FROM telemetry_events
            {where_clause}
            ORDER BY received_at DESC, tiebreaker DESC, event_id DESC
            LIMIT ?
        """
        params.append(safe_limit)

        db = await connect(self.db_path)
        try:
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
        finally:
            await db.close()

        return [_row_to_event(r) for r in rows]

    async def get(self, event_id: str) -> TelemetryEventOut | None:
        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT event_id, session_id, agent_id, hook_id, phase,
                       payload_json, received_at, tiebreaker
                FROM telemetry_events WHERE event_id = ?
                """,
                (event_id,),
            )
            row = await cur.fetchone()
        finally:
            await db.close()
        return _row_to_event(row) if row else None

    # ─── D9 / L3-02 — skill usage telemetry ───────────────────────────────
    async def skill_usage(
        self,
        skill_id: str,
        since: str | None = None,
        l2_base_url: str | None = None,
    ) -> dict[str, Any]:
        """Return per-skill invocation stats. Primary: L2 audit log. Fallback: L3 local store."""
        # L2-primary path
        if l2_base_url:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    params: dict[str, str] = {}
                    if since is not None:
                        params["since"] = since
                    resp = await client.get(
                        f"{l2_base_url}/v1/memory/{skill_id}/usage",
                        params=params if params else None,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        data["source"] = "l2"
                        return data
            except (httpx.ConnectError, httpx.TimeoutException):
                pass  # fall through to L3 fallback

        # L3-fallback path
        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """SELECT COUNT(*) as invocations,
                          MIN(received_at) as first_seen,
                          MAX(received_at) as last_seen
                   FROM telemetry_events
                   WHERE json_extract(payload_json, '$.skill_id') = ?""",
                (skill_id,),
            )
            row = await cur.fetchone()
        finally:
            await db.close()

        assert row is not None
        return {
            "skill_id": skill_id,
            "invocations": row["invocations"],
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
            "source": "l3_fallback",
        }

    # ─── REQ-EAASP-02 — governance decision ledger ──────────────────────────
    async def record_governance_decision(
        self,
        decision_id: str,
        session_id: str,
        hook_id: str,
        tool_name: str,
        risk_level: str,
        decision: str,
        approver: str | None,
        rationale: str,
    ) -> GovernanceDecisionOut:
        """Append-only insert into ``governance_decisions``.

        Frozen contract (`docs/audit/3.7.3-GAP-AUDIT.md` §6):
        - Single-line signature above is the canonical public method.
        - Input validation happens BEFORE any DB open (no partial row possible).
        - BEGIN IMMEDIATE + rollback-on-error + close-on-finally.
        - Returns the persisted row as ``GovernanceDecisionOut``.
        - Never updates/replaces an existing row — that is a different decision_id.
        """
        # Input validation — every identifier must be non-empty.
        if not decision_id:
            raise ValueError("decision_id must be a non-empty string")
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not hook_id:
            raise ValueError("hook_id must be a non-empty string")
        if not tool_name:
            raise ValueError("tool_name must be a non-empty string")
        if not rationale:
            raise ValueError("rationale must be a non-empty string")
        # Enum validation — DB CHECK constraints also enforce these, but
        # validating here gives callers a clean ValueError instead of an
        # aiosqlite IntegrityError on every code path.
        if risk_level not in {"read", "write_local", "write_external"}:
            raise ValueError(
                f"risk_level must be 'read', 'write_local', or 'write_external', "
                f"got {risk_level!r}"
            )
        if decision not in {"allow", "approve", "deny", "gate_request"}:
            raise ValueError(
                f"decision must be 'allow', 'approve', 'deny', or 'gate_request', "
                f"got {decision!r}"
            )

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                await db.execute(
                    """
                    INSERT INTO governance_decisions
                        (decision_id, session_id, hook_id, tool_name,
                         risk_level, decision, approver, rationale)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        decision_id,
                        session_id,
                        hook_id,
                        tool_name,
                        risk_level,
                        decision,
                        approver,
                        rationale,
                    ),
                )
                cur = await db.execute(
                    """
                    SELECT decision_id, session_id, hook_id, tool_name,
                           risk_level, decision, approver, rationale, ts
                    FROM governance_decisions WHERE decision_id = ?
                    """,
                    (decision_id,),
                )
                row = await cur.fetchone()
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        assert row is not None
        return _row_to_governance(row)

    async def get_governance_decision(
        self, decision_id: str
    ) -> GovernanceDecisionOut | None:
        """Look up a single decision by primary key. Returns None if absent."""
        db = await connect(self.db_path)
        try:
            cur = await db.execute(
                """
                SELECT decision_id, session_id, hook_id, tool_name,
                       risk_level, decision, approver, rationale, ts
                FROM governance_decisions WHERE decision_id = ?
                """,
                (decision_id,),
            )
            row = await cur.fetchone()
        finally:
            await db.close()
        return _row_to_governance(row) if row else None

    async def query_governance_decisions(
        self,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[GovernanceDecisionOut]:
        """Newest-first list of governance decisions. Limit clamped (C3).

        Mirrors ``query()`` shape for telemetry events so callers can reuse
        the same pagination semantics.
        """
        safe_limit = _clamp_limit(limit, default=100, maximum=500)
        where: list[str] = []
        params: list[Any] = []
        if session_id is not None:
            where.append("session_id = ?")
            params.append(session_id)
        where_clause = ("WHERE " + " AND ".join(where)) if where else ""

        sql = f"""
            SELECT decision_id, session_id, hook_id, tool_name,
                   risk_level, decision, approver, rationale, ts
            FROM governance_decisions
            {where_clause}
            ORDER BY ts DESC, decision_id DESC
            LIMIT ?
        """
        params.append(safe_limit)

        db = await connect(self.db_path)
        try:
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
        finally:
            await db.close()
        return [_row_to_governance(r) for r in rows]


def _row_to_event(row: Any) -> TelemetryEventOut:
    payload_raw = row["payload_json"]
    payload = json.loads(payload_raw) if payload_raw else {}
    return TelemetryEventOut(
        event_id=row["event_id"],
        session_id=row["session_id"],
        agent_id=row["agent_id"],
        hook_id=row["hook_id"],
        phase=row["phase"],
        payload=payload,
        received_at=row["received_at"],
        tiebreaker=row["tiebreaker"],
    )


def _row_to_governance(row: Any) -> GovernanceDecisionOut:
    return GovernanceDecisionOut(
        decision_id=row["decision_id"],
        session_id=row["session_id"],
        hook_id=row["hook_id"],
        tool_name=row["tool_name"],
        risk_level=row["risk_level"],
        decision=row["decision"],
        approver=row["approver"],
        rationale=row["rationale"],
        ts=row["ts"],
    )


def _clamp_limit(value: int | None, *, default: int, maximum: int) -> int:
    if value is None or value <= 0:
        return default
    return min(int(value), maximum)
