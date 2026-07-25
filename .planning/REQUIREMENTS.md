# Requirements: Grid

**Defined:** 2026-07-25
**Milestone:** v3.9 (route-catalog RBAC wiring + authorization auditor)
**Core Value:** Grid 作为 substitutable L1 runtime,通过 gRPC contract 被 EAASP L2-L4 调用,且任何符合 `contract-v1.2.0` 的对比 runtime 都能替换它。

> **Read first.** This file is the **active** requirements ledger. v3.8 (2026-07-24) and earlier milestones are archived to `.planning/milestones/v3.{X}-REQUIREMENTS.md`. Locked decisions from the v3.9 discussion are NOT negotiated below — they are normative for this milestone.

---

## v3.9 Requirements

**Goal:** Make `grid-server` route-by-route authorization **explicitly declared and statically enforced**: every non-public business HTTP route is annotated with the `Action` it requires, every public route is named on an explicit allowlist, and a CI auditor fails any route that is neither. The Action enum is extended (and the `Role × Action` matrix updated) whenever the catalog reveals an action that the current 7-Action vocabulary does not express. `AuthMode::None/ApiKey` semantics are not changed; `AuthMode::Full` runs full RBAC.

**Context (post-v3.8):** v3.8 demonstrated `requires(Action)` on three representative routes and shipped JWT + RBAC + tenant isolation. The remaining ~127 endpoints in `crates/grid-server/src/api/mod.rs` + `crates/grid-server/src/router.rs` have no `requires(...)` annotation. A new route can quietly bypass RBAC without detection. v3.9 closes that gap by making "every route has either an Action or a public marker" a CI-enforced invariant.

**REQ-IDs** use v3.9 numbering, continue from v3.8 (no `RBAC-05..` duplicate).

### CAT — Route Catalog & Action extension

- [ ] **CAT-01**: A `RouteCatalog` source of truth exists at `crates/grid-server/src/rbac/catalog.rs` listing every business HTTP route registered by `api::routes()` + `build_router()`, with each entry carrying `(method, path, route_kind)` where `route_kind ∈ { Requires(Action), Public }`. The router is rewritten so it builds its route table from this catalog (or, where the rewrite is too invasive, the catalog is generated from the router via a `build_catalog()` function that the auditor consumes).
- [ ] **CAT-02**: Public routes are explicitly enumerated on an `allowlist` constant (e.g. `/api/health`, `/api/health/live`, plus the login path that is invoked before the JWT is issued). Anything not on the allowlist AND not decorated with `Requires(Action)` is a CI failure.
- [ ] **CAT-03**: When the auditor surfaces a route whose semantic action is not expressible by the existing 7-Action `Action` enum (`Read`, `CreateSession`, `RunAgent`, `ManageMcp`, `ManageSkills`, `ManageUsers`, `ManageBilling`), the team is allowed to ADD new variants to the enum (e.g. `ManageHooks`, `ManageMemories`, `ManageAudit`, `ManageConfig`, `ManageSecrets`, `ManageSandbox`, `ManageScheduler`) and to update `Role::can(Action)` in `crates/grid-engine/src/auth/roles.rs`. Adding variants is **not** a scope-reduction — full Role × Action matrix regeneration is part of the deliverable.
- [ ] **CAT-04**: The `RouteCatalog` is `pub` so the auditor (CAT-05) and tests (CAT-06) can consume it. Tests can assert "every endpoint in `api::routes()` has an entry in the catalog."

### AUD — Static route auditor

- [ ] **AUD-01**: A static auditor binary or test (`cargo run -p grid-server --bin route-auditor` OR `cargo test -p grid-server --test route_auditor`) takes the `RouteCatalog` and walks the routes registered by `build_router()`. For each route it asserts: (a) either `route_kind == Public` AND the path is on the `allowlist`, OR (b) `route_kind == Requires(Action)` AND the action is exercisable by at least one Role. Mismatch → non-zero exit code with a clear, human-readable report naming the offending route.
- [ ] **AUD-02**: The auditor is wired into `.github/workflows/ci.yml` (or the existing CI pipeline) under a job that runs after `cargo check --workspace` and before `cargo test`. The auditor PASSES on the v3.9 catalog and exits 0; on any unprotected route it exits 1 with the missing-route report.
- [ ] **AUD-03**: The auditor integrates with the existing `cargo test -p grid-server` matrix and is also runnable as a standalone `make` target (e.g. `make rbac-audit`) so a developer can run it locally before pushing.

### RBAC — Full business-route wiring

- [ ] **RBAC-05**: Every non-public business HTTP route in `api::routes()` is annotated with `Requires(Action)` via `axum::middleware::from_fn_with_state(...)` or the existing `require_action_middleware(Action)` wrapper. The set of routes affected is the union of all `.route(...)` calls in `crates/grid-server/src/api/{admin,agents,audit,auth,autonomous,budget,collaboration,config,context,eval_sessions,events,executions,hooks,knowledge_graph,mcp_logs,mcp_servers,mcp_tools,memories,metering,metrics,providers,sandbox,scheduler,secrets,security,sessions,skills,sync,tasks,tools,user_context}.rs` + `mod.rs` + `router.rs`.
- [ ] **RBAC-06**: The `require_action_middleware` path used in v3.8.2 (which reads `Extension<JwtClaims>` and consults `Role::can(action)`) is reused unchanged. The v3.9 wiring is purely additive — every annotated route hits the same middleware. `AuthMode::None/ApiKey` requests continue to bypass the JWT path and use the existing `UserContext::has_permission` flow (D-04 below).
- [ ] **RBAC-07**: `Owner` always succeeds on every annotated route (RBAC-04 invariant preserved); `Viewer` cannot call any non-Read annotated route; `User` can call Read + CreateSession + RunAgent; `Admin` extends to ManageMcp / ManageSkills / ManageUsers. The specific role-per-action policy is regenerated in `Role::can(Action)` to fill in the new Action variants.
- [ ] **RBAC-08**: The auditor test `rbac_05_full_route_catalog_annotated` enumerates every route in `api::routes()` and asserts each has an entry in the `RouteCatalog`; the test fails with a list of unannotated routes if any drift appears.

### MODE — AuthMode compatibility

- [ ] **MODE-01**: `AuthMode::None` — every existing route remains reachable without auth. The `public` allowlist and the `requires(Action)` annotations do NOT change `AuthMode::None` behavior. Tests: `cargo test -p grid-server --features grid-server/testing --test test_auth_modes None` continues to PASS (regression).
- [ ] **MODE-02**: `AuthMode::ApiKey` — every existing route remains reachable with a valid `X-API-Key`. The `requires(Action)` annotations apply when the request has `Extension<JwtClaims>` (it does not in ApiKey mode). Tests: `cargo test -p grid-server --features grid-server/testing --test test_auth_modes ApiKey` continues to PASS (regression).
- [ ] **MODE-03**: `AuthMode::Full` — every annotated route runs the `require_action_middleware` JWT-aware path. Missing/invalid JWT → 401. Insufficient role → 403. `Viewer` JWT calling a non-Read annotated route → 403. The 8/8 `test_auth_modes test_full` cases continue to PASS plus the new `RBAC-05..08` cases.

### TEST — Hermetic validation

- [ ] **TEST-07**: The auditor (AUD-01) is exercised by a self-test: a test fixture builds a fake `Router` with one deliberately unprotected route and asserts the auditor exits 1 with the expected message. This guards against the auditor silently vacuously-passing.
- [ ] **TEST-08**: Hermetic integration test that walks every annotated route in `api::routes()`; for each route, mints a JWT for each `Role` and asserts the expected status code (200/403/401). The matrix is small (`7 roles × ~130 routes` is bounded by the canonical Role set: Viewer/User/Admin/Owner × 130 ≈ 520 cases; we keep it to "at least one positive case per route + one negative case per Read route when called as Viewer").
- [ ] **TEST-09**: Regression sweep across v3.7 + v3.8 baseline tests (`test_auth_modes` 8/8, `multi_user_jwt` 9/9, `multi_user_auth_endpoints` 7/7, `multi_user_rbac_tenant` 10/10) — every test PASS in `GRID_MODE=multi_user` and `GRID_MODE=single_user` modes. ASK before running the full v3.7 175-test baseline per `feedback_no_full_tests`.

### DOC — Catalog + auditor operator docs

- [ ] **DOC-04**: `USER_GUIDE.md` §12 catalogue-auditor mode (what `make rbac-audit` does, how to read its report, how to add a new route, how to add a new Action variant). Reuses the v3.8 USER_GUIDE §11 multi-user section pattern.
- [ ] **DOC-05**: `PRODUCTION_USABILITY_2026-07-25.md` dated walkthrough: (1) auditor PASS on v3.9 catalog, (2) auditor FAIL demonstrably on a synthetic unplugged route, (3) RBAC matrix regenerated for new Actions, (4) all `AuthMode` regressions observed to PASS.
- [ ] **DOC-06**: `ROLE_ACTION_MATRIX_2026-07-25.md` reference table — the full regenerated `Role × Action` matrix, including any new Action variants added in CAT-03. Mirrors the existing `roles.rs:69` matrix but updated.

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

*Last updated: 2026-07-25 — v3.9 (route-catalog RBAC wiring + authorization auditor) bootstrapped. v3.8 (grid-server multi-user login) SHIPPED 2026-07-24, archived to `.planning/milestones/v3.8-REQUIREMENTS.md`. Pre-v3.8 milestones archived under `.planning/milestones/v3.{X}-REQUIREMENTS.md`.*
