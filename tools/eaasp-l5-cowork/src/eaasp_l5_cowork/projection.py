"""CoworkProjection — read-only projection layer for the four-card substrate.

v3.13.0 — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action /
Approval) + 回溯闭环 (retrospective cycle).

The projection is **read-only** (D-31). Every accessor is a SELECT
against the existing L2 / L3 / L4 / A2A SQLite stores; the
projection NEVER writes to those stores. The projection layer
also enforces the tenant boundary (D-33 / v3.12.1 D-28 pattern):
a cross-tenant caller sees an empty card list, never another
tenant's data.

Storage layout (read-only):

- L4 ``event_room_events`` + ``sessions`` + ``event_rooms`` →
  EventCard projection
- L2 ``anchors`` (memory_anchors) → EvidenceCard projection
- L4 ``telemetry_events`` + L3 ``governance_decisions`` →
  ActionCard projection
- L3 ``governance_decisions`` → ApprovalCard projection

Frozen contract (audit §7.1): the projection is best-effort.
Every SELECT wraps in a try/except so a missing column / table
(a legacy L2 / L3 DB that hasn't been migrated yet) returns an
empty list rather than crashing the Cowork backend.
"""

from __future__ import annotations

import json
import os
from typing import Any

import aiosqlite

from .cards import (
    ActionCard,
    ApprovalCard,
    CardBase,
    EvidenceCard,
    EventCard,
    _make_card_id,
    _ts_to_iso,
    make_payload_summary,
)


# ─── Env-driven DB path resolution (D-30: no new tables / no new cols) ──
#
# The projection reads the EXISTING L2 / L3 / L4 stores. Default
# paths match the canonical ``make dev-eaasp`` layout so the L5
# Cowork backend can run alongside the other EAASP services with
# no extra config.


def _env_path(env_var: str, default: str) -> str:
    """Resolve a DB path env var with strict-by-default fallback (ADR-V2-028).

    Falls back to ``default`` when the env var is unset. Empty
    string raises — that is the strict-by-default posture
    (ADR-V2-028) — and matches the L2 / L3 / L4 conventions where
    an empty DB path is treated as a malformed config rather than
    a silent default.
    """
    raw = os.environ.get(env_var)
    if raw is None:
        return default
    if raw == "":
        raise ValueError(
            f"{env_var} is set to an empty string "
            "(strict-by-default per ADR-V2-028; unset the var to use the default)"
        )
    return raw


def _safe_int(value: Any, default: int = 0) -> int:
    """Best-effort int parse — returns ``default`` on failure."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


async def _resolve_session_tenant(
    db: aiosqlite.Connection, session_id: str
) -> str | None:
    """Resolve the tenant for a session via ``event_room_members``.

    Looks up the session in the Event Room membership table and
    returns the room's ``tenant_id``. Returns ``None`` when the
    session is not bound to any Event Room (legacy / L0-only
    sessions — caller may fall back to a default tenant).
    """
    cur = await db.execute(  # noqa: F821
        """
        SELECT er.tenant_id
        FROM event_room_members erm
        JOIN event_rooms er ON er.room_id = erm.room_id
        WHERE erm.session_id = ?
        ORDER BY erm.joined_at ASC
        LIMIT 1
        """,
        (session_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    try:
        return str(row["tenant_id"])
    except (KeyError, TypeError):
        # Row is a tuple (no row factory) — fall back to positional.
        return str(row[0]) if row else None


# ─── Projection class ─────────────────────────────────────────────────────


class CoworkProjection:
    """Read-only projection over L2 / L3 / L4 SQLite stores.

    Construction takes the DB paths for the three stores. Tests
    pass per-test ``tmp_path`` directories so the projection
    reads against fixture-populated DBs (the v3.7.3 NEW-A1
    pre-test fixture isolation pattern).
    """

    def __init__(
        self,
        *,
        l2_db_path: str | None = None,
        l3_db_path: str | None = None,
        l4_db_path: str | None = None,
    ) -> None:
        # Resolve defaults from env so the L5 service can start
        # alongside the canonical EAASP v2.0 layout with no
        # extra config.
        self.l2_db_path = (
            l2_db_path
            if l2_db_path is not None
            else _env_path("EAASP_L2_DB_PATH", "./data/memory.db")
        )
        self.l3_db_path = (
            l3_db_path
            if l3_db_path is not None
            else _env_path("EAASP_L3_DB_PATH", "./data/governance.db")
        )
        self.l4_db_path = (
            l4_db_path
            if l4_db_path is not None
            else _env_path("EAASP_L4_DB_PATH", "./data/orchestration.db")
        )

    # ─── Internal helpers ───────────────────────────────────────────────

    async def _open_l4(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self.l4_db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    async def _open_l3(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self.l3_db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    async def _open_l2(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self.l2_db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    async def _resolve_tenant(self, session_id: str) -> str:
        """Resolve the tenant for a session (D-33).

        Falls back to ``"default"`` when the session is not bound
        to any Event Room — this matches the L4 default tenant
        convention used by the v3.12.1 walkthrough.
        """
        try:
            db = await self._open_l4()
            try:
                tenant = await _resolve_session_tenant(db, session_id)
            finally:
                await db.close()
        except Exception:
            tenant = None
        return tenant or "default"

    # ─── EventCard projection (CARD-EVENT-01..03) ──────────────────────

    async def list_event_cards(
        self, session_id: str, *, tenant_id: str | None = None
    ) -> list[EventCard]:
        """Return every EventCard for the session, tenant-bound.

        Tenant binding (D-33): if ``tenant_id`` is provided, only
        events whose ``room_id`` belongs to that tenant are
        returned. If ``tenant_id`` is None, the projection
        auto-resolves via ``_resolve_tenant``.
        """
        resolved_tenant = tenant_id or await self._resolve_tenant(session_id)
        cards: list[EventCard] = []
        try:
            db = await self._open_l4()
        except Exception:
            return cards
        try:
            cur = await db.execute(
                """
                SELECT ere.seq, ere.room_id, ere.session_id,
                       ere.event_type, ere.payload_json, ere.created_at,
                       er.tenant_id
                FROM event_room_events ere
                JOIN event_rooms er ON er.room_id = ere.room_id
                WHERE ere.session_id = ? AND er.tenant_id = ?
                ORDER BY ere.seq ASC
                """,
                (session_id, resolved_tenant),
            )
            rows = await cur.fetchall()
        except Exception:
            # Legacy L4 DB without event_room_events table — fall
            # back to session_events so the projection still has
            # data to render.
            await db.close()
            try:
                db = await self._open_l4()
                cur = await db.execute(
                    """
                    SELECT seq, session_id, event_type, payload_json,
                           created_at, '' AS room_id
                    FROM session_events
                    WHERE session_id = ?
                    ORDER BY seq ASC
                    """,
                    (session_id,),
                )
                rows = await cur.fetchall()
            except Exception:
                return cards
            for r in rows:
                payload = _parse_payload(r["payload_json"])
                cards.append(
                    EventCard(
                        id=_make_card_id(
                            "event", session_id, r["seq"], r["event_type"]
                        ),
                        session_id=str(r["session_id"]),
                        tenant_id=resolved_tenant,
                        created_at=_ts_to_iso(r["created_at"]),
                        summary=make_payload_summary(payload),
                        event_seq=_safe_int(r["seq"]),
                        room_id=None,
                        event_type=str(r["event_type"] or ""),
                        extra={
                            "event_type": str(r["event_type"] or ""),
                            "source": "session_events",
                        },
                    )
                )
            return cards

        for r in rows:
            payload = _parse_payload(r["payload_json"])
            cards.append(
                EventCard(
                    id=_make_card_id(
                        "event",
                        session_id,
                        r["seq"],
                        r["event_type"],
                    ),
                    session_id=str(r["session_id"]),
                    tenant_id=str(r["tenant_id"] or resolved_tenant),
                    created_at=_ts_to_iso(r["created_at"]),
                    summary=make_payload_summary(payload),
                    event_seq=_safe_int(r["seq"]),
                    room_id=str(r["room_id"]) if r["room_id"] else None,
                    event_type=str(r["event_type"] or ""),
                    extra={"event_type": str(r["event_type"] or "")},
                )
            )
        await db.close()
        return cards

    async def list_event_cards_by_room(
        self, room_id: str, *, tenant_id: str | None = None
    ) -> list[EventCard]:
        """Return every EventCard for the room (CARD-EVENT-02), tenant-bound."""
        cards: list[EventCard] = []
        try:
            db = await self._open_l4()
        except Exception:
            return cards
        try:
            cur = await db.execute(
                """
                SELECT ere.seq, ere.room_id, ere.session_id,
                       ere.event_type, ere.payload_json, ere.created_at,
                       er.tenant_id
                FROM event_room_events ere
                JOIN event_rooms er ON er.room_id = ere.room_id
                WHERE ere.room_id = ?
                  AND (? IS NULL OR er.tenant_id = ?)
                ORDER BY ere.seq ASC
                """,
                (room_id, tenant_id, tenant_id),
            )
            rows = await cur.fetchall()
        except Exception:
            return cards
        finally:
            await db.close()

        for r in rows:
            payload = _parse_payload(r["payload_json"])
            cards.append(
                EventCard(
                    id=_make_card_id(
                        "event",
                        str(r["session_id"]),
                        r["seq"],
                        r["event_type"],
                    ),
                    session_id=str(r["session_id"]),
                    tenant_id=str(r["tenant_id"]),
                    created_at=_ts_to_iso(r["created_at"]),
                    summary=make_payload_summary(payload),
                    event_seq=_safe_int(r["seq"]),
                    room_id=str(r["room_id"]),
                    event_type=str(r["event_type"] or ""),
                    extra={"event_type": str(r["event_type"] or "")},
                )
            )
        return cards

    # ─── EvidenceCard projection (CARD-EVIDENCE-01..03) ────────────────

    async def list_evidence_cards(
        self, session_id: str, *, tenant_id: str | None = None
    ) -> list[EvidenceCard]:
        """Return every EvidenceCard for the session (CARD-EVIDENCE-02)."""
        resolved_tenant = tenant_id or await self._resolve_tenant(session_id)
        cards: list[EvidenceCard] = []
        try:
            db = await self._open_l2()
        except Exception:
            return cards
        try:
            cur = await db.execute(
                """
                SELECT anchor_id, event_id, session_id, type, data_ref,
                       snapshot_hash, source_system, tool_version,
                       model_version, rule_version, created_at, metadata
                FROM anchors
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,),
            )
            rows = await cur.fetchall()
        except Exception:
            return cards
        finally:
            await db.close()

        for r in rows:
            metadata_raw = r["metadata"]
            metadata = _parse_payload(metadata_raw) if metadata_raw else {}
            summary = make_payload_summary(
                {
                    "type": r["type"],
                    "data_ref": r["data_ref"],
                    "source_system": r["source_system"],
                    "tool_version": r["tool_version"],
                    "snapshot_hash": (
                        r["snapshot_hash"][:12] + "…"
                        if r["snapshot_hash"]
                        else None
                    ),
                    **({"metadata_keys": list(metadata.keys())} if metadata else {}),
                }
            )
            confirmed = bool(r["snapshot_hash"]) and bool(r["tool_version"])
            cards.append(
                EvidenceCard(
                    id=_make_card_id("evidence", str(r["anchor_id"])),
                    session_id=str(r["session_id"]),
                    tenant_id=resolved_tenant,
                    created_at=_ts_to_iso(r["created_at"]),
                    summary=summary,
                    anchor_id=str(r["anchor_id"]),
                    evidence_type=str(r["type"] or ""),
                    confirmed=confirmed,
                    extra={
                        "event_id": str(r["event_id"] or ""),
                        "source_system": str(r["source_system"] or ""),
                        "tool_version": str(r["tool_version"] or ""),
                    },
                )
            )
        return cards

    # ─── ActionCard projection (CARD-ACTION-01..03) ─────────────────────

    async def list_action_cards(
        self, session_id: str, *, tenant_id: str | None = None
    ) -> list[ActionCard]:
        """Return every ActionCard for the session (CARD-ACTION-02).

        Joins ``telemetry_events`` to ``governance_decisions`` on
        ``(session_id, hook_id)`` to surface the canonical
        ``risk_level`` (CARD-ACTION-03).
        """
        resolved_tenant = tenant_id or await self._resolve_tenant(session_id)
        cards: list[ActionCard] = []
        # First read the L4 telemetry_events to get the action rows.
        try:
            l4 = await self._open_l4()
        except Exception:
            return cards

        # Build a session-scoped risk_level lookup from L3 governance_decisions.
        risk_by_hook: dict[str, str] = {}
        risk_by_tool: dict[str, str] = {}
        try:
            l3 = await self._open_l3()
            try:
                cur = await l3.execute(
                    """
                    SELECT hook_id, tool_name, risk_level
                    FROM governance_decisions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )
                rows = await cur.fetchall()
                for r in rows:
                    if r["hook_id"]:
                        risk_by_hook[str(r["hook_id"])] = str(r["risk_level"])
                    if r["tool_name"]:
                        risk_by_tool[str(r["tool_name"])] = str(
                            r["risk_level"]
                        )
            except Exception:
                pass
            finally:
                await l3.close()
        except Exception:
            pass

        try:
            cur = await l4.execute(
                """
                SELECT event_id, session_id, agent_id, hook_id, phase,
                       payload_json, received_at, tiebreaker
                FROM telemetry_events
                WHERE session_id = ?
                ORDER BY tiebreaker ASC, received_at ASC, event_id ASC
                """,
                (session_id,),
            )
            rows = await cur.fetchall()
        except Exception:
            return cards
        finally:
            await l4.close()

        for r in rows:
            payload = _parse_payload(r["payload_json"])
            tool_name = _extract_tool_name(payload, r["hook_id"])
            risk = (
                risk_by_hook.get(str(r["hook_id"]) or "")
                or risk_by_tool.get(tool_name)
                or _default_risk_level(payload)
            )
            received_at = str(r["received_at"] or "")
            cards.append(
                ActionCard(
                    id=_make_card_id(
                        "action", session_id, r["event_id"], tool_name
                    ),
                    session_id=str(r["session_id"]),
                    tenant_id=resolved_tenant,
                    created_at=_ts_to_iso(received_at),
                    summary=make_payload_summary(payload),
                    tool_seq=_safe_int(r["tiebreaker"]),
                    tool_name=tool_name,
                    risk_level=risk,
                    requested_at=received_at,
                    dispatched_at=received_at,
                    extra={
                        "agent_id": str(r["agent_id"] or ""),
                        "hook_id": str(r["hook_id"] or ""),
                        "phase": str(r["phase"] or ""),
                    },
                )
            )
        return cards

    # ─── ApprovalCard projection (CARD-APPROVAL-01..03) ─────────────────

    async def list_approval_cards(
        self, session_id: str, *, tenant_id: str | None = None
    ) -> list[ApprovalCard]:
        """Return every ApprovalCard for the session (CARD-APPROVAL-02).

        Includes the v3.11.2 5-stage rows (plan / check / draft /
        approve / execute) plus the v3.12.0 ``await_human`` and
        ``approve_pause`` paused-state rows.
        """
        resolved_tenant = tenant_id or await self._resolve_tenant(session_id)
        cards: list[ApprovalCard] = []
        try:
            db = await self._open_l3()
        except Exception:
            return cards
        try:
            cur = await db.execute(
                """
                SELECT decision_id, session_id, hook_id, tool_name,
                       risk_level, decision, approver, rationale,
                       stage, ts
                FROM governance_decisions
                WHERE session_id = ?
                ORDER BY ts ASC, decision_id ASC
                """,
                (session_id,),
            )
            rows = await cur.fetchall()
        except Exception:
            return cards
        finally:
            await db.close()

        for r in rows:
            rationale = str(r["rationale"] or "")
            # Rationale already IS the producer-supplied 1-line summary;
            # use it directly so the Cowork card renders the exact text.
            summary = make_payload_summary(rationale)
            cards.append(
                ApprovalCard(
                    id=_make_card_id(
                        "approval",
                        session_id,
                        r["stage"] or "",
                        r["decision_id"],
                    ),
                    session_id=str(r["session_id"]),
                    tenant_id=resolved_tenant,
                    created_at=_ts_to_iso(r["ts"]),
                    summary=summary,
                    decision_id=str(r["decision_id"]),
                    stage=str(r["stage"]) if r["stage"] else None,
                    decision=str(r["decision"] or ""),
                    approver=str(r["approver"]) if r["approver"] else None,
                    risk_level=str(r["risk_level"] or "read"),
                    tool_name=str(r["tool_name"] or ""),
                    extra={
                        "hook_id": str(r["hook_id"] or ""),
                    },
                )
            )
        return cards


# ─── Internal helpers (private — exported only for tests) ─────────────────


def _parse_payload(raw: Any) -> dict[str, Any]:
    """Best-effort JSON parse; returns ``{}`` on failure."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {"raw": raw[:200]}
    if isinstance(parsed, dict):
        return parsed
    return {"value": parsed}


def _extract_tool_name(payload: dict[str, Any], hook_id: Any) -> str:
    """Pull the canonical tool name out of a telemetry payload.

    Priority: explicit ``tool_name`` field → ``tool`` field →
    ``hook_id`` (L3 hook identifier — fallback when the L1
    runtime didn't surface the tool name) → ``"unknown"``.
    """
    for key in ("tool_name", "tool"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    if isinstance(hook_id, str) and hook_id:
        return hook_id
    return "unknown"


def _default_risk_level(payload: dict[str, Any]) -> str:
    """Best-effort risk_level fallback for actions without an L3 row.

    Reads the payload's ``risk_level`` / ``risk`` field if present;
    otherwise defaults to ``"read"`` (the no-side-effect floor —
    matches the v3.11.1 Rego template default).
    """
    for key in ("risk_level", "risk"):
        value = payload.get(key)
        if isinstance(value, str) and value in {
            "read",
            "write_local",
            "write_external",
            "privileged",
        }:
            return value
    return "read"


__all__ = ["CoworkProjection"]
