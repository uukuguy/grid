# Phase 5.3 deferred-items (out-of-scope discoveries during execution)

> Logged per execute-plan workflow scope-boundary rule: only auto-fix
> issues directly caused by current task's changes; everything else
> goes here for orchestrator triage.

## Pre-existing issues observed (NOT caused by 05.3-01)

### grid-cli lib references missing `output` module
- **Discovered:** Task 5.3-01-05 verification (`cargo check --workspace`)
- **Symptom:** `error[E0583]: file not found for module \`output\`` at
  `crates/grid-cli/src/lib.rs:20`
- **Pre-existing:** Confirmed via `git stash` test 2026-05-20 — the
  error reproduces against the worktree base commit
  `c0af57a653cae9713d3d7d3c3b810ab25d3ab0ab` without any 05.3-01
  edits applied.
- **Scope:** Unrelated to CONTRACT-01/02; appears to be a
  feature-flag mismatch (perhaps `output.rs` lives behind `--features
  studio` only and the top-level mod declaration didn't get gated).
- **Action:** Logged for follow-up phase (e.g., 5.4 infra hardening
  cluster), not fixed here.
