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

## v3.10 Requirements — EAASP v2.0 platform-skeleton alignment

**Defined:** 2026-07-26 (bootstrap)
**Goal:** Align `tools/eaasp-*` reference implementations with the canonical EAASP v2.0 platform contract (`docs/design/EAASP/EAASP-Design-Specification-v2.0.docx`) along three axes (MAT memory/manifest, PIPE orchestration pipes, VERIFY certifier conformance) without widening the existing `contract-v1.2.0` surface or adding new dependencies. Skeleton alignment is a precondition for the future EVOLUTION_PATH §三 Phase 3 (OPA approval chain) / Phase 4 (A2A Event Room) / Phase 5 (L5 Cowork UI) / Phase 6 (ecosystem expansion) work — it brings the reference implementations into section-by-section parity with the spec, so subsequent phase work can land without first having to re-derive the skeleton.

**Context (post-v3.9):** v3.9 closed the grid-server route-catalog RBAC gap (20/20 REQ-IDs, 49 targeted tests PASS, 134-route catalog). The next bottleneck — visible across `tools/eaasp-l2-memory-engine/`, `tools/eaasp-l3-governance/`, `tools/eaasp-l4-orchestration/`, `tools/eaasp-skill-registry/`, `tools/eaasp-mcp-orchestrator/`, `tools/eaasp-certifier/` — is that the reference implementations have drifted from the canonical EAASP v2.0 spec on three independent axes: (a) memory/manifest schema (MAT), (b) orchestration pipe topology (PIPE), and (c) certifier conformance surface (VERIFY). Without section-by-section alignment, the contract-v1.2.0 certifier (`tools/eaasp-certifier`) cannot certify future spec additions, and the reference implementations cannot serve as a clean substrate for Phase 3 OPA / Phase 4 A2A / Phase 5 L5 / Phase 6 ecosystem. v3.10 produces a section-by-section alignment matrix, then lands each axis in its own phase.

**REQ-IDs** use v3.10 numbering (MAT / PIPE / VERIFY / COMPAT / TRACE), 16 total, continue from v3.9 (no overlap with `CAT-*` / `AUD-*` / `RBAC-*` / `MODE-*` / `TEST-*` / `DOC-*`).

### MAT — Memory & Manifest skeleton alignment

- [x] **MAT-01**: A `tools/eaasp-spec-alignment/memory_manifest.md` document maps every L2 memory + skill manifest field in the EAASP v2.0 spec (§L2 Memory Engine, §Skill Manifest) to its current implementation site in `tools/eaasp-l2-memory-engine/` and `tools/eaasp-skill-registry/`. Each mapping carries `(spec_section, impl_path, impl_symbol, status ∈ {aligned, drift, missing})`. Drift and missing entries are filed as v3.10 follow-up items in DEFERRED_LEDGER.md.
- [x] **MAT-02**: The 7 L2 MCP tools (`search`, `read`, `write_file`, `write_anchor`, `confirm`, `list`, `delete`) declared in the spec are confirmed against `tools/eaasp-l2-memory-engine/src/mcp.rs`. Each tool's request/response shape is reconciled to the spec by section; mismatches (param names, return shapes, pagination semantics, time-decay filter) are listed in `memory_manifest.md` and patched in-place when patch is ≤10 LOC.
- [x] **MAT-03**: Skill manifest fields (`name`, `version`, `entrypoints`, `required_tools`, `mcp_servers`, `permissions`) in the spec are cross-referenced against `tools/eaasp-skill-registry/src/manifest.rs`. Any field that exists in spec but is not implemented is filed as `missing` in `memory_manifest.md`; spec-only fields are NOT silently dropped (D-12: skeleton alignment is honest about gaps).

### PIPE — Orchestration pipe topology alignment

- [x] **PIPE-01**: A `tools/eaasp-spec-alignment/pipe_topology.md` document maps the EAASP v2.0 spec's §L4 Orchestration pipe topology (input → context → governance → dispatch → result → audit → output, per EAASP_v2_0_EVOLUTION_PATH.md §三 3 管道 cross-reference) to its current implementation in `tools/eaasp-l4-orchestration/src/`. Each pipe stage is labeled `(spec_section, impl_path, impl_function, status ∈ {aligned, drift, missing})`.
- [x] **PIPE-02**: SSE event shape declared by spec (§L4 SSE Events) is compared against the `Event` enum in `tools/eaasp-l4-orchestration/src/event.rs`. Each event variant is reconciled by field; mismatches (event-name casing, payload field order, required-vs-optional) are listed in `pipe_topology.md` and patched when ≤10 LOC.
- [x] **PIPE-03**: L3 governance gate boundaries (risk classification input/output, decision enum, append-only log) are verified against `tools/eaasp-l3-governance/src/` per spec §L3. The 2026-07-23 v3.7.3 gate boundary (risk metadata defaults to `read`; L3 evaluates after tool resolution and before dispatch; request/final decisions append-only and surfaced via L4 events) is the baseline; v3.10 patches any spec-vs-impl drift without changing the gate semantics.
- [x] **PIPE-04**: L4 orchestration session lifecycle (create → run → resume → terminate) is reconciled against spec §L4 Session Lifecycle. The existing double-Terminate NO-OP semantics (ADR-V2-017 §2) is preserved verbatim; v3.10 only documents the alignment, does not change runtime behavior.

### VERIFY — Certifier conformance surface alignment

- [x] **VERIFY-01**: A `tools/eaasp-spec-alignment/certifier_surface.md` document maps each EAASP v2.0 spec assertion (every `### §N.M` assertion in `EAASP-Design-Specification-v2.0.docx`) to its current certifier coverage in `tools/eaasp-certifier/src/`. Each assertion carries `(spec_section, certifier_test_path, status ∈ {certified, not_certified, partial})`. `not_certified` entries above the `contract-v1.2.0` baseline are filed as deferred (D-13: no new contract surface in v3.10).
- [x] **VERIFY-02**: The 21 RPC surface (17 runtime + 4 hook per `proto/eaasp/runtime/v2/`) is verified end-to-end against `tools/eaasp-certifier` — every RPC has at least one PASS-path test and one XFAIL-path test (per Phase 3 sign-off 42 PASS / 22 XFAIL × 7 runtime baseline). The post-v3.10 certifier run must reproduce this 7-runtime green state (D-14).
- [x] **VERIFY-03**: A `make v3.10-spec-audit` target is added to the Makefile, running `cargo run -p eaasp-certifier -- spec-audit --report tools/eaasp-spec-alignment/REPORT.md` and producing a section-by-section delta table. The target exits 0 on aligned surface, exits 1 on any `drift` / `missing` / `not_certified` entry. CI gate ordering is `cargo check → make v3.10-spec-audit → cargo test` per the v3.9 pattern (D-03 carry-over).

### COMPAT — Contract + L1 substitutability guard

- [x] **COMPAT-01**: `proto/eaasp/runtime/v2/{common,runtime,hook}.proto` remain wire-compatible with `contract-v1.2.0`. No new RPC methods, no removed RPC methods, no breaking field-type changes in v3.10. Verified by `cargo test -p eaasp-certifier` PASS state pre and post each phase.
- [x] **COMPAT-02**: All 7 L1 runtimes (`grid-runtime` + claude-code / goose / nanobot / pydantic-ai / claw-code / ccb; `hermes` frozen per ADR-V2-017) continue to pass `contract-v1.2.0` certifier after each v3.10 phase. Verified by `make v2-phase3-e2e-rust` + per-runtime `make v2-phase3-e2e` runs. L1 substitutability guard (D-14) is the gate.
- [x] **COMPAT-03**: Shared-core rule (ADR-V2-023 P1) preserved across any v3.10 changes — `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品. Verified by the existing `test_rbac_engine_layer_is_leg_agnostic` + a new `test_v3_10_shared_core_unchanged` that snapshots `grid-engine::auth` + `grid-types::session` public API surface pre/post v3.10.

### TRACE — Spec traceability evidence

- [x] **TRACE-01**: `docs/status/PRODUCTION_USABILITY_2026-07-26.md` dated walkthrough: (1) `make v3.10-spec-audit` PASS on v3.10 baseline, (2) spec-audit FAIL demonstrably on a synthetic misalignment (drop one memory MCP tool from the catalog and re-run), (3) `make v2-phase3-e2e-rust` PASS for all 7 L1 runtimes post-v3.10, (4) `cargo check -p grid-server` PASS (v3.9 catalog regression guard). Reuses the v3.9 PRODUCTION_USABILITY_2026-07-25.md pattern.
- [x] **TRACE-02**: `tools/eaasp-spec-alignment/ALIGNMENT_MATRIX.md` cross-index: every EAASP v2.0 spec section (`### §N.M`) is listed with `(status, v3.10_phase, post_v3.10_owner)`. Gaps above the `contract-v1.2.0` baseline are explicitly listed as `deferred_to_v3.11+` with rationale, so the spec surface is honest about what is and isn't covered. Used as input to v3.11+ Phase 3 OPA / Phase 4 A2A / Phase 5 L5 planning.

## Future Requirements (deferred — explicit v3.10+ backlog)

- **Phase 3 production OPA approval chain** — pre-work blocked on v3.10 skeleton alignment; v3.11+ scope per `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md`.

## v3.11.0 Requirements — EAASP Phase 3 OPA sidecar infrastructure (D-19..D-22 locked)

**Context (post-v3.10):** v3.10 SHIPPED the EAASP v2.0 platform-skeleton alignment matrix. The V310-OPA-01 deferred entry (L3 production OPA/Rego backend) is the first concrete v3.11 deliverable. ADR-V2-034 (sidecar OPA on `127.0.0.1:18181`, in-repo Rego templates + atomic user bundles, fail-closed on OPA error) is now Accepted and is the deployment-topology anchor for the rest of v3.11.

**REQ-IDs** use v3.11 numbering (OPA-*, INSTALL-*, COMPAT-*). 5 REQ-IDs cover 03.11.0; 03.11.1..03.11.3 are scheduled in follow-up phases.

- [x] **OPA-01**: A `docs/design/EAASP/adrs/ADR-V2-034-opa-backend-deployment-topology.md` ADR is committed and `status: Accepted` in its YAML frontmatter; documents the sidecar topology, in-repo Rego templates, atomic user bundles, fail-closed failure mode, and references `EVOLUTION_PATH §三 Phase 3` and `v2.0 spec §2.4 + §15.9`.
- [x] **OPA-02**: A `scripts/eaasp-install-opa.sh` script downloads the official Open Policy Agent release binary for the host OS/arch, SHA256-verifies it against the official `sha256sums.txt`, and installs it to `third_party/opac/opa`. Fails closed on checksum mismatch, unsupported OS/arch, or GitHub API failure.
- [x] **INSTALL-01**: A `make opa-install` Makefile target invokes `scripts/eaasp-install-opa.sh`; a `make opa-clean` target removes the installed binary. Both are listed in `.PHONY`.
- [x] **COMPAT-01**: `third_party/` is added to `.gitignore` so the downloaded binary is never committed.
- [x] **COMPAT-02**: No shared crate (`grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge`) is touched. ADR-V2-023 P1 (shared-core rule) preserved. v3.9 route-catalog RBAC (134 routes) and v3.10 spec-audit gates continue to pass.
- [x] **DEFER-LEDGER-CLOSE-01**: `V310-OPA-01` in `docs/design/EAASP/DEFERRED_LEDGER.md` is moved from `📦 deferred_to_v3.11+` to `✅ CLOSED 2026-07-26 (v3.11.0 lift ADR-V2-034 Accepted + sidecar topology + make opa-install)`.

## v3.11.1 Requirements — L3 OPA backend adapter + Rego templates

**Defined:** 2026-07-26 (v3.11.0 already shipped)
**Goal:** Land the production OPA adapter that turns `tools/eaasp-l3-governance/` from an in-process decision matrix into an OPA-calling governance layer. ADR-V2-034 §4 froze the contract; this phase implements it. The adapter sits behind a flag (`opa_enabled`) so existing in-process behavior is preserved as the dev/test path while the OPA sidecar is the production path.

**REQ-IDs** use v3.11.1 numbering (`OPA-BACKEND-*`, `REGO-*`, `FAIL-CLOSED-*`, `DISABLED-*`). 9 REQ-IDs cover this phase; 03.11.2 / 03.11.3 remain future scope.

### OPA-BACKEND — Production adapter

- [x] **OPA-BACKEND-01**: An `OPABackend` adapter lives at `tools/eaasp-l3-governance/src/eaasp_l3_governance/opa_backend.py`. Its public surface (`OPABackend`, `OPADecision`, `OPAConfig`, `require_env`, `parse_timeout_seconds`, `normalize_base_url`) is importable from the package root. The `OPABackend.evaluate(request)` coroutine POSTs to `/{base_url}/v1/data/governance/decision` with `{"input": request}` as the JSON body and decodes the response into a frozen `OPADecision` dataclass.
- [x] **OPA-BACKEND-02**: `OPABackend.evaluate()` returns an `OPADecision` that ALWAYS carries stable contract fields (`allow: bool`, `decision: Literal["allow", "approval", "deny"]`, `reason: str`, `obligations: list[str]`, plus `infra_unavailable: bool`, `cause: str | None`, `raw: dict[str, Any] | None`). A bare OPA top-level body (no `result` wrapper) is also accepted; the parser verifies that exactly one of `result` / top-level satisfies the shape contract.
- [x] **OPA-BACKEND-03**: `OPABackend.from_env()` (ADR-V2-028 strict-by-default) reads `L3_OPA_URL`, `L3_OPA_TIMEOUT_SECONDS`, `L3_OPA_BUNDLE_DIR` from the environment. Missing or unparseable values raise `RuntimeError` with the env-var name in the message; there is no silent fallback to in-process.
- [x] **OPA-BACKEND-04**: `PolicyEngine.evaluate_with_opa()` (new method on `tools/eaasp-l3-governance/src/eaasp_l3_governance/policy_engine.py`) routes through the injected `OPABackend` when `opa_enabled=True`. The in-process `evaluate_gate()` path is unchanged. OPA's 3-state decision (`allow` / `approval` / `deny`) maps into the existing 4-state audit shape (`allow` / `gate_request` / `deny`); the OPA `reason` is preserved in the rationale so the audit row is pivotable on it.

### REGO — In-repo Rego bundle

- [x] **REGO-01**: `tools/eaasp-l3-governance/policies/governance.rego` exists with `package governance; import rego.v1` and implements deny-always-wins (spec §15.9), risk classification (spec §6.1), and the 3-state decision contract (spec §6.9 + §6.10). The bundle cites ADR-V2-034 in its header. Sample input data lives at `tools/eaasp-l3-governance/policies/data.json`.
- [x] **REGO-02**: The Rego bundle's response envelope matches the `OPADecision` contract: `{allow, decision, reason, obligations}`. Field names and the decision enum (`"allow"` / `"approval"` / `"deny"`) DO NOT change without bumping `OPABackend._parse_opa_response` (frozen by ADR-V2-034 §Decision item 4).

### FAIL-CLOSED — Fail-closed contract

- [x] **FAIL-CLOSED-01**: Five failure modes (connection-refused, timeout, non-2xx HTTP, parse error, missing/extra fields) all return an `OPADecision` with `decision="deny"`, `allow=False`, `infra_unavailable=True`, a stable `cause` identifier (`opa_connection_refused` / `opa_timeout` / `opa_non_2xx` / `opa_parse_error` / `opa_response_missing_field` / `opa_bundle_not_found`), and a rationale that includes the cause so the audit row can be filtered by cause in postmortem.
- [x] **FAIL-CLOSED-02**: `PolicyEngine.evaluate_with_opa()` persists the fail-closed audit row (decision=`deny`) regardless of cause and emits a structured log carrying `session_id` + `hook_id` + `cause`. The request ledger is append-only — no reordering, no replacement.

### DISABLED — OPA-disabled integration

- [x] **DISABLED-01**: When `L3_OPA_ENABLED` is unset / falsy, the `/v1/evaluate` endpoint routes through `evaluate_gate()` (the in-process decision matrix) without instantiating an `OPABackend`. The end-to-end integration test calls the API surface and asserts `backend == "in_process"`, with a 4-test hermetic coverage that verifies validation guards and `HookNotFoundError → 404` behavior.

---

## v3.11.2 Requirements — 5-stage approval chain state machine

**Defined:** 2026-07-27 (v3.11.0 + v3.11.1 SHIPPED)
**Goal:** Implement the EAASP spec §6.9–6.10 Plan → Check → Draft → Approve → Execute 5-stage approval state machine on top of the L3 OPA backend (v3.11.1) and the L4 event stream. Each stage persists one row in the append-only `governance_decisions` ledger (new nullable `stage` column) and emits a `governance.approval.<stage>` SSE event. Deny in any stage short-circuits remaining stages; the Approve stage pauses for human-in-the-loop. Closes `V310-APPROVAL-01`.

**REQ-IDs** use v3.11.2 numbering (`STAGE-*`, `SSE-*`, `AUDIT-*`, `DENY-*`). 14 REQ-IDs cover this phase; 03.11.3 live walkthrough remains future scope.

### STAGE — State machine contract

- [x] **STAGE-01**: `APPROVAL_STAGE_PLAN` / `APPROVAL_STAGE_CHECK` / `APPROVAL_STAGE_DRAFT` / `APPROVAL_STAGE_APPROVE` / `APPROVAL_STAGE_EXECUTE` are exported from `tools/eaasp-l3-governance/src/eaasp_l3_governance/approval_state_machine.py` and form the canonical `STAGE_ORDER` tuple (`("plan", "check", "draft", "approve", "execute")`).
- [x] **STAGE-02**: `ApprovalStateMachine.__init__(policy_input, session_id, hook_id, caller_principal, audit_store, event_sink=None)` validates session_id / hook_id / caller_principal / policy_input BEFORE any DB open (audit §6 contract).
- [x] **STAGE-03**: `ApprovalStateMachine.run(evaluator)` iterates `STAGE_ORDER` in order, invoking the supplied evaluator per stage. Returns an `ApprovalChainResult` with `stages_completed`, `final_decision` (`approve` / `deny` / `await_human`), `final_reason`, and a `records` list of `StageRecord`.
- [x] **STAGE-04**: On full success (all 5 stages allow without deny or human pause), `final_decision == "approve"` and `stages_completed == 5`. Five `StageRecord`s are produced, one per stage.
- [x] **STAGE-05**: `ApprovalStateMachine.resume_with_human_decision(human_decision, human_reason, evidence_refs)` accepts `human_decision in {"allow", "deny"}`. On allow, runs the execute stage and persists an `await_human` audit row carrying the human's reason; on deny, terminates without an execute row.

### SSE — L4 governance.approval.* events

- [x] **SSE-01**: `SessionEventStream.emit_governance_approval_plan(...)` writes a `governance.approval.plan` event with payload `{stage, decision_id, request_id, session_id, hook_id, decision, reason, caller_principal, evidence_refs, ts}`.
- [x] **SSE-02**: `SessionEventStream.emit_governance_approval_check(...)` writes a `governance.approval.check` event with the same canonical payload shape.
- [x] **SSE-03**: `SessionEventStream.emit_governance_approval_draft(...)` writes a `governance.approval.draft` event with the same canonical payload shape.
- [x] **SSE-04**: `SessionEventStream.emit_governance_approval_approve(...)` writes a `governance.approval.approve` event with the same canonical payload shape. This is the human-in-the-loop pause stage.
- [x] **SSE-05**: `SessionEventStream.emit_governance_approval_execute(...)` writes a `governance.approval.execute` event with the same canonical payload shape.

### AUDIT — Append-only ledger extension

- [x] **AUDIT-01**: `audit.py`'s `record_governance_decision(...)` accepts an optional `stage` kwarg (default `None`) that is persisted in the new `governance_decisions.stage` column. v3.11.0 / v3.11.1 rows are preserved (column NULL by default).
- [x] **AUDIT-02**: `governance_decisions.stage` column is added to the schema via an idempotent `ALTER TABLE` migration. A partial index `idx_governance_decisions_stage` is created for stage-routed queries.

### DENY — Deny-always-wins

- [x] **DENY-01**: When a stage evaluator returns `decision == "deny"`, `ApprovalStateMachine.run()` short-circuits the remaining stages: no further audit rows are written and no further SSE events are emitted. `final_decision == "deny"`, `final_reason` carries the denier's reason.
- [x] **DENY-02**: When `resume_with_human_decision` is called with `human_decision == "deny"`, the execute stage row is NOT persisted; the chain terminates with `final_decision == "deny"` and the human's reason in `final_reason`.

### v3.11.2 Traceability

| Phase | REQ-IDs |
|---|---|
| **03.11.1 L3 OPA backend adapter + Rego templates** | OPA-BACKEND-01, OPA-BACKEND-02, OPA-BACKEND-03, OPA-BACKEND-04, REGO-01, REGO-02, FAIL-CLOSED-01, FAIL-CLOSED-02, DISABLED-01 |
| **Total** | **9 REQ-IDs / 1 phase / 4 categories** |

### v3.11.0 Traceability

| Phase | REQ-IDs |
|---|---|
| **03.11.0 OPA sidecar infrastructure** | OPA-01, OPA-02, INSTALL-01, COMPAT-01, COMPAT-02, DEFER-LEDGER-CLOSE-01 |
| **03.11.1 L3 OPA backend adapter** | OPA-BACKEND-01..04, REGO-01..02, FAIL-CLOSED-01..02, DISABLED-01 |
| **03.11.2 5-stage approval state machine** ✅ SHIPPED 2026-07-27 | STAGE-01..05, SSE-01..05, AUDIT-01..02, DENY-01..02 |
| **03.11.3 single-point live walkthrough** (next) | `make opa-install` + `make dev-eaasp` + `threshold-calibration` skill + dated production evidence |
- **Phase 4 A2A / Event Room** — v3.12+ scope.
- **Phase 5 L5 Cowork UI** — v3.13+ scope.
- **Phase 6 ecosystem expansion** — v3.14+ scope.
- **`web-platform/` Quality 7.5→9.0** — separate milestone (carried forward from v3.9 OOS).
- **`grid-desktop` Quality 6.5→9.0** — separate milestone (carried forward from v3.9 OOS).
- **`grid-platform` route catalog audit** — separate milestone; v3.10 only audits `tools/eaasp-*` and `grid-engine` shared core (carried forward from v3.9 OOS).

## Out of Scope (v3.10)

- **Phase 3 production OPA backend** — only the in-process `PolicyEngine` from 3.7.3 is in scope; OPA sidecar is a separate item per `docs/design/EAASP/PHASE_3_DESIGN.md`.
- **Phase 4 A2A / Phase 5 L5 Cowork / Phase 6 ecosystem** — untouched; deferred to v3.11+.
- **New EAASP-spec sections beyond `contract-v1.2.0`** — v3.10 surfaces the gap, does not implement it (D-13).
- **Proto contract surface widening** — v3.10 only reconciles to existing 21 RPC surface; new RPCs are deferred (D-13).
- **Schema migration for L2 memory / skill manifest** — v3.10 reconciles existing fields only; new fields are deferred (D-16).
- **L1 runtime additions or substitutions** — the 7-runtime matrix is frozen for v3.10 (D-14).

## Locked Decisions (from v3.10 discussion — non-negotiable)

| # | Decision | Source |
|---|----------|--------|
| D-11 | **EAASP v2.0 platform-skeleton alignment scope.** v3.10 aligns `tools/eaasp-*` reference implementations with the canonical EAASP v2.0 platform contract (`docs/design/EAASP/EAASP-Design-Specification-v2.0.docx`) along three axes (MAT / PIPE / VERIFY), without adding new dependencies or widening the existing `contract-v1.2.0` surface. | user directive |
| D-12 | **Three-axis skeleton mapping.** MAT (memory/manifest), PIPE (orchestration pipes), VERIFY (certifier conformance). Each axis has its own 03.10.x phase and Phase #1 deliverable proves the skeleton fits the spec (memory_manifest.md / pipe_topology.md / certifier_surface.md). | scope discipline |
| D-13 | **Backward-compatible contract surface.** Existing `proto/eaasp/runtime/v2/` (21 RPC: 17 runtime + 4 hook) and `contract-v1.2.0` tests must remain green; no proto-breaking changes in v3.10. New spec sections are surfaced via `certifier_surface.md` as `not_certified` and deferred. | user directive |
| D-14 | **L1 substitutability guard preserved.** All 7 L1 runtimes (`grid-runtime` + 6 comparison: claude-code / goose / nanobot / pydantic-ai / claw-code / ccb; `hermes` frozen per ADR-V2-017) must continue to pass contract v1.2.0 certifier after each v3.10 phase. Verified by `make v2-phase3-e2e-rust`. | ADR-V2-023 P1 |
| D-15 | **No new external crate dependency** (D-07 carry-over); same rule for Python (no new PyPI deps beyond existing `uv` lockfile). v3.10 uses existing `grid-types` / `grid-engine` / `eaasp-certifier` / `eaasp-l2-memory-engine` / `eaasp-l3-governance` / `eaasp-l4-orchestration` / `eaasp-skill-registry` / `eaasp-mcp-orchestrator` toolchain. | CLAUDE.md §Constraints |
| D-16 | **No schema migration** (D-08 carry-over). v3.10 skeleton alignment is Rust + Python source + spec documentation only. No DB migration, no proto schema migration. | CLAUDE.md §Constraints |
| D-17 | **Shared-core rule (ADR-V2-023 P1, D-09 carry-over) preserved.** Any change to `grid-types` / `grid-engine` / `grid-sandbox` / `grid-hook-bridge` must remain leg-agnostic across engine 接入面 (EAASP) and Grid 独立产品. Verified by `test_v3_10_shared_core_unchanged` (new in COMPAT-03). | ADR-V2-023 P1 |
| D-18 | **Phase ladder 03.10.0 → 03.10.1 → 03.10.2 → 03.10.3 (or merge to 3 phases if scope allows).** 03.10.0 = skeleton audit + alignment matrix (foundation; every later phase consumes the matrix); 03.10.1 = MAT axis; 03.10.2 = PIPE axis; 03.10.3 = VERIFY axis. COMPAT + TRACE run cross-axis (03.10.1 / 03.10.2 / 03.10.3 each gate on COMPAT-01..03 and emit a TRACE-01 / TRACE-02 update). | user directive |

## Traceability (filled by roadmapper)

| Phase | REQ-IDs |
|-------|---------|
| **03.10.0** Skeleton audit + alignment matrix | MAT-01, PIPE-01, VERIFY-01, TRACE-02 |
| **03.10.1** MAT axis | MAT-02, MAT-03, COMPAT-01, COMPAT-02, COMPAT-03, TRACE-01 |
| **03.10.2** PIPE axis | PIPE-02, PIPE-03, PIPE-04, COMPAT-01, COMPAT-02, COMPAT-03, TRACE-01 |
| **03.10.3** VERIFY axis | PIPE-01 (final wiring), VERIFY-02, VERIFY-03, COMPAT-01, COMPAT-02, COMPAT-03, TRACE-01, TRACE-02 (final) |
| **Total** | **16 REQ-IDs / 4 phases / 5 categories** |

---

*Last updated: 2026-07-26 — v3.11.1 L3 OPA backend adapter + Rego templates SHIPPED (9/9 REQ-IDs / 4 categories / 57 targeted tests PASS). v3.11.0 OPA sidecar infrastructure SHIPPED 2026-07-26 (6/6 REQ-IDs, archived to `.planning/milestones/v3.11.0-*`). v3.10 EAASP v2.0 platform-skeleton alignment SHIPPED 2026-07-26 (16 REQ-IDs / 5 categories / locked decisions D-11..D-18). v3.9 (route-catalog RBAC wiring + authorization auditor) SHIPPED 2026-07-26 (20/20 REQ-IDs, archived to `.planning/milestones/v3.9-*`). v3.8 (grid-server multi-user login) SHIPPED 2026-07-24, archived to `.planning/milestones/v3.8-REQUIREMENTS.md`. Pre-v3.8 milestones archived under `.planning/milestones/v3.{X}-REQUIREMENTS.md`.*