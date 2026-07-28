"""Retrospective cycle (回溯闭环) — placeholder for 03.13.2.

v3.13.0 ships a placeholder module so the public API
(``RetrospectiveChain``, ``RetrospectiveTrace``, ``CrossRef``)
can be imported by the Cowork backend + the CLI shim. The
full implementation — RETROSPECTIVE-01..05 + idempotency +
cross-tenant 403 boundary — lands in 03.13.2.

Until 03.13.2 lands, this module exposes the type surface so
``from eaasp_l5_cowork import RetrospectiveChain`` does not
break callers (CLI, downstream tooling).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cards import ActionCard, ApprovalCard, EvidenceCard, EventCard


@dataclass
class CrossRef:
    """A directed edge between two cards in a retrospective chain.

    Final shape lands in 03.13.2; the placeholder carries the
    same field names so the public API is stable.
    """

    source_card_id: str
    target_card_id: str
    kind: str  # e.g. "action_evidence", "approval_action", "event_action"
    rationale: str = ""


@dataclass
class RetrospectiveChain:
    """The full retrospective chain for a single session.

    Carries the four card lists in canonical order + cross-refs
    linking each card to the cards that caused it. Read-only and
    idempotent (RETROSPECTIVE-04 lands in 03.13.2).
    """

    session_id: str
    tenant_id: str
    events: list["EventCard"] = field(default_factory=list)
    evidence: list["EvidenceCard"] = field(default_factory=list)
    actions: list["ActionCard"] = field(default_factory=list)
    approvals: list["ApprovalCard"] = field(default_factory=list)
    cross_refs: list[CrossRef] = field(default_factory=list)


@dataclass
class RetrospectiveTrace:
    """Trace facade — full implementation lands in 03.13.2.

    Placeholder so callers can import and construct without
    ImportError. The real class will accept ``CoworkProjection``
    + tenant binding + idempotency hooks.
    """

    session_id: str
    tenant_id: str


__all__ = [
    "CrossRef",
    "RetrospectiveChain",
    "RetrospectiveTrace",
]
