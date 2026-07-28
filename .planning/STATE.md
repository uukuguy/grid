---
gsd_state_version: 1.0
milestone: v3.13
milestone_name: EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle)
status: in_progress
stopped_at: v3.13 SHIPPED 2026-07-29 (4 phases complete, 13+ REQ-IDs / 5 categories, tag `v3.13` pushed). V310-COWORK-01 ✅ CLOSED. v3.12 SHIPPED 2026-07-27 at commit 894639dd. V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 ✅ CLOSED.
last_updated: "2026-07-29T16:00:00.000Z"
last_activity: 2026-07-29
progress:
  total_phases: 4
  completed_phases: 4
  total_plans: 4
  completed_plans: 4
  percent: 100
  prior_milestones:
    v3.13_completed_phases: 4
    v3.13_completed_plans: 4
    v3.13_percent: 100
    v3.12_completed_phases: 4
    v3.12_completed_plans: 4
    v3.12_percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Grid 作为 substitutable L1 runtime,通过 gRPC contract 被 EAASP L2-L4 调用,且任何符合 `contract-v1.2.0` 的对比 runtime 都能替换它。`contract-v1.1.0` 是 Phase 3 sign-off 历史契约版本(2026-04-18,42 PASS / 22 XFAIL × 7 runtime)。
**Current focus:** Milestone v3.13 (EAASP Phase 5 — L5 Cowork 四卡 + 回溯闭环) SHIPPED 2026-07-29. Four phases complete (03.13.0 four-card data model + projection + L4 SSE bridge → 03.13.1 four-card SSE fan-out + state transitions + persistence → 03.13.2 retrospective cycle trace API → 03.13.3 single-point live walkthrough + tag v3.13), 13+ REQ-IDs / 5 categories (CARD-EVENT / CARD-EVIDENCE / CARD-ACTION / CARD-APPROVAL / RETROSPECTIVE), tag `v3.13` pushed. V310-COWORK-01 ✅ CLOSED. Prior milestone v3.12 SHIPPED 2026-07-27 at commit `894639dd`.

Canonical product-status sources:

- `docs/PROJECT_PRODUCT_OVERVIEW.md` (maintained SSOT)
- `docs/status/PRODUCT_STATUS_2026-07-17.md` (dated audit snapshot)

## Current Position

Milestone: **v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) ✅ SHIPPED 2026-07-29 (4-phase ladder 03.13.0 → 03.13.1 → 03.13.2 → 03.13.3; 100% complete, 4/4 phases)**
Scope: 4 phases (03.13.0 Event/Evidence/Action/Approval four-card data model + projection + L4 SSE bridge → 03.13.1 four-card SSE fan-out + state transitions + persistence → 03.13.2 retrospective cycle (trace API) → 03.13.3 single-point live walkthrough + tag v3.13). 13+ REQ-IDs across 5 categories (CARD-EVENT / CARD-EVIDENCE / CARD-ACTION / CARD-APPROVAL / RETROSPECTIVE).
v3.13 SHIPPED 2026-07-29: `tools/eaasp-l5-cowork/` (new package — projection layer + state machine + RETROSPECTIVE trace + CLI + SSE fan-out); 82 targeted tests PASS; dual-gate PASS (134 routes RBAC + 4 files / 37 rows spec-audit); `docs/status/PRODUCTION_USABILITY_2026-07-29.md` captures the live walkthrough evidence; `docs/design/EAASP/DEFERRED_LEDGER.md` V310-COWORK-01 → ✅ CLOSED; tag `v3.13` annotated.
Prior milestone: **v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd**
Prior scope: 4 phases complete (03.12.0 → 03.12.3), 13-16 REQ-IDs in 5 categories (SCHEMA / EVENT-ROOM / A2A / SESSION / COMPAT + TRACE cross-axis).
Prior verification: 03.12.0 audit.py `DECISION_ALLOWLIST` widens to `{allow, approve, deny, gate_request, await_human}` + `db.migrate_decision_await_human` idempotent ALTER TABLE migration + `approval_state_machine.py` paused Approve stage writes `approve_pause` row carrying `DECISION_AWAIT_HUMAN` (14 new targeted tests PASS). 03.12.1 Event Room data model + SQLite migration + multi-session event fan-out + `L4 /v1/rooms/{room_id}/sessions/{session_id}/events` endpoint with `ManageRooms` Action variant + 5 rounds of security review fixes (room_id required + principal-keyed membership gate + sibling-path parity + HMAC-SHA256 + ContextVar auth + log sanitization + empty-id test + caller auth + principal required + audit reliability). 03.12.2 A2A Router + A2A protocol envelope + 5 SSE event types + ReviewSet + aggregation engine + conflict detection + A2ARouter facade over EventRoom + MultiSessionCoordinator + review_set fail-open aggregation + principal-mismatch gate + cross_session audit pivot. 03.12.3 single-point live walkthrough against real OPA sidecar + Event Room + A2A Router.
Prior close: `make rbac-audit` PASS (134 routes); `make v3.10-spec-audit` PASS (4 files / 37 rows); ADR-V2-023 P1 shared-core rule preserved (no shared-crate change); ADR-V2-035 Accepted (A2A Router credential gate); V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 ✅ CLOSED.
Prior-prior milestone: **v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27**
Prior-prior scope: 4 phases complete (03.11.0 → 03.11.3), 29/29 REQ-IDs in 11 categories (OPA + INSTALL + OPA-BACKEND + REGO + FAIL-CLOSED + DISABLED + STAGE + SSE / AUDIT / DENY + LIVE).
Prior-prior verification: 57 + targeted regression tests PASS; real OPA sidecar v0.68.0 on `127.0.0.1:18181`; 5 SSE events in canonical order (seq 26–30, single request_id); 18 rows in L3 `governance_decisions` ledger across 3 chain runs; `make rbac-audit` PASS (134 routes); `make v3.10-spec-audit` PASS (4 files / 37 rows); ADR-V2-023 P1 shared-core rule preserved (no shared-crate change).
Prior-prior-prior milestone: **v3.10 EAASP v2.0 platform-skeleton alignment ✅ SHIPPED 2026-07-26** (4 phases, 16/16 REQ-IDs, 174 targeted tests PASS).

Next-milestone candidates (after v3.13 SHIPS):

- `web-platform/` Quality 7.5→9.0.
- `grid-desktop` Quality 6.5→9.0.
- EAASP Phase 6 ecosystem expansion (V310-ECOSYSTEM-01 / V310-MAT-01).

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

### v3.13.0..03.13.3 EAASP Phase 5 — L5 Cowork 四卡 + 回溯闭环 🔵 BOOTSTRAPPING 2026-07-27

- 4 phases planned (03.13.0 Event/Evidence/Action/Approval four-card data model + projection + L4 SSE bridge → 03.13.1 four-card SSE fan-out + state transitions + persistence → 03.13.2 retrospective cycle (trace API) → 03.13.3 single-point live walkthrough + tag v3.13).
- 13–16 REQ-IDs across 5 categories (CARD-EVENT / CARD-EVIDENCE / CARD-ACTION / CARD-APPROVAL / RETROSPECTIVE) + COMPAT cross-axis carry-over.
- Locked decisions D-30..D-37 (see PROJECT.md §Key Decisions):
  - **D-30** v3.13 scope = EAASP Phase 5 L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle). Closes V310-COWORK-01. v3.14+ = Phase 6 ecosystem.
  - **D-31** L5 仍以 EAASP v2.0 spec §4 + §4.4 为权威源;本仓前端 (web/ + web-platform/) 仍为 dormant 状态;v3.13 在 `tools/eaasp-l5-cowork/` (新建) 落模拟器级四卡 backend + projection.
  - **D-32** 四卡全部派生自 v3.12 已落地的 L2 evidence anchor + L3 governance_decisions + L4 event_room_events + A2A review.closed 事件;不新建独立存储.
  - **D-33** 回溯闭环 (retrospective cycle) = 任何四卡 record 都能以 `session_id` 为根 trace 到 Event → Evidence → Action → Approval 全链;新增 `tools/eaasp-l5-cowork/retrospective.py` 提供 trace API.
  - **D-34** 仍以 Phase 0.5 MVP 人工可执行性为最低标尺 (threshold-calibration skill + `make dev-eaasp`).
  - **D-35** v3.9 / v3.10 / v3.11 / v3.12 硬约束 (134 routes RBAC, spec-audit, ADR-V2-023 P1 shared-core, ADR-V2-028 strict-by-default, ADR-V2-034 OPA sidecar) 不动.
  - **D-36** 探索策略保持 Explore + Grep (本仓无 `.codegraph/`).
  - **D-37** v3.13 不开新前端 (react/typescript);仍 `tools/eaasp-*/` 模拟器级实现;不开新服务端口.

### v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd

- 4 phases SHIPPED (03.12.0 / 03.12.1 / 03.12.2 / 03.12.3), 13-16 REQ-IDs in 5 categories (SCHEMA / MIGRATION / AWAIT-HUMAN / EVENT-ROOM / A2A / SESSION / COMPAT + TRACE cross-axis).
- 03.12.0 audit.py CHECK constraint patch SHIPPED: `DECISION_ALLOWLIST` widens to `{allow, approve, deny, gate_request, await_human}`; `db.migrate_decision_await_human` idempotent ALTER TABLE migration (v3.11.0 / v3.11.1 / v3.11.2 legacy DBs preserved); `approval_state_machine.py` paused Approve stage writes `approve_pause` row carrying `DECISION_AWAIT_HUMAN`; 14 new targeted tests PASS in `test_audit_decision_await_human.py` + `test_audit_await_human_migration.py`; V311-AUDIT-01 ✅ CLOSED.
- 03.12.1 Event Room + multi-session SHIPPED: `EventRoom` data model + SQLite migration + multi-session event fan-out + `L4 /v1/rooms/{room_id}/sessions/{session_id}/events` endpoint with `ManageRooms` Action variant; 5 rounds of security review fixes (room_id required + principal-keyed membership gate + sibling-path parity + HMAC-SHA256 + ContextVar auth + log sanitization + empty-id test + caller auth + principal required + audit reliability).
- 03.12.2 A2A Router SHIPPED: A2A protocol envelope + 5 SSE event types + ReviewSet + aggregation engine + conflict detection + A2ARouter facade over EventRoom + MultiSessionCoordinator + review_set fail-open aggregation + principal-mismatch gate + cross_session audit pivot; ADR-V2-035 Accepted (A2A Router credential gate).
- 03.12.3 single-point live walkthrough SHIPPED: end-to-end live walkthrough against real OPA sidecar + Event Room + A2A Router; documented at `docs/status/PRODUCTION_USABILITY_2026-07-28.md` (target file).
- `make rbac-audit` PASS (134 routes). `make v3.10-spec-audit` PASS (4 files / 37 rows). ADR-V2-023 P1 shared-core rule preserved (no shared-crate change). ADR-V2-034 OPA sidecar ALIVE through every phase. V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 → ✅ CLOSED. Tag `v3.12` pushed.

## Completed Milestones

### v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd

- 4 phases (03.12.0 / 03.12.1 / 03.12.2 / 03.12.3), 13-16 REQ-IDs in 5 categories (SCHEMA / EVENT-ROOM / A2A / SESSION / COMPAT) + TRACE cross-axis.
- 03.12.0 audit.py CHECK constraint patch SHIPPED: `DECISION_ALLOWLIST` widens to include `await_human`; `db.migrate_decision_await_human` idempotent ALTER TABLE migration; `approval_state_machine.py` paused Approve stage writes `approve_pause` row carrying `DECISION_AWAIT_HUMAN`; 14 new targeted tests PASS in `test_audit_decision_await_human.py` + `test_audit_await_human_migration.py`; `docs/design/EAASP/DEFERRED_LEDGER.md` V311-AUDIT-01 → ✅ CLOSED.
- 03.12.1 Event Room + multi-session SHIPPED: `EventRoom` data model + SQLite migration + multi-session event fan-out + `L4 /v1/rooms/{room_id}/sessions/{session_id}/events` endpoint with `ManageRooms` Action variant; 5 rounds of security review fixes (room_id required + principal-keyed membership gate + sibling-path parity + HMAC-SHA256 + ContextVar auth + log sanitization + empty-id test + caller auth + principal required + audit reliability).
- 03.12.2 A2A Router SHIPPED: A2A protocol envelope + 5 SSE event types + ReviewSet + aggregation engine + conflict detection + A2ARouter facade over EventRoom + MultiSessionCoordinator + review_set fail-open aggregation + principal-mismatch gate + cross_session audit pivot; ADR-V2-035 Accepted (A2A Router credential gate).
- 03.12.3 single-point live walkthrough SHIPPED: end-to-end live walkthrough against real OPA sidecar + Event Room + A2A Router.
- v3.9 RBAC audit still PASS (134 routes — unchanged). v3.10 spec-audit still PASS (4 files / 37 rows). ADR-V2-023 P1 shared-core rule preserved (no shared-crate change). ADR-V2-034 OPA sidecar ALIVE through every phase. V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 → ✅ CLOSED. Tag `v3.12` pushed.

### v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27

- 4 phases (03.11.0 / 03.11.1 / 03.11.2 / 03.11.3), 29/29 REQ-IDs in 11 categories (OPA + INSTALL + OPA-BACKEND + REGO + FAIL-CLOSED + DISABLED + STAGE + SSE / AUDIT / DENY + LIVE).
- ADR-V2-034 Accepted; `make opa-install` reproducible (03.11.0); L3 OPA backend `OPABackend.evaluate()` called from `PolicyEngine.evaluate_with_opa()` when `opa_enabled=True`; Rego template `policies/governance.rego` implements deny-always-wins (spec §15.9), risk classification (spec §6.1), and 3-state decision contract (spec §6.9, §6.10); 5 fail-closed modes covered with stable cause identifiers carried in the audit rationale; 5-stage approval state machine (Plan → Check → Draft → Approve → Execute) with `governance.approval.*` SSE events + append-only `governance_decisions.stage` column extension; `V310-OPA-01` + `V310-APPROVAL-01` ✅ CLOSED.
- 57 + targeted regression tests PASS; v3.11.3 single-point live walkthrough against real OPA sidecar v0.68.0 captured at `docs/status/PRODUCTION_USABILITY_2026-07-27.md` (5 SSE events in canonical order; 18 rows in L3 ledger across 3 chain runs).
- v3.9 RBAC audit still PASS (134 routes); v3.10 spec-audit still PASS (4 files / 37 rows); ADR-V2-023 P1 shared-core rule preserved (no shared-crate change).

### v3.9 grid-server route-catalog RBAC ✅ SHIPPED 2026-07-26

- 3 phases (03.9.0 / 03.9.1 / 03.9.2), 20/20 REQ-IDs closed.
- Canonical 134-entry HTTP route catalog + exact 3-route public allowlist (D-01/D-02).
- `AuthMode::Full` per-route catalog RBAC via canonical Axum `MatchedPath`; `AuthMode::None/ApiKey` semantics fully preserved (D-05).
- Shared `Action` registry expanded from 7 → 20 variants, parser + `Role::can` matrix synchronized (D-04).
- Owner-only boundaries preserved: `ManageUsers`/`ManageConfig` stay Owner-only (D-04).
- Standalone `route-auditor` binary + `make rbac-audit` + CI gate ordering `cargo check → rbac-audit → cargo test` (D-03).
- Post-ship fixes (security review): unified public-bypass with `PUBLIC_ROUTE_ALLOWLIST` for `/api/health`, `/api/health/live`, `/api/v1/auth/login`; corrected JWT `user` role mapping; `catalog_rbac_middleware` now distinguishes Public / Requires(action) / not-in-catalog; route-chain regression test added.
- 49 targeted tests PASS, `cargo check -p grid-server` PASS, `make rbac-audit` PASS with 134 routes.

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
- **v3.10 locked decisions** (from v3.10 discussion, 2026-07-26 — bootstrap pending plan-phase):
  - D-11 EAASP v2.0 platform-skeleton alignment scope: align `tools/eaasp-*` reference implementations with the canonical EAASP v2.0 platform contract (`docs/design/EAASP/EAASP-Design-Specification-v2.0.docx`) without adding new dependencies.
  - D-12 Three-axis skeleton mapping: (1) MAT (memory/manifest), (2) PIPE (orchestration pipes), (3) VERIFY (certifier conformance). Each axis has its own 03.10.x phase and Phase #1 deliverable proves the skeleton fits the spec.
  - D-13 Backward-compatible contract surface: existing `proto/eaasp/runtime/v2/` (21 RPC: 17 runtime + 4 hook) and `contract-v1.2.0` tests must remain green; no proto-breaking changes in v3.10.
  - D-14 L1 substitutability guard preserved: all 7 L1 runtimes (`grid-runtime` + 6 comparison: claude-code / goose / nanobot / pydantic-ai / claw-code / ccb; `hermes` frozen per ADR-V2-017) must continue to pass contract v1.2.0 certifier after each v3.10 phase.
  - D-15 No new external crate dependency (D-07 carry-over); same rule for Python (no new PyPI deps beyond existing `uv` lockfile).
  - D-16 No schema migration (D-08 carry-over); skeleton alignment is Rust + Python source + proto commentary only.
  - D-17 Shared-core rule (ADR-V2-023 P1, D-09 carry-over) preserved: any change to `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` must remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品.
  - D-18 Phase ladder 03.10.0 (skeleton audit + alignment matrix) → 03.10.1 (MAT axis) → 03.10.2 (PIPE axis) → 03.10.3 (VERIFY axis). Optionally merged into 3 phases if scope allows per scope review at plan-phase.

- **v3.11 locked decisions** (from v3.11.0 bootstrap, 2026-07-26):
  - D-19 OPA sidecar deployment topology: ADR-V2-034 — sidecar OPA on `127.0.0.1:18181`, in-repo Rego templates + atomic user bundles, fail-closed on OPA error. `make opa-install` downloads official OPA binary with SHA256 verify.
  - D-20 No shared-crate change: v3.11.0 / 03.11.1 / 03.11.2 / 03.11.3 must NOT touch `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge`; ADR-V2-023 P1 (shared-core rule) preserved; COMPAT-02 verified at every phase.
  - D-21 Backward-compatible contract surface: `proto/eaasp/runtime/v2/` 21 RPC + `contract-v1.2.0` tests remain green; no proto-breaking changes; new spec sections deferred to v3.12+ (D-13 carry-over).
  - D-22 Phase ladder 03.11.0 (sidecar + ADR) → 03.11.1 (L3 OPA backend + Rego) → 03.11.2 (5-stage approval state machine) → 03.11.3 (single-point live walkthrough).
- **v3.12 locked decisions** (from v3.12 bootstrap, 2026-07-27 — non-negotiable):
  - D-23 `audit.py` CHECK constraint patch is mandatory phase 0. v3.11.3 live walkthrough §7 surfaced that `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include `await_human`; the 5-stage state machine emits `await_human` at the Approve stage; without this fix, 03.12.1 / 03.12.2 / 03.12.3 cannot reproduce paused-state audit evidence. v3.12.0 MUST patch the schema first; no implementation work in 03.12.1 / 03.12.2 may proceed before 03.12.0 ships. Closes `V311-AUDIT-01`.
  - D-24 v3.12 scope = EAASP Phase 4. v3.12 delivers A2A Router + Event Room + multi-session coordination per EAASP_v2_0_EVOLUTION_PATH.md §三 Phase 4 scope (spec §5.3 / §14 / §17). Closes V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01. v3.13+ = Phase 5 L5 / Phase 6 ecosystem.
  - D-25 MVP executable baseline + new A2A coordination scenario. Phase 0.5 MVP human-executable floor (`threshold-calibration` skill + `make dev-eaasp`) remains the minimum bar; v3.12 adds a new A2A coordination walkthrough scenario on top of that floor.
  - D-26 `audit.py` CHECK constraint extension uses idempotent `ALTER TABLE` migration. The extension MUST use `ALTER TABLE` (matching the existing v3.11.2 `stage` column migration pattern at the same `audit.py` module); existing DBs upgrade cleanly without losing history. No destructive schema work. No new tables / no new columns beyond the CHECK constraint extension.
  - D-27 v3.12 stays in `tools/eaasp-*/` simulator-level implementations. v3.12 does not open a new repo / does not open a new service port; uses the existing 7 EAASP services (skill-registry / L2 / L3 / mock-scada / MCP orchestrator / grid-runtime / L4) on `.grid/dev-eaasp-live.sh` launch topology. Event Room + A2A Router live in `tools/eaasp-l4-orchestration/` (per v3.7.3 L4 ownership pattern).
  - D-28 v3.12 安全边界 + shared-core rule + rbac-audit + v3.10-spec-audit + OPA sidecar all continue to PASS. v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + ADR-V2-023 P1 shared-core rule + ADR-V2-034 OPA sidecar ALL continue to PASS through every v3.12 phase. No shared-crate change is anticipated, but if any change is required it must remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品.
  - D-29 v3.12 探索策略 = Explore + Grep. No `.codegraph/` in this repo; no MCP codegraph tool available. Codebase pattern reads gate by CLAUDE.md "Level 1+ single-pass reads" rule.
- **v3.13 locked decisions** (from v3.13 bootstrap, 2026-07-27 — non-negotiable):
  - D-30 v3.13 scope = EAASP Phase 5 L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle). Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 Phase 5 (spec §4 + §4.4). Closes `V310-COWORK-01`.
  - D-31 L5 仍以 EAASP v2.0 spec §4 + §4.4 为权威源;本仓前端 (web/ + web-platform/) 仍为 dormant 状态;v3.13 在 `tools/eaasp-l5-cowork/` (新建) 落模拟器级四卡 backend + projection.
  - D-32 四卡全部派生自 v3.12 已落地的 L2 evidence anchor + L3 governance_decisions + L4 event_room_events + A2A review.closed 事件;不新建独立存储. v3.13 = 投影 + 视图层;底层仍是 v3.7.3 / v3.10 / v3.11 / v3.12 既有数据.
  - D-33 回溯闭环 (retrospective cycle) = 任何四卡 record 都能以 `session_id` 为根 trace 到 Event → Evidence → Action → Approval 全链;新增 `tools/eaasp-l5-cowork/retrospective.py` 提供 trace API (`trace_session(session_id) -> RetrospectiveChain`).
  - D-34 仍以 Phase 0.5 MVP 人工可执行性为最低标尺 (threshold-calibration skill + `make dev-eaasp`);v3.13 extends the same MVP floor with a four-card walkthrough scenario.
  - D-35 v3.9 / v3.10 / v3.11 / v3.12 硬约束不动 — Owner-only 边界不动 / AuthMode 兼容不动 / CI 顺序不动 / grid-engine 共享核心不动 / ADR-V2-023 P1 / ADR-V2-028 / ADR-V2-034 OPA sidecar / v3.11.2 5-stage approval / v3.12.1 Event Room ContextVar 鉴权 / v3.12.2 A2A Router + ReviewSet 全部保留.
  - D-36 探索策略保持 Explore + Grep (本仓无 `.codegraph/`).
  - D-37 v3.13 不开新前端 (react/typescript);仍 `tools/eaasp-*/` 模拟器级实现;不开新服务端口。

### Pending Todos

- **03.13.0 plan-phase**: run `/gsd-plan-phase 03.13.0` (D-30..D-37 locked; 03.13.0 = Event/Evidence/Action/Approval four-card data model + projection + L4 SSE bridge).
- **03.13.1 plan-phase**: after 03.13.0 ships, plan four-card SSE fan-out + state transitions + persistence.
- **03.13.2 plan-phase**: after 03.13.1 ships, plan retrospective cycle (trace API).
- **03.13.3 plan-phase**: after 03.13.2 ships, plan single-point live walkthrough + tag v3.13.

### Blockers/Concerns

- **Quality gaps in shipped components**: `web-platform/` (Quality 7.5) and `grid-desktop` (Quality 6.5) shipped with Activation but remain below the 9.0+ bar the rest of the components have hit. Need follow-on feature work (Markdown + toast + skeletons + error states for web-platform/; Icons + IPC proxy + Grid rebrand for grid-desktop).
- **EAASP v2.0 platform-evolution gaps (explicit future work)**: Phase 6 ecosystem expansion (V310-ECOSYSTEM-01 / V310-MAT-01); L1 infrastructure tier changes (V310-SANDBOX-01). Per `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md`. Phase 5 L5 Cowork moved into v3.13 scope.
- **138 unpushed commits**: accumulated across v3.2–v3.5. Push decision deferred to user.
- **Local environment**: `.env` has `OPENAI_NO_PROXY=1` for Clash. `LLM_PROVIDER=openai` code default.
- **v3.9 Action vocabulary growth discipline** (D-04): extension is allowed but each new variant must map to a coherent semantic; auditor surfaces gaps; "manage everything" catch-all is forbidden.
- **v3.10 spec drift risk**: the canonical EAASP v2.0 spec is `EAASP-Design-Specification-v2.0.docx` (~4373 KB). Skeleton alignment must reference this spec by section number (D-11); otherwise drift between `tools/eaasp-*` and the spec will reappear. v3.10 audit phase (03.10.0) MUST produce a section-by-section delta before any code changes.
- **v3.10 certifier gap**: existing `tools/eaasp-certifier` exercises `contract-v1.2.0` (17 runtime + 4 hook RPC). Skeleton alignment MUST not silently widen the certifier surface; new spec sections without contract backing must be tracked as deferred (D-13 + D-14).
- **v3.13 L5 frontend dormant** (D-31): web/ + web-platform/ remain dormant; v3.13 is a Python projection layer, not a UI milestone. UI activation deferred to a separate future milestone.

## Session Continuity

Last session: 2026-07-27 (autonomous v3.12 climb — 03.12.0 audit.py CHECK constraint patch + 03.12.1 Event Room + multi-session + 03.12.2 A2A Router + 03.12.3 single-point live walkthrough; tag `v3.12` pushed 894639dd; then v3.13 milestone bootstrap — this commit).
Stopped at: v3.13 bootstrapping — 4-phase ladder 03.13.0 / 03.13.1 / 03.13.2 / 03.13.3 planned; no implementation work yet. v3.12 SHIPPED 2026-07-27 @ 894639dd — 4 phases complete (03.12.0 audit.py CHECK constraint patch + 03.12.1 Event Room + multi-session + 03.12.2 A2A Router + 03.12.3 single-point live walkthrough; tag `v3.12` pushed).

Prior sessions:

- 2026-07-27 (autonomous v3.11.2 + 03.11.3 climb): v3.11 SHIPPED — 29/29 REQ-IDs closed (4 phases: 03.11.0 OPA sidecar / 03.11.1 L3 OPA backend + Rego / 03.11.2 5-stage approval state machine / 03.11.3 single-point live walkthrough against real OPA sidecar v0.68.0).
- 2026-07-26 (autonomous v3.9 climb): v3.9 SHIPPED — 03.9.0 catalog, 03.9.1 full RBAC, 03.9.2 CI auditor all complete; targeted gates 51 PASS.
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

*Milestone v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) bootstrapping (this commit). v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd (4 phases, 13-16 REQ-IDs / 5 categories, tag `v3.12` pushed). v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27. v3.10 EAASP v2.0 platform-skeleton alignment ✅ SHIPPED 2026-07-26. v3.9 SHIPPED 2026-07-26. v3.8 SHIPPED 2026-07-24. v3.7 SHIPPED 2026-07-23.*
