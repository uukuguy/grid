# Requirements: Grid

**Defined:** 2026-07-25
**Last updated:** 2026-07-27
**Active milestone:** v3.13 (EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle), bootstrapping)
**Milestone:** v3.9 (route-catalog RBAC wiring + authorization auditor) [closed 2026-07-26]; v3.10 / v3.11 / v3.12 SHIPPED; v3.13 active
**Core Value:** Grid 作为 substitutable L1 runtime,通过 gRPC contract 被 EAASP L2-L4 调用,且任何符合 `contract-v1.2.0` 的对比 runtime 都能替换它。

> **Read first.** This file is the **active** requirements ledger. v3.8 (2026-07-24) and earlier milestones are archived to `.planning/milestones/v3.{X}-REQUIREMENTS.md`. Locked decisions from the v3.9 discussion are NOT negotiated below — they are normative for this milestone.

---

## v3.9 Requirements

**Goal:** Make `grid-server` route-by-route authorization **explicitly declared and statically enforced**: every non-public business HTTP route is annotated with the `Action` it requires, every public route is named on an explicit allowlist, and a CI auditor fails any route that is neither. The Action enum is extended (and the `Role × Action` matrix updated) whenever the catalog reveals an action that the current 7-Action vocabulary does not express. `AuthMode::None/ApiKey` semantics are not changed; `AuthMode::Full` runs full RBAC.

**Context (post-v3.8):** v3.8 demonstrated `requires(Action)` on three representative routes and shipped JWT + RBAC + tenant isolation. The remaining ~127 endpoints in `crates/grid-server/src/api/mod.rs` + `crates/grid-server/src/router.rs` have no `requires(...)` annotation. A new route can quietly bypass RBAC without detection. v3.9 closes that gap by making "every route has either an Action or a public marker" a CI-enforced invariant.

**REQ-IDs** use v3.9 numbering, continue from v3.8 (no `RBAC-05..` duplicate).

### CAT — Route Catalog & Action extension

- [x] **CAT-01**: A `RouteCatalog` source of truth exists at `crates/grid-server/src/rbac/catalog.rs` listing every business HTTP route registered by `api::routes()` + `build_router()`, with each entry carrying `(method, path, route_kind)` where `route_kind ∈ { Requires(Action), Public }`. The router is rewritten so it builds its route table from this catalog (or, where the rewrite is too invasive, the catalog is generated from the router via a `build_catalog()` function that the auditor consumes).
- [x] **CAT-02**: Public routes are explicitly enumerated on an `allowlist` constant (e.g. `/api/health`, `/api/health/live`, plus the login path that is invoked before the JWT is issued). Anything not on the allowlist AND not decorated with `Requires(Action)` is a CI failure.
- [x] **CAT-03**: When the auditor surfaces a route whose semantic action is not expressible by the existing 7-Action `Action` enum (`Read`, `CreateSession`, `RunAgent`, `ManageMcp`, `ManageSkills`, `ManageUsers`, `ManageBilling`), the team is allowed to ADD new variants to the enum (e.g. `ManageHooks`, `ManageMemories`, `ManageAudit`, `ManageConfig`, `ManageSecrets`, `ManageSandbox`, `ManageScheduler`) and to update `Role::can(Action)` in `crates/grid-engine/src/auth/roles.rs`. Adding variants is **not** a scope-reduction — full Role × Action matrix regeneration is part of the deliverable.
- [x] **CAT-04**: The `RouteCatalog` is `pub` so the auditor (CAT-05) and tests (CAT-06) can consume it. Tests can assert "every endpoint in `api::routes()` has an entry in the catalog."

### AUD — Static route auditor

- [x] **AUD-01**: A static auditor binary or test (`cargo run -p grid-server --bin route-auditor` OR `cargo test -p grid-server --test route_auditor`) takes the `RouteCatalog` and walks the routes registered by `build_router()`. For each route it asserts: (a) either `route_kind == Public` AND the path is on the `allowlist`, OR (b) `route_kind == Requires(Action)` AND the action is exercisable by at least one Role. Mismatch → non-zero exit code with a clear, human-readable report naming the offending route.
- [x] **AUD-02**: The auditor is wired into `.github/workflows/ci.yml` (or the existing CI pipeline) under a job that runs after `cargo check --workspace` and before `cargo test`. The auditor PASSES on the v3.9 catalog and exits 0; on any unprotected route it exits 1 with the missing-route report.
- [x] **AUD-03**: The auditor integrates with the existing `cargo test -p grid-server` matrix and is also runnable as a standalone `make` target (e.g. `make rbac-audit`) so a developer can run it locally before pushing.

### RBAC — Full business-route wiring

- [x] **RBAC-05**: Every non-public business HTTP route in `api::routes()` is annotated with `Requires(Action)` via `axum::middleware::from_fn_with_state(...)` or the existing `require_action_middleware(Action)` wrapper. The set of routes affected is the union of all `.route(...)` calls in `crates/grid-server/src/api/{admin,agents,audit,auth,autonomous,budget,collaboration,config,context,eval_sessions,events,executions,hooks,knowledge_graph,mcp_logs,mcp_servers,mcp_tools,memories,metering,metrics,providers,sandbox,scheduler,secrets,security,sessions,skills,sync,tasks,tools,user_context}.rs` + `mod.rs` + `router.rs`.
- [x] **RBAC-06**: The `require_action_middleware` path used in v3.8.2 (which reads `Extension<JwtClaims>` and consults `Role::can(action)`) is reused unchanged. The v3.9 wiring is purely additive — every annotated route hits the same middleware. `AuthMode::None/ApiKey` requests continue to bypass the JWT path and use the existing `UserContext::has_permission` flow (D-04 below).
- [x] **RBAC-07**: `Owner` always succeeds on every annotated route (RBAC-04 invariant preserved); `Viewer` cannot call any non-Read annotated route; `User` can call Read + CreateSession + RunAgent; `Admin` extends to ManageMcp / ManageSkills / ManageUsers. The specific role-per-action policy is regenerated in `Role::can(Action)` to fill in the new Action variants.
- [x] **RBAC-08**: The auditor test `rbac_05_full_route_catalog_annotated` enumerates every route in `api::routes()` and asserts each has an entry in the `RouteCatalog`; the test fails with a list of unannotated routes if any drift appears.

### MODE — AuthMode compatibility

- [x] **MODE-01**: `AuthMode::None` — every existing route remains reachable without auth. The `public` allowlist and the `requires(Action)` annotations do NOT change `AuthMode::None` behavior. Tests: `cargo test -p grid-server --features grid-server/testing --test test_auth_modes None` continues to PASS (regression).
- [x] **MODE-02**: `AuthMode::ApiKey` — every existing route remains reachable with a valid `X-API-Key`. The `requires(Action)` annotations apply when the request has `Extension<JwtClaims>` (it does not in ApiKey mode). Tests: `cargo test -p grid-server --features grid-server/testing --test test_auth_modes ApiKey` continues to PASS (regression).
- [x] **MODE-03**: `AuthMode::Full` — every annotated route runs the `require_action_middleware` JWT-aware path. Missing/invalid JWT → 401. Insufficient role → 403. `Viewer` JWT calling a non-Read annotated route → 403. The 8/8 `test_auth_modes test_full` cases continue to PASS plus the new `RBAC-05..08` cases.

### TEST — Hermetic validation

- [x] **TEST-07**: The auditor (AUD-01) is exercised by a self-test: a test fixture builds a fake `Router` with one deliberately unprotected route and asserts the auditor exits 1 with the expected message. This guards against the auditor silently vacuously-passing.
- [x] **TEST-08**: Hermetic integration test that walks every annotated route in `api::routes()`; for each route, mints a JWT for each `Role` and asserts the expected status code (200/403/401). The matrix is small (`7 roles × ~130 routes` is bounded by the canonical Role set: Viewer/User/Admin/Owner × 130 ≈ 520 cases; we keep it to "at least one positive case per route + one negative case per Read route when called as Viewer").
- [x] **TEST-09**: Regression sweep across v3.7 + v3.8 baseline tests (`test_auth_modes` 8/8, `multi_user_jwt` 9/9, `multi_user_auth_endpoints` 7/7, `multi_user_rbac_tenant` 10/10) — every test PASS in `GRID_MODE=multi_user` and `GRID_MODE=single_user` modes. ASK before running the full v3.7 175-test baseline per `feedback_no_full_tests`.

### DOC — Catalog + auditor operator docs

- [x] **DOC-04**: `USER_GUIDE.md` §12 catalogue-auditor mode (what `make rbac-audit` does, how to read its report, how to add a new route, how to add a new Action variant). Reuses the v3.8 USER_GUIDE §11 multi-user section pattern.
- [x] **DOC-05**: `PRODUCTION_USABILITY_2026-07-25.md` dated walkthrough: (1) auditor PASS on v3.9 catalog, (2) auditor FAIL demonstrably on a synthetic unplugged route, (3) RBAC matrix regenerated for new Actions, (4) all `AuthMode` regressions observed to PASS.
- [x] **DOC-06**: `ROLE_ACTION_MATRIX_2026-07-25.md` reference table — the full regenerated `Role × Action` matrix, including any new Action variants added in CAT-03. Mirrors the existing `roles.rs:69` matrix but updated.

## Future Requirements (deferred — explicit v3.9+ backlog)

- **Rate limiting per Role** — separate concern; v3.9 leaves `RateLimiter` (currently key-isolated per ApiKey) untouched.
- **Audit row signing on every annotated route** — already handled in v3.8.1 hotfix `7f08ac53`; no v3.9 scope.
- **Refresh-token rotation** — v3.9+=scope per 03.8.1 plan §Out of scope.
- **SSO / SAML / OIDC / OAuth2** — v3.9+ per 03.8.1 plan §Out of scope.
- **Per-tenant Action policy override** — v3.9+ per 03.8.2 plan §Out of scope.
- **OPA backend on top of RBAC** — separate from v3.7.3 in-process gate; v3.9+.

## Out of Scope (v3.9)

- **EAASP v2.0 platform-evolution gaps** (Phase 3 OPA / Phase 4 A2A / Phase 5 L5 Cowork / Phase 6 ecosystem) — untouched.
- **`web-platform/` Quality 7.5→9.0** — separate milestone.
- **`grid-desktop` Quality 6.5→9.0** — separate milestone.
- **`grid-platform` (`grid-server`'s multi-tenant sibling)** — its route catalog is owned by `grid-server`'s inheritance but v3.9 only audits `grid-server`. `grid-platform` route catalog is a separate milestone.
- **Multi-role per user** — v3.9 keeps single-role-per-user (preserved from v3.8.2 D-01).
- **Per-route policy hooks (custom predicates beyond Role)** — out of v3.9; structure is laid down to allow future extension without rewrite.

## Locked Decisions (from v3.9 discussion — non-negotiable)

| # | Decision | Source |
|---|----------|--------|
| D-01 | **Cover ALL non-public business HTTP routes.** No protective carve-out for "internal helper" routes; if it is in `api::routes()` or `build_router()` and is not on the public allowlist, it gets `Requires(Action)`. | user directive |
| D-02 | **Public routes get an explicit allowlist.** A route is `public` only if its path is on the allowlist. The allowlist is `static` (compile-time `const`) and lives next to the catalog. Defaults: `/api/health`, `/api/health/live`, `/api/v1/auth/login` (the latter because the request body is the credential, not a JWT). | user directive |
| D-03 | **CI static auditor enforces per-route invariants.** The auditor is a CI step, not a manual review. A failing auditor blocks merges. The auditor's job is the invariant: `∀ route, route.has_public_marker ∨ route.has_action_marker`. | user directive |
| D-04 | **Action vocabulary is extensible.** When an endpoint's semantic action does not fit the existing 7-Action enum, the enum is extended (new variants like `ManageHooks`, `ManageMemories`, `ManageAudit`, `ManageConfig`, `ManageSecrets`, `ManageSandbox`, `ManageScheduler`) and the `Role × Action` matrix is regenerated. The 7-Action baseline is a starting point, not a cap. | user directive |
| D-05 | **AuthMode::None / ApiKey semantics are fully compatible.** v3.9 wiring is purely additive; the existing `test_auth_modes None` and `test_auth_modes ApiKey` paths are bit-for-bit unchanged. Only `AuthMode::Full` runs the new per-route RBAC. | user directive |
| D-06 | **RouteCatalog structure is the source of truth.** The simplest implementation that satisfies D-01/D-02/D-03 is acceptable; the auditor being correct matters more than the implementation aesthetic. Both `manual-decorated-router` and `generate-catalog-from-router` patterns are acceptable; catalog-as-`pub` data is the contract. | scope discipline |
| D-07 | **No new external crate dependency.** The existing `grid-engine` / `grid-server` toolchain is sufficient. | CLAUDE.md §Constraints |
| D-08 | **No schema migration.** The route catalog is Rust code; the Role × Action matrix is Rust code. No DB migration. | CLAUDE.md §Constraints |
| D-09 | **Shared-core rule (ADR-V2-023 P1) preserved.** Any change to `grid-engine` (the `Role × Action` matrix) MUST work for both engine 接入面 (EAASP) and Grid 独立产品. EAASP does not currently consume `Role::can(Action)` for HTTP routing, so adding new Action variants is safe; verified by the test `test_rbac_engine_layer_is_leg_agnostic` (new). | ADR-V2-023 P1 |
| D-10 | **Phase 3.9.0 → 3.9.1 → 3.9.2 is the agreed ladder.** Catalog/allowlist first (so the auditor has a stable target), then full wiring + matrix regeneration (so the auditor can PASS), then CI auditor + regression (so future drift is caught). | user directive |

## Traceability (filled by roadmapper)

| Phase | REQ-IDs |
|-------|---------|
| **03.9.0** Route catalog + public allowlist | CAT-01, CAT-02, CAT-04 |
| **03.9.1** Full business-route wiring + Action matrix | RBAC-05, RBAC-06, RBAC-07, RBAC-08, CAT-03, MODE-01, MODE-02, MODE-03 |
| **03.9.2** CI auditor + regression sweep | AUD-01, AUD-02, AUD-03, TEST-07, TEST-08, TEST-09, DOC-04, DOC-05, DOC-06 |
| **Total** | **20 REQ-IDs / 3 phases / 5 categories** |

---

## v3.11.3 Requirements — single-point live walkthrough (LIVE-01..04)

**Defined:** 2026-07-27 (v3.11.0 + v3.11.1 + v3.11.2 SHIPPED)
**Goal:** Run a real end-to-end live walkthrough of the 5-stage approval state machine against the real OPA sidecar v0.68.0 on `127.0.0.1:18181`, capture dated production evidence at `docs/status/PRODUCTION_USABILITY_2026-07-27.md` + `docs/status/PRODUCTION_USABILITY_LOGS_2026-07-27/`, and surface the `audit.py` CHECK constraint gap on `await_human` (deferred to v3.12.0 per D-23).

**REQ-IDs** use v3.11.3 numbering (`LIVE-*`). 4 REQ-IDs cover this phase.

### LIVE — Live walkthrough

- [x] **LIVE-01**: 7 EAASP services up via `.grid/dev-eaasp-live.sh` (skill-registry + L2 + L3 w/ OPA + mock-scada + MCP orchestrator + grid-runtime + L4). OPA sidecar v0.68.0 listens on `127.0.0.1:18181`. Health summary captured in `docs/status/PRODUCTION_USABILITY_LOGS_2026-07-27/health-summary.txt`.
- [x] **LIVE-02**: 5 SSE events emitted in canonical order (governance.approval.plan → check → draft → approve → execute, seq 26–30, single request_id) via `SessionEventStream.emit_governance_approval_<stage>(...)` for a `scada_set_setpoint mode=enforce risk_level=write_external` chain. SSE capture in `docs/status/PRODUCTION_USABILITY_LOGS_2026-07-27/sse-capture.json` + `sse-capture.raw`.
- [x] **LIVE-03**: 5 POST `/v1/data/governance/decision` roundtrips captured (OPA HTTP traffic in `opa-sidecar-*.log`); 3-state OPA decision (`allow` / `approval` / `deny`) verified end-to-end; 18 rows in L3 `governance_decisions` ledger across 3 chain runs (count captured in `l3-audit-row-count.txt`, decisions in `l3-audit-decisions.tsv`).
- [x] **LIVE-04**: v3.9 RBAC audit still PASS (134 routes / `make rbac-audit`); v3.10 spec-audit still PASS (4 files / 37 rows / `make v3.10-spec-audit`); ADR-V2-023 P1 shared-core rule preserved (no shared-crate change); ADR-V2-034 OPA sidecar topology verified end-to-end. **`docs/status/JOURNAL.md` untouched** per task directive.

**Live walkthrough known finding (deferred to v3.12.0 per D-23):** `audit.py`'s CHECK constraint on `governance_decisions.decision` currently lists only `{allow, approve, deny, gate_request}` — the `await_human` sentinel that L3's 5-stage state machine emits at the Approve stage is not in that allowlist. Documented in `docs/status/PRODUCTION_USABILITY_2026-07-27.md` §7. Filed as `V311-AUDIT-01` in `docs/design/EAASP/DEFERRED_LEDGER.md`. The 5 SSE events in LIVE-02 carry canonical `allow` / `approve` for the persistence path; only the in-process harness sees `await_human` (which it does not write to L3 today). v3.12.0 widens the CHECK constraint via idempotent `ALTER TABLE` per D-26.

### v3.11.3 Traceability

| Phase | REQ-IDs |
|---|---|
| **03.11.0 OPA sidecar infrastructure** | OPA-01, OPA-02, INSTALL-01, COMPAT-01, COMPAT-02, DEFER-LEDGER-CLOSE-01 |
| **03.11.1 L3 OPA backend adapter + Rego templates** | OPA-BACKEND-01..04, REGO-01..02, FAIL-CLOSED-01..02, DISABLED-01 |
| **03.11.2 5-stage approval state machine** | STAGE-01..05, SSE-01..05, AUDIT-01..02, DENY-01..02 |
| **03.11.3 single-point live walkthrough** | LIVE-01, LIVE-02, LIVE-03, LIVE-04 |
| **Total** | **29 REQ-IDs / 4 phases / 11 categories** (OPA + INSTALL + OPA-BACKEND + REGO + FAIL-CLOSED + DISABLED + STAGE + SSE + AUDIT + DENY + LIVE) |

---


## v3.12 Requirements — EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd

**Defined:** 2026-07-27 (v3.11 SHIPPED + v3.11.3 walkthrough surfaced `audit.py` CHECK constraint gap; v3.12 is the next-milestone bootstrap)
**Goal:** Begin EAASP v2.0 EVOLUTION_PATH §三 Phase 4 by delivering the **A2A Router** (agent-to-agent coordination across multiple sessions) and **Event Room** (multi-session event coordination that V310-A2A-01 deferred from v3.10 and V310-SESSION-01 deferred from v3.10 require). The milestone also closes a real bug surfaced during the v3.11 single-point live walkthrough (LIVE known finding above): `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include the `await_human` sentinel value emitted by the 5-stage approval state machine at the Approve stage. v3.12.0 patches the schema first (idempotent `ALTER TABLE` migration per D-26); v3.12.1 lands the Event Room + multi-session coordination; v3.12.2 lands the A2A Router; v3.12.3 is a single-point live walkthrough that demonstrates the whole Phase 4 surface.

**Status (post-2026-07-27 walkthrough):** ✅ SHIPPED. All 4 phases (03.12.0 / 03.12.1 / 03.12.2 / 03.12.3) complete. Tag `v3.12` pushed at commit `894639dd`. V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01 ✅ CLOSED. v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 + ADR-V2-034 OPA sidecar all preserved.

**REQ-IDs** use v3.12 numbering (`SCHEMA-*`, `EVENT-ROOM-*`, `A2A-*`, `SESSION-*`, `COMPAT-*`). 13–16 REQ-IDs across 5 categories, continue from v3.11 (no overlap with `OPA-*` / `OPA-BACKEND-*` / `REGO-*` / `FAIL-CLOSED-*` / `DISABLED-*` / `STAGE-*` / `SSE-*` / `AUDIT-*` / `DENY-*` / `LIVE-*`).

### SCHEMA — `audit.py` CHECK constraint patch ✅ SHIPPED 2026-07-27

- [x] **SCHEMA-01**: `audit.py`'s CHECK constraint on `governance_decisions.decision` is extended to include `await_human` alongside the existing `{allow, approve, deny, gate_request}`. The constraint is implemented as a SQLite `CHECK` clause on the column (or a TRIGGER-based equivalent) and is verified to be in effect for both fresh and migrated DBs.
- [x] **SCHEMA-02**: Idempotent `ALTER TABLE` migration on `governance_decisions` drops the old CHECK constraint and adds the new one with `await_human` (matching the existing v3.11.2 `stage` column migration pattern at the same `audit.py` module). Existing DBs upgrade cleanly without losing history; fresh DBs (CREATE TABLE) carry the new constraint inline.
- [x] **SCHEMA-03**: `audit.py`'s in-process enum validation (line 282) is updated to accept `await_human` and the `DECISION_AWAIT_HUMAN` sentinel constant. The Python `Decision` enum / Literal type (or its equivalent) gains the `await_human` variant. Backwards-compatible: `await_human` rows coexist with `allow` / `approve` / `deny` / `gate_request` rows in the same `governance_decisions` table.

### MIGRATION — `audit.py` CHECK constraint migration coverage ✅ SHIPPED 2026-07-27

- [x] **MIGRATION-01**: `db.migrate_decision_await_human(path)` is idempotent. Hand-constructing a v3.11.x ledger (4-value CHECK allowlist, no `await_human`), running the migration widens the allowlist to include `await_human`; calling the migration a second time is a NO-OP. Fresh schemas (v3.12.0+ CREATE TABLE) carry the widened allowlist inline and the migration is a NO-OP.
- [x] **MIGRATION-02**: The migration preserves all pre-existing rows (allow / approve / deny / gate_request) verbatim. v3.11.2 / v3.11.3 rows with a populated `stage` column also survive — the migration's `INSERT INTO new (col1, col2, ...) SELECT col1, col2, ... FROM legacy` projects only the columns the legacy row carries; pre-v3.11.2 rows land with `stage = NULL`.

### AWAIT-HUMAN — `DECISION_AWAIT_HUMAN` ledger evidence ✅ SHIPPED 2026-07-27

- [x] **AWAIT-HUMAN-01**: `audit.DECISION_ALLOWLIST` exposes `await_human` alongside `allow`, `approve`, `deny`, `gate_request`. `AuditStore.record_governance_decision` accepts `decision="await_human"` and the row persists to the ledger (no `aiosqlite.IntegrityError`, no `ValueError`).
- [x] **AWAIT-HUMAN-02**: The 5-stage state machine's paused Approve stage routes `DECISION_AWAIT_HUMAN` through the full `record_governance_decision` flow. The ledger carries a dedicated `approve_pause` row carrying `decision="await_human"` (in addition to the upstream `approve` policy verdict row). After the human signs off, the resume path writes the human verdict (`allow` / `deny`) as a follow-on row. Before v3.12.0 the row was silently swallowed (audit.py rejected `await_human` with `ValueError`); v3.12.0 fixes this end-to-end.

### EVENT-ROOM — Multi-session Event Room substrate ✅ SHIPPED 2026-07-27

- [x] **EVENT-ROOM-01**: An `EventRoom` abstraction lives in `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_room.py` (per v3.7.3 L4 ownership pattern; D-27). An `EventRoom` is a logical namespace that spans multiple sessions and binds their events together. The `EventRoom.create(room_id, name, tenant_id, owner_session_id)` constructor + `EventRoom.bind_session(room_id, session_id)` / `EventRoom.list_sessions(room_id)` / `EventRoom.list_rooms(tenant_id)` accessors are public.
- [x] **EVENT-ROOM-02**: Multi-session event fan-out — when an event is emitted to an `EventRoom`, it is delivered to every session bound to that room. The L4 SSE stream carries the fan-out via a new `governance.session.cross` event family (per the v3.12.1 SSE extension). The fan-out is bounded by the room's session list; cross-tenant leakage is impossible by construction.
- [x] **EVENT-ROOM-03**: `EventRoom.fan_out_event(room_id, event, origin_session_id)` is the dispatch entry point. It is policy-gated by the v3.7.3 governance gate (L3 `PolicyEngine.evaluate_gate`) and the v3.11.2 5-stage approval state machine (`ApprovalStateMachine.run`); the cross-session dispatch path runs through the same gate.

### A2A — Agent-to-agent Router ✅ SHIPPED 2026-07-27

- [x] **A2A-01**: An `A2ARouter` service lives in `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/a2a_router.py`. It exposes `A2ARouter.dispatch(from_session_id, to_session_id, payload, evidence_refs)` which initiates a cross-session turn. The dispatch path runs through the v3.7.3 governance gate + the v3.11.2 5-stage approval state machine (per D-25: human-in-the-loop pause applies to A2A dispatch the same way it applies to a single-session chain).
- [x] **A2A-02**: The A2A dispatch path emits 5 SSE events with the same canonical payload shape as v3.11.2 (`governance.approval.<stage>` family) but a new `cross_session: bool = true` field. The 5-stage chain persists 5 rows to the L3 `governance_decisions` ledger (with the new `await_human` CHECK constraint from SCHEMA-01 honoring the paused-state row), plus 5 `governance.session.cross` events for the cross-session fan-out.
- [x] **A2A-03**: `A2ARouter.dispatch` is rejected with `403 Forbidden` when the source session and target session are in different `EventRoom`s or different tenants. Cross-tenant A2A dispatch is explicitly out of v3.12 scope (per v3.12 §Out of Scope; deferred to v3.13+).
- [x] **A2A-04**: The A2A Router's `dispatch` path persists an audit row with `cross_session=True` and the linked `room_id` so the audit ledger is pivotable on cross-session activity.

### SESSION — Multi-session coordination ✅ SHIPPED 2026-07-27

- [x] **SESSION-01**: A new `L4 /v1/rooms/{room_id}/sessions/{session_id}/events` endpoint accepts a POST that fans an event out via `EventRoom.fan_out_event(...)`. The endpoint is RBAC-guarded per v3.9 route-catalog (a new `ManageRooms` `Action` variant; D-04 v3.9 vocabulary extension pattern).
- [x] **SESSION-02**: A new `L4 /v1/rooms/{room_id}/sessions/{session_id}/dispatch` endpoint wraps `A2ARouter.dispatch(...)` end-to-end. The endpoint returns `202 Accepted` with the `request_id` of the 5-stage chain; clients poll `L4 /v1/rooms/{room_id}/sessions/{session_id}/chains/{request_id}` for the chain's progress.
- [x] **SESSION-03**: v3.11.2's per-session SSE contract is preserved verbatim (the existing `governance.approval.<stage>` events still fire per session); the new `governance.session.cross` event family is added on top, not in place of, the per-session contract. Regression: v3.11.2's `test_governance_sse.py` still PASS without modification.

### COMPAT — Contract + L1 substitutability + 安全边界 guards ✅ SHIPPED 2026-07-27

- [x] **COMPAT-01**: `proto/eaasp/runtime/v2/{common,runtime,hook}.proto` remain wire-compatible with `contract-v1.2.0`. No new RPC methods, no removed RPC methods, no breaking field-type changes in v3.12. Verified by `cargo test -p eaasp-certifier` PASS state pre and post each phase.
- [x] **COMPAT-02**: All 7 L1 runtimes (`grid-runtime` + claude-code / goose / nanobot / pydantic-ai / claw-code / ccb; `hermes` frozen per ADR-V2-017) continue to pass `contract-v1.2.0` certifier after each v3.12 phase. Verified by `make v2-phase3-e2e-rust` + per-runtime `make v2-phase3-e2e` runs. L1 substitutability guard (D-14) is the gate.
- [x] **COMPAT-03**: Shared-core rule (ADR-V2-023 P1) preserved across any v3.12 changes — `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品. Verified by the existing `test_rbac_engine_layer_is_leg_agnostic` + a new `test_v3_12_shared_core_unchanged` that snapshots `grid-engine::auth` + `grid-types::session` + `grid-types::runtime` public API surface pre/post v3.12. (D-28)
- [x] **COMPAT-04**: v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + ADR-V2-034 OPA sidecar ALL continue to PASS through every v3.12 phase. (D-28)

### TRACE — Spec traceability evidence ✅ SHIPPED 2026-07-27

- [x] **TRACE-01**: `docs/status/PRODUCTION_USABILITY_2026-07-28.md` dated walkthrough: (1) `audit.py` CHECK constraint patch holds under live OPA sidecar (`await_human` row persisted to `governance_decisions` ledger), (2) Event Room fans events across 2+ sessions, (3) A2A Router dispatches a cross-session turn end-to-end through the 5-stage approval chain (with the Approve stage pausing for human-in-the-loop and the `await_human` row in the audit ledger), (4) `make rbac-audit` + `make v3.10-spec-audit` + `make v2-phase3-e2e-rust` PASS post-v3.12. Reuses the v3.11.3 PRODUCTION_USABILITY_2026-07-27.md pattern. (D-25)
- [x] **TRACE-02**: `tools/eaasp-spec-alignment/ALIGNMENT_MATRIX.md` cross-index update: every EAASP v2.0 spec section that v3.12 touches (spec §5.3 / §14 / §17) is listed with `(status, v3.12_phase, post_v3.12_owner)`. Gaps above the `contract-v1.2.0` baseline are explicitly listed as `deferred_to_v3.13+` with rationale, so the spec surface is honest about what is and isn't covered. (D-12 carry-over)

## Future Requirements (deferred — explicit v3.12+ backlog)

- **Phase 5 L5 Cowork UI** — V310-COWORK-01; moved into v3.13 scope (planned).
- **Phase 6 ecosystem expansion** — V310-ECOSYSTEM-01 / V310-MAT-01; v3.14+ scope.
- **L1 infrastructure tier changes (gVisor / Firecracker / Kata)** — V310-SANDBOX-01; long-term.
- **NATS JetStream backend for EventStream** — D75; long-term.
- **Cross-tenant A2A dispatch** — explicitly out of v3.12; deferred to v3.13+ scope.
- **L4 event window cursor (>10k events)** — D36; Phase 3+ scale testing.

## Out of Scope (v3.12)

- **Phase 5 L5 Cowork UI** — v3.13 scope (per V310-COWORK-01).
- **Phase 6 ecosystem expansion** — v3.14+ scope.
- **L1 infrastructure tier changes** — long-term.
- **NATS JetStream backend for EventStream** — long-term.
- **New service ports / new repository** — D-27 forbids; v3.12 stays in `tools/eaasp-*/` and reuses the existing 7 EAASP services on `.grid/dev-eaasp-live.sh`.
- **Schema migration beyond the `audit.py` CHECK constraint extension** — D-26: the constraint extension is the only schema change in v3.12; new tables / new columns are deferred.
- **Proto contract widening** — D-13 / D-21 carry-over; v3.12 reconciles to existing 21 RPC only.
- **L1 runtime additions or substitutions** — the 7-runtime matrix is frozen for v3.12.
- **`web-platform/` Quality 7.5→9.0** — separate milestone.
- **`grid-desktop` Quality 6.5→9.0** — separate milestone.
- **`grid-platform` route catalog audit** — separate milestone.

## Locked Decisions (from v3.12 discussion — non-negotiable)

| # | Decision | Source |
|---|----------|--------|
| D-23 | **`audit.py` CHECK constraint patch is mandatory phase 0.** v3.11.3 live walkthrough §7 surfaced that `audit.py`'s CHECK constraint on `governance_decisions.decision` does not include `await_human`; the 5-stage state machine emits `await_human` at the Approve stage; without this fix, 03.12.1 / 03.12.2 / 03.12.3 cannot reproduce paused-state audit evidence. v3.12.0 MUST patch the schema first; no implementation work in 03.12.1 / 03.12.2 may proceed before 03.12.0 ships. Closes `V311-AUDIT-01`. | user directive (v3.11.3 walkthrough known finding) |
| D-24 | **v3.12 scope = EAASP Phase 4.** v3.12 delivers A2A Router + Event Room + multi-session coordination per EAASP_v2_0_EVOLUTION_PATH.md §三 Phase 4 scope (spec §5.3 / §14 / §17). Closes V310-A2A-01 + V310-SESSION-01 + V311-AUDIT-01. v3.13+ = Phase 5 L5 / Phase 6 ecosystem (V310-COWORK-01 / V310-ECOSYSTEM-01 / V310-MAT-01). | user directive |
| D-25 | **MVP executable baseline + new A2A coordination scenario.** Phase 0.5 MVP human-executable floor (`threshold-calibration` skill + `make dev-eaasp`) remains the minimum bar; v3.12 adds a new A2A coordination walkthrough scenario on top of that floor (request A's approve stage pauses; event room fans out; another session's A2A dispatch resumes the chain). | CLAUDE.md §Runtime Verification Tasks + scope discipline |
| D-26 | **`audit.py` CHECK constraint extension uses idempotent migration.** The extension MUST use `ALTER TABLE` (matching the existing v3.11.2 `stage` column migration pattern at the same `audit.py` module); existing DBs upgrade cleanly without losing history. No destructive schema work. No new tables / no new columns beyond the CHECK constraint extension. | user directive |
| D-27 | **v3.12 stays in `tools/eaasp-*/` simulator-level implementations.** v3.12 does not open a new repo / does not open a new service port; uses the existing 7 EAASP services (skill-registry / L2 / L3 / mock-scada / MCP orchestrator / grid-runtime / L4) on `.grid/dev-eaasp-live.sh` launch topology. Event Room + A2A Router live in `tools/eaasp-l4-orchestration/` (per v3.7.3 L4 ownership pattern). | CLAUDE.md §Constraints + D-15 carry-over |
| D-28 | **v3.12 安全边界 + shared-core rule + rbac-audit + v3.10-spec-audit + OPA sidecar all continue to PASS.** v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + ADR-V2-023 P1 shared-core rule + ADR-V2-034 OPA sidecar ALL continue to PASS through every v3.12 phase. No shared-crate change is anticipated, but if any change is required it must remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品. | D-09 / D-14 / D-17 / D-20 carry-over |
| D-29 | **v3.12 探索策略 = Explore + Grep.** No `.codegraph/` in this repo; no MCP codegraph tool available. Codebase pattern reads gate by CLAUDE.md "Level 1+ single-pass reads" rule (each source file read once; subsequent detail via Grep with specific pattern). | CLAUDE.md §Tool & MCP Usage |

## Traceability (filled by roadmapper)

| Phase | REQ-IDs |
|-------|---------|
| **03.12.0 Schema + audit constraint patch ✅ SHIPPED 2026-07-27** | SCHEMA-01 ✅, SCHEMA-02 ✅, SCHEMA-03 ✅, MIGRATION-01 ✅, MIGRATION-02 ✅, AWAIT-HUMAN-01 ✅, AWAIT-HUMAN-02 ✅, COMPAT-01..04 (verified preserved), TRACE-02 |
| **03.12.1 Event Room + multi-session ✅ SHIPPED 2026-07-27** | EVENT-ROOM-01 ✅, EVENT-ROOM-02 ✅, EVENT-ROOM-03 ✅, SESSION-01 ✅, SESSION-03 ✅, COMPAT-01 ✅, COMPAT-02 ✅, COMPAT-03 ✅, COMPAT-04 ✅, TRACE-01 |
| **03.12.2 A2A Router ✅ SHIPPED 2026-07-27** | A2A-01 ✅, A2A-02 ✅, A2A-03 ✅, A2A-04 ✅, SESSION-02 ✅, SESSION-03 ✅, COMPAT-01 ✅, COMPAT-02 ✅, COMPAT-03 ✅, COMPAT-04 ✅, TRACE-01 |
| **03.12.3 single-point live walkthrough ✅ SHIPPED 2026-07-27 @ 894639dd** | LIVE-01 ✅ (v3.12-context), LIVE-02 ✅ (v3.12-context), LIVE-03 ✅ (v3.12-context), LIVE-04 ✅ (v3.12-context), TRACE-01 ✅ (final), TRACE-02 ✅ (final) |
| **Total** | **13–16 REQ-IDs / 4 phases / 5 categories** (SCHEMA / EVENT-ROOM / A2A / SESSION / COMPAT + TRACE cross-axis) |

---


## v3.13 Requirements — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle)

**Defined:** 2026-07-27 (v3.12 SHIPPED 2026-07-27 @ 894639dd; V310-COWORK-01 was deferred from v3.10 / v3.11 / v3.12 to v3.13 per EVOLUTION_PATH §三 Phase 5)
**Goal:** Begin EAASP v2.0 EVOLUTION_PATH §三 Phase 5 by delivering the **L5 Cowork UI substrate** as a four-card projection layer (Event / Evidence / Action / Approval) plus a **retrospective cycle** (回溯闭环) that lets any four-card record trace back to its full Event → Evidence → Action → Approval chain by `session_id`. v3.13 does NOT build a frontend (web/ + web-platform/ remain dormant); it lands a simulator-level backend + projection at `tools/eaasp-l5-cowork/` that derives the four cards from already-shipped L2 evidence anchor + L3 governance_decisions + L4 event_room_events + A2A review.closed events. v3.13.0 establishes the four-card data model + projection + L4 SSE bridge; v3.13.1 wires four-card SSE fan-out + state transitions + persistence; v3.13.2 builds the retrospective cycle (trace API); v3.13.3 is a single-point live walkthrough that demonstrates the full Phase 5 surface and pushes tag `v3.13`.

**Context (post-v3.12):** v3.12 SHIPPED the Event Room + multi-session coordination + A2A Router + audit.py CHECK constraint patch (including `await_human` for paused-state audit evidence). The data needed for an L5 Cowork UI is now in place — every L2 piece of evidence has an anchor, every L3 governance decision has a row, every L4 Event Room event has a session_id + room_id, every A2A dispatch has a `cross_session` audit row. v3.13's job is to project these four orthogonal data dimensions into a single Cowork substrate that operators can pivot on `session_id`. Per EVOLUTION_PATH §三 Phase 5: spec §4 (L5 Cowork UX) + §4.4 (four-card UI). Closes V310-COWORK-01.

**Status (post-2026-07-29 SHIP):** ✅ SHIPPED 2026-07-29. 4-phase ladder complete (03.13.0 / 03.13.1 / 03.13.2 / 03.13.3); 13+ REQ-IDs / 5 categories closed; tag `v3.13` annotated.

**REQ-IDs** use v3.13 numbering (`CARD-EVENT-*`, `CARD-EVIDENCE-*`, `CARD-ACTION-*`, `CARD-APPROVAL-*`, `RETROSPECTIVE-*`). 13–16 REQ-IDs across 5 categories, continue from v3.12 (no overlap with `SCHEMA-*` / `MIGRATION-*` / `AWAIT-HUMAN-*` / `EVENT-ROOM-*` / `A2A-*` / `SESSION-*` / `COMPAT-*` / `TRACE-*`).

### CARD-EVENT — Event card (L4 Event Room + A2A envelope)

- [x] **CARD-EVENT-01**: `EventCard` is a projection type in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/cards.py` that derives its `id`, `session_id`, `room_id`, `event_type`, `payload_summary`, `created_at`, `tenant_id` from `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/event_room_events` (per v3.12.1 SQLite table). The projection is a SELECT, not a COPY — v3.13 ships no new storage.
- [x] **CARD-EVENT-02**: An `EventCard` is keyed by `(session_id, event_seq)`; the projection supports `list_event_cards(session_id) -> list[EventCard]` and `list_event_cards_by_room(room_id) -> list[EventCard]` accessors. Both bound their result to the principal's tenant (no cross-tenant leakage; matches v3.12.1 D-28 security gate).
- [x] **CARD-EVENT-03**: The `EventCard.payload_summary` carries a deterministic 1-line summary of the underlying event payload (e.g. `"scada_set_setpoint mode=enforce risk=write_external room=r-7"`) so the Cowork UI can render the card without pulling the full payload.

### CARD-EVIDENCE — Evidence card (L2 evidence anchor)

- [x] **CARD-EVIDENCE-01**: `EvidenceCard` is a projection type in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/cards.py` that derives its `id`, `session_id`, `evidence_type`, `content_summary`, `created_at`, `confirmed`, `tenant_id` from `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/memory_anchors` (per v3.7.3 L2 memory anchor surface). The projection is a SELECT, not a COPY.
- [x] **CARD-EVIDENCE-02**: An `EvidenceCard` is keyed by `anchor_id`; the projection supports `list_evidence_cards(session_id) -> list[EvidenceCard]` (joins L2 memory_anchors on `session_id` via the L2 `memory_anchors.session_id` column). Both bound to principal's tenant.
- [x] **CARD-EVIDENCE-03**: The `EvidenceCard.content_summary` carries a deterministic 1-line summary of the underlying L2 memory anchor (e.g. `"scada_setpoint_history 2026-07-15..2026-07-25"`) so the Cowork UI can render the card without pulling the full L2 payload.

### CARD-ACTION — Action card (L5 sandbox / tool invocation record)

- [x] **CARD-ACTION-01**: `ActionCard` is a projection type in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/cards.py` that derives its `id`, `session_id`, `tool_name`, `risk_level`, `requested_at`, `dispatched_at`, `tenant_id` from `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/telemetry_events` (per v3.7.3 L4 telemetry surface + v3.11 L3 governance request/final events). The projection is a SELECT, not a COPY.
- [x] **CARD-ACTION-02**: An `ActionCard` is keyed by `(session_id, tool_seq)`; the projection supports `list_action_cards(session_id) -> list[ActionCard]`. Bound to principal's tenant.
- [x] **CARD-ACTION-03**: The `ActionCard.risk_level` is the canonical risk classification surfaced by the v3.11.1 Rego template (spec §6.1) — `read` / `write_internal` / `write_external` / `privileged`. The card carries the risk_level so the Cowork UI can sort / filter by risk.

### CARD-APPROVAL — Approval card (L3 governance_decisions + 5-stage state machine)

- [x] **CARD-APPROVAL-01**: `ApprovalCard` is a projection type in `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/cards.py` that derives its `id`, `session_id`, `stage`, `decision`, `rationale`, `decided_at`, `tenant_id` from `tools/eaasp-l3-governance/src/eaasp_l3_governance/governance_decisions` (per v3.11.2 5-stage state machine + v3.12.0 audit.py CHECK constraint widening). The projection is a SELECT, not a COPY.
- [x] **CARD-APPROVAL-02**: An `ApprovalCard` is keyed by `(session_id, stage, decision_id)`; the projection supports `list_approval_cards(session_id) -> list[ApprovalCard]`. Bound to principal's tenant. All 5 stages (plan / check / draft / approve / execute) appear in the result for a complete 5-stage chain; the `await_human` paused-state row appears as a separate `approval_pause` card.
- [x] **CARD-APPROVAL-03**: The `ApprovalCard.decision` carries the canonical 5-state decision from v3.11.2 / v3.12.0 extended allowlist — `allow` / `approve` / `deny` / `gate_request` / `await_human`. The card also carries the `stage` field from the v3.11.2 `stage` column extension so the Cowork UI can show the 5-stage stage-position badge.

### RETROSPECTIVE — Retrospective cycle (回溯闭环)

- [x] **RETROSPECTIVE-01**: `tools/eaasp-l5-cowork/src/eaasp_l5_cowork/retrospective.py` exposes `trace_session(session_id) -> RetrospectiveChain`. The chain is a typed structure carrying the four card lists in canonical order: `events: list[EventCard]`, `evidence: list[EvidenceCard]`, `actions: list[ActionCard]`, `approvals: list[ApprovalCard]`, plus `cross_refs: list[CrossRef]` linking each card to the cards that caused it (e.g. an Action card cross-references its upstream Evidence card by `anchor_id`).
- [x] **RETROSPECTIVE-02**: A `L5 /v1/cowork/trace/{session_id}` endpoint wraps `trace_session(session_id)` and returns the full `RetrospectiveChain` payload. The endpoint is RBAC-guarded per v3.9 route-catalog (reuses the existing `Read` `Action`; no new `Action` variant required for read-only trace).
- [x] **RETROSPECTIVE-03**: A `Cowork` CLI command in `tools/eaasp-cli-v2/src/eaasp_cli_v2/cli.py` — `eaasp cowork trace {session_id}` — prints the four-card trace to stdout in a human-readable form (one line per card, grouped by Event / Evidence / Action / Approval, with cross-refs marked). Reuses the threshold-calibration skill for executable floor (D-34).
- [x] **RETROSPECTIVE-04**: The retrospective trace is **read-only** and **does not mutate** any underlying L2 / L3 / L4 record. Invariant: `trace_session(s)` invoked twice for the same `session_id` returns the same chain (modulo deterministic ordering). Verified by `test_retrospective_idempotent.py`.
- [x] **RETROSPECTIVE-05**: The retrospective trace is **bounded by the principal's tenant**. Cross-tenant `trace_session` calls are rejected with `403 Forbidden` (matching v3.12.1 D-28 security gate).

### COMPAT — Contract + L1 substitutability + 安全边界 guards (v3.13 cross-axis)

- [ ] **COMPAT-01**: `proto/eaasp/runtime/v2/{common,runtime,hook}.proto` remain wire-compatible with `contract-v1.2.0`. No new RPC methods, no removed RPC methods, no breaking field-type changes in v3.13. Verified by `cargo test -p eaasp-certifier` PASS state pre and post each phase.
- [ ] **COMPAT-02**: All 7 L1 runtimes (`grid-runtime` + claude-code / goose / nanobot / pydantic-ai / claw-code / ccb; `hermes` frozen per ADR-V2-017) continue to pass `contract-v1.2.0` certifier after each v3.13 phase. Verified by `make v2-phase3-e2e-rust` + per-runtime `make v2-phase3-e2e` runs. L1 substitutability guard (D-14 carry-over) is the gate.
- [ ] **COMPAT-03**: Shared-core rule (ADR-V2-023 P1) preserved across any v3.13 changes — `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品. Verified by the existing `test_rbac_engine_layer_is_leg_agnostic` + a new `test_v3_13_shared_core_unchanged` that snapshots `grid-engine::auth` + `grid-types::session` + `grid-types::runtime` public API surface pre/post v3.13. (D-35)
- [ ] **COMPAT-04**: v3.9 route-catalog RBAC (134 routes / `make rbac-audit`) + v3.10 spec-audit (4 files / 37 rows / `make v3.10-spec-audit`) + v3.11 OPA sidecar (ADR-V2-034) + v3.12 Event Room ContextVar auth + v3.12.2 A2A Router + ReviewSet all continue to PASS through every v3.13 phase. (D-35)
- [ ] **COMPAT-05**: v3.13 不开新服务端口 (D-37);`tools/eaasp-l5-cowork/` is a third-party Python module that consumes the existing 7 EAASP services via HTTP — no new listening port.

### TRACE — Spec traceability evidence (v3.13 cross-axis)

- [ ] **TRACE-01**: `docs/status/PRODUCTION_USABILITY_2026-07-29.md` dated walkthrough: (1) four-card data model + projection holds under live OPA sidecar + Event Room + A2A Router, (2) `trace_session(session_id)` returns a complete chain for any `session_id` that has produced events in v3.12 + v3.13 phases, (3) `make rbac-audit` + `make v3.10-spec-audit` + `make v2-phase3-e2e-rust` PASS post-v3.13. Reuses the v3.12.3 PRODUCTION_USABILITY_2026-07-28.md pattern. (D-25 carry-over)
- [ ] **TRACE-02**: `tools/eaasp-spec-alignment/ALIGNMENT_MATRIX.md` cross-index update: every EAASP v2.0 spec section that v3.13 touches (spec §4 + §4.4) is listed with `(status, v3.13_phase, post_v3.13_owner)`. Gaps above the `contract-v1.2.0` baseline are explicitly listed as `deferred_to_v3.14+` with rationale. (D-12 carry-over)
- [ ] **TRACE-03**: The four-card projection is **provably derived** — for any `session_id`, the union of `EventCard` + `EvidenceCard` + `ActionCard` + `ApprovalCard` IDs exactly matches the `(session_id, ...)` subset of the underlying L2 / L3 / L4 tables. Verified by `test_four_card_projection_is_derived.py` (cross-table count parity assertion).

## Future Requirements (deferred — explicit v3.13+ backlog)

- **Phase 6 ecosystem expansion** — V310-ECOSYSTEM-01 / V310-MAT-01; v3.14+ scope.
- **L1 infrastructure tier changes (gVisor / Firecracker / Kata)** — V310-SANDBOX-01; long-term.
- **NATS JetStream backend for EventStream** — D75; long-term.
- **Cross-tenant A2A dispatch** — explicitly out of v3.12; deferred to v3.13+ scope (sub-task per D-30).
- **L4 event window cursor (>10k events)** — D36; Phase 3+ scale testing.
- **Actual L5 Cowork UI (React + Tailwind)** — separate milestone; web/ + web-platform/ remain dormant. v3.13 only ships the Python projection layer (D-31 carry-over).
- **Cross-room retrospective trace** — v3.13 trace is per-session; cross-room chained trace deferred to v3.13.2+ refinement.

## Out of Scope (v3.13)

- **Phase 6 ecosystem expansion** — v3.14+ scope.
- **L1 infrastructure tier changes** — long-term.
- **NATS JetStream backend for EventStream** — long-term.
- **New service ports / new repository** — D-37 forbids; v3.13 stays in `tools/eaasp-*/` and reuses the existing 7 EAASP services on `.grid/dev-eaasp-live.sh`.
- **New schema / new tables** — D-32 forbids; v3.13 = projection layer only, derived from existing L2 / L3 / L4 / A2A tables.
- **New frontend (React / TypeScript / Vite)** — D-37 forbids; web/ + web-platform/ remain dormant. v3.13 = Python projection + CLI only.
- **Proto contract widening** — D-13 / D-21 carry-over; v3.13 reconciles to existing 21 RPC only.
- **L1 runtime additions or substitutions** — the 7-runtime matrix is frozen for v3.13.
- **`web-platform/` Quality 7.5→9.0** — separate milestone.
- **`grid-desktop` Quality 6.5→9.0** — separate milestone.
- **`grid-platform` route catalog audit** — separate milestone.
- **Cross-tenant retrospective trace** — D-30 / D-32 confine v3.13 to per-tenant, per-session trace; cross-tenant grouping deferred.
- **Actual L5 Cowork UI UX work** — D-31 forbids; v3.13 is the backend projection layer only.

## Locked Decisions (from v3.13 discussion — non-negotiable)

| # | Decision | Source |
|---|----------|--------|
| D-30 | **v3.13 scope = EAASP Phase 5 L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle).** Per `EAASP_v2_0_EVOLUTION_PATH.md` §三 Phase 5 (spec §4 + §4.4). Closes `V310-COWORK-01`. v3.14+ = Phase 6 ecosystem expansion (V310-ECOSYSTEM-01 / V310-MAT-01). | user directive |
| D-31 | **L5 仍以 EAASP v2.0 spec §4 + §4.4 为权威源;本仓前端 (web/ + web-platform/) 仍为 dormant 状态;v3.13 在 `tools/eaasp-l5-cowork/` (新建) 落模拟器级四卡 backend + projection.** The four-card UI substrate is a Python projection layer, not a frontend. UI activation deferred to a separate future milestone. | CLAUDE.md §Frontend status + D-27 carry-over |
| D-32 | **四卡全部派生自 v3.12 已落地的 L2 evidence anchor + L3 governance_decisions + L4 event_room_events + A2A review.closed 事件;不新建独立存储.** v3.13 = projection + 视图层;底层仍是 v3.7.3 / v3.10 / v3.11 / v3.12 既有数据. No new tables, no new columns, no new event types. | user directive (per D-32 directive) |
| D-33 | **回溯闭环 (retrospective cycle) = 任何四卡 record 都能以 `session_id` 为根 trace 到 Event → Evidence → Action → Approval 全链;新增 `tools/eaasp-l5-cowork/retrospective.py` 提供 trace API (`trace_session(session_id) -> RetrospectiveChain`).** Trace is read-only, idempotent, bounded by tenant. | user directive |
| D-34 | **仍以 Phase 0.5 MVP 人工可执行性为最低标尺 (threshold-calibration skill + `make dev-eaasp`);v3.13 extends the same MVP floor with a four-card walkthrough scenario.** v3.13.3 produces `docs/status/PRODUCTION_USABILITY_2026-07-29.md` that exercises `eaasp cowork trace {session_id}` end-to-end against the real OPA sidecar + Event Room + A2A Router. | CLAUDE.md §Runtime Verification Tasks + D-25 carry-over |
| D-35 | **v3.9 / v3.10 / v3.11 / v3.12 硬约束不动.** Owner-only 边界不动 / AuthMode 兼容不动 / CI 顺序不动 / grid-engine 共享核心不动 / ADR-V2-023 P1 / ADR-V2-028 / ADR-V2-034 OPA sidecar / v3.11.2 5-stage approval / v3.12.1 Event Room ContextVar 鉴权 / v3.12.2 A2A Router + ReviewSet 全部保留. v3.9 RBAC + v3.10 spec-audit + ADR-V2-034 OPA sidecar + v3.12 Event Room + v3.12 A2A Router all continue to PASS. | D-09 / D-14 / D-17 / D-20 / D-28 carry-over |
| D-36 | **探索策略保持 Explore + Grep (本仓无 `.codegraph/`).** Same as v3.12 D-29. | CLAUDE.md §Tool & MCP Usage |
| D-37 | **v3.13 不开新前端 (react/typescript);仍 `tools/eaasp-*/` 模拟器级实现;不开新服务端口.** v3.13 lives in `tools/eaasp-l5-cowork/` (Python module) + `tools/eaasp-cli-v2/` (CLI command extension). No new HTTP routes bind to new ports. The `L5 /v1/cowork/trace/{session_id}` endpoint sits behind the existing EAASP L4 service port (per `.grid/dev-eaasp-live.sh` launch topology). | D-27 carry-over + v3.13 spec |

## Traceability (filled by roadmapper)

| Phase | REQ-IDs |
|-------|---------|
| **03.13.0 Event/Evidence/Action/Approval four-card data model + projection + L4 SSE bridge ✅ SHIPPED 2026-07-29** | CARD-EVENT-01 ✅, CARD-EVENT-02 ✅, CARD-EVENT-03 ✅, CARD-EVIDENCE-01 ✅, CARD-EVIDENCE-02 ✅, CARD-EVIDENCE-03 ✅, CARD-ACTION-01 ✅, CARD-ACTION-02 ✅, CARD-ACTION-03 ✅, CARD-APPROVAL-01 ✅, CARD-APPROVAL-02 ✅, CARD-APPROVAL-03 ✅, COMPAT-01..05 ✅, TRACE-02 ✅ |
| **03.13.1 Four-card SSE fan-out + state transitions + persistence ✅ SHIPPED 2026-07-29** | CARD-EVENT-02 (SSE extension) ✅, CARD-APPROVAL-02 (state transitions) ✅, COMPAT-01..04 ✅, TRACE-01 ✅, TRACE-02 ✅ |
| **03.13.2 Retrospective cycle (trace API) ✅ SHIPPED 2026-07-29** | RETROSPECTIVE-01 ✅, RETROSPECTIVE-02 ✅, RETROSPECTIVE-03 ✅, RETROSPECTIVE-04 ✅, RETROSPECTIVE-05 ✅, COMPAT-01..04 ✅, TRACE-01 ✅, TRACE-02 ✅ |
| **03.13.3 single-point live walkthrough + tag v3.13 ✅ SHIPPED 2026-07-29** | TRACE-01 (final) ✅, TRACE-02 (final) ✅, TRACE-03 ✅, COMPAT-01..05 (final) ✅, RETROSPECTIVE-04 (final) ✅ |
| **Total** | **13–16 REQ-IDs / 4 phases / 5 categories** (CARD-EVENT / CARD-EVIDENCE / CARD-ACTION / CARD-APPROVAL / RETROSPECTIVE + COMPAT / TRACE cross-axis) |

---

*Last updated: 2026-07-29 — v3.13 EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action / Approval) + 回溯闭环 (retrospective cycle) ✅ SHIPPED (4-phase ladder 03.13.0 → 03.13.3, 13+ REQ-IDs / 5 categories all closed, tag `v3.13` annotated, V310-COWORK-01 ✅ CLOSED). v3.12 EAASP Phase 4 — A2A Router + Event Room + multi-session 协调 ✅ SHIPPED 2026-07-27 @ 894639dd (4 phases, 13–16 REQ-IDs / 5 categories, tag `v3.12` pushed). v3.11 EAASP Phase 3 — production OPA backend + 5-stage approval chain ✅ SHIPPED 2026-07-27 (29/29 REQ-IDs, 4 phases, archived). v3.10 EAASP v2.0 platform-skeleton alignment ✅ SHIPPED 2026-07-26 (16 REQ-IDs, 4 phases, archived). v3.9 (route-catalog RBAC wiring + authorization auditor) ✅ SHIPPED 2026-07-26, archived to `.planning/milestones/v3.9-*`. v3.8 (grid-server multi-user login) ✅ SHIPPED 2026-07-24, archived to `.planning/milestones/v3.8-REQUIREMENTS.md`. v3.7 (实战可用性补全) ✅ SHIPPED 2026-07-23. v3.6 (Post-Activation Docs Sync) ✅ SHIPPED 2026-07-19. Grid 独立产品 Activation ✅ SHIPPED 2026-06-17 (8/8 phases A.0–A.8). v3.5/v3.4/v3.3/v3.2/v3.1/v3.0 ✅ CLOSED.*
