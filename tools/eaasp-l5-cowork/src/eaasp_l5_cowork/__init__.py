"""EAASP v2.0 L5 Cowork UI substrate.

v3.13 — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action /
Approval) + 回溯闭环 (retrospective cycle).

Per EAASP_v2_0_EVOLUTION_PATH.md §三 Phase 5 + spec §4 + §4.4:

- The L5 Cowork substrate is a **projection layer** over already-
  shipped L2 (memory_anchors), L3 (governance_decisions + 5-stage
  approval), L4 (event_room_events) + A2A (review.closed). v3.13
  ships **no new tables**, **no new columns**, **no new event
  types**, **no new service ports**, and **no new frontend** (web/
  + web-platform/ remain dormant per the v3.13 bootstrap D-37).
- The projection exposes four card types:
    * ``EventCard``     — from L4 ``event_room_events``
    * ``EvidenceCard``  — from L2 ``anchors`` (memory_anchors)
    * ``ActionCard``    — from L4 ``telemetry_events`` + L3
                          ``governance_decisions`` (risk_level)
    * ``ApprovalCard``  — from L3 ``governance_decisions``
                          (5-stage + await_human)
- The retrospective cycle (``retrospective.py``) joins the four
  card lists into a single ``RetrospectiveChain`` + cross-refs
  + trace API + ``eaasp cowork trace {session_id}`` CLI.

Locked decisions (per ``.planning/PROJECT.md`` D-30..D-37):

- **D-30** — projection only (no new tables / no new columns / no
  new event types).
- **D-31** — read-only by default (RETROSPECTIVE-04 idempotency).
- **D-32** — every card is a SELECT from the L2/L3/L4 store, not
  a COPY.
- **D-33** — tenant-bound by membership (v3.12.1 D-28 pattern);
  cross-tenant calls rejected with 403.
- **D-34** — executable floor = Phase 0.5 MVP threshold-
  calibration skill (real LLM key + mock-scada).
- **D-35** — reused FastAPI / loguru / aiosqlite stack (matches
  L4 orchestration conventions).
- **D-36** — SSE event family = ``cowork.card.<type>.<event>``
  + ``cowork.workflow.<event>`` (matches v3.11.2 governance.* and
  v3.12.2 a2a.* family naming).
- **D-37** — no new frontend in v3.13; web/ + web-platform/
  remain dormant.

Boundary invariants (ADR-V2-023 P1 + v3.9 RBAC + v3.10 spec-audit
+ ADR-V2-034 OPA sidecar):

- The L5 substrate lives at ``tools/eaasp-l5-cowork/`` alongside
  the other ``tools/eaasp-*`` simulators.
- No shared crate (grid-engine / grid-runtime / grid-types /
  grid-sandbox / grid-hook-bridge) is touched — the projection
  reads the existing L2/L3/L4 SQLite stores directly.
- No new routes are added to the grid-server route catalog;
  Cowork endpoints live under the L5 FastAPI app on a dedicated
  port (env-configurable; default ``:18086``).
"""

from __future__ import annotations

__version__ = "0.1.0"

from .cards import (
    ActionCard,
    ApprovalCard,
    CardBase,
    EvidenceCard,
    EventCard,
    make_payload_summary,
)
from .cowork import CoworkBackend, CoworkConfig
from .projection import CoworkProjection
from .retrospective import (
    CrossRef,
    RetrospectiveChain,
    RetrospectiveTrace,
)

__all__ = [
    "ActionCard",
    "ApprovalCard",
    "CardBase",
    "CoworkBackend",
    "CoworkConfig",
    "CoworkProjection",
    "CrossRef",
    "EvidenceCard",
    "EventCard",
    "RetrospectiveChain",
    "RetrospectiveTrace",
    "make_payload_summary",
]
