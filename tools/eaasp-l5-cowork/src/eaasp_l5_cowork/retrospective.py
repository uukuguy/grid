"""Retrospective cycle (回溯闭环) — full implementation (v3.13.2).

v3.13.2 — EAASP Phase 5 — L5 Cowork 四卡 + 回溯闭环 (retrospective
cycle).

REQ-IDs: RETROSPECTIVE-01..05.

- RETROSPECTIVE-01: ``trace_session(session_id) -> RetrospectiveChain``
  carrying the four card lists in canonical order + cross_refs
  linking each card to the cards that caused it.
- RETROSPECTIVE-02: ``GET /v1/cowork/trace/{session_id}`` REST endpoint.
- RETROSPECTIVE-03: ``eaasp cowork trace {session_id}`` CLI command.
- RETROSPECTIVE-04: trace is **read-only** and **idempotent** —
  ``trace_session(s)`` invoked twice for the same ``session_id``
  returns the same chain (modulo deterministic ordering).
- RETROSPECTIVE-05: trace is **tenant-bound** — cross-tenant calls
  rejected with 403.

Cross-ref shape (the v3.13.0 placeholder + v3.13.2 substance):

- ``action_evidence`` — an Action card cross-references its
  upstream Evidence card (matching ``event_id`` → ``anchor.event_id``).
- ``approval_action`` — an Approval card cross-references its
  driving Action card (matching ``hook_id`` + ``tool_name``).
- ``event_action`` — an Event card cross-references its triggering
  Action card (matching the ``tool_name`` payload field).
- ``approval_event`` — an Approval card cross-references the Event
  card that emitted the corresponding SSE event.

The cross-refs are computed deterministically — same inputs →
same edges, every time (RETROSPECTIVE-04 idempotency invariant).

The trace is read-only: it NEVER mutates any L2 / L3 / L4 record
or any Cowork state machine row (RETROSPECTIVE-04).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .projection import CoworkProjection
from .state import CoworkStateStore

if TYPE_CHECKING:
    from .cards import (
        ActionCard,
        ApprovalCard,
        EvidenceCard,
        EventCard,
    )


# ─── Cross-ref types ─────────────────────────────────────────────────────


CROSSREF_ACTION_EVIDENCE = "action_evidence"
CROSSREF_APPROVAL_ACTION = "approval_action"
CROSSREF_EVENT_ACTION = "event_action"
CROSSREF_APPROVAL_EVENT = "approval_event"


@dataclass
class CrossRef:
    """A directed edge between two cards in a retrospective chain.

    Field semantics (RETROSPECTIVE-01):

    - ``source_card_id`` — the downstream card (the one caused by
      the upstream card). For example, in an ``action_evidence``
      edge, ``source_card_id`` is the Action card and
      ``target_card_id`` is the Evidence card.
    - ``target_card_id`` — the upstream card.
    - ``kind`` — one of the ``CROSSREF_*`` constants.
    - ``rationale`` — human-readable 1-line rationale for the
      edge (used by the CLI to render the trace).
    """

    source_card_id: str
    target_card_id: str
    kind: str
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_card_id": self.source_card_id,
            "target_card_id": self.target_card_id,
            "kind": self.kind,
            "rationale": self.rationale,
        }


# ─── Chain shape ─────────────────────────────────────────────────────────


@dataclass
class RetrospectiveChain:
    """The full retrospective chain for a single session.

    Carries the four card lists in canonical order +
    ``cross_refs`` linking each card to the cards that caused it.
    Read-only and idempotent (RETROSPECTIVE-04).
    """

    session_id: str
    tenant_id: str
    events: list["EventCard"] = field(default_factory=list)
    evidence: list["EvidenceCard"] = field(default_factory=list)
    actions: list["ActionCard"] = field(default_factory=list)
    approvals: list["ApprovalCard"] = field(default_factory=list)
    cross_refs: list[CrossRef] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "events": [e.to_dict() for e in self.events],
            "evidence": [e.to_dict() for e in self.evidence],
            "actions": [a.to_dict() for a in self.actions],
            "approvals": [a.to_dict() for a in self.approvals],
            "cross_refs": [r.to_dict() for r in self.cross_refs],
            "summary": {
                "events": len(self.events),
                "evidence": len(self.evidence),
                "actions": len(self.actions),
                "approvals": len(self.approvals),
                "cross_refs": len(self.cross_refs),
            },
        }


# ─── Errors ──────────────────────────────────────────────────────────────


class CrossTenantForbidden(Exception):
    """Raised when a cross-tenant trace is attempted (RETROSPECTIVE-05)."""


# ─── Trace facade ───────────────────────────────────────────────────────


class RetrospectiveTrace:
    """Trace facade — the canonical entry point for RETROSPECTIVE-01.

    Construction accepts the projection + the state store. The
    facade does NOT mutate any of those stores; every accessor
    is a read-only projection / query.

    Frozen contract (audit §7.1 + RETROSPECTIVE-04): the facade
    is best-effort and idempotent. Two calls with the same
    inputs return the same chain (modulo deterministic ordering
    + tenant binding).
    """

    def __init__(
        self,
        projection: CoworkProjection,
        state_store: CoworkStateStore | None = None,
    ) -> None:
        self.projection = projection
        self.state_store = state_store

    async def trace_session(
        self,
        session_id: str,
        *,
        tenant_id: str,
    ) -> RetrospectiveChain:
        """Return the full ``RetrospectiveChain`` for ``session_id``.

        RETROSPECTIVE-01 + RETROSPECTIVE-04 + RETROSPECTIVE-05:
        tenant-bound, read-only, idempotent.
        """
        # Project the four card lists (read-only — D-31/D-32).
        events = await self.projection.list_event_cards(
            session_id, tenant_id=tenant_id
        )
        evidence = await self.projection.list_evidence_cards(
            session_id, tenant_id=tenant_id
        )
        actions = await self.projection.list_action_cards(
            session_id, tenant_id=tenant_id
        )
        approvals = await self.projection.list_approval_cards(
            session_id, tenant_id=tenant_id
        )

        # Defensive tenant gate: every card must match the caller
        # tenant (RETROSPECTIVE-05). If any card disagrees, the
        # projection is in an inconsistent state — refuse the
        # entire chain rather than emit a partial trace.
        for c in (*events, *evidence, *actions, *approvals):
            if c.tenant_id != tenant_id:
                raise CrossTenantForbidden(
                    f"card {c.id!r} has tenant_id={c.tenant_id!r} "
                    f"but caller is {tenant_id!r}"
                )

        chain = RetrospectiveChain(
            session_id=session_id,
            tenant_id=tenant_id,
            events=events,
            evidence=evidence,
            actions=actions,
            approvals=approvals,
        )
        chain.cross_refs = _compute_cross_refs(chain)
        return chain


# ─── Cross-ref derivation (deterministic) ───────────────────────────────


def _compute_cross_refs(chain: RetrospectiveChain) -> list[CrossRef]:
    """Compute the cross_refs for ``chain`` deterministically.

    Pure function — same ``chain`` → same list every time
    (RETROSPECTIVE-04 invariant). Sorted by
    ``(source_card_id, kind, target_card_id)`` so the order is
    stable across invocations.
    """
    refs: list[CrossRef] = []

    # Index evidence by event_id (every anchor carries its event_id).
    evidence_by_event: dict[str, list] = {}
    for ev in chain.evidence:
        event_id = ev.extra.get("event_id", "")
        if event_id:
            evidence_by_event.setdefault(event_id, []).append(ev)

    # Index approvals by (hook_id, tool_name).
    approvals_by_tool: dict[tuple[str, str], list] = {}
    for ap in chain.approvals:
        key = (
            ap.extra.get("hook_id", ""),
            ap.tool_name or "",
        )
        approvals_by_tool.setdefault(key, []).append(ap)

    # Index events by event_type + payload.tool_name when present.
    events_by_tool: dict[str, list] = {}
    for ev in chain.events:
        tool_name = ""
        try:
            payload = ev.summary  # summary is a deterministic 1-line
            # The summary encodes payload.tool_name when present.
            for tok in payload.split():
                if tok.startswith("tool="):
                    tool_name = tok.split("=", 1)[1]
                    break
        except Exception:
            tool_name = ""
        if tool_name:
            events_by_tool.setdefault(tool_name, []).append(ev)

    # Edges:
    # 1. action → evidence (matching event_id via payload field).
    for action in chain.actions:
        # The action payload summary may carry event_id; otherwise
        # fall back to hook_id-based matching (not always
        # possible, but the hook_id → event_id link lives in the
        # action.extra dict).
        action_event_id = action.extra.get("event_id", "")
        if action_event_id and action_event_id in evidence_by_event:
            for ev in evidence_by_event[action_event_id]:
                refs.append(
                    CrossRef(
                        source_card_id=action.id,
                        target_card_id=ev.id,
                        kind=CROSSREF_ACTION_EVIDENCE,
                        rationale=(
                            f"action {action.tool_name!r} was "
                            f"anchored by evidence {ev.anchor_id!r}"
                        ),
                    )
                )

    # 2. approval → action (matching hook_id + tool_name).
    for ap in chain.approvals:
        key = (
            ap.extra.get("hook_id", ""),
            ap.tool_name or "",
        )
        for action in chain.actions:
            if (action.extra.get("hook_id", ""), action.tool_name) == key:
                refs.append(
                    CrossRef(
                        source_card_id=ap.id,
                        target_card_id=action.id,
                        kind=CROSSREF_APPROVAL_ACTION,
                        rationale=(
                            f"approval {ap.stage}/{ap.decision} gated "
                            f"action {action.tool_name!r}"
                        ),
                    )
                )

    # 3. event → action (matching payload tool_name).
    for ev in chain.events:
        try:
            for tok in ev.summary.split():
                if tok.startswith("tool="):
                    tool_name = tok.split("=", 1)[1]
                    for action in chain.actions:
                        if action.tool_name == tool_name:
                            refs.append(
                                CrossRef(
                                    source_card_id=ev.id,
                                    target_card_id=action.id,
                                    kind=CROSSREF_EVENT_ACTION,
                                    rationale=(
                                        f"event {ev.event_type!r} "
                                        f"triggered action {tool_name!r}"
                                    ),
                                )
                            )
        except Exception:
            continue

    # 4. approval → event (matching stage ↔ event_type).
    event_by_type: dict[str, list] = {}
    for ev in chain.events:
        event_by_type.setdefault(ev.event_type, []).append(ev)
    for ap in chain.approvals:
        if not ap.stage:
            continue
        evt_type = f"governance.approval.{ap.stage}"
        for ev in event_by_type.get(evt_type, []):
            refs.append(
                CrossRef(
                    source_card_id=ap.id,
                    target_card_id=ev.id,
                    kind=CROSSREF_APPROVAL_EVENT,
                    rationale=(
                        f"approval stage {ap.stage!r} emitted "
                        f"event {evt_type!r}"
                    ),
                )
            )

    # Deterministic sort (RETROSPECTIVE-04).
    refs.sort(
        key=lambda r: (r.source_card_id, r.kind, r.target_card_id)
    )
    return refs


# ─── Render helpers (used by the CLI + walkthrough) ─────────────────────


def render_trace_human(chain: RetrospectiveChain) -> str:
    """Render ``chain`` as a human-readable 1-line-per-card block.

    Used by the ``eaasp cowork trace {session_id}`` CLI
    (RETROSPECTIVE-03). Output is deterministic — same chain
    always produces the same string.
    """
    lines: list[str] = []
    lines.append(
        f"Retrospective chain session_id={chain.session_id} "
        f"tenant_id={chain.tenant_id}"
    )
    lines.append(
        f"  summary: "
        f"{len(chain.events)} events / "
        f"{len(chain.evidence)} evidence / "
        f"{len(chain.actions)} actions / "
        f"{len(chain.approvals)} approvals / "
        f"{len(chain.cross_refs)} cross_refs"
    )
    lines.append("  events:")
    for ev in chain.events:
        lines.append(f"    [{ev.event_seq:>4}] {ev.event_type}  {ev.summary}")
    lines.append("  evidence:")
    for ev in chain.evidence:
        marker = "✓" if ev.confirmed else "·"
        lines.append(
            f"    {marker} {ev.anchor_id}  {ev.evidence_type}  {ev.summary}"
        )
    lines.append("  actions:")
    for ac in chain.actions:
        lines.append(
            f"    [{ac.tool_seq:>4}] {ac.tool_name}  "
            f"risk={ac.risk_level}  {ac.summary}"
        )
    lines.append("  approvals:")
    for ap in chain.approvals:
        lines.append(
            f"    [{ap.stage or '-':>8}] {ap.decision}  {ap.summary}"
        )
    lines.append("  cross_refs:")
    for ref in chain.cross_refs:
        lines.append(
            f"    {ref.kind}: {ref.source_card_id} -> {ref.target_card_id}"
        )
    return "\n".join(lines)


__all__ = [
    "CROSSREF_ACTION_EVIDENCE",
    "CROSSREF_APPROVAL_ACTION",
    "CROSSREF_APPROVAL_EVENT",
    "CROSSREF_EVENT_ACTION",
    "CrossRef",
    "CrossTenantForbidden",
    "RetrospectiveChain",
    "RetrospectiveTrace",
    "render_trace_human",
]
