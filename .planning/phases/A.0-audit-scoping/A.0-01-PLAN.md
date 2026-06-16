<objective>
Audit all Grid 独立产品 dormant crates and produce prioritized activation backlog.
Purpose: Assess readiness of 7 dormant crates/composants, identify concrete gaps, and size the work needed to activate Grid as a standalone product.
</objective>

<context>
v3.4 Full INBOX Drain + v3.5 Debt Finalization both SHIPPED. DEFERRED_LEDGER.md 100% CLOSED. Debt era over — shift to product activation. This audit phase is the foundation for all subsequent activation work.

**ADR constraint (ADR-V2-024 §Open Item #3)**: grid-cli + grid-server are the priority combination. Platform/desktop/web deployment comes after.
</context>

<findings>

## Implementation Depth Scores

| Crate/Component | Score | LOC | Verdict |
|-----------------|-------|-----|---------|
| grid-cli | 8/10 | ~15k | Nearly complete — eval stubs only gap |
| grid-eval | 7/10 | ~17k | Full-featured but CLI-only |
| web/ | 7/10 | ~20k | Well-implemented workbench, mock fallbacks |
| grid-server | 6/10 | ~15k | Feature-rich, RBAC unwired |
| grid-platform | 6/10 | ~4k | Solid multi-tenant arch, thin tests |
| grid-desktop | 3/10 | ~330 | Tauri shell only |
| web-platform/ | 3/10 | ~4k | Auth layer good, rest placeholder |

## Critical Gaps (by priority)

### P1 — Blocking production readiness

| # | Crate | Gap | Impact |
|---|-------|-----|--------|
| P1-1 | grid-server | RBAC middleware implemented but unwired — no route uses `require_role_middleware` | All endpoints share same auth level, can't differentiate admin vs user |
| P1-2 | grid-server | `ApiError` enum defined but unused — handlers return ad-hoc `(StatusCode, Json(...))` tuples | No consistent error shape, frontend can't parse errors reliably |
| P1-3 | grid-server | `GET /api/v1/budget` returns hardcoded 200k always | Budget feature non-functional |
| P1-4 | grid-server | `GET /api/v1/context/snapshot` + `/zones` create transient empty objects | Context observability completely broken |
| P1-5 | grid-server | `PUT /api/v1/config` and admin `/reload` CORS & log_level recorded but not applied | Hot-reload ineffective for key settings |
| P1-6 | web/ | MCP ToolInvoker + LogViewer use hardcoded mock fallbacks when API unavailable | Places in UI where real data is silently replaced with fakes |
| P1-7 | web/ | `window.__GRID_TOKEN` magic global for WS auth token | Fragile, hard to debug, no TypeScript safety |
| P1-8 | grid-cli | `eval run/compare/benchmark/watch` are stubs — print "use cargo run -p octo-eval" | 4 of 11 eval commands non-functional |

### P2 — Needed for full activation

| # | Crate | Gap | Impact |
|---|-------|-----|--------|
| P2-1 | web/ | Inconsistent error handling — `window.alert()` in Tasks/Schedule vs toast atoms in Chat | Poor UX, some errors lost silently |
| P2-2 | web/ | Zero test files | No regression safety net for 20k LOC of UI |
| P2-3 | web/ | No auth layer (not needed for single-user but needed if paired with grid-platform) | Can't switch to multi-tenant backend later without rewrite |
| P2-4 | web-platform/ | Chat session history not loaded (explicit gap at Chat.tsx:98) | Users can't resume conversations |
| P2-5 | web-platform/ | No Markdown rendering (plain text only) | Chat quality far below web/ |
| P2-6 | web-platform/ | No ErrorBoundary, no toast system | Crashes invisible to user |
| P2-7 | web/ | `NavRail.tsx` only shows logo icon — no sidebar, no settings | Missing basic navigation & config |
| P2-8 | grid-server | Deprecated `/ws` legacy path still active | Confusion risk for API consumers |

### P3 — Polish & feature completeness

| # | Crate | Gap | Impact |
|---|-------|-----|--------|
| P3-1 | grid-cli | MCP logs command shows server state only, no live log streaming | Partial feature |
| P3-2 | grid-cli | `config set` not persisted (env var for current process only) | Misleading UX |
| P3-3 | grid-cli | `doctor --repair` only handles Config File case — 9/10 checks have no auto-repair | Limited self-healing |
| P3-4 | grid-cli | Knowledge graph query falls back to memory search | Inaccurate for graph queries |
| P3-5 | web-platform/ | Dashboard StatsCards all show same value (copy-paste bug) | Dashboard useless |
| P3-6 | web-platform/ | User profile button in Header does nothing | Dead UI element |
| P3-7 | grid-platform | Thin test coverage (2 integration files, no auth/API handler tests) | Regression risk |
| P3-8 | grid-desktop | Only 6 IPC commands — no agent/session interaction from desktop layer | Just a WebView shell |
| P3-9 | grid-desktop | Updater endpoint hardcoded to non-existent GitHub repo | Auto-update broken |

## Architecture Observations

1. **web/ vs web-platform/ divergence**: Two separate codebases evolved independently — different themes (dark vs light), different API patterns (raw fetch vs ApiClient class), different brand names (Grid Studio vs Octo Platform). Should merge or at least share common API client, components, and design system.

2. **ApiClient in web-platform/ is superior**: The structured `ApiClient` class with JWT auto-refresh should be extracted and used by web/ too.

3. **grid-cli + grid-server already form a working stack**: CLI can talk to server, TUI works, WS streaming works end-to-end. The activation is about hardening, not building from scratch.

4. **grid-eval is surprisingly mature**: 8 scoring strategies, 12 suites, multi-model comparison, regression detection. Just needs bridge from grid-cli stubs and a web UI.

</findings>

<recommendations>

## Prioritized Activation Phases

### Wave 1: Single-User Workbench (grid-server + web/ + grid-cli)

**Phase A.1: grid-server Hardening** (~3-4 plans)
- Wire RBAC middleware to all routes
- Replace ad-hoc error tuples with `ApiError` throughout
- Fix budget endpoint to read real usage
- Fix context snapshot/zones to read live session state
- Make CORS and log_level hot-reload actually work
- Remove deprecated `/ws` legacy path

**Phase A.2: web/ Production Polish** (~3-4 plans)
- Remove MCP mock fallbacks — connect to real API
- Standardize error handling (toast system everywhere, no `window.alert()`)
- Add test framework (Vitest + Testing Library) + critical-path tests
- Replace `window.__GRID_TOKEN` with proper config-based token
- Add sidebar with settings, session list, and user menu
- Extract `ApiClient` from web-platform/ as shared module

**Phase A.3: grid-cli Polish** (~2 plans)
- Implement eval bridge (connect CLI eval commands to grid-eval library)
- MCP live log streaming
- `config set` persistence
- Doctor --repair for all 10 checks

### Wave 2: Multi-Tenant Platform

**Phase A.4: Cross-Cutting Foundation** (~1 plan)
- Merge web/ and web-platform/ design system (shared components, ApiClient, theme tokens)
- Standardize brand name (Grid, not Octo)

**Phase A.5: grid-platform Hardening** (~2 plans)
- Full test coverage (auth, API handlers, tenant lifecycle)
- Rate limiting per tenant
- Proper error type hierarchy

**Phase A.6: web-platform/ Production** (~3 plans)
- Fix chat history loading
- Add Markdown rendering (reuse web/ components)
- Add ErrorBoundary + toast system
- Fix dashboard stats
- Wire user profile button

### Wave 3: Desktop + Eval

**Phase A.7: grid-desktop Feature Work** (~2 plans)
- Add IPC commands for agent/session interaction
- Bundle frontend assets directly (don't depend on grid-cli dashboard)
- Fix auto-updater endpoint

**Phase A.8: grid-eval Web UI** (~2 plans)
- Build web dashboard for eval results
- CI integration (GitHub Actions workflow)
- Parallel runner

</recommendations>
