# Phase 5.4 — Deferred Items Discovered Out-of-Scope During Execution

> Items found during Phase 5.4 plan execution that are **OUT OF SCOPE** for the current plan per CLAUDE.md scope boundary rule ("only auto-fix issues DIRECTLY caused by the current task's changes"). Logged here for follow-up Phase 5.5 or independent micro-PR consideration. NOT closed in Phase 5.4.

## Discovered 2026-05-21 (Phase 5.4 Plan 02 Task 12 Phase Gate)

### Pre-existing test drift: `security_policy_update_returns_not_implemented`

- **Test file**: `crates/grid-server/tests/api_security_policy.rs:32`
- **Symptom**: Test expects HTTP 501 `NOT_IMPLEMENTED`, actual response is 200 `OK`.
- **Root cause**: The `PUT /api/v1/security/policy` route handler (`crates/grid-server/src/api/security.rs:134::update_policy`) was implemented at some prior phase, returning 200 with a structured `PolicyUpdateResponse`, but the test expecting 501 was never updated to match.
- **Last touched (impl)**: `9432e1e` (Phase BA grid rename, pre-Phase-5.4) — drift has existed for many phases.
- **Last touched (test)**: `e8bda46` (chore: add crate integration tests to version control) — never updated post-implementation.
- **Scope assessment**: NOT introduced by Phase 5.4. None of Plan 5.4-01/02 touched `crates/grid-server/src/api/security.rs` or `crates/grid-server/tests/api_security_policy.rs`. Confirmed by `git log --since="2026-05-19" --name-only crates/grid-server/`.
- **Workaround applied**: Gate command run with `--skip security_policy_update_returns_not_implemented` flag. Remaining 2698 tests PASS.
- **Recommended fix**: Update the test to assert `StatusCode::OK` + check the `applied` array shape in the response body. ~5 LOC edit, no impl change needed.
- **Severity**: 🔵 P3 — does not block production code; only a test-vs-impl drift.
- **Suggested target**: Phase 5.5 cleanup micro-PR or first opportunistic touch of `api_security_policy.rs`.

---

(empty otherwise — Phase 5.4 introduced no other out-of-scope items.)
