"""Session event stream — append-only per-session ordered log.

Used by ``SessionOrchestrator`` for standalone ``append`` calls (outside the
create_session transaction) and by the API layer for ``list_events`` queries.

Writes use ``BEGIN IMMEDIATE`` per reviewer C1 to serialize concurrent writers.
``list_events`` clamps ``limit`` to ``[1..500]`` per C3.

REQ-EAASP-04 (Phase 3.7.3): governance helpers emit ``governance.request``
and ``governance.decision`` events through the same session event stream.
Event append is best-effort — failure logs and returns ``None`` so the
authoritative gate decision and audit ledger remain unaffected.
"""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from .db import connect

_VALID_GOVERNANCE_DECISIONS: set[str] = {"allow", "approve", "deny", "gate_request"}
_VALID_RISK_LEVELS: set[str] = {"read", "write_local", "write_external"}


class SessionEventStream:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def append(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        created_at: int | None = None,
    ) -> int:
        """Append a single event; returns the new ``seq``.

        Raises ``aiosqlite.IntegrityError`` when ``session_id`` does not exist
        in the ``sessions`` table (FK violation). Callers are expected to
        surface that as a 404 at the HTTP layer.
        """
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not event_type:
            raise ValueError("event_type must be a non-empty string")

        ts = int(created_at if created_at is not None else time.time())
        payload_json = json.dumps(payload, sort_keys=True)

        db = await connect(self.db_path)
        try:
            await db.execute("BEGIN IMMEDIATE")
            try:
                cur = await db.execute(
                    """
                    INSERT INTO session_events
                        (session_id, event_type, payload_json, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, event_type, payload_json, ts),
                )
                seq = cur.lastrowid
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        finally:
            await db.close()

        assert seq is not None
        return int(seq)

    async def list_events(
        self,
        session_id: str,
        from_seq: int = 1,
        to_seq: int = 2**31 - 1,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Return events in ascending seq order inside ``[from_seq, to_seq]``.

        ``limit`` is clamped to ``[1..500]`` (C3).
        """
        safe_limit = _clamp_limit(limit, default=500, maximum=500)
        if from_seq is None or from_seq < 1:
            from_seq = 1
        if to_seq is None:
            to_seq = 2**31 - 1
        # N1 (reviewer): reject nonsensical ranges instead of silently
        # rewriting them — callers that truly want "everything from X" should
        # omit ``to_seq`` rather than passing ``to_seq < from_seq``.
        if to_seq < from_seq:
            raise ValueError(
                f"to_seq ({to_seq}) must be >= from_seq ({from_seq})"
            )

        db = await connect(self.db_path)
        try:
            # Phase 1: include event_id, source, metadata_json, cluster_id
            # columns. These are NULL for pre-Phase-1 rows; COALESCE ensures
            # consistent empty-string output for legacy rows.
            cur = await db.execute(
                """
                SELECT seq, session_id, event_type, payload_json, created_at,
                       event_id, source, metadata_json, cluster_id
                FROM session_events
                WHERE session_id = ?
                  AND seq BETWEEN ? AND ?
                ORDER BY seq ASC
                LIMIT ?
                """,
                (session_id, from_seq, to_seq, safe_limit),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()

        def _metadata(raw: str | None) -> dict[str, Any]:
            if not raw:
                return {}
            try:
                return json.loads(raw)
            except (ValueError, TypeError):
                return {}

        return [
            {
                "seq": int(r["seq"]),
                "session_id": r["session_id"],
                "event_type": r["event_type"],
                "payload": json.loads(r["payload_json"]) if r["payload_json"] else {},
                "created_at": int(r["created_at"]),
                "event_id": r["event_id"] or "",
                "source": r["source"] or "",
                "metadata": _metadata(r["metadata_json"]),
                "cluster_id": r["cluster_id"],
            }
            for r in rows
        ]

    # ─── REQ-EAASP-04 — governance event helpers ───────────────────────────
    async def emit_governance_request(
        self,
        session_id: str,
        decision_id: str,
        hook_id: str,
        tool_name: str,
        risk_level: str,
        action_preview: str,
    ) -> int | None:
        """Append a ``governance.request`` event (best-effort).

        Returns the new ``seq`` on success, or ``None`` if the append failed.
        The audit §7.1 contract is: event failure must NEVER invert the gate
        decision (which lives in the L3 ``governance_decisions`` ledger).
        """
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not decision_id:
            raise ValueError("decision_id must be a non-empty string")
        if not hook_id:
            raise ValueError("hook_id must be a non-empty string")
        if not tool_name:
            raise ValueError("tool_name must be a non-empty string")
        if not action_preview:
            raise ValueError("action_preview must be a non-empty string")
        if risk_level not in _VALID_RISK_LEVELS:
            raise ValueError(
                f"risk_level must be 'read', 'write_local', or 'write_external', "
                f"got {risk_level!r}"
            )
        payload = {
            "decision_id": decision_id,
            "hook_id": hook_id,
            "tool_name": tool_name,
            "risk_level": risk_level,
            "action_preview": action_preview,
        }
        return await self._safe_append(session_id, "governance.request", payload)

    async def emit_governance_decision(
        self,
        session_id: str,
        decision_id: str,
        decision: str,
        approver: str,
    ) -> int | None:
        """Append a ``governance.decision`` event (best-effort).

        Returns the new ``seq`` on success, or ``None`` if the append failed.
        The audit §7.1 contract is: event failure must NEVER invert the gate
        decision (which lives in the L3 ``governance_decisions`` ledger).
        """
        if not session_id:
            raise ValueError("session_id must be a non-empty string")
        if not decision_id:
            raise ValueError("decision_id must be a non-empty string")
        if decision not in _VALID_GOVERNANCE_DECISIONS:
            raise ValueError(
                f"decision must be 'allow', 'approve', 'deny', or 'gate_request', "
                f"got {decision!r}"
            )
        if not approver:
            raise ValueError("approver must be a non-empty provenance string")
        payload = {
            "decision_id": decision_id,
            "decision": decision,
            "approver": approver,
        }
        return await self._safe_append(session_id, "governance.decision", payload)

    async def _safe_append(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int | None:
        """Append helper that swallows persistence/runtime failures.

        Per audit §7.1, governance event delivery is best-effort — a failure
        here must not flip the authoritative gate decision. We catch only
        the persistence errors that bubble out of ``append()`` and log them
        with loguru so operators can correlate missing events with backend
        outages.
        """
        try:
            return await self.append(session_id, event_type, payload)
        except Exception as exc:  # broad: any DB outage must not crash callers
            logger.warning(
                "governance event append failed (event_type={}, session_id={}): {}",
                event_type,
                session_id,
                exc,
            )
            return None


def _clamp_limit(value: int | None, *, default: int, maximum: int) -> int:
    """Clamp a query limit to a safe range. Reviewer note C3 (S3.T2)."""
    if value is None or value <= 0:
        return default
    return min(int(value), maximum)
