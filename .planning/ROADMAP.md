# Grid — Roadmap

> **Milestone:** Grid 独立产品 Activation 🟡 SCOPING
> **Previous milestones:** v3.5 Debt Finalization ✅ (2026-06-16), v3.4 Full INBOX Drain ✅ (2026-06-16)
> **Archive:** `milestones/v3.4-ROADMAP.md`, `milestones/v3.5-ROADMAP.md`

## Milestones

- ✅ **v3.0 Phase 4 — Product Scope Decision** — (shipped 2026-04-28, ADR-V2-024 Accepted)
- ✅ **v3.1 Phase 5 — Engine Hardening** — SHIPPED 2026-05-22 (6 phases, 23 REQ-IDs, 6 ADRs)
- ✅ **v3.2 Phase 6 — Tech-Debt Triage** — SHIPPED 2026-05-26 (3 phases, 6 REQ-IDs)
- ✅ **v3.3 Phase 7 — Engine + Platform Debt Sweep** — SHIPPED 2026-06-07 (Phase 7.3 L3 RBAC, 8/8 REQ-IDs)
- ✅ **v3.4 Phase 7/8 — Full INBOX Drain** — SHIPPED 2026-06-16 (10 phases, 67 REQ-IDs, 2 ADRs)
- ✅ **v3.5 Phase 9 — Debt Finalization** — SHIPPED 2026-06-16 (3 phases, LEDGER 100% CLOSED)
- 🟡 **Grid 独立产品 Activation** — SCOPING (post-debt, post-v3.5)

---

## Milestone: Grid 独立产品 Activation 🟡

**Goal:** Activate the dormant Grid independent product leg per ADR-V2-024. All technical debt cleared (DEFERRED_LEDGER.md 100% ✅ CLOSED). Shift from debt-sweep mode to product-building mode.

**Context:** Grid has been built primarily through its engine 接入面 (EAASP integration). The independent product crates (`grid-server`, `grid-platform`, `grid-desktop`, `web/`, `web-platform/`, `grid-eval`) exist but are dormant — scaffolding or partially-featured. The engine layer is production-ready. Now activate the product surface.

**Activation targets (priority-ordered per ADR-V2-024 Open Item #3):**

| Crate/App | Current State | Activation Needed |
|-----------|--------------|-------------------|
| **grid-cli** | Feature-complete (command tree, streaming, TUI, session mgmt) | Audit + doc polish, verify prod-readiness |
| **grid-server** | WS + auth + config hot-reload (v3.1) | Feature set audit, frontend pairing, full endpoint spec |
| **web/** (single-user UI) | Scaffolding only (React + Vite + Jotai + Tailwind) | Full UI implementation |
| **grid-platform** | Scaffolding only (Axum + JWT + quota) | Full multi-tenant server implementation |
| **web-platform/** (multi-tenant UI) | Scaffolding only | Full UI implementation |
| **grid-desktop** | Tauri app scaffolding | Full desktop app implementation |
| **grid-eval** | Scaffolding only | Evaluation suite implementation |

**Shared core rule (ADR-V2-023 P1, retained under ADR-V2-024):** changes to `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` must work for both engine 接入面 (EAASP) and Grid independent product.

### Phase Plan (draft — to be refined after audit)

- [ ] **Phase A.0: Audit & Scoping** — Audit grid-server feature set, grid-cli readiness, web/ scaffolding. Produce gap analysis + prioritized backlog.
- [ ] **Phase A.1: grid-server Feature Audit & Hardening** — Full endpoint audit, config completeness, error handling. Make grid-server production-ready as single-user workbench backend.
- [ ] **Phase A.2: web/ Single-User UI — Foundation** — React SPA shell, routing, API client, auth flow. Connect to grid-server.
- [ ] **Phase A.3: web/ Single-User UI — Core Features** — Session management, tool execution, streaming, settings. Full workbench experience.
- [ ] **Phase A.4: grid-cli Polish & Docs** — CLI audit, help text, man page, install script, release CI.
- [ ] **Phase A.5: grid-platform Multi-Tenant Backend** — JWT auth, tenant isolation, quota management, admin API.
- [ ] **Phase A.6: web-platform/ Multi-Tenant UI** — Admin dashboard, tenant management.
- [ ] **Phase A.7: grid-desktop Tauri App** — Wrap web/ + grid-server into desktop bundle.
- [ ] **Phase A.8: grid-eval Suite** — Eval harness, benchmarks, standard suites.

### Dependencies

```
A.0 Audit ──┬── A.1 grid-server ──┬── A.2 web/ foundation ── A.3 web/ features
            │                     │
            └── A.4 grid-cli polish
            │
            └── A.5 grid-platform ── A.6 web-platform/
                                    └── A.7 grid-desktop (after A.3 + A.1)
                                    
A.8 grid-eval — independent, can run anytime
```

### Success Criteria

1. grid-server: all endpoints documented, configuration complete, error handling consistent, test coverage ≥80%
2. web/: single-user workbench with session management, streaming tool output, settings
3. grid-cli: polished help text, installable via `cargo install`, CI release pipeline
4. grid-platform: multi-tenant auth working, quota enforced, admin API functional
5. grid-desktop: Tauri bundle running grid-server + web/ as desktop app
6. grid-eval: at least 3 standard benchmark suites, scoring framework

---

## Progress

| Phase | Plans | Status | Notes |
|-------|-------|--------|-------|
| A.0 Audit & Scoping | 0/1 | 🟡 Pending | Assess all dormant crates |
| A.1 grid-server | 0/? | ⬜ Not Scoped | Depends on A.0 |
| A.2 web/ foundation | 0/? | ⬜ Not Scoped | Depends on A.1 |
| A.3 web/ features | 0/? | ⬜ Not Scoped | Depends on A.2 |
| A.4 grid-cli | 0/? | ⬜ Not Scoped | Depends on A.0 |
| A.5 grid-platform | 0/? | ⬜ Not Scoped | Depends on A.0 |
| A.6 web-platform/ | 0/? | ⬜ Not Scoped | Depends on A.5 |
| A.7 grid-desktop | 0/? | ⬜ Not Scoped | Depends on A.3 + A.1 |
| A.8 grid-eval | 0/? | ⬜ Not Scoped | Independent |

---

## Coverage Index

To be populated after Phase A.0 audit — REQ-IDs will map to specific gaps discovered.

---

*Last updated: 2026-06-16 — v3.4/v3.5 shipped, Grid 独立产品 activation roadmap created. Next: Phase A.0 audit.*
