---
type: resume-baton
milestone: v3.7 (SHIPPED + ARCHIVED 2026-07-23)
next_focus: v3.8 candidate scope decision
date: 2026-07-23
author: Claude (claude-opus-4-8) via Claude Code CLI
---

# Next-Session Handoff

> Updated: 2026-07-23 end of session.

## TL;DR

1. **v3.7 milestone SHIPPED + ARCHIVED 2026-07-23** — 3 phases (3.7.1 grid-cli / 3.7.2 web/ / 3.7.3 EAASP 本地仿真); 3.7.4 grid-server multi-user SKIPPED per user 2026-07-19 → deferred to v3.8
2. **Immediate next action:** User picks v3.8 candidate scope (5 options: A web-platform/ 7.5→9.0, B grid-desktop 6.5→9.0, C1 Phase 3 OPA, C2 Phase 4 A2A, C3 Phase 5 L5, C4 Phase 6 ecosystem, OR grid-server multi-user login)
3. **4 commits unpushed** on `main` (`main...origin/main [ahead 4]`) — push decision deferred to user; v3.7 tag (`v3.7`) already pushed

## Where things stand

- **Latest shipped milestone:** v3.7 实战可用性补全 (Production-Usability Closure) ✅
- **Tests:** 175/175 PASS across milestone (Phase 3.7.1: 14+7+9 / Phase 3.7.2: 26+5 / Phase 3.7.3: 136)
- **Commits:** 50 in v3.7 range (`3a85a06c` → `e18081af`); plus 2 close-out commits + 1 state record + 1 worklog = 54 total this milestone
- **Archive:** `.planning/milestones/v3.7-ROADMAP.md` (20.2K), `.planning/MILESTONES.md` entry supplemented, `.planning/RETROSPECTIVE.md` created, `.planning/PROJECT.md` evolved
- **Working tree:** clean
- **Branch:** `main` (no phase branches per `branching_strategy: none`)

## What this session delivered

### Phase 3.7.1 grid-cli 实战可用性 (SHIPPED 2026-07-19)
- `grid quickstart <scenario>` + `grid session resume` + `grid run --parallel` + error UX per D-05..D-07
- 12 doctor checks (incl. Hooks File + Eval Bridge)
- 14/14 hermetic scenario integration tests + 7/7 unit tests + 9/9 doctor checks
- 8/9 REQ-AUDITs closed (88.9%)
- S1-S5 walkthrough docs + dated `PRODUCTION_USABILITY_2026-07-19.md`

### Phase 3.7.2 web/ dashboard 实战化 (SHIPPED 2026-07-21)
- WS auto-reconnect + SessionControls global + memory_added toast + seq field + Live badge
- 9 REQ-WEB items closed; UI-SPEC 7/7; auditor 8.83/10
- 26/26 vitest + 5/5 Playwright E1-E3
- S7 walkthrough doc + operation guides in USER_GUIDE §10

### Phase 3.7.3 EAASP 本地仿真补全 (SHIPPED 2026-07-23, this climb session)
- Risk classification taxonomy (`read | write_local | write_external`) in Rust + Python, backward-compatible default `read`
- L3 `PolicyEngine.evaluate_gate()` decision matrix (risk × mode)
- Append-only `governance_decisions` ledger (9 cols + 2 CHECK constraints + `gd_<uuid>` / `gd_<uuid>_final` PK pattern, `BEGIN IMMEDIATE` transactions)
- L4 `governance.request` + `governance.decision` SSE events (best-effort)
- CLI `--yes` / `--no` flags + interactive `Approve? [y/N]` prompt; exit code 4 on deny
- Deterministic `scada_set_setpoint` mock-SCADA skill with `risk_level: write_external`
- S8 walkthrough doc (300 lines) + dated `PRODUCTION_USABILITY_2026-07-23.md` (300+ lines) with honest `LIVE BLOCKED` label
- 136/136 tests PASS (L3 76 + L4 events 11 + CLI 18 + mock-SCADA 19 + Rust skill-parser 12)
- `cargo check --workspace` 0 errors, 16 pre-existing warnings
- 8/8 REQ-EAASP-01..08 closed
- All 10 locked decisions (D-01..D-10) honored

## Next steps (immediate, action-level)

1. **User decision: pick v3.8 candidate scope** — Options per `.planning/PROJECT.md` §Active:
   - **grid-server multi-user** (user 2026-07-19 explicit deferral from 3.7.4) — RBAC + JWT tenant scoping + cross-user session isolation
   - **A** web-platform/ Quality 7.5→9.0
   - **B** grid-desktop Quality 6.5→9.0
   - **C1** Phase 3 production OPA backend
   - **C2** Phase 4 A2A + Event Room
   - **C3** Phase 5 L5 Cowork UI
   - **C4** Phase 6 ecosystem expansion

   Recommended priority per ADR-V2-024 Open Item #3 (grid-cli + grid-server first; both at 9.0+ already, so grid-server multi-user is the natural axis extension) — but user may prefer Quality gap closure first.

2. **Optional:** Push 4 unpushed commits to `main`:
   ```bash
   git push origin main
   ```

3. **Optional:** Re-run live walkthrough with `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` to upgrade `PRODUCTION_USABILITY_*.md` from hermetic evidence to real transcripts (S1-S8 all currently show `LIVE BLOCKED` honestly per CLAUDE.md §Runtime Verification Tasks).

## Don't go down these paths again (ruled out)

- **Full Phase 3 production OPA backend** — deferred to v3.8+; v3.7.3 wires minimum credible in-process gate only. **Reasoning:** 4-day milestone scope discipline; in-process gate demonstrates governance observability; OPA sidecar is multi-week work
- **Multi-party approval chains** — v3.8+. **Reasoning:** v3.7.3 single-user interactive prompt is enough for credibility evaluation
- **L3 HTTP approval endpoints** — explicitly out per D-06. **Reasoning:** CLI is the gate client for v3.7.3; L4 SSE carries the request/decision events for future L5 consumers without needing HTTP endpoints now
- **Sandbox tier enforcement** — Phase 3 scope per EVOLUTION_PATH; ADR-V2-005 exists but sandbox tier wiring is future. **Reasoning:** orthogonal to gate logic; separate scope
- **L1 / proto changes** — explicitly forbidden per D-07 backward compat. **Reasoning:** preserves L1 substitutability per ADR-V2-006 + `contract-v1.2.0`

## Ready-to-paste commands / configs

```bash
# v3.8 candidate scope decision + start
/gsd-new-milestone

# Push unpushed commits
git push origin main

# Live walkthrough (requires API keys)
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
cargo run --bin grid -- quickstart S1
eaasp session run -s scada-set-setpoint -r grid-runtime "..."

# Resume on next session
/gsd-resume-work
```

## Reference pointers

- **v3.7 archive:** `.planning/milestones/v3.7-ROADMAP.md`
- **MILESTONES.md entry:** `.planning/MILESTONES.md` §"v3.7 实战可用性补全"
- **Retrospective:** `.planning/RETROSPECTIVE.md` §"Milestone: v3.7 — 实战可用性补全"
- **PROJECT.md:** `.planning/PROJECT.md` (evolved with v3.7 → Validated, v3.8 candidate → Active)
- **ROADMAP.md:** `.planning/ROADMAP.md` (v3.7 collapsed to one-line entry with archive link)
- **Work log:** `docs/dev/WORK_LOG.md` (5 GSD adoption notes prepended)
- **Per-phase artifacts:**
  - `.planning/phases/03.7.1-grid-cli/3.7.1-{CONTEXT,DISCUSSION-LOG,01-PLAN,01-SUMMARY,02-PLAN,02-SUMMARY,03-PLAN,03-SUMMARY}.md`
  - `.planning/phases/03.7.2-web-production/03.7.2-{CONTEXT,DISCUSSION-LOG,UI-SPEC,VERIFICATION,01-PLAN,01-SUMMARY,02-PLAN,02-SUMMARY}.md`
  - `.planning/phases/03.7.3-eaasp-phase-0-2-5-phase-3-governance-hooks/03.7.3-{CONTEXT,DISCUSSION-LOG,01-PLAN,01-SUMMARY,02-PLAN,02-SUMMARY,VERIFICATION}.md`
- **Implementation files:** see `git log --stat 04e4a8fb..e18081af` (50 commits in v3.7 range)
- **Dated evidence:** `docs/status/PRODUCTION_USABILITY_2026-07-19.md` (3.7.1), `WEB_PRODUCTION_USABILITY_2026-07-20.md` (3.7.2), `PRODUCTION_USABILITY_2026-07-23.md` (3.7.3)