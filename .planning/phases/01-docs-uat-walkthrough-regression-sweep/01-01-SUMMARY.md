# Phase 01 (wrapper for intended 03.8.3) SUMMARY — Docs + UAT walkthrough + regression sweep

> **Note on phase number.** The GSD roadmap parser failed to recognise
> the decimal phase identifier `03.8.3` and emitted an accidental `Phase 1`
> entry into `.planning/ROADMAP.md`. The user explicitly authorised using
> the accidentally-created `01-docs-uat-walkthrough-regression-sweep`
> directory as the **GSD wrapper** for the intended Phase 03.8.3 work.
> The plan frontmatter declares `wrapper_for: 03.8.3`. This SUMMARY
> reflects the intended 03.8.3 phase.

**Status:** SHIPPED 2026-07-24 (climb session)
**Requirements closed:** DOC-01, DOC-02, DOC-03, TEST-05, TEST-06
**Tests passing:**
- 33/33 v3.8 hermetic integration (multi_user_jwt 9 + test_auth_modes 8 + multi_user_auth_endpoints 7 + multi_user_rbac_tenant 9)
- 44/44 grid-engine auth unit tests
- 3/3 grid-engine agent::tenant unit tests
- 39/39 grid-engine audit unit tests

## Commits (T1 → T6 in execution order)

| # | Hash | Subject |
|---|------|---------|
| Plan | 260e770f | docs(01-03.8.3): plan — Docs + UAT walkthrough + regression sweep |
| T1+T2 | 49b73292 | docs(01-03.8.3): USER_GUIDE.md §11 — multi-user mode (DOC-01 + DOC-02) |
| T3 | f65cf770 | docs(01-03.8.3): PRODUCTION_USABILITY_2026-07-24 — 5-scenario UAT walkthrough (DOC-03 + TEST-05) |
| T4 | 4248eb1d | docs(01-03.8.3): correct v3.8 hermetic test count to 33 (TEST-06) |
| T5 | 70157420 | docs(01-03.8.3): ROADMAP/STATE/REQUIREMENTS — mark 03.8.3 SHIPPED |

## Goal-backward verification

- [x] USER_GUIDE.md §11 exists with TOC entry; covers login flow, JWT claims, refresh, logout, RBAC matrix, env-var reference, single→multi switch procedure, known gaps, cross-references (DOC-01, DOC-02)
- [x] PRODUCTION_USABILITY_2026-07-24.md exists with 5 scenarios + Live BLOCKED status; each scenario cites its hermetic test evidence (DOC-03, TEST-05)
- [x] All 33 v3.8 hermetic + 44 auth unit + 3 tenant unit + 39 audit unit tests PASS on re-run (TEST-06)
- [x] ROADMAP.md v3.8 milestone ladder shows all 4 phases as SHIPPED
- [x] STATE.md frontmatter reflects phase-complete (4/4)
- [x] REQUIREMENTS.md DOC-01..03 + TEST-05 + TEST-06 checkboxes ticked
- [x] No code changes — docs + GSD artifacts only (preserves the 03.8.2 hermetic baseline)
- [x] No `cargo test --workspace` invoked (per `feedback_no_full_tests`)
- [x] All commits end with the required footers: `Generated-By: Claude (claude-opus-4-8) via Claude Code CLI` and `Co-Authored-By: claude-flow <ruv@ruv.net>`

## What landed

### §11 in `docs/cli/USER_GUIDE.md`

Six sub-sections + cross-references:

- **§11.1 登录流程 (login flow)** — `POST /api/v1/auth/login` request/response/error shapes; AUTH-04 safe-body invariant proof.
- **§11.2 JWT claims 结构** — `JwtClaims` table with v3.8 breaking-change notes (pre-v3.8 tokens rejected because missing `tenant_id`/`jti`); HS256 + 32-byte secret requirement.
- **§11.3 刷新 (refresh)** — security hotfix `7f08ac53` (role+tenant_id re-read from UserStore, not old JWT); D-04 single-token sliding expiration.
- **§11.4 注销 (logout)** — `TokenBlacklist` consulted by middleware on every request; single-instance limitation; security hotfix history.
- **§11.5 RBAC matrix 参考** — `Role × Action` table from `crates/grid-engine/src/auth/roles.rs::Role::can`; cross-tenant 403 enforcement.
- **§11.6 Operator 环境变量参考** — DOC-02 four env vars with defaults + strict-mode failure semantics:
  - `GRID_AUTH_MODE` (corrected from plan's `GRID_MODE` — verified at `crates/grid-server/src/config.rs:496`)
  - `GRID_JWT_SECRET` (ADR-V2-028 strict-by-default; 32-byte minimum)
  - `GRID_TOKEN_TTL_SECS` (default 86400)
  - `GRID_USERS_JSON` (Argon2id + JSON wire shape + duplicate-email/user_id validation)
- **§11.7 单用户 → 多用户切换** — operator procedure.
- **§11.8 已知 honest gaps** — six deferred items (live UAT blocked; jti rotation v3.9+; shared blacklist v3.9+; full route catalog wiring v3.9+; constant-time `verify_credentials` v3.9+; DB-backed users v3.9+).
- **§11.9 相关文档** — links to all v3.8 SUMMARY docs + source files.

Frontmatter updated: `version: v3.7.1 → v3.8.3`; `date: 2026-07-20 → 2026-07-24`; footer status line updated.

### Dated walkthrough at `docs/status/PRODUCTION_USABILITY_2026-07-24.md`

- Executive summary + 5/5 PASS table.
- Scenario-by-scenario evidence with verbatim test assertions.
- Test inventory: 33 v3.8 hermetic + 44 auth unit + 3 tenant unit + 39 audit unit.
- Cross-reference index to all v3.8 SUMMARYs + security hotfixes.
- Acceptance: PARTIAL — hermetic 5/5 PASS; live HTTP-only walkthrough is operator-reproducible (no LLM dependency); live end-to-end with agent invocation deferred to environment with `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` (matching the v3.7.3 walkthrough precedent).

### Planning state updates

- `.planning/ROADMAP.md` v3.8 line: bullet expanded to enumerate all 4 phases as SHIPPED; milestone header updated to `🟢 03.8.0–03.8.3 SHIPPED 2026-07-24`.
- `.planning/STATE.md` frontmatter: `status: not-started → phase-complete`; `progress: 0/0 → 4/4`; Current Position block updated; explicit "milestone close deferred" note per user instruction.
- `.planning/REQUIREMENTS.md`: DOC-01..03 + TEST-05 + TEST-06 checkboxes ticked with phase/date attribution; DOC-02 env-var list corrected.

## Deviations from plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Hermetic test count corrected from 34 to 33**
- **Found during:** Task 4 (regression sweep, after writing walkthrough)
- **Issue:** Plan and walkthrough initially listed "34 v3.8 hermetic tests" based on an earlier miscount. Verified against Phase 03.8.2 SUMMARY's authoritative 33/33 figure and against `cargo test` output: 9 multi_user_jwt + 8 test_auth_modes + 7 multi_user_auth_endpoints + 9 multi_user_rbac_tenant = 33.
- **Fix:** Corrected the walkthrough's test inventory table + the heredoc command comment. No impact on plan structure.
- **Files modified:** `docs/status/PRODUCTION_USABILITY_2026-07-24.md`
- **Commit:** 4248eb1d

### Plan corrections

**2. [D-03 verification] Env var name corrected from `GRID_MODE` to `GRID_AUTH_MODE`**
- **Found during:** Plan Task 2 (env-var reference)
- **Issue:** Plan D-03 listed `GRID_MODE` based on the original 03.8.1 plan's wording. `grep -rn "GRID_MODE\b" crates/ tools/ lang/` returned zero matches; the actual env var is `GRID_AUTH_MODE` read at `crates/grid-server/src/config.rs:496`.
- **Fix:** Updated plan + USER_GUIDE §11.6.1 + REQUIREMENTS DOC-02 to use the correct env var name. Documented the correction so future readers don't repeat the mistake.
- **Files modified:** `01-01-PLAN.md`, `docs/cli/USER_GUIDE.md`, `.planning/REQUIREMENTS.md`
- **Commits:** 260e770f (plan), 49b73292 (USER_GUIDE), 70157420 (REQUIREMENTS)

**3. [D-03 verification] Removed `GRID_REFRESH_TTL_SECS` from DOC-02 env-var list**
- **Found during:** Plan Task 2 (env-var reference)
- **Issue:** Original 03.8.1 plan listed `GRID_REFRESH_TTL_SECS`. Per v3.8.1 D-04 (single-token sliding expiration; refresh reads role+tenant_id from UserStore, not old JWT), there is no separate refresh-token TTL — the same `GRID_TOKEN_TTL_SECS` covers both access and refresh.
- **Fix:** Updated DOC-02 to list only the four env vars that actually exist in code: `GRID_AUTH_MODE`, `GRID_JWT_SECRET`, `GRID_TOKEN_TTL_SECS`, `GRID_USERS_JSON`. Documented the simplification in the REQUIREMENTS checkbox annotation.
- **Files modified:** `01-01-PLAN.md`, `docs/cli/USER_GUIDE.md` §11.6, `.planning/REQUIREMENTS.md`
- **Commits:** 260e770f, 49b73292, 70157420

**4. [Wrapper-directory] Created plan under `01-` slug instead of `03.8.3-`**
- **Found during:** Session start (per user instruction)
- **Issue:** Roadmap parser failure to handle decimal `03.8.3` resulted in an accidental `Phase 1` entry in `.planning/ROADMAP.md` and an empty `01-docs-uat-walkthrough-regression-sweep/` directory.
- **Fix:** User authorised using the accidentally-created directory as the GSD wrapper for intended Phase 03.8.3. Plan frontmatter declares `wrapper_for: 03.8.3`; SUMMARY, STATE, ROADMAP, and REQUIREMENTS reflect the intended number.
- **Files modified:** All GSD artifacts under `.planning/phases/01-docs-uat-walkthrough-regression-sweep/`, `.planning/STATE.md`, `.planning/ROADMAP.md`

## Auth gates

None. No LLM API keys or operator secrets required for this phase — auth surface work is documentation-only, exercised via hermetic tests that use in-process `AuthConfig` + `UserStore::from_json` fixtures.

## Out of scope (carried to v3.9+)

- Live end-to-end walkthrough with LLM API key (BLOCKED on environment; hermetic 5/5 PASS sufficient).
- DB-backed `users` table (D-01 of 03.8.1 plan).
- Multi-role per user.
- Refresh-token jti rotation (D-04 simplification retained in v3.8).
- Shared `TokenBlacklist` backend for multi-instance deployments.
- Full route-catalog wiring of `requires(Action)` on every endpoint (03.8.2 demonstrated on 3 routes).
- Constant-time `verify_credentials` fallback.
- SSO / SAML / OIDC / OAuth2.
- v3.8 milestone close / archive (per user instruction 2026-07-24: stop after phase completion).
- Push of unpushed commits on `main` (4 commits ahead of origin/main; decision deferred to user).

## Notes for v3.8 milestone close (when user authorises)

- All four v3.8 SUMMARY files exist under `.planning/phases/03.8.*/` and this wrapper directory.
- `gsd-complete-milestone` should be run with the appropriate milestone flag.
- The wrapper directory `01-docs-uat-walkthrough-regression-sweep/` should be renamed/linked to `03.8.3-docs-uat-regression/` for archive consistency, OR annotated in the milestone close summary as a wrapper.

## Self-Check: PASSED

- [x] `01-01-PLAN.md` exists (164 lines, 8.7K)
- [x] `01-01-SUMMARY.md` exists (this file)
- [x] `docs/cli/USER_GUIDE.md` exists with §11 (1577 lines, +265 from baseline)
- [x] `docs/status/PRODUCTION_USABILITY_2026-07-24.md` exists (397 lines)
- [x] `.planning/ROADMAP.md` updated (v3.8 SHIPPED)
- [x] `.planning/STATE.md` updated (phase-complete)
- [x] `.planning/REQUIREMENTS.md` updated (5 checkboxes ticked)
- [x] All 5 commit hashes present in `git log`:
  - 260e770f (plan)
  - 49b73292 (USER_GUIDE §11)
  - f65cf770 (walkthrough)
  - 4248eb1d (count correction)
  - 70157420 (planning state)
- [x] All 33 v3.8 hermetic tests PASS
- [x] All 44 auth unit tests PASS
- [x] All 3 agent::tenant unit tests PASS
- [x] All 39 audit unit tests PASS

## Reference pointers

- **§11 operator + user docs**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/docs/cli/USER_GUIDE.md` §11
- **Dated walkthrough**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/docs/status/PRODUCTION_USABILITY_2026-07-24.md`
- **Plan**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/.planning/phases/01-docs-uat-walkthrough-regression-sweep/01-01-PLAN.md`
- **JWT primitive code**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/crates/grid-engine/src/auth/config.rs`
- **Login/refresh/logout handlers**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/crates/grid-server/src/api/auth.rs`
- **RBAC middleware**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/crates/grid-server/src/middleware/auth.rs`
- **TenantContext::for_multi_user**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/crates/grid-engine/src/agent/tenant.rs:27`
- **Role × Action matrix**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/crates/grid-engine/src/auth/roles.rs:69`
- **UserStore**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/crates/grid-engine/src/auth/user_store.rs`
- **TokenBlacklist**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/crates/grid-engine/src/auth/token_blacklist.rs`
- **Earlier SUMMARY docs**: `03.8.0-SUMMARY.md`, `03.8.1-SUMMARY.md`, `03.8.2-SUMMARY.md` under `.planning/phases/03.8.*/`
- **Security hotfixes**: commits `7f08ac53` (blacklist bypass + refresh-stale-claim) and `4b6a3539` (audit IDOR)
- **v3.7.3 walkthrough template**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/.claude/worktrees/agent-a93389b41dbe4a8e3/docs/status/PRODUCTION_USABILITY_2026-07-23.md`
