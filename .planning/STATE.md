---
gsd_state_version: 1.0
milestone: activation
milestone_name: Grid 独立产品 Activation
status: executing
  stopped_at: Phase A.3 complete, ready for A.4
  last_updated: "2026-06-17T00:00:00.000Z"
  last_activity: 2026-06-17
  progress:
    total_phases: 8
    completed_phases: 3
    total_plans: 3
    completed_plans: 3
    percent: 38
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-16 — Grid 独立产品 Activation section)

**Core value:** Grid 作为 substitutable L1 runtime,通过 16-method gRPC contract 被 EAASP L2-L4 调用,且任何符合 contract-v1.1 的对比 runtime 都能替换它。
**Current focus:** Grid 独立产品 Activation — Phase A.2 web/ Production Polish (remove mock fallbacks, add tests, sidebar, ApiClient extraction).

## Current Position

Phase: A.1 grid-server Hardening ✅ COMPLETE
Next Phase: A.2 web/ Production Polish (Ready)
Status: Wave 1 — Single-User Workbench activation
Last activity: 2026-06-16

Progress: 2/8 phases (A.0 + A.1 complete)

## Audit Findings Summary

| Crate | Score | Key Gaps |
|-------|-------|----------|
| grid-server | 6/10 | RBAC unwired, ApiError unused, budget hardcoded, context broken, hot-reload ineffective |
| grid-cli | 8/10 | eval stubs, MCP log streaming partial, config set not persisted |
| web/ | 7/10 | MCP mock fallbacks, inconsistent errors, zero tests, magic token global |
| grid-eval | 7/10 | Web UI missing, no CI, single-threaded |
| grid-platform | 6/10 | Thin tests, no rate limiting, string-based errors |
| web-platform/ | 3/10 | Chat history broken, no Markdown, dashboard buggy |
| grid-desktop | 3/10 | WebView shell only, 6 IPC commands

## Completed Milestones

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

### Pending Todos

None.

### Blockers/Concerns

- **Grid 独立产品 dormancy**: `grid-server`, `grid-platform`, `grid-desktop`, `web/`, `web-platform/` all dormant per ADR-V2-024. Need activation audit to assess current state vs production readiness.
- **138 unpushed commits**: accumulated across v3.2–v3.5. Push decision deferred to user.
- **Local environment**: `.env` has `OPENAI_NO_PROXY=1` for Clash. `LLM_PROVIDER=openai` code default.

## Session Continuity

Last session: 2026-06-17
Stopped at: Phase A.3 complete, ready for A.4 cross-cutting foundation
Resume path: **Phase A.4 Cross-Cutting Foundation** — merge web/ + web-platform/ design systems, extract shared ApiClient, standardize brand name to "Grid"

Prior sessions:

- 2026-06-17: **Phase A.3 grid-cli Final Polish COMPLETE** — config persistence, doctor repair (5 checks)
- 2026-06-17: **Phase A.2 web/ Production Polish COMPLETE** — MCP mocks removed, errors → toast, 9 vitest tests
- 2026-06-17: **Phase A.1 grid-server Hardening COMPLETE** — 7/7 P1 gaps fixed
- 2026-06-16: **Phase A.0 Audit & Scoping COMPLETE** — 7 crate audits, gap analysis
- 2026-06-16: **v3.5 Debt Finalization SHIPPED** — LEDGER 100% CLOSED
- 2026-06-07–16: **v3.4 Full INBOX Drain SHIPPED** — 10 phases, 67/67 REQ-IDs

---

*State updated 2026-06-17. 3/8 activation phases complete. 6 commits in this session.*
