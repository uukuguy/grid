# Current State

> **Updated**: 2026-07-30 — v3.14 EAASP Phase 6 SHIPPED + text-sync gap closed + handoff checkpoint refresh

## Project Snapshot

- Project: Grid — agent runtime stack (engine-axis: `grid-engine` / `grid-runtime` / `grid-types` / `grid-sandbox` / `grid-hook-bridge`) + Grid independent product (`grid-server` / `grid-platform` / `grid-cli` / `grid-eval` / `web/` / `web-platform/` / `grid-desktop`) + co-located EAASP v2.0 simulator reference (`tools/eaasp-*/`, no upstream EAASP project).
- Current branch: `main`
- Theme-level focus: **EVOLUTION_PATH §三 8-Phase 路线 ALL SHIPPED** (v3.10 platform-skeleton + v3.11 OPA / 5-stage approval + v3.12 A2A / Event Room + v3.13 L5 Cowork + v3.14 Ontology / Marketplace / SDK ecosystem). v3.14 is the **final phase** per D-46; v3.15+ moves to the data/integration axis per ADR-V2-024.
- Project route: managed (lightweight-memory + GSD state machine, both maintained)
- Canonical worklists: `.planning/ROADMAP.md` (GSD) + `docs/PROJECT_PRODUCT_OVERVIEW.md` (project SSOT)
- Active work package: **none — milestone boundary** (v3.14 SHIPPED + closed; awaiting v3.15 scope selection)

## Current Architecture

### Shared core (engine-axis AND independent-product axis)
- `crates/grid-engine/` — agent loop, context, memory (L0/L1/L2), MCP, providers, tools, skills, security, audit, metrics.
- `crates/grid-runtime/` — L1 runtime adapter wrapping `grid-engine`; flagship L1 implementation.
- `crates/grid-types/` — zero-dep shared types.
- `crates/grid-sandbox/` — sandbox runtime adapters.
- `crates/grid-hook-bridge/` — Rust ↔ L2/L3 hook event bridge.
- **ADR-V2-023 P1** (shared-core rule, retained under ADR-V2-024 dual-axis): no leg-specific branches in shared code.

### EAASP v2.0 simulator reference (`tools/eaasp-*/`) — co-located
- L0 Protocol: `proto/eaasp/runtime/v2/{common,runtime,hook}.proto` (21 RPC: 17 + 4 hooks)
- L1 Runtime: 7 adapters (1 production `grid-runtime` + 6 comparison runtimes: claude-code / goose / nanobot / pydantic-ai / claw-code / ccb; hermes frozen per ADR-V2-017)
- L2 Memory & Skills: `eaasp-l2-memory-engine` (FTS5 + HNSW + time-decay hybrid) + `eaasp-skill-registry` + `eaasp-mcp-orchestrator` + `eaasp-certifier`
- L3 Governance: `eaasp-l3-governance` (policy DSL + risk classification + OPA backend adapter v3.11.1)
- L4 Orchestration: `eaasp-l4-orchestration` (Event Room v3.12.1 + A2A Router v3.12.2 + L5 Cowork v3.13.0 + Ecosystem v3.14)
- Contract: `contract-v1.2.0` (current latest); `contract-v1.1.0` (historical Phase 3 sign-off 2026-04-18, 42 PASS / 22 XFAIL × 7 runtime)
- Spec authority: `docs/design/EAASP/EAASP-Design-Specification-v2.0.docx`
- **No upstream EAASP project exists** — `tools/eaasp-*/` are simulator-level reference implementations of the EAASP v2.0 platform contract (per EVOLUTION_PATH §三 Phase 0–6 roadmap, all SHIPPED 2026-07-30).

### Grid independent product
- `crates/grid-cli/` (8/10 → 9.0 ✅) — main client
- `crates/grid-server/` (single-user workbench, 9.0 ✅)
- `crates/grid-platform/` (multi-tenant, 9.0 ✅)
- `crates/grid-eval/` (9.0 ✅)
- `web/` (9.0 ✅) + `web-platform/` (7.5, candidate A for v3.15)
- `grid-desktop/` (6.5, candidate B for v3.15; Tauri desktop, agent/session interaction not yet wired)

## Dual-Gate Status (last verified 2026-07-30 @ `349f769b`)

| Gate | Command | Result |
|------|---------|--------|
| v3.9 RBAC catalog | `make rbac-audit` | **PASS / 134 routes** |
| v3.10 spec-audit | `make v3.10-spec-audit` | **PASS / 4 files / 38 rows** (post-`§7.5-7.8 Phase 6 ecosystem surface (v3.14 cross-index)` row, added in `03.14.3` close commit `98dfecf7`) |
| v3.11.2 5-stage approval chain | (carry-over) | PASS |
| v3.12.1 Event Room ContextVar auth | (carry-over) | PASS |
| v3.12.2 A2A Router + ReviewSet | (carry-over) | PASS |
| v3.13 L5 Cowork + RETROSPECTIVE trace API | (carry-over) | PASS |
| v3.14 Ontology + Marketplace + SDK | (carry-over) | PASS |

**Note on row count**: ADR-V2-034 / ADR-V2-035 bodies intentionally retain the **37** figure (v3.11.x / v3.12.x Acceptance-time historical snapshot per ADR governance immutable-Accepted-body rule). REPORT.md + certifier + walkthrough reflect the post-v3.14 **38** figure. See `docs/status/PRODUCTION_USABILITY_2026-07-30.md` §双 gate snapshot rationale note.

## Open Problems

1. **v3.15+ scope not yet selected** — candidates listed in `docs/status/RESUME-NEXT-SESSION.md` §下一候选 (5 options: web-platform 7.5→9.0 / grid-desktop 6.5→9.0 / grid-platform route-catalog audit / start-EAASP 一键脚本 / EAASP 仿真环境 E2E 验证套件). Per ADR-V2-024 Open Item #3 priority axis, **grid-cli + grid-server** is the recommended next axis (data/integration per ADR-V2-024 §1). User decision pending.
2. **5-component audit table frozen at v3.7 milestone** — Activation SHIPPED 2026-06-17 audit scores in `docs/PROJECT_PRODUCT_OVERVIEW.md` §Audit Findings Summary (grid-cli/web/grid-server/grid-eval/grid-platform at 9.0+; web-platform 7.5; grid-desktop 6.5).
3. **CI Makefile tier gap** — carried forward from Phase 5.4; not blocking v3.14. See `~/.claude/projects/-Users-sujiangwen-sandbox-LLM-speechless-ai-SGAI-grid-sandbox/memory/project_ci_makefile_tier_gap.md`.
4. **`v2-phase3-e2e-rust` Makefile target drift** — `docs/status/PRODUCTION_USABILITY_2026-07-30.md` documents the target as "pass in current `make`-only invocation" gap. Tracked as separate project-level documentation-drift cleanup, NOT a v3.14.3 deliverable.

## Hard Constraints (D-44, all preserved)

- v3.9 RBAC + v3.10 spec-audit + ADR-V2-023 P1 (no shared-crate change) + ADR-V2-028 (strict-by-default config) + ADR-V2-034 (OPA sidecar topology) + v3.11.2 5-stage approval + v3.12.1 Event Room ContextVar auth + v3.12.2 A2A Router + v3.13 L5 Cowork + retrospective — all continue to PASS.

## Key Files

### Loaded every Claude session
- `CLAUDE.md` (project root)
- `/Users/sujiangwen/.claude/projects/-Users-sujiangwen-sandbox-LLM-speechless-ai-SGAI-grid-sandbox/memory/MEMORY.md`

### State / handoff (lightweight-memory)
- `docs/status/RESUME-NEXT-SESSION.md` — current session baton
- `docs/status/CURRENT-STATE.md` — this file (structural snapshot)
- `docs/status/JOURNAL.md` — append-only event log
- `docs/status/PRODUCTION_USABILITY_2026-07-{27,28,29,30}.md` — v3.11–v3.14 dated walkthrough evidence

### State / handoff (GSD state machine)
- `.planning/STATE.md` — milestone state (v3.14 SHIPPED)
- `.planning/ROADMAP.md` — canonical milestone worklist
- `.planning/RESUME-NEXT-SESSION.md` — GSD session baton
- `.planning/REQUIREMENTS.md` — REQ-IDs per milestone
- `.planning/PROJECT.md` — project context
- `.planning/RETROSPECTIVE.md` — milestone-level retrospectives
- `.planning/phases/03.14.{0,1,2,3}-*/` — v3.14 phase artifacts (6 files)

### Implementation entry points
- `crates/grid-server/src/middleware/auth.rs` — JWT/AuthMode/RBAC middleware
- `crates/grid-server/src/api/` — server route handlers and authorization boundaries
- `crates/grid-engine/src/auth/` — shared roles, permissions, auth configuration
- `crates/grid-engine/src/agent/tenant.rs` — tenant context and isolation primitives
- `tools/eaasp-ecosystem/` — v3.14 Ontology + Marketplace + SDK CLI + ecosystem_client
- `sdk/python/src/eaasp/` — v3.14.2 SDK scaffolding

### Reference docs
- `docs/PROJECT_PRODUCT_OVERVIEW.md` — project SSOT (product status)
- `docs/status/PRODUCT_STATUS_2026-07-17.md` — dated audit snapshot (2026-07-17 docs sync)
- `docs/design/EAASP/EAASP-Design-Specification-v2.0.docx` — EAASP spec authority
- `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md` — 8-Phase decision registry (now ALL SHIPPED)
- `docs/design/EAASP/DEFERRED_LEDGER.md` — 8 × V310-* + V311-AUDIT-01 all ✅ CLOSED
- `docs/design/EAASP/adrs/ADR-V2-024-...md` — dual-axis strategy (supersedes V2-023)
- `docs/design/EAASP/adrs/ADR-V2-029-...md` — engine vs data/integration boundary
- `docs/design/EAASP/adrs/ADR-V2-034-...md` — OPA sidecar topology
- `docs/design/EAASP/adrs/ADR-V2-035-...md` — A2A Router conflict detection

## Resume Instructions

1. Read this file (`docs/status/CURRENT-STATE.md`) for the structural baseline.
2. Read `docs/status/RESUME-NEXT-SESSION.md` for session intent and v3.15+ candidates.
3. Cross-read `.planning/STATE.md` and `.planning/ROADMAP.md` for GSD milestone state.
4. Run `git status -sb` and `git log --oneline -5` to confirm HEAD.
5. Read `CLAUDE.md` + auto-loaded MEMORY.md before implementation.
6. If picking up from v3.14, start with `/gsd-resume-work` or read `.planning/phases/03.14.{0,1,2,3}-*/PLAN.md` + `SUMMARY.md`.
7. If proposing v3.15 scope, refer to `docs/status/RESUME-NEXT-SESSION.md` §下一候选 and ADR-V2-024 Open Item #3 priority axis.

---

## Session 2026-07-30 — EAASP 仿真环境验证 (closed)

**Scope**: Live full-stack end-to-end verification of the EAASP v2.0 simulator
(`tools/eaasp-*`) including OPA sidecar + 4 L1 runtimes + L2/L3/L4/L5 +
ecosystem services. Verified per `docs/status/VERIFICATION_PLAN_2026-07-30.md`
4-phase plan (services + audit gates + skill E2E + SDK typed exceptions).

**Headline result**: All 14 services (OPA + skill-registry + L2 memory +
L3 governance + MCP orchestrator + mock-scada + L4 orchestration + grid-runtime
+ claude-code-runtime + nanobot-runtime + goose-runtime + L5 cowork + L5
ecosystem) brought up cleanly; all Phase 2 audit gates PASS (134 RBAC routes
+ 38 spec rows + 75 eaasp-ecosystem pytest + 23 SDK pytest). Real LLM
session.run invoked; SSE events captured; SDK typed exceptions verified.

**4 bugs found and fixed in this session** (10 commits ahead origin/main):

| # | Commit | Severity | Description |
|---|---|---|---|
| 1 | `8e3594e2` | MEDIUM (latent bug) | skill-registry CREATE INDEX embedded in CREATE TABLE block prevented `migrate_add_access_scope` from running on legacy registry.db files (D11/L2-06). Removed from block; created idempotently by migration. 36/36 eaasp-skill-registry tests pass. |
| 2 | `a6d75300` | HIGH (RBAC) | L4 `/v1/sessions/create` + CLI never forwarded `X-Session-Scope` header required by L3 `/v1/sessions/{id}/validate` (D8/L3-04). CLI now reads `EAASP_SESSION_SCOPE` env; L4 forwards to L3. |
| 3 | `3398d567` | CRITICAL (security review) | L4 RBAC enforcement was `fail-open`: missing header → wildcard `"*"` fallback; free-form scope strings allowed impersonation. Fixed to truly fail-closed: missing header → 403 `missing_scope`; scope mismatch → 403 `scope_mismatch`. CLI `EAASP_SESSION_SCOPE` now REQUIRED. |
| 4 | `bbc5d7df` | HIGH (security review round-2) | `_resolve_skill_bound_scope` had 3 fail-open fallbacks (skill_registry=None / read_skill raises / no access_scope declared → trust caller's claim). All 3 paths now return None → 403. Explicit `EAASP_DEV_DISABLE_SCOPE_BINDING=1` env var added for documented dev/test passthrough. 285/286 L4 tests pass. |

**Modified examples skills** (re-runnability fix):
- `examples/skills/threshold-calibration/SKILL.md` — `access_scope` changed
  from `org:eaasp-mvp` (collides with `skill-extraction`) to
  `org:eaasp-verify-2026-07-30` so the §6.2 submit+promote chain is
  reproducible from a fresh state.

**Verification artifacts** (workspace-only, in `.grid/verify-2026-07-30/`):
- `MANUAL.md` — step-by-step manual for human execution
- `evidence-phase-1-2.md` — Phase 1+2 evidence (services + audit gates)
- `evidence-phase-3-4.md` — Phase 3+4 evidence (skill E2E + SDK exceptions)
- `logs/{opa,dev-eaasp,l5-cowork,l5-ecosystem}.log` — all command output

**Outstanding limitations** (not blocking):
- `submit_skill` endpoint on the running L5 ecosystem binary has a body/query
  mismatch — server expects `req` as query param, source expects JSON body.
  Pre-existing latent bug; needs a fresh `uv pip install` to rebuild venv.
- §7.3 (404 → `EaaspEcosystemPromotionError`) cross_tenant ACL fires before
  404 check, so this scenario can't be cleanly exercised without first
  seeding an acme-tenant skill (which currently can't be done due to
  the submit_skill bug above).
- `tests/test_session_orchestrator.py::test_create_session_happy_path` has
  a pre-existing assertion mismatch (`policy_version == "3"` vs computed
  sha256 hash). Confirmed pre-existed via `git stash` (not from these
  changes).

**Service teardown confirmed**: All 14 services stopped; ports 18081-18090,
18181-18182, 50051-50054, 50063 clean. 0 `eaasp-*` / `grid-runtime` / `opa`
processes running.

**Worktree**: this session's repo only — main branch only; 0 sub-worktrees
created.

---

*Session closed 2026-07-30. Next session reads this section + RESUME-NEXT-SESSION.md + JOURNAL.md latest entry (`9210a406`).*
