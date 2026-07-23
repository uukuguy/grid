# Grid — Roadmap

> **Latest shipped milestone:** v3.7 实战可用性补全 (Production-Usability Closure) ✅ 2026-07-23
> **Active milestone:** v3.8 grid-server multi-user login (Tenant + RBAC + JWT) 🟡 STARTED 2026-07-23
> **Archive:** `milestones/v3.4-ROADMAP.md`, `milestones/v3.5-ROADMAP.md`, `milestones/v3.7-ROADMAP.md`
> **Current project root:** details in `.planning/PROJECT.md` §Current Milestone + `.planning/REQUIREMENTS.md` v3.8 section.

## Milestones

- ✅ **v3.0 Phase 4 — Product Scope Decision** — (shipped 2026-04-28, ADR-V2-024 Accepted)
- ✅ **v3.1 Phase 5 — Engine Hardening** — SHIPPED 2026-05-22 (6 phases, 23 REQ-IDs, 6 ADRs)
- ✅ **v3.2 Phase 6 — Tech-Debt Triage** — SHIPPED 2026-05-26 (3 phases, 6 REQ-IDs)
- ✅ **v3.3 Phase 7 — Engine + Platform Debt Sweep** — SHIPPED 2026-06-07 (Phase 7.3 L3 RBAC, 8/8 REQ-IDs)
- ✅ **v3.4 Phase 7/8 — Full INBOX Drain** — SHIPPED 2026-06-16 (10 phases, 67 REQ-IDs, 2 ADRs)
- ✅ **v3.5 Phase 9 — Debt Finalization** — SHIPPED 2026-06-16 (3 phases, LEDGER 100% CLOSED)
- ✅ **Grid 独立产品 Activation** — SHIPPED 2026-06-17 (8/8 phases A.0–A.8; repo renamed `grid-sandbox` → `grid`)
- ✅ **v3.6 Post-Activation Docs Sync** — SHIPPED 2026-07-19 (7 docs commits @ a29f626, 46/46 UAT PASS)
- ✅ **v3.7 实战可用性补全 (Production-Usability Closure)** — SHIPPED 2026-07-23 (3 phases: grid-cli / web/ / EAASP 本地仿真; 3.7.4 grid-server multi-user deferred to v3.8). 175/175 tests PASS, 50 commits, 76 files. Full details: `.planning/milestones/v3.7-ROADMAP.md` + `.planning/MILESTONES.md`
- 🟡 **v3.8 grid-server multi-user login (Tenant + RBAC + JWT)** — STARTED 2026-07-23 (climb); closes v3.7.4 user-deferral (RBAC + JWT tenant scoping + cross-user session isolation). 4 phases planned (3.8.0 → 3.8.3), 21 REQ-IDs in 6 categories. Details: `.planning/PROJECT.md` §Current Milestone + `.planning/REQUIREMENTS.md` v3.8 section.

---

## Milestone: v3.8 grid-server multi-user login (Tenant + RBAC + JWT) 🟡 STARTED 2026-07-23

**Goal:** Take `grid-server` from `AuthMode::ApiKey` + `TenantContext::for_single_user` to a real multi-user tenancy: JWT-issued sessions carrying `tenant_id` + `role` claims, RBAC enforced at the route handler layer, cross-user session isolation. Auth surface stays as **Grid 独立产品** (per ADR-V2-024 双轴 framework — engine 接入面 uses EAASP's own auth, not Grid); types live in `grid-engine` and are shared but the JWT issuance/refresh/logout endpoints live only in `grid-server`.

**Context:** Auth primitives already exist: `AuthMode { None, ApiKey, Full }`, `Role { Viewer, User, Admin, Owner }`, `Action { Read, CreateSession, RunAgent, ManageMcp, ManageSkills, ManageUsers, ManageBilling }`, `Permission { Read, Write, Admin }`, complete `Role × Action` matrix in `crates/grid-engine/src/auth/roles.rs`. v3.8 wires enforcement and ships endpoints.

**Scope ladder (per v3.7 proven pattern — discuss → research → patterns → plan → plan-checker → execute → verify, batched into 4 phases):**

| # | Phase | Goal | Requirements | Success criteria |
|---|-------|------|--------------|------------------|
| **03.8.0** | JWT primitive + AuthMode::Full path | Mint + verify JWT with `tenant_id`/`user_id`/`role` claims; wire through existing middleware | AUTH-01, AUTH-04, AUTH-05 | hermetic mint+verify test, tampered signature → 401, missing claim → 401 |
| **03.8.1** | Login + refresh + logout endpoints + audit | `POST /auth/login` + `/auth/refresh` + `/auth/logout`; token blacklist; audit stamping | AUTH-02, AUTH-03, AUDIT-01 | 3 hermetic integration tests, audit rows carry tenant_id |
| **03.8.2** | RBAC route-layer enforcement + TenantContext::for_multi_user | `requires(Action)` middleware; cross-tenant scope enforcement | RBAC-01..04, TENANT-01..03, SESSION-01..03 | 6 hermetic tests (role escalation, cross-tenant block, list scoping, concurrent isolation, etc.) |
| **03.8.3** | Docs + UAT walkthrough + regression guard | USER_GUIDE §11, env-var reference, dated walkthrough, regression sweep | DOC-01..03, TEST-05, TEST-06 | 5/5 UAT, all v3.7 single-user tests still PASS in `GRID_MODE=single_user` |

### Why this ladder

- **03.8.0 (foundation)** must come first — every later phase depends on JWT verification working
- **03.8.1 (endpoints)** — surfaces the auth surface to clients; depends on 03.8.0
- **03.8.2 (RBAC + isolation)** — depends on 03.8.1 (because enforcement reads `req.extensions().get::<Claims>()` set by 03.8.1 middleware)
- **03.8.3 (docs + UAT + regression)** — final; writes dated evidence and verifies the single-user mode path is untouched

### Out of scope (deferred to v3.9+)

- **SSO / SAML / OIDC** — JWT + local creds only this milestone
- **`web-platform/` multi-tenant UI** wiring — separate milestone
- **`grid-desktop` 6.5→9.0** — untouched
- **`grid-platform` Quality 9.0 push** — already 9.0+ per v3.7 audit, no scope here
- **EAASP Phase 3 production OPA / Phase 4 A2A / Phase 5 L5 / Phase 6 ecosystem** — untouched
- **OAuth2 Authorization Code / PKCE** — JWT-only this milestone

### Risks & guards

- **R-1: Single-user regression** — `GRID_MODE=multi_user` opt-in; default = `single_user`; existing 175/175 tests from v3.7 must still PASS
- **R-2: `grid-engine` shared-core bleed** — per ADR-V2-023 P1; only ADD to `AuthConfig` (new `multi_user_tenant_ids` field); never delete or rename existing fields
- **R-3: JWT secret hardcoding** — `GRID_JWT_SECRET` fail-fast per ADR-V2-028 strict-by-default
- **R-4: Cross-tenant data leak** — every handler that reads a resource by id MUST use `OwnedResource::fetch(tenant_id, id)`; covered by `requires(Read)` middleware that injects `Claims`; verified in 03.8.2 isolated tests

### Shared core rule (ADR-V2-023 P1, retained)

Changes to `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` must work for both engine 接入面 (EAASP) and Grid 独立产品. v3.8 only ADDs to `grid-engine::auth::AuthConfig`; does not break engine-facing path.

---

## Milestone: Grid 独立产品 Activation ✅ SHIPPED

---

## Milestone: Grid 独立产品 Activation ✅ SHIPPED

**Goal:** Activate the dormant Grid independent product leg per ADR-V2-024. All technical debt cleared (DEFERRED_LEDGER.md 100% ✅ CLOSED). Shift from debt-sweep mode to product-building mode.

**Context:** Grid has been built primarily through its engine 接入面 (EAASP integration). The independent product crates (`grid-server`, `grid-platform`, `grid-desktop`, `web/`, `web-platform/`, `grid-eval`) exist but are dormant — scaffolding or partially-featured. The engine layer is production-ready. Now activate the product surface.

**Activation targets (priority-ordered per ADR-V2-024 Open Item #3):**

| Crate/App | Current State | Score | Activation Needed |
|-----------|--------------|-------|-------------------|
| **grid-cli** | 16 commands, full TUI, streaming, 140+ tests | 8/10 | Eval bridge stubs, MCP logs, config persist |
| **web/** (single-user UI) | 8 tabs, WS streaming, Markdown, 20k LOC | 7/10 | Remove mocks, standardize errors, add tests, sidebar |
| **grid-server** | ~130 endpoints, HMAC/JWT auth, WS protocol | 6/10 | Wire RBAC, fix ApiError, budget, context, hot-reload |
| **grid-platform** | JWT auth, tenant isolation, 25 routes | 6/10 | Tests, rate limiting, proper errors |
| **grid-eval** | 8 scorers, 12 suites, multi-model compare | 7/10 | Web UI, CI, parallel runner |
| **grid-desktop** | Tauri 2 shell, tray, 6 IPC | 3/10 | Agent/session IPC, asset bundling |
| **web-platform/** (multi-tenant UI) | Auth layer, basic chat, no Markdown | 3/10 | Chat history, Markdown, ErrorBoundary, dashboard fix |

**Shared core rule (ADR-V2-023 P1):** changes to `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` must work for both engine 接入面 and Grid independent product.

### Phase Plan (refined from A.0 audit)

#### Wave 1: Single-User Workbench (priority targets per ADR-V2-024)

- [x] **Phase A.1: grid-server Hardening** — Wire RBAC middleware to all routes, replace ad-hoc error tuples with `ApiError`, fix budget endpoint to read real usage, fix context snapshot/zones to read live session, make CORS/log_level hot-reload effective, remove deprecated `/ws` legacy path. *8 P1 gaps, 3-4 plans.*
- [x] **Phase A.2: web/ Production Polish** — Remove MCP mock fallbacks, standardize error handling (toast everywhere), add Vitest + critical-path tests, replace `window.__GRID_TOKEN` with config-based token, add sidebar + settings. *7 P2 gaps, 3-4 plans.*
- [x] **Phase A.3: grid-cli Final Polish** — Implement eval bridge (connect CLI eval commands to grid-eval library), MCP live log streaming, `config set` persistence, doctor `--repair` for all 10 checks. *4 P2/P3 gaps, 2 plans.*

#### Wave 2: Multi-Tenant Platform

- [x] **Phase A.4: Cross-Cutting Foundation** — Merge web/ and web-platform/ design system (shared ApiClient, components, theme tokens). Standardize brand name to "Grid" (from "Octo"). *1 plan.*
- [x] **Phase A.5: grid-platform Hardening** — Full test coverage (auth, API handlers, tenant lifecycle), rate limiting per tenant, proper `ErrorCode` enum replacing `String`. *3 P3 gaps, 2 plans.*
- [x] **Phase A.6: web-platform/ Production** — Fix chat history loading, add Markdown rendering (reuse web/ components), add ErrorBoundary + toast system, fix dashboard stats copy-paste bug, wire user profile button. *6 P2/P3 gaps, 3 plans.*

#### Wave 3: Desktop + Eval

- [x] **Phase A.7: grid-desktop Feature Work** — Add IPC commands for agent/session interaction, bundle frontend assets in app, fix auto-updater endpoint. *3 P3 gaps, 2 plans.*
- [x] **Phase A.8: grid-eval Web UI** — Build web dashboard for eval results, CI integration (GitHub Actions workflow), parallel runner. *3 features, 2 plans.*

### Dependencies

```
A.1 grid-server ──┬── A.2 web/ polish
                  │
                  ├── A.4 cross-cutting foundation ──┬── A.5 grid-platform ── A.6 web-platform/
                  │                                  │
                  └── A.3 grid-cli polish             └── A.7 grid-desktop (after A.6)
                  
A.8 grid-eval — independent, can run anytime with web/ components
```

### Success Criteria

1. grid-server: RBAC wired, ApiError used consistently, budget/context endpoints functional, hot-reload works
2. web/: no mock fallbacks, consistent error handling, tests passing, sidebar + settings
3. grid-cli: eval commands functional (not stubs), all doctor checks repairable
4. web-platform/: chat history loads, Markdown renders, dashboard shows real data
5. grid-platform: test coverage ≥70%, rate limiting active
6. grid-desktop: can start/stop agents from desktop IPC
7. grid-eval: web dashboard shows results, CI workflow runs on PR

---

## Progress

| Phase | Plans | Status | Priority |
|-------|-------|--------|----------|
| A.0 Audit & Scoping | 1/1 | ✅ Complete | — |
| A.1 grid-server Hardening | 1/1 | ✅ Complete | P1 |
| A.2 web/ Production Polish | 1/1 | ✅ Complete | P1 |
| A.3 grid-cli Final Polish | 1/1 | ✅ Complete | P1 |
| A.4 Cross-Cutting Foundation | 1/1 | ✅ Complete | P2 |
| A.5 grid-platform Hardening | 1/1 | ✅ Complete | P2 |
| A.6 web-platform/ Production | 1/1 | ✅ Complete | P2 |
| A.7 grid-desktop Feature Work | 1/1 | ✅ Complete | P3 |
| A.8 grid-eval CI Enhancement | 1/1 | ✅ Complete | P3 |

---

## Milestone: v3.6 Post-Activation Docs Sync 🟡 STARTED 2026-07-18

**Goal:** Align the canonical product-status narrative to the post-Activation reality so future sessions and external readers can find a single, maintained source. Carry forward the docs-sync work the prior session drafted in the `grid-eaasp-product-docs-sync-2026-07-18` working set without mixing the docs-sync flow into the GSD phase management path (no superpowers/lwm/project-state artifacts in `.planning/`).

**Context:** Grid 独立产品 Activation shipped 2026-06-17 (8/8 phases A.0–A.8). On 2026-07-17 a docs sync draft was sketched in the conversation but not committed. On 2026-07-18 the user instructed to bring the docs sync into the GSD project-management system — the working set was reset to `05c6d7db` and the v3.6 phase was created in `ROADMAP.md`. This phase reconciles the post-Activation narrative and the EAASP v2 platform-evolution status (Phase 3 OPA approval chain / Phase 4 A2A / Phase 5 L5 Cowork / Phase 6 ecosystem) across the project's public, internal, and planning surfaces.

**Activation targets (post-Activation):**

| Surface | Current State | v3.6 Target |
|---------|---------------|-------------|
| `docs/PROJECT_PRODUCT_OVERVIEW.md` | Pre-Activation narrative (Activation listed as scoping) | Maintained SSOT with 5 canonical facts + Section 3 status snapshot + Section 4 future work + 16/17/21 RPC reconciliation |
| `AGENTS.md` / `CLAUDE.md` | Pre-Activation toolchain framing | Canonical-facts block; preserved Leg A/B see-link to ADR-V2-024; CLAUDE.md symlink to AGENTS.md |
| `README.md` / `README.zh.md` | Bilingual pre-Activation product status | Bilingual "Product status" section in front of Quick Start; same 5 facts in both languages (genuine Chinese, not literal English copy) |
| `.planning/PROJECT.md` / `.planning/STATE.md` | Pre-Activation current phase + stale `[ ]` activation tag | Post-Activation focus; v3.5 / Activation marked shipped; EAASP platform gaps declared as future work |
| `docs/status/PRODUCT_STATUS_<date>.md` | (none) | New immutable date-stamped audit snapshot that locks the canonical facts at the sync moment |

**Shared core rule (ADR-V2-023 P1 retained under ADR-V2-024):** docs changes are documentation-only and must not touch `grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge` or any source code under `crates/`, `lang/`, `tools/`, `web/`, `web-platform/`, or `proto/`.

### Phase 3.6.1: docs/PROJECT_PRODUCT_OVERVIEW.md SSOT + dated snapshot

**Goal:** Establish the maintained product-status SSOT and a date-stamped immutable audit snapshot.

- [ ] Plan 3.6.1-01: SSOT additions (Section 3 status snapshot, Section 3.1.1 EAASP phase→milestone alignment, Section 4 explicit future work) + new immutable `docs/status/PRODUCT_STATUS_2026-07-18.md` snapshot.
- Validate: 9-token parity check across both files (`2026-06-17`, `A.8`, `7`, `6 comparison`, `contract-v1.1.0`, `contract-v1.2.0`, `模拟器级参考实现`, `A2A`, `Cowork`).

### Phase 3.6.2: AGENTS.md canonical-facts block + CLAUDE.md symlink + README status sections

**Goal:** Surface the canonical facts at the project's root entrypoint and the public bilingual READMEs.

- [ ] Plan 3.6.2-01: AGENTS.md canonical-facts block; CLAUDE.md re-create as relative symlink to AGENTS.md (git mode 120000); English README "Product status" section; Chinese README `产品状态` section in genuine Chinese.
- Validate: `test -L CLAUDE.md && readlink CLAUDE.md = AGENTS.md`; bilingual parity check (3 tokens in both languages + `6 comparison` in EN + `6 个对比` in ZH).

### Phase 3.6.3: .planning/PROJECT.md + .planning/STATE.md sync

**Goal:** Bring the GSD planning state into alignment with the post-Activation reality.

- [ ] Plan 3.6.3-01: rewrite PROJECT.md current-phase block to post-Activation; mark v3.5 shipped; declare EAASP platform-evolution gaps as future work; correct the `4/7 components at 9.0+` to `5/7` (scoreboard-table vs prose mismatch in STATE.md Audit Findings Summary); update STATE.md core value to v1.2.0 current + v1.1.0 historical; add canonical-source links to SSOT and dated snapshot.
- Validate: Task 3 planning token check (3 tokens: `2026-06-17`, `contract-v1.2.0`, `PROJECT_PRODUCT_OVERVIEW.md`).

### Success Criteria

1. SSOT and dated snapshot agree on the 5 canonical facts and the 4 EAASP platform gaps.
2. `AGENTS.md` carries the canonical-facts block with the correct `docs/status/PRODUCT_STATUS_2026-07-18.md` link; `CLAUDE.md` is a relative symlink to `AGENTS.md` (mode 120000).
3. Bilingual READMEs have matching "Product status" sections in genuine Chinese (not literal English copy).
4. `.planning/PROJECT.md` / `.planning/STATE.md` describe post-Activation reality and reference the SSOT and dated snapshot.
5. No superpowers, project-state, lwm, or other GSD-incompatible skill artifacts appear in `.planning/` or anywhere in the working tree (clean working tree, no untracked scratch dirs).

---

## Coverage Index

To be populated after Phase A.0 audit — REQ-IDs will map to specific gaps discovered.

---

## Milestone: v3.7 实战可用性补全 (Production-Usability Closure) 🟡 STARTED 2026-07-19

**Goal:** Close the gap between the **Activation Quality 9.0+ scores** (declared in v3.6 docs sync) and **实战可用性 (real-world usability)** declared by the user on 2026-07-19. Activation 9.0 ≠ 实战可用 — `grid-cli` / `web/` / `EAASP 本地仿真` need to be runnable end-to-end against realistic enterprise-agent scenarios before this milestone closes.

**Context:** Activation milestone (8/8 phases A.0–A.8) shipped 2026-06-17 with the **Quality Scoreboard** in `.planning/STATE.md` scoring `grid-cli`/`web/`/`grid-server`/`grid-eval`/`grid-platform` at 9.0+ each. On 2026-07-19 the user clarified: these scores measure internal code health, NOT real-world usability. `grid-cli` must let one person drive an agent end-to-end; `web/` must be a usable dashboard for monitoring/tracking agents; `EAASP` local tools must be a credible simulation of an enterprise platform close enough to production. The user explicitly **deferred** `grid-server` multi-user login scenario to the next milestone — single-user grid-server work landed in Phase A.1.

**Scope (priority-ordered per user direction 2026-07-19):**

| Crate/Tool | Activation Score | Real-world Status | v3.7 Target |
|------------|------------------|-------------------|-------------|
| `crates/grid-cli/` | 9.0 ✅ | **完整独立工作** — needs end-to-end实战 verification | Run any enterprise-style agent scenario from CLI without manual stitching; verify all 16 commands work in a 真实场景 walkthrough |
| `web/` (grid-web single-user UI) | 9.0 ✅ | **实战不可用** (per user 2026-07-19) | Dashboard for monitoring/tracking agent execution; close the Activation-9.0 ↔ 实战-不可用 gap |
| `tools/eaasp-*/` (EAASP 本地仿真) | 5/7 audit | **接近实战企业平台** — simulator-level → credible enterprise simulation | Wire enough of L0/L1/L2/L3/L4 + Phase 3 governance gate hooks so a 真实 enterprise workflow can be exercised locally without external EAASP |
| `crates/grid-server/` | 9.0 ✅ | **Deferred** to next milestone | Multi-user login scenario (per user 2026-07-19) → v3.8 |

**Out of scope (deferred to v3.8+):**

- `grid-server` multi-user login scenario — RBAC + JWT tenant scoping + cross-user session isolation. User explicitly deferred until single-user stack is 实战可用.
- EAASP v2.0 platform-evolution gaps (Phase 3 production OPA / Phase 4 A2A / Phase 5 L5 Cowork UI / Phase 6 ecosystem) — still future work, NOT addressed by v3.7.
- `web-platform/` (multi-tenant UI, Quality 7.5) and `grid-desktop` (Quality 6.5) — these are Activation-shipped but below 9.0+; user did NOT include them in v3.7 scope, so they stay in Activation-deferred backlog.

**Shared core rule (ADR-V2-023 P1 retained under ADR-V2-024):** any change to `grid-engine` / `grid-runtime` / `grid-types` / `grid-sandbox` / `grid-hook-bridge` must work for both engine 接入面 and Grid independent product. v3.7 work predominantly touches `crates/grid-cli/` + `web/` + `tools/eaasp-*/` — none are shared core, but if a change crosses that boundary it must respect the rule.

**Acceptance standard — "实战可用" definition (per user 2026-07-19):**

1. **grid-cli**: A non-developer can `grid` + start a realistic enterprise-style task (multi-step agent with tool use, memory, hooks) and observe meaningful output without CLI-flag tuning.
2. **grid-web** (`web/`): A non-developer can open the dashboard, observe a running agent's progress in real time, see its tool calls, see its memory writes, and stop/resume it without code intervention.
3. **EAASP 本地仿真**: A non-developer can `eaasp session run -s <skill> -r <runtime> "<prompt>"` against a realistic enterprise scenario and see L2 memory + L3 governance gate + L4 SSE streaming behave as a credible enterprise platform would — close enough to实战 that a customer could evaluate the platform locally before committing to deployment.

### Phase 3.7.1: grid-cli 实战可用性补全

**Goal:** Make `grid-cli` runnable end-to-end for realistic enterprise-agent scenarios without manual stitching.

- [ ] Plan 3.7.1-01: Audit current `grid` command surface (16 commands) against 3–5 realistic enterprise scenarios (multi-step agent + tool use + memory + hooks + LLM streaming). Identify every gap between Activation-9.0 code quality and end-to-end runnability.
- [ ] Plan 3.7.1-02: Close the gaps surfaced in 3.7.1-01. Each plan must pass: (a) the scenario runs from a clean checkout with documented env vars; (b) no manual CLI-flag tuning required; (c) output is meaningful and actionable for a non-developer observer.
- Validate: 3 实战 scenarios PASS end-to-end without code intervention; documented in `docs/status/PRODUCTION_USABILITY_2026-XX-XX.md` walkthrough.

### Phase 3.7.2: web/ 实战可用性补全 (grid-web dashboard 实战化)

**Goal:** Close the gap between Activation-9.0 and 实战不可用 for `web/`. Specifically: build a dashboard that a non-developer can open, observe a running agent, see its tool calls, see its memory writes, and stop/resume it without code intervention.

- [ ] Plan 3.7.2-01: Identify the specific "实战不可用" gaps in `web/` — likely candidates: WS streaming reconnect on agent crash, tool-call event ordering in UI, memory write visibility, stop/resume UX, mock fallbacks still in code paths per A.2 audit.
- [ ] Plan 3.7.2-02: Close the gaps. End-to-end test: open `web/` against a running `grid-server` + a real agent task; verify monitor/track/stop/resume works without devtools intervention.
- Validate: Video/walkthrough of a non-developer running an enterprise scenario through `web/` end-to-end; UAT pass with 1–2 external observers (or self-recorded walkthrough if external observers not available).

### Phase 3.7.3: EAASP 本地仿真补全 (Phase 0–2.5 + Phase 3 governance hooks)

**Goal:** Move `tools/eaasp-*/` from "simulator-level reference implementation" (per docs/PROJECT_PRODUCT_OVERVIEW.md) to "credible enterprise simulation close enough to实战 that a customer could evaluate locally".

- [x] Plan 3.7.3-01: Audit which of the 8 EAASP evolution phases are SHIPPED (Phase 0–2.5 ✅ per canonical facts) vs deferred (Phase 3 OPA / Phase 4 A2A / Phase 5 L5 / Phase 6 ecosystem). For each deferred phase that affects 实战 credibility, identify what minimally must be wired to make the simulation believable.
- [x] Plan 3.7.3-02: Wire the minimum credible set of deferred-phase hooks into the simulation — e.g. Phase 3 governance gate hooks so risk-classified actions actually pause for approval rather than silently pass. Don't implement the full deferred phase; only the hooks needed for credibility. **SHIPPED 2026-07-23** — 8/8 REQ-EAASP closed (Rust RiskLevel enum + L3 evaluate_gate + append-only audit + L4 SSE events + CLI --yes/--no + S8 mock-SCADA setpoint). 136/136 targeted tests PASS.
- Validate: 1 实战 enterprise scenario (e.g. "agent writes to external system, governance gate triggers, user approves, action completes") runs end-to-end through EAASP local tools with observable governance behavior.

### Phase 3.7.4: SKIPPED — grid-server multi-user deferred to v3.8

Per user 2026-07-19: "grid-server 是下一步再讨论，目前先把单用户的 grid-cli/grid-web/EAASP仿真做好". This phase is intentionally left empty. v3.8 candidate scope will be defined when 3.7.1/3.7.2/3.7.3 close.

### Success Criteria

1. `grid-cli` runs 3 documented enterprise scenarios end-to-end without manual CLI-flag tuning.
2. `web/` runs a real agent scenario with non-developer-observable dashboard monitor/track/stop/resume.
3. `tools/eaasp-*/` runs a real enterprise scenario with credible governance gate behavior.
4. No regression in v3.6 docs-sync SSOT, snapshot, AGENTS/CLAUDE/READMEs, or planning state.
5. `grid-server` work stays untouched (deferred to v3.8).
6. `grid-engine` / `grid-runtime` / `grid-types` / `grid-sandbox` / `grid-hook-bridge` changes (if any) respect ADR-V2-023 P1 shared-core rule.

### Phase 4: --milestone v3.7 --name Production-Usability Closure --description 4 phases: grid-cli / web/ / EAASP 本地仿真 实战补全; grid-server 多用户 deferred

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 3
**Plans:** 2/2 plans complete

Plans:
- [ ] TBD (run /gsd-plan-phase 4 to break down)

---

*Last updated: 2026-07-19 — v3.7 Production-Usability Closure added after v3.6 SHIPPED.*
