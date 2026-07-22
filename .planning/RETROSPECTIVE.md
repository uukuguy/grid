# Project Retrospective

## Milestone: v3.7 — 实战可用性补全 (Production-Usability Closure)

**Shipped:** 2026-07-23
**Phases:** 3 shipped (3.7.1 / 3.7.2 / 3.7.3) + 1 SKIPPED (3.7.4 → v3.8)
**Plans:** 7 (3.7.1: 3, 3.7.2: 2, 3.7.3: 2)
**Tasks:** 18 total
**Git range:** `3a85a06c` → `dbb6588c` (50 commits, 76 files, 17,095 insertions)
**Calendar:** 2026-07-19 → 2026-07-23 (4 days)

### What Was Built

- **Phase 3.7.1 grid-cli 实战可用性** — `grid quickstart <scenario>`, `grid session resume`, `grid run --parallel`, error UX per D-05..D-07, 12 doctor checks (Hooks File + Eval Bridge), 8/9 REQ-AUDITs closed, S1-S5 walkthrough docs
- **Phase 3.7.2 web/ dashboard 实战化** — WS auto-reconnect, SessionControls global, memory_added toast, seq field, Live badge, 9 REQ-WEB items closed, UI-SPEC 7/7, auditor 8.83/10, S7 walkthrough
- **Phase 3.7.3 EAASP 本地仿真补全 (Phase 3 governance hooks)** — Risk classification taxonomy (Rust + Python), L3 `PolicyEngine.evaluate_gate()` + `governance_decisions` ledger, L4 `governance.request`/`governance.decision` SSE events, CLI `--yes`/`--no` + interactive approval, deterministic S8 mock-SCADA scenario, 8/8 REQ-EAASP-01..08 closed

### What Worked

- **Auto-advance chain `discuss → plan → execute → verify → milestone-close`** ran flat across 5 skills (gsd-discuss-phase → gsd-plan-phase → gsd-execute-phase → gsd-complete-milestone) without intermediate user checkpoints. All decisions captured in CONTEXT.md upfront (D-01..D-10), enabling plan-checker to PASS with 0 blockers on first try.
- **CONTEXT.md canonical_refs pre-mapped** the read set for planner + executor — no scout detour needed in plan-phase. Reused 3.7.1 + 3.7.2 phase artifacts (CONTEXT.md, SUMMARY.md patterns) for pattern consistency.
- **Pyright false-positive acceptance**: `reportArgumentType "str | None" → str` warnings on `record_governance_decision()` SQLite ROW access are runtime-safe (CHECK constraints guarantee non-NULL); runtime tests 131/131 PASS verify. Per memory `feedback_phase5_4_sub_details` Fact 5: "Pyright on `lang/claude-code-runtime-python/` 有真假诊断".
- **Hermetic S8 test** fully exercises the production code paths (`evaluate_gate → audit row → approve → tool side effect`) without requiring live LLM API key. Aligns with CLAUDE.md §Runtime Verification Tasks.
- **Backward compat preserved** (D-07): default `risk_level = "read"` + default `mode = "enforce"` keeps all 12 pre-existing L3 tests, 14 EAASP Python runtime tests, 5 cli-v2 tests untouched. New gate activates only when skill manifest declares `risk_level != "read"` AND L3 not in shadow override.

### What Was Inefficient

- **gsd-tools `milestone complete` scanned wrong milestone heading** (v3.6 instead of v3.7), producing 0 phases / 0 plans / 0 tasks in the entry. Had to manually supplement `MILESTONES.md` with actual stats + accomplishments. **Pattern for next milestone**: if analyzer misfires, always verify output counts before trusting them.
- **`roadmap analyze` shows latest milestone heading only** — the actual archive to `milestones/v3.7-ROADMAP.md` succeeded (20.2K file), but the analyzer JSON would mislead anyone trying to verify milestone completion programmatically.
- **No REQUIREMENTS.md** in this project (CLAUDE.md convention uses D-XX + REQ-EAASP-NN instead). Means `phase complete` warnings about "STATE.md field not found" are harmless and can be ignored.
- **Two-step CLAUDE.md `userEmail` hard-rule check** was necessary mid-execution (per memory `Identity & Email Sources` rule). No `Co-Authored-By: ...@fastmail.com` slipped in — commit footer correctly used `claude-opus-4-8` and `ruv@ruv.net`.

### Patterns Established

- **Risk-classified action gating** = reusable pattern for any "action with side effects requires human approval" future feature. The L3 `evaluate_gate()` + L4 SSE + CLI approval UX is composable; future phases (e.g., C1 Phase 3 production OPA) can replace the in-process gate with HTTP OPA calls without changing the CLI or L4 contract.
- **`gd_<uuid>` request + `gd_<uuid>_final` final ledger PK pattern** = two-row append-only audit where the request row is written first (decision_id PRIMARY KEY), then a second row with `_final` suffix captures the user's approval/denial. Both rows in same `BEGIN IMMEDIATE` txn. Clean separation of "pending" vs "resolved" governance decisions.
- **Mock-SCADA deterministic fixture** (xfmr-042/temperature_limit_c=70.0) is reusable for future Phase 4 A2A / Phase 5 L5 UI tests that need a stable external system target.

### Key Lessons

1. **Plan-checker 0-blocker on first iteration** correlates strongly with thorough CONTEXT.md upfront. Future phases: invest in CONTEXT.md canonical_refs and D-XX decisions BEFORE spawning planner.
2. **Hermetic test coverage of side-effect code paths** is acceptable per CLAUDE.md §Runtime Verification Tasks when LLM API key absent. Don't gate completion on live LLM when hermetic test exercises the same code paths.
3. **Pyright false positives for SQLite ROW access** are project-wide noise. Suppress via `# type: ignore[reportArgumentType]` on the row unpack line OR add explicit `cast(str, row[0])`. Phase 3.7.3 chose neither (acceptable per existing project convention; runtime tests verify safety).
4. **gsd-tools analyzer can misfire on multi-milestone ROADMAP.md** — always verify the JSON counts before treating them as authoritative. Manual supplement of `MILESTONES.md` entry was necessary.
5. **Phase-completion commit footer pattern** (the two GSD-generated lines) is non-negotiable per CLAUDE.md. Verified across all 12 v3.7 commits — no drift.

### Cost Observations

- **Sessions:** 1 single session from `/clear` → `gsd-resume-work` → `/gsd-complete-milestone v3.7`. ~7 hours wall-clock equivalent (estimated from commit timestamps + plan/executor durations: 18 min Plan 01 + 38 min Plan 02 + 18 min verifier + ~2 hours orchestration overhead).
- **Subagents spawned:** 5 (planner + plan-checker + 2 executors + verifier). All `gsd-*` specialized agents.
- **Human checkpoints required:** 0 (auto-advance chain end-to-end).
- **Notable efficiency:** Plan 02 executor's 165 tool uses for 3 tasks / 19 files is on the high side — the executor did multiple rounds of test-running + cargo check + assertion verification. Acceptable for a 19-file plan; would be a concern for larger scopes.

---

## Cross-Milestone Trends

| Milestone | Plans | Commits | LOC Δ | Tests Δ | Wall-clock |
|-----------|------:|--------:|------:|--------:|-----------:|
| v3.5 Debt Finalization | 3 | ~30 | ~5000 | +0 (debt era) | 1 day |
| Grid Activation (A.0–A.8) | ~30 | ~80 | ~30000 | +200 | 1 day (parallel) |
| v3.6 Docs Sync | 7 | 7 | +500 (docs) | +0 | 1 session |
| **v3.7 Production-Usability** | **7** | **50** | **+17095** | **+175** | **4 days** |