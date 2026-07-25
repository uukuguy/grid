# Current State

## Project Snapshot

- Project: Grid — agent runtime stack and Grid independent product
- Current branch: `main`
- Theme-level focus: v3.8 shipped; define the next product milestone
- Project route: managed
- Canonical worklist: `.planning/ROADMAP.md`
- Active work package: none (milestone boundary)

## Current Architecture

- Shared engine: `grid-engine` / `grid-runtime` / `grid-types` provide the EAASP-compatible L1 runtime surface.
- Grid server: `crates/grid-server/` provides the independent-product HTTP/WS workbench, including AuthMode, JWT, RBAC, tenant scoping, sessions, and audit.
- Client and product surfaces: `grid-cli`, `web/`, `web-platform/`, `grid-desktop`, and `grid-platform`.
- Planning state: `.planning/STATE.md`, `.planning/ROADMAP.md`, and archived milestone artifacts under `.planning/milestones/`.

## Open Problems

- Next milestone scope is not selected after v3.8 closure.
- Full route-catalog `requires(Action)` coverage and an auditor remain candidates for follow-on work.
- `web-platform/` and `grid-desktop` remain below the 9.0 quality bar.
- EAASP Phase 3–6 platform evolution remains future work.

## Key Files

### Loaded every Claude session
- `CLAUDE.md`
- `/Users/sujiangwen/.claude/projects/-Users-sujiangwen-sandbox-LLM-speechless-ai-SGAI-grid-sandbox/memory/MEMORY.md`

### State / handoff
- `docs/status/RESUME-NEXT-SESSION.md` — current session baton
- `docs/status/CURRENT-STATE.md` — structural snapshot
- `.planning/STATE.md` — GSD milestone state
- `.planning/ROADMAP.md` — canonical milestone worklist

### Implementation entry points
- `crates/grid-server/src/middleware/auth.rs` — JWT/AuthMode/RBAC middleware
- `crates/grid-server/src/api/` — server route handlers and authorization boundaries
- `crates/grid-engine/src/auth/` — shared roles, permissions, and auth configuration
- `crates/grid-engine/src/agent/tenant.rs` — tenant context and isolation primitives

## Resume Instructions

1. Read this file for the structural baseline.
2. Read `docs/status/RESUME-NEXT-SESSION.md` for session intent.
3. Read `.planning/STATE.md` and `.planning/ROADMAP.md` for milestone status.
4. Run `git status --short` and `git log --oneline -5`.
5. Read `CLAUDE.md` and the auto-loaded project memory before implementation.
