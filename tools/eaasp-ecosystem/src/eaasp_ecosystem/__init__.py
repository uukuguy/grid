"""EAASP v2.0 Phase 6 — Ecosystem expansion (Ontology + Skill Marketplace).

v3.14 — EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem
(final phase of the EVOLUTION_PATH §三 8-Phase 路线).

Per ``EAASP_v2_0_EVOLUTION_PATH.md`` §三 Phase 6 + spec §7.5–§7.8:

- The ecosystem substrate is a **projection layer** over the
  already-shipped v3.13 L5 Cowork four-card projection + L2
  evidence anchor + L3 governance_decisions + L4 event_room +
  v3.11.2 ``eaasp-skill-registry``. v3.14 ships **no new
  tables**, **no new columns**, **no new event types**, **no new
  service ports**, and **no new frontend** (web/ + web-platform/
  remain dormant per D-39).
- The Ontology service derives a taxonomy + cross-domain links
  purely by SELECT against the existing stores (per D-40
  "派生不复制"). The Marketplace API extends (does not replace)
  the v3.11.2 ``eaasp-skill-registry`` (per D-41). The SDK
  scaffolding is a thin client wrapper that does NOT re-
  implement business logic (per D-42).

Locked decisions (per ``.planning/PROJECT.md`` D-38..D-46):

- **D-38** — v3.14 scope = EAASP Phase 6 ecosystem; final
  phase; closes ``V310-ECOSYSTEM-01`` + 8-Phase roadmap.
- **D-39** — no new repo / no new service port / no new
  frontend. Ecosystem endpoints sit behind the existing L4
  service port (default ``:18084``) — the ecosystem package is
  a third-party Python module that *consumes* the existing L2 /
  L3 / L4 / skill-registry services via HTTP (per COMPAT-05).
- **D-40** — Ontology 派生不复制: every ``TaxonomyNode`` /
  ``CrossDomainLink`` / ``MarketplaceSkill`` / ``SubmissionAudit``
  derives via SELECT from existing tables. No new tables, no
  new columns, no new event types.
- **D-41** — Marketplace extends (not replaces) v3.11.2
  ``eaasp-skill-registry`` (Cargo). The 4-stage promotion
  lifecycle writes new lifecycle rows to the registry's
  existing ``skill_lifecycle`` table; ACL + analytics are
  computed on top.
- **D-42** — SDK scaffolding is a thin client wrapping the
  marketplace + ontology endpoints. No business logic re-
  implementation. ``sdk/python/eaasp_sdk/`` is the typed
  Python client; ``tools/eaasp-ecosystem-sdk/`` is the CLI
  wrapper + JSON-schema codegen hooks.
- **D-43** — executable floor = Phase 0.5 MVP threshold-
  calibration skill + ``make dev-eaasp``. v3.14.3 produces
  ``docs/status/PRODUCTION_USABILITY_2026-07-30.md`` exercising
  the full ecosystem walkthrough against the real OPA sidecar
  + Event Room + A2A Router + L5 Cowork + Ontology + Marketplace
  + SDK.
- **D-44** — v3.9 RBAC + v3.10 spec-audit + ADR-V2-034 OPA
  sidecar + v3.12 Event Room + v3.12.2 A2A Router + v3.13 L5
  Cowork + retrospective all continue to PASS. ADR-V2-023 P1
  shared-core rule unchanged.
- **D-45** — Explore + Grep exploration strategy (no
  ``.codegraph/`` in this repo).
- **D-46** — v3.14 is the final phase of the 8-Phase roadmap;
  once 03.14.3 ships, ``V310-ECOSYSTEM-01`` → ✅ CLOSED and
  the 8-Phase roadmap is declared ALL SHIPPED.

Boundary invariants (ADR-V2-023 P1 + v3.9 RBAC + v3.10
spec-audit + ADR-V2-034 OPA sidecar):

- The ecosystem package lives at ``tools/eaasp-ecosystem/``
  alongside the other ``tools/eaasp-*`` simulators.
- No shared crate (grid-engine / grid-runtime / grid-types /
  grid-sandbox / grid-hook-bridge) is touched — the projection
  layer is read-only against the L2 / L3 / L4 / L5 SQLite
  stores, never writes to them.
- Cross-tenant access is rejected with 403 (D-33-style tenant
  guard, matching v3.12.1 Event Room + v3.13 L5 Cowork).
"""

from __future__ import annotations

__all__ = [
    "__version__",
]

__version__ = "0.1.0"