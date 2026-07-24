---
type: resume-baton
milestone: v3.8 (grid-server multi-user login — user-deferred from v3.7.4 on 2026-07-19)
next_focus: Phase 03.8.3 — Docs + UAT walkthrough + regression sweep
date: 2026-07-24
author: Claude (claude-opus-4-8) via Claude Code CLI
related: gsd-resume-work
---

# Next-Session Handoff

> Updated: 2026-07-24 end of session (climb-mode closed cleanly).

## TL;DR

1. **v3.8 ladder: 03.8.0 ✅ / 03.8.1 ✅ / 03.8.2 ✅ SHIPPED + 3 security hotfixes shipped** (2 from the 03.8.1 endpoint commit; 1 from the 03.8.2 AUDIT-02 commit). 03.8.3 (docs + UAT + regression) is the next climb.
2. **Immediate next action:** spawn Phase 03.8.3 (docs + walkthrough + regression). Per `feedback_no_full_tests` discipline: ASK before running the full `cargo test --workspace` if 03.8.3 changes nothing test-touching.
3. **Optional sidequests** (only do these if the user says so or they fall inside the climb):
   - Audit the rest of the route catalog for `requires(Action)` annotations (a Phase 03.8.2 deferred-task note in the plan).
   - Run a live walkthrough with API keys (currently BLOCKED on missing `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`).
4. **Push the 4 unpushed commits on `main`** (`main...origin/main [ahead 4]`) — push decision deferred to user.

## Where things stand

| Phase | Status | Requirements closed | Hermetic tests |
|-------|--------|---------------------|----------------|
| **03.8.0** | ✅ SHIPPED | AUTH-01, AUTH-04, AUTH-05 | 9 |
| **03.8.1** | ✅ SHIPPED (+2 security hotfixes) | AUTH-02, AUTH-03, AUDIT-01 | 7 |
| **03.8.2** | ✅ SHIPPED (+1 security hotfix) | RBAC-01..04, SESSION-01..03, TENANT-03, AUDIT-02 (+TENANT-01/02 transitively) | 10 |
| **03.8.3** | ⏳ NEXT | DOC-01..03 + TEST-01..06 | — |

**Total v3.8 hermetic coverage: 34/34 PASS across all 4 suites.**
**Audit infrastructure: 39/39 grid-engine audit tests PASS.**
**Working tree: clean (no uncommitted changes).**

## What this climb-mode session delivered (high level)

- **03.8.0 JWT primitive** — 6 atomic commits + plan; `mint_jwt`/`validate_jwt` symmetric pair, HS256 with `MIN_JWT_SECRET_BYTES=32`, `try_from_env()` strict-by-default, JwtClaims carries tenant_id+role+jti.
- **03.8.1 Login/Refresh/Logout + Audit** — 8 atomic commits + 2 security hotfixes; UserStore (Argon2id), TokenBlacklist (in-memory), login/refresh/logout HTTP handlers, AppState wiring, migration v14 (audit tenant_id/role columns), audit middleware reads Extension<JwtClaims>, two security hotfixes for blacklist bypass + refresh-stale-claim.
- **03.8.2 RBAC + Tenant + AUDIT-02** — 6 atomic commits + 1 security hotfix; `TenantContext::for_multi_user`, JWT-aware RBAC middleware path, tenant-scoped `SessionStore` accessors with `TenantSessionResult` enum, AUDIT-02 cross-tenant escape hatch, and a security hotfix after the IDOR showed the prior implementation only enforced Owner when `cross_tenant=true` was set.

## Security-review findings — all addressed

| # | Severity | Subsystem | Commit | Fix |
|---|----------|-----------|--------|-----|
| 1 | CRITICAL | `auth` middleware blacklist bypass | `7f08ac53` | Full middleware now consults `config.token_blacklist` after `validate_jwt`; logged-out JWTs rejected on every protected endpoint |
| 2 | HIGH | `/refresh` stale-claim | `7f08ac53` | Refresh reads role + tenant_id from UserStore (not from old JWT claims); new jti minted, old token still valid until exp per D-04 |
| 3 | HIGH | `/audit` IDOR | `4b6a3539` | `list_audit` now derives tenant scope from `claims.tenant_id` unconditionally; new `query_for_tenant` + `count_for_tenant` enforce `tenant_id = ?` in SQL |

All three have regression tests proving the fix.

## What landed in v3.8.2 (this session tail)

### Code
- **`TenantContext::for_multi_user(tenant_id, user_id, role)`** in `crates/grid-engine/src/agent/tenant.rs` (engine-side; per ADR-V2-023 P1).
- **`require_action_middleware`** in `crates/grid-server/src/middleware/auth.rs` now has a JWT-aware path that reads `Extension<JwtClaims>`, parses role, builds `TenantContext::for_multi_user`, enforces `Role::can(action)`. Legacy `UserContext::has_permission` path preserved for AuthMode::None / ApiKey (D-08 single-user semantics).
- **Tenant-scoped `SessionStore` accessors**: `get_session_for_tenant(...) -> TenantSessionResult { Ok | TenantMismatch | NotFound }` + `list_sessions_for_tenant(...)`. Default impls compose on the existing user-scoped methods; production deployments with explicit tenant columns should override.
- **`AuditStorage::query_for_tenant` + `count_for_tenant`** (security hotfix): SQL `WHERE tenant_id = ?`. Un-scoped `query`/`count` retained for the Owner cross-tenant path and the AuthMode::None / ApiKey fallback.
- **`list_audit` handler** in `crates/grid-server/src/api/audit.rs` rewritten to unconditionally derive scope from `claims.tenant_id`; the un-scoped path is reached ONLY for Owner + `?cross_tenant=true`. Every cross_tenant attempt (Owner or not) writes a SECURITY audit row.
- **`AuthConfig.token_blacklist: Option<Arc<TokenBlacklist>>`** — added in the 03.8.1 hotfix (`7f08ac53`), wired into the AppState's `auth_config` so the Full-mode middleware consults it on every request. `Default` sets it to `None`. A `derive(Debug)` was added to `TokenBlacklist` to keep `AuthConfig: Debug`.

### Tests
- `crates/grid-server/tests/multi_user_rbac_tenant.rs` — 10 hermetic tests (9 phase tests + 1 hotfix regression test `audit_02_non_owner_cannot_enumerate_other_tenants_audit`). Covers RBAC-01..04 + SESSION-02/03 + TENANT-03 + the hotfix's IDOR proof.
- 3 inline unit tests in `crates/grid-engine/src/agent/tenant.rs` (multi_user_admin / viewer / owner).
- All 34/34 v3.8 hermetic tests PASS across `multi_user_jwt` + `test_auth_modes` + `multi_user_auth_endpoints` + `multi_user_rbac_tenant`.

### Doc
- **`docs/.../03.8.2-SUMMARY.md`** (this phase summary).
- **`.planning/STATE.md`** points at 03.8.3 as the next phase.

## What's left in the climb

### Phase 03.8.3 — Docs + UAT walkthrough + regression sweep

Per the original v3.8 plan in `.planning/phases/03.8.2-rbac-tenant/03.8.2-01-PLAN.md §3.8.3 deferred`, this phase ships:

- `USER_GUIDE.md` §11 multi-user mode (login flow, JWT mint, refresh, logout, RBAC matrix reference) — **DOC-01**
- Operator env-var reference: `GRID_MODE`, `GRID_JWT_SECRET`, `GRID_TOKEN_TTL_SECS`, `GRID_USERS_JSON` — **DOC-02**
- `PRODUCTION_USABILITY_2026-07-2X.md` dated walkthrough with 5 scenarios:
  - (1) login; (2) cross-tenant block; (3) role escalation block;
  - (4) refresh; (5) logout — **DOC-03 + TEST-05**
- **TEST-06**: regression sweep across full v3.7 baseline (175 tests) — ASK before running per `feedback_no_full_tests`.

### Optional sidequests

1. **Audit the route catalog for `requires(Action)` annotations.** Phase 03.8.2 deliberately demos `requires()` on three representative routes only (`/admin/users`, `/audit`, `/sessions/{id}`); wiring every endpoint is explicitly deferred to v3.9+ per the plan §Task 4. A future phase could add a route-catalog auditor test that fails on any unprotected mutating route.

2. **Live walkthrough.** Currently `LIVE BLOCKED` on missing API keys per the v3.7 precedent. If the user provides one, swap the hermetic-only tests for real LLM transcripts.

3. **Push 4 unpushed commits on `main`.** Per established v3.7 precedent, push decision is the user's; they may want to review `4b6a3539` (the recent security hotfix) before pushing.

4. **Close v3.8 milestone** (Task #67 is pending). Per `gsd-complete-milestone`: archive phase directories, write a milestone-level summary, tag if release-ready. This is naturally the LAST step after 03.8.3 ships.

## Reference pointers

- **Canonical project status**: `.planning/STATE.md`
- **v3.8 requirements**: `.planning/REQUIREMENTS.md` (v3.8 section)
- **Phase plans**:
  - `.planning/phases/03.8.0-jwt-primitive/03.8.0-01-PLAN.md` + `03.8.0-SUMMARY.md`
  - `.planning/phases/03.8.1-auth-endpoints/03.8.1-01-PLAN.md` + `03.8.1-SUMMARY.md`
  - `.planning/phases/03.8.2-rbac-tenant/03.8.2-01-PLAN.md` + `03.8.2-SUMMARY.md`
- **CLAUDE.md (project root)**: `CLAUDE.md` — global rules, test discipline, lock-failure-handling policies
- **Auto-memory**: `~/.claude/projects/-Users-sujiangwen-sandbox-LLM-speechless-ai-SGAI-grid-sandbox/memory/MEMORY.md`
- **Project Status overview**: `docs/PROJECT_PRODUCT_OVERVIEW.md`
- **Phase archive target (next milestone close)**: `.planning/milestones/v3.8-ROADMAP.md` (created by `gsd-complete-milestone`)

## Don't go down these paths again (ruled out)

- **Full `cargo test --workspace` as a default action.** Per `feedback_no_full_tests`: targeted tests only, ASK before full runs.
- **Adding per-tenant storage / multi-role provisioning.** v3.9+ scope per 03.8.2 plan §Out of scope.
- **Refresh-token rotation (revoke old jti on refresh).** v3.9+ per 03.8.1 plan §Out of scope (D-04: single-token sliding expiration).
- **OAuth2 / SSO / SAML / OIDC.** v3.9+ per 03.8.1 plan §Out of scope.
- **Demo-ing every route's RBAC.** v3.8.2 demonstrated on 3 routes; rest deferred to v3.9+.

## Ready-to-paste commands / configs

```bash
# v3.8.3 bootstrap
/gsd-discuss-phase 3.8.3

# Or jump straight into execution per the proven v3.8 climb pattern:
/gsd-new-milestone --phase 3.8.3

# Live walkthrough (if API keys provided)
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
cargo run --bin grid -- quickstart S1

# Resume on next session (recommended command)
/gsd-resume-work

# Verify the AUDIT-02 hotfix end-to-end (current session's last work)
/bin/sh -c 'cd ... && cargo test -p grid-server --features grid-server/testing --test multi_user_rbac_tenant audit_02_non_owner_cannot_enumerate_other_tenants_audit -- --test-threads=1'

# Push (decision deferred to user)
git push origin main
```
