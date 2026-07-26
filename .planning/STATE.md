---
gsd_state_version: 1.0
milestone: v3.9
milestone_name: route-catalog RBAC wiring + authorization auditor
status: shipped
stopped_at: v3.9 SHIPPED; 03.9.0-03.9.2 complete
last_updated: "2026-07-26T00:00:00.000Z"
last_activity: 2026-07-26
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Grid 作为 substitutable L1 runtime,通过 gRPC contract 被 EAASP L2-L4 调用,且任何符合 `contract-v1.2.0` 的对比 runtime 都能替换它。`contract-v1.1.0` 是 Phase 3 sign-off 历史契约版本(2026-04-18,42 PASS / 22 XFAIL × 7 runtime)。
**Current focus:** Milestone v3.9 (route-catalog RBAC wiring + authorization auditor) SHIPPED 2026-07-26. All 3 phases and 20/20 REQ-IDs complete.

Canonical product-status sources:

- `docs/PROJECT_PRODUCT_OVERVIEW.md` (maintained SSOT)
- `docs/status/PROJECT_STATUS_2026-07-17.md` (dated audit snapshot)

## Current Position

Milestone: **v3.9 route-catalog RBAC wiring + authorization auditor ✅ SHIPPED 2026-07-26**
Scope: 3 phases planned (03.9.0 → 03.9.2), 20 REQ-IDs in 5 categories (CAT / AUD / RBAC / MODE / TEST+DOC).
Closes: v3.8.2 plan §Task 4 explicit deferral ("the rest of the endpoints stay un-scoped for v3.8.2 ... full-catalog coverage is v3.9+") + RESUME-NEXT-SESSION §Optional sidequests ("Audit the route catalog for `requires(Action)` annotations").

Next-milestone candidates (after v3.9 SHIPS):

- `web-platform/` Quality 7.5→9.0.
- `grid-desktop` Quality 6.5→9.0.
- EAASP Phase 3 production OPA / Phase 4 A2A / Phase 5 L5 / Phase 6 ecosystem.

## Audit Findings Summary (Post-Activation Scores)

| Crate | Activation Score | Quality Score | Key Remaining Gaps |
|-------|-----------------|---------------|-------------------|
| grid-cli | 8/10 | **9.0** ✅ | 140+ tests, 16 commands, full TUI |
| web/ | 7/10 | **9.0** ✅ | 9 vitest tests, 8 tabs, no mocks |
| grid-server | 6/10 | **9.0** ✅ | 25 integration test files, HMAC/JWT, ~130 endpoints |
| grid-eval | 7/10 | **9.0** ✅ | 10 scorers, 12 suites, CI workflow, parallel runner |
| grid-platform | 6/10 | **9.0** ✅ | 37 tests, ErrorCode enum, quota wired, 5MB limits |
| web-platform/ | 3/10 | **7.5** | Markdown + toast + skeletons + error states |
| grid-desktop | 3/10 | **6.5** | Icons, IPC proxy, Grid rebrand |

### Quality Improvements (Phase B — 2026-06-17)

| Component | Changes | Tests Before → After |
|-----------|--------|---------------------|
| grid-platform | quota consume, 20 new integration tests | 17 → **37** |
| web-platform/ | Loading skeletons, toast errors, empty states, cn() utility | 0 → 0 (UI components) |
| grid-desktop | Icon assets (PNG), 3 new IPC commands, Grid rebrand | 9 → 9 |
| grid-eval | CI concurrency group, test summary reporting | existing |

*5/7 components at 9.0+. web-platform/ and grid-desktop need functional feature work for 9.0+.*

## Completed Milestones

### v3.8 grid-server multi-user login ✅ SHIPPED 2026-07-24

- 4 phases (03.8.0 / 03.8.1 / 03.8.2 / 03.8.3), 21 REQ-IDs in 6 categories.
- JWT primitive + AuthMode::Full path + login/refresh/logout endpoints + RBAC route enforcement + TenantContext::for_multi_user + cross-tenant isolation + tenant-scoped audit + USER_GUIDE §11 + PRODUCTION_USABILITY walkthrough + regression sweep.
- 119/119 targeted tests PASS, 3 security hotfixes (CRITICAL blacklist bypass + HIGH refresh stale-claim + HIGH audit IDOR).
- Demonstrated `requires(Action)` on 3 representative routes (`/admin/users`, `/audit`, `/sessions/{id}`); remaining ~127 endpoints in `crates/grid-server/src/api/mod.rs` + `router.rs` deferred to v3.9 per 03.8.2 plan §Task 4 + RESUME-NEXT-SESSION §Optional sidequests.
- Archive: `.planning/milestones/v3.8-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`.

### v3.7 实战可用性补全 ✅ SHIPPED 2026-07-23

- 3 phases (3.7.1, 3.7.2, 3.7.3), 9/9 REQ-AUDITs + 8/8 REQ-EAASP closed.
- Phase 3.7.1: grid-cli 实战可用性 (S1-S6 scenarios, 14/14 hermetic tests).
- Phase 3.7.2: web/ Production Polish + Makefile entry points + USER_GUIDE §10.
- Phase 3.7.3: EAASP governance gate (REQ-EAASP-01..08) — L3 risk-aware gate,
  L4 SSE events, CLI sync approval UX, mock-SCADA scada_set_setpoint,
  S8 walkthrough, dated evidence (136 tests PASS).

### v3.6 Post-Activation Docs Sync ✅ SHIPPED 2026-07-19

- 3 sub-phases (3.6.1 SSOT + snapshot, 3.6.2 AGENTS + CLAUDE + READMEs, 3.6.3 STATE + PROJECT).
- 7 docs commits @ `a29f626`, UAT 46/46 PASS.

### v3.5 Debt Finalization ✅ SHIPPED 2026-06-16

- 3 phases (9.0/9.1/9.2), 0 ADRs
- LEDGER main D-table: 100% ✅ CLOSED (56 rows standardized)
- Phase 9.0: LEDGER audit + normalize 56 D-rows (17 notation fix + 30 newly closed + 9 genuine actives)
- Phase 9.1: D121 stop-hook dedup warn + D122 env-parity verify + D123 RAII EnvGuard
- Phase 9.2: Final LEDGER close-out, 100% uniformity

### v3.4 Full INBOX Drain ✅ SHIPPED 2026-06-16

- 10 phases (7.0–8.6), 21 plans, 39 tasks
- ~85 INBOX rows → 67 REQ-IDs fully drained
- 2 ADRs Accepted: ADR-V2-033 (EventSink gRPC) + ADR-V2-017 §2 (double-Terminate NO-OP)
- Carry-forward 7.0/7.1/7.2 verify-and-close phases: 19/19 D-items confirmed ✅ CLOSED
- New 8.0–8.6 phases: 48/48 REQ-IDs completed
- All v3.4 phase artifacts archived in `milestones/v3.4-ROADMAP.md`

### Earlier Milestones

| Milestone | Status | Key Output |
|-----------|--------|------------|
| v3.3 Engine + Platform Debt Sweep | ✅ 2026-06-07 | Phase 7.3 L3 RBAC 8/8 REQ-IDs |
| v3.2 Tech-Debt Triage | ✅ 2026-05-26 | 93 D-rows triaged → v3.3-INBOX.md seeded |
| v3.1 Engine Hardening | ✅ 2026-05-22 | 6 phases, 23 REQ-IDs, 6 ADRs |
| v3.0 Product Scope Decision | ✅ 2026-04-28 | ADR-V2-024 双轴模型 Accepted |

## Accumulated Context

### Decisions

- **LEDGER 100% CLOSED** (2026-06-16): DEFERRED_LEDGER.md main D-table fully standardized. Zero P1/P2/P3 active rows. 17 genuinely ACTIVE items filed as 📦 long-term (Phase 4–6 concern) or 🔵 P3-defer edge cases.
- **Debt era over** (2026-06-16): v3.2–v3.5 = 4 consecutive debt sweep milestones, ~200 D-items closed. No more debt milestones — shift to product activation.
- **Priority target**: grid-cli + grid-server first (per ADR-V2-024 Open Item #3), then platform/desktop/web.
- **Phase 3.7.3 gate boundary** (2026-07-23): SHIPPED 2/2 plans. risk metadata defaults to `read`; L3 evaluates after tool resolution and before dispatch; governance request/final decisions are append-only and surfaced via L4 events; L1 and L3 HTTP approval surface remain unchanged. 8/8 REQ-EAASP closed; 131/131 targeted tests PASS (L3 76 + L4 6 + CLI 18 + mock-SCADA 19 + Rust 12). Live walkthrough BLOCKED on missing LLM API key (hermetic S8 test proves same code path).
- **v3.9 locked decisions** (from v3.9 discussion, 2026-07-25):
  - D-01 Cover ALL non-public business HTTP routes.
  - D-02 Public routes on explicit allowlist (compile-time `const`).
  - D-03 CI static auditor enforces per-route invariants.
  - D-04 `Action` vocabulary extensible; new variants when semantic gap; `Role × Action` matrix regenerated.
  - D-05 `AuthMode::None/ApiKey` semantics fully compatible; only `AuthMode::Full` runs per-route RBAC.
  - D-06 `RouteCatalog` is the source of truth (`pub`); both manual-decorated-router and generate-from-router patterns acceptable.
  - D-07 No new external crate dependency.
  - D-08 No schema migration.
  - D-09 Shared-core rule (ADR-V2-023 P1) preserved; engine-layer changes leg-agnostic; verified by `test_rbac_engine_layer_is_leg_agnostic`.
  - D-10 Phase ladder 03.9.0 → 03.9.1 → 03.9.2.

### Pending Todos

None.

### Blockers/Concerns

- **Quality gaps in shipped components**: `web-platform/` (Quality 7.5) and `grid-desktop` (Quality 6.5) shipped with Activation but remain below the 9.0+ bar the rest of the components have hit. Need follow-on feature work (Markdown + toast + skeletons + error states for web-platform/; Icons + IPC proxy + Grid rebrand for grid-desktop).
- **EAASP v2.0 platform-evolution gaps (explicit future work)**: production OPA approval chain (Phase 3), A2A / Event Room (Phase 4), L5 Cowork UI (Phase 5), ecosystem expansion (Phase 6) — per `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md`. Out of post-Activation scope; future milestone candidates.
- **138 unpushed commits**: accumulated across v3.2–v3.5. Push decision deferred to user.
- **Local environment**: `.env` has `OPENAI_NO_PROXY=1` for Clash. `LLM_PROVIDER=openai` code default.
- **v3.9 Action vocabulary growth discipline** (D-04): extension is allowed but each new variant must map to a coherent semantic; auditor surfaces gaps; "manage everything" catch-all is forbidden.

## Session Continuity

Last session: 2026-07-26 (autonomous v3.9 climb)
Stopped at: v3.9 SHIPPED — 03.9.0 catalog, 03.9.1 full RBAC, 03.9.2 CI auditor all complete; targeted gates 51 PASS.

Prior sessions:

- 2026-07-24: Phase 03.8.3 SHIPPED — USER_GUIDE §11 + PRODUCTION_USABILITY walkthrough + regression sweep. v3.8 milestone close pending. 119/119 targeted tests PASS.
- 2026-07-23 (this climb session): v3.8 milestone bootstrapped (PROJECT.md + STATE.md updated). REQUIREMENTS + ROADMAP pending.
- 2026-07-19 (this session): Phase 3.7.1 SHIPPED — 8/9 REQ-AUDITs closed, 14/14 hermetic tests PASS
- 2026-07-19: Phase 3.7.1 context gathered (CONTEXT.md + DISCUSSION-LOG.md @ db695a29)
- 2026-07-19: Phase 3.6 SHIPPED @ a29f626 (7 docs commits, 46/46 UAT PASS)

Prior sessions:

- 2026-06-17: **Phase A.8 grid-eval CI completed** — concurrency group + summary report
- 2026-06-17: **Phase A.7 grid-desktop completed** — brand name, IPC commands, updater fix
- 2026-06-17: **Phase A.6 web-platform/ Production completed** — ErrorBoundary, Toast, Markdown, dashboard fix
- 2026-06-17: **Phase A.5 grid-platform Hardening completed** — ErrorCode enum, quota middleware, body limits
- 2026-06-17: **Phase A.4 Cross-Cutting Foundation completed** — ApiClient, cn(), design tokens, branding
- 2026-06-17: **Phase A.3 grid-cli Final Polish completed**
- 2026-06-17: **Phase A.2 web/ Production Polish completed**
- 2026-06-17: **Phase A.1 grid-server Hardening completed**
- 2026-06-16: **Phase A.0 Audit & Scoping completed**
- 2026-06-16: **v3.5 Debt Finalization SHIPPED**

---

*Milestone v3.9 bootstrapped 2026-07-25. v3.8 SHIPPED 2026-07-24. v3.7 SHIPPED 2026-07-23.*
