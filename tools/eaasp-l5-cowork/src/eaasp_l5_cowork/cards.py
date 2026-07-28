"""Four-card projection data model.

v3.13.0 — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action /
Approval).

Each card is a typed dataclass that derives its fields via SELECT
from the existing L2 / L3 / L4 / A2A SQLite stores (D-32). The
projection is **read-only** and never writes to the underlying
stores.

Card surfaces:

- ``EventCard``     — projection from L4 ``event_room_events`` row.
- ``EvidenceCard``  — projection from L2 ``anchors`` row (memory
                      anchor) joined to ``event_id`` via the
                      session-scoped anchor list.
- ``ActionCard``    — projection from L4 ``telemetry_events`` +
                      the canonical L3 ``risk_level`` carried on
                      the ``governance_decisions`` row.
- ``ApprovalCard``  — projection from L3 ``governance_decisions``
                      row (5-stage + ``await_human``).

The ``payload_summary`` / ``content_summary`` / ``rationale``
fields are deterministic 1-line summaries derived from the
underlying payload. The summariser is pure-functional and
read-only; it never reads from disk nor mutates state.

Card keying (REQ-IDs CARD-EVENT-02 / CARD-EVIDENCE-02 /
CARD-ACTION-02 / CARD-APPROVAL-02):

- EventCard     keyed by ``(session_id, event_seq)``
- EvidenceCard  keyed by ``anchor_id``
- ActionCard    keyed by ``(session_id, tool_seq)``
- ApprovalCard  keyed by ``(session_id, stage, decision_id)``

All cards carry a ``tenant_id`` field. Tenant binding is enforced
in the projection layer (the SELECT joins through
``event_room_members`` → ``event_rooms.tenant_id`` for Event /
Approval cards; for Evidence cards, the L2 anchor's session_id is
joined to the L4 session membership to resolve the tenant).

Frozen contract (audit §7.1): the dataclasses are best-effort
read projections. They NEVER mutate the underlying stores.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ─── Summary length budget (REQ-EVENT-03 / EVIDENCE-03 / APPROVAL-03) ─────
#
# 1-line deterministic summary. Long enough to convey context;
# short enough to fit a card UI row. Truncated with an ellipsis
# marker so the operator can tell truncation happened.
SUMMARY_MAX_LEN = 200
SUMMARY_ELLIPSIS = "..."


def _truncate_summary(text: str) -> str:
    """Truncate ``text`` to ``SUMMARY_MAX_LEN`` with an ellipsis marker.

    If ``text`` fits, return unchanged. Otherwise append the ellipsis
    marker so the consumer can detect truncation visually.
    """
    if len(text) <= SUMMARY_MAX_LEN:
        return text
    return text[: SUMMARY_MAX_LEN - len(SUMMARY_ELLIPSIS)] + SUMMARY_ELLIPSIS


def make_payload_summary(payload: dict[str, Any] | str | None) -> str:
    """Build a deterministic 1-line summary from an event payload.

    The summary is a single line (no newlines) and at most
    ``SUMMARY_MAX_LEN`` characters. It is *deterministic*: the same
    payload always produces the same string.

    Strategy: prefer a canonical ``summary`` field if the producer
    already set one; otherwise serialise the payload to a stable
    JSON (sort_keys=True, no spaces) and take a digest-hash tail.

    Examples:

        >>> make_payload_summary({"mode": "enforce", "risk": "write_external"})
        'mode=enforce risk=write_external'
        >>> make_payload_summary({"scada_set_setpoint": True, "room": "r-7"})
        'scada_set_setpoint=True room=r-7'
    """
    if payload is None:
        return "<empty>"
    if isinstance(payload, str):
        return _truncate_summary(payload.replace("\n", " "))
    if not isinstance(payload, dict):
        # Fallback for unknown types — stringify deterministically.
        return _truncate_summary(repr(payload).replace("\n", " "))

    # Producer-supplied summary wins (e.g. a2a.review.closed carries
    # ``final_decision``; we surface it).
    if "summary" in payload and isinstance(payload["summary"], str):
        return _truncate_summary(payload["summary"].replace("\n", " "))

    # Build a stable "k=v k=v" rendering. Sort keys for determinism;
    # skip nested dicts (collapse via len if present).
    parts: list[str] = []
    for k in sorted(payload.keys()):
        v = payload[k]
        if isinstance(v, dict):
            v = f"{{{len(v)}keys}}"
        elif isinstance(v, (list, tuple)):
            v = f"[{len(v)}]"
        elif v is None:
            v = "null"
        elif isinstance(v, bool):
            v = str(v)
        else:
            v = str(v)
        # Avoid newlines in the summary (single-line contract).
        v = v.replace("\n", " ").replace("\r", " ")
        parts.append(f"{k}={v}")
    raw = " ".join(parts)
    if not raw:
        # Fallback for empty dict — hash to keep determinism.
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        return f"<empty payload sha={digest}>"
    return _truncate_summary(raw)


def _ts_to_iso(ts: int | str | None) -> str | None:
    """Render a unix-epoch int (or ISO string) as UTC ISO-8601.

    Returns ``None`` if ``ts`` is ``None``. Best-effort: malformed
    values are returned as their string form so the projection
    surface remains stable.
    """
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (ValueError, OSError, TypeError):
        return str(ts)


# ─── Card base ────────────────────────────────────────────────────────────


@dataclass
class CardBase:
    """Common fields every four-card projection carries.

    All four card types share these fields so the Cowork backend
    can fan them out uniformly and the retrospective trace can
    sort / filter / group them in a single pass.
    """

    id: str
    """Stable per-card id — ``"<type>_<key_hash>"`` so a card's
    identity is deterministic across re-projections of the same
    underlying row.
    """

    session_id: str
    """Owning L4 session id (matches the underlying store's
    session_id column)."""

    tenant_id: str
    """Tenant binding (REQUIRED per D-33). Cross-tenant callers
    never see this card."""

    created_at: str | None
    """UTC ISO-8601 timestamp of the underlying event. ``None``
    for rows that lack a timestamp."""

    summary: str
    """Deterministic 1-line summary (see ``make_payload_summary``)."""

    # ─── Cross-card metadata (populated by the projection layer) ─────
    extra: dict[str, Any] = field(default_factory=dict)
    """Free-form extra metadata the projection layer attaches so
    the Cowork UI can render without an extra round-trip. Examples:
    ``{"event_type": "a2a.review.closed"}``, ``{"stage": "approve"}``.
    """

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict for JSON / SSE payload."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at,
            "summary": self.summary,
            **{f"extra_{k}": v for k, v in self.extra.items()},
        }


def _make_card_id(card_type: str, *key_parts: Any) -> str:
    """Build a deterministic card id from a card type + key parts.

    The id is a SHA-256 prefix so cards are stable across re-
    projection and safe to log / emit as SSE event ids.
    """
    h = hashlib.sha256()
    h.update(card_type.encode("utf-8"))
    for part in key_parts:
        h.update(b"\x1f")
        h.update(str(part).encode("utf-8"))
    return f"{card_type}_{h.hexdigest()[:16]}"


# ─── Event card (L4 event_room_events + session_events) ───────────────────


@dataclass
class EventCard(CardBase):
    """Projection from L4 ``event_room_events`` + ``session_events``.

    Field mapping (v3.13.0 — CARD-EVENT-01):

    - ``session_id`` ← ``event_room_events.session_id``
    - ``room_id``   ← ``event_room_events.room_id`` (None when
                       the projection pulls from ``session_events``)
    - ``event_type`` ← ``event_room_events.event_type``
    - ``summary``   ← deterministic 1-line summary of
                       ``payload_json``
    - ``created_at`` ← ``event_room_events.created_at``
    - ``tenant_id`` ← joined via ``event_rooms.tenant_id`` (or
                       via ``event_room_members`` membership)
    """

    event_seq: int = 0
    room_id: str | None = None
    event_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        out.update(
            {
                "card_type": "event",
                "event_seq": self.event_seq,
                "room_id": self.room_id,
                "event_type": self.event_type,
            }
        )
        return out


# ─── Evidence card (L2 anchors / memory_anchors) ──────────────────────────


@dataclass
class EvidenceCard(CardBase):
    """Projection from L2 ``anchors`` (memory_anchors).

    Field mapping (v3.13.0 — CARD-EVIDENCE-01):

    - ``id`` ← ``anchor_id`` (deterministic via ``_make_card_id``)
    - ``session_id`` ← ``anchors.session_id``
    - ``evidence_type`` ← ``anchors.type``
    - ``summary`` ← deterministic 1-line summary of ``metadata`` +
                     ``data_ref`` + ``source_system``
    - ``created_at`` ← ``anchors.created_at``
    - ``tenant_id`` ← joined via L4 ``event_room_members`` →
                       ``event_rooms.tenant_id`` (fallback: the
                       principal bound to the anchor's session via
                       the L4 session creator record).
    - ``confirmed`` ← true when the anchor has a ``snapshot_hash``
                      and ``tool_version`` set (the v3.7.3 L2
                      "confirmed" sentinel per anchor.md).
    """

    anchor_id: str = ""
    evidence_type: str = ""
    confirmed: bool = False

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        out.update(
            {
                "card_type": "evidence",
                "anchor_id": self.anchor_id,
                "evidence_type": self.evidence_type,
                "confirmed": self.confirmed,
            }
        )
        return out


# ─── Action card (L4 telemetry_events + L3 governance_decisions) ──────────


@dataclass
class ActionCard(CardBase):
    """Projection from L4 ``telemetry_events`` + L3 governance_decisions.

    Field mapping (v3.13.0 — CARD-ACTION-01):

    - ``session_id`` ← ``telemetry_events.session_id``
    - ``tool_name`` ← ``telemetry_events.hook_id`` (when present)
                       or extracted from ``payload_json.tool``
    - ``risk_level`` ← joined from the L3 ``governance_decisions``
                        row carrying the same ``hook_id`` (or, on
                        miss, defaults to ``"read"`` — the
                        no-side-effect floor; matches the v3.11.1
                        Rego template default).
    - ``tool_seq`` ← ``telemetry_events.tiebreaker`` (monotonic
                       per session)
    - ``summary`` ← deterministic 1-line summary of
                       ``payload_json``
    - ``requested_at`` ← ``telemetry_events.received_at``
    - ``dispatched_at`` ← ``telemetry_events.received_at``
                            (the L4 ingest path is synchronous
                            under the v3.7.3 PostToolUse hook).
    """

    tool_seq: int = 0
    tool_name: str = ""
    risk_level: str = "read"
    requested_at: str | None = None
    dispatched_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        out.update(
            {
                "card_type": "action",
                "tool_seq": self.tool_seq,
                "tool_name": self.tool_name,
                "risk_level": self.risk_level,
                "requested_at": self.requested_at,
                "dispatched_at": self.dispatched_at,
            }
        )
        return out


# ─── Approval card (L3 governance_decisions — 5-stage + await_human) ──────


@dataclass
class ApprovalCard(CardBase):
    """Projection from L3 ``governance_decisions``.

    Field mapping (v3.13.0 — CARD-APPROVAL-01):

    - ``id`` ← ``decision_id``
    - ``session_id`` ← ``governance_decisions.session_id``
    - ``stage`` ← ``governance_decisions.stage`` (one of
                   ``plan`` / ``check`` / ``draft`` / ``approve``
                   / ``execute`` / ``approve_pause`` / ``await_human``
                   per the v3.11.2 + v3.12.0 extensions)
    - ``decision`` ← ``governance_decisions.decision`` (one of
                      ``allow`` / ``approve`` / ``deny`` /
                      ``gate_request`` / ``await_human`` per the
                      v3.12.0 widened allowlist)
    - ``summary`` ← ``governance_decisions.rationale`` (truncated
                     to SUMMARY_MAX_LEN; the rationale is the
                     producer-supplied 1-line summary)
    - ``created_at`` ← ``governance_decisions.ts``
    - ``tenant_id`` ← joined via L4 ``event_room_members`` →
                       ``event_rooms.tenant_id`` (matches the
                       v3.12.1 D-28 pattern)
    """

    decision_id: str = ""
    stage: str | None = None
    decision: str = ""
    approver: str | None = None
    risk_level: str = "read"
    tool_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = super().to_dict()
        out.update(
            {
                "card_type": "approval",
                "decision_id": self.decision_id,
                "stage": self.stage,
                "decision": self.decision,
                "approver": self.approver,
                "risk_level": self.risk_level,
                "tool_name": self.tool_name,
            }
        )
        return out


__all__ = [
    "ActionCard",
    "ApprovalCard",
    "CardBase",
    "EvidenceCard",
    "EventCard",
    "SUMMARY_ELLIPSIS",
    "SUMMARY_MAX_LEN",
    "_make_card_id",
    "_truncate_summary",
    "_ts_to_iso",
    "make_payload_summary",
]
