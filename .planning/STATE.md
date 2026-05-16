---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: Phase 5 — Engine Hardening (grid-cli + grid-server)
status: executing
stopped_at: Phase 5.2 mid-execution (9/19 tasks) — paused for deepseek-chat shakedown + ExecutionMode design
last_updated: "2026-05-16T09:00:00.000Z"
last_activity: 2026-05-16 -- DeepSeek provider + ExecutionMode gate landed; Phase 5.2 still 9/19
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 3
  completed_plans: 2
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-29)

**Core value:** Grid 作为 substitutable L1 runtime,通过 16-method gRPC contract 被 EAASP L2-L4 调用,且任何符合 contract-v1.1 的对比 runtime 都能替换它。
**Current focus:** Phase 05.2 — cli-hardening

## Current Position

Phase: 05.2 (cli-hardening) — EXECUTING
Plan: 1 of 1
Next phase: 5.2 (CLI Hardening) — ready to plan
Status: Executing Phase 05.2
Last activity: 2026-05-04 -- Phase 05.2 execution started

Progress: [▓▓▓░░░░░░░] 33% (2/6 milestone phases complete — 5.0 + 5.1)

**Previous milestone closure**: Phase 4 milestone v3.0 ✅ CLOSED 2026-04-28 — 3/3 phases (4.0/4.1/4.2), ADR-V2-024 Accepted (双轴模型), 16 commits pushed to origin/main.

## Performance Metrics

**Velocity:**

- Total plans completed (executed): 3 ✅
- Total plans planned (ready to execute): 0
- Average duration: ~75 min (Phase 4.0 ~25 min mechanical + Phase 4.1 ~3.5h audit + 4 plan iterations + cross-AI review)
- Total execution time: ~4h cumulative

**By Phase:**

| Phase | Plans | Status | Notes |
|-------|-------|--------|-------|
| 4.0 Bootstrap & Cleanup | **1/1 ✅** | COMPLETE 2026-04-27 (5 commits + SUMMARY) | 5/5 SC PASS, 7/7 must-haves PASS, 0 deviations |
| 4.1 Discuss & Audit | **1/1 ✅** | COMPLETE 2026-04-27 (8 commits + SUMMARY + VERIFICATION) | 14/15 must-haves PASS, SC#4 GOVERNANCE-03 deferred per cross-AI Q4 consensus + user decision; 4-iteration plan 经过 cross-AI review (4 reviewers: claude/gemini/opencode-glm5.4/codex) + 5 fixes + B1+B2 fixes |
| 4.2 Decide & Document | **1/1 ✅** | COMPLETE 2026-04-28 (13 commits + SUMMARY + Phase Gate PASS) | 8/8 tasks PASS, 5/5 SC ✅, ADR-V2-024 Accepted (supersedes V2-023), GOVERNANCE-03 闭环 (3/3 ✓ verdict in SUMMARY §T6), audit-fidelity-grep modality 实证 (T1+T2+T3) |
| 5.0 Hook Envelope Baseline | **1/1 ✅** | COMPLETE 2026-05-19 (commit 584b1cf) | D134 GA1 resolved, stop scope test added, 11 tests PASS |
| 5.1 Runtime Tier ADR + Contract Test Parametrization | **1/1 ✅** | COMPLETE 2026-05-02 (5 task commits + SUMMARY + VERIFICATION) | 4/4 SC PASS, 4/4 must-haves PASS, NEW-D2 closed, ADR-V2-025 Accepted, CONTRACT-00 + WATCH-05 ✓ |
| 5.2 CLI Hardening | 0/TBD | Not started | Depends on 5.0 |
| 5.3 Contract Evolution | 0/TBD | Not started | Depends on 5.1 |
| 5.4 Server Hardening | 0/TBD | Not started | Depends on 5.3 |
| 5.5 Interface ADR + Milestone Close | 0/TBD | Not started | Depends on 5.4 |

**Recent Trend:**

- Last 5 plans: [05.1-01 ✅ 2026-05-02, 05.0-01 ✅ 2026-05-19, 04.0-01 ✅ 2026-04-27, 04.1-01 ✅ 2026-04-27, 04.2-01 ✅ 2026-04-28]
- Trend: design-heavy phase 跑通 — cross-AI review (4 reviewers + 7 fixes) 显著提升 audit 框架严谨性,catch 到 B1 pre-committed verdict 隐患 (T4 hardcoded "两腿都推进" 被 Path 1 fix 改成 verdict-format regex + runtime substitution)

*Updated after each plan completion*

## Phase 4.0 Final Snapshot (2026-04-27 ✅)

**Phase dir `.planning/phases/04.0-bootstrap-cleanup-gsd/` 全 7 文件:**

- `04.0-CONTEXT.md` (167 LOC) — discuss-phase 5 gray areas locked, OQ2 path correction
- `04.0-RESEARCH.md` (594 LOC) — 3 OQs resolved A/A/A
- `04.0-VALIDATION.md` (109 LOC) — 5 grep assertions + Phase Gate
- `04.0-PATTERNS.md` (391 LOC) — 5 file analogs + Phase 4a task block template
- `04.0-01-PLAN.md` (859 LOC) — 5 tasks T1-T5 verbatim substitutions, plan-checker PASSED
- `04.0-01-SUMMARY.md` (NEW 2026-04-27) — executor self-report
- `04.0-VERIFICATION.md` (NEW 2026-04-27) — verifier `## VERIFICATION PASSED` 7/7

**5 tasks 执行结果:**

- T1 CLEANUP-01 ✅ commit `54349d1` (chunk_type sweep + ADR-V2-021 marker)
- T2 CLEANUP-02 ✅ commit `a5df8bb` (D120 row-edit + close-out convention)
- T3 CLEANUP-03 ✅ commit `7b00c6c` (strategy-grid-two-leg-checklist.md NEW)
- T4 CLEANUP-04 ✅ commit `fcef926` (.github/CODEOWNERS filesystem-correct)
- T5 GOVERNANCE-01 ✅ zero-diff dry-run pass (no commit per OQ3)
- SUMMARY ✅ commit `269e373`

**实际**: 5 commits (4 cleanup + 1 SUMMARY), 命中 CONTEXT.md D-C-01 "5 下限" 预期。

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- **GSD takeover (2026-04-26)**: 接管自 dev-phase-manager + superpowers,Phase 4 起以 GSD 体系驱动,但 DEFERRED_LEDGER / WORK_LOG / ADR plugin 全部保留作 SSOT 例外
- **Milestone v3.1 granularity = 6 phases**: 在 standard 5-8 区间内偏低端, watchlist-spread strategy (8 watchlist 项分散到 5 phase) 避免单独 watchlist phase 阻塞主线
- **Quality profile (Opus) + parallelization=true**: Phase 5 plan-phase 阶段沿用 Phase 4 体系, plan-phase 评估各 phase 是否需要 parallel plans

### Pending Todos

None yet — `/gsd-add-todo` 暂未使用。

### Blockers/Concerns

- **None blocking Phase 5.0 start.** ROADMAP.md 创建后 Phase 5.0 (Hook Envelope Baseline) 进入 ready-to-plan 状态; 无前置阻塞。
- **Watchlist-spread 实操风险**(由 plan-phase 评估, 不阻塞 milestone 启动): 5.0 hook envelope baseline 修复必须先于 5.3 contract evolution 的 hook event 扩展, 5.4 server hardening 的 SERVER-03 (Stop hook 写 trajectory) 也依赖 5.0 baseline; 这两条依赖在 ROADMAP Phase Details "Depends on" 段已显式记录, plan-phase 不必再补。

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At | Phase 5 Mapping |
|----------|------|--------|-------------|-----------------|
| Functional | D109 — workflow.required_tools 不变量未文档化 | 🟠 P1, mapped to Phase 5.3 (WATCH-01) | Phase 2 S3.T2 (历史) | 5.3 |
| Functional | D120 — Rust HookContext schema 缺 event/skill_id 字段 | 🟠 P1, mapped to Phase 5.0 (WATCH-00, D134 前置) | Phase 2 S3.T5 (历史) | 5.0 |
| Functional | D134 — Shipped skill hooks read nested `.payload.output.X` 但 ADR-V2-006 §2.3 是 top-level | 🟠 P1, mapped to Phase 5.0 (WATCH-02, must-fix) | Phase 2.5 S0.T3 (历史) | 5.0 |
| Functional | D136 — grid-runtime hook 在 probe turn 不触发(3 contract xfails) | 🟠 P1, mapped to Phase 5.3 (WATCH-03) | Phase 2.5 S0.T4 (历史) | 5.3 |
| Functional | D142 — grid-runtime 不读 EAASP_DEPLOYMENT_MODE | 🟡 P1-defer, mapped to Phase 5.4 (WATCH-04) | ADR-V2-019 audit (历史) | 5.4 |
| Functional | D143 — claude-code-runtime 不读 EAASP_DEPLOYMENT_MODE + 无 max_sessions=1 gate | 🟡 P1-defer, mapped to Phase 5.4 (WATCH-04) | ADR-V2-019 audit (历史) | 5.4 |
| Contract | NEW-D2 — test_chunk_type_contract.py 仅 3 tests,not 7-runtime parametric | 🟠 P1, mapped to Phase 5.1 (WATCH-05) | Phase 4a project review | 5.1 |
| ADR | NEW-E2 — F3 reports 29 missing `enforcement.trace` items | 🟡 advisory, mapped to Phase 5.5 (WATCH-06) | Phase 4a session-04-26 audit | 5.5 |
| ADR | NEW-E3 — ADR-V2-019 still Proposed, blocks on D142+D143 | 🟡 advisory, mapped to Phase 5.4 (WATCH-07, after WATCH-04 closes) | Phase 4a session-04-26 audit | 5.4 |
| ADR/Functional | NEW-E4 — ADR-V2-016 实现漂移:D87 Fix 2 强制 tool_choice=Required 续航 在 TUI 对话场景误命中 (deepseek-chat × web_search 反复执行)。需 `ExecutionMode { Conversational, LongWorkflow }` + ADR-V2-026 retroactive supersede。RFC 草稿:`.planning/research/2026-05-16-agent-loop-execution-mode-rfc.md` | 🟠 P1, mapped to Phase 5.3 (WATCH-08) | 2026-05-16 deepseek shakedown | 5.3 |
| Refactor | NEW-C2 — TUI key_handler.rs 大文件拆分 | 🟠 P1 (提优先级), mapped to Phase 5.2 (CLI-04) | Phase 4a review | 5.2 |
| Refactor | NEW-C1/C3 — harness.rs / grid-eval 大文件 | 🟡 P3 deferred 直到 second consumer (NOT in v3.1) | Phase 4a review | v3.2+ |
| Tech-debt | D-batch (~40 P3 / housekeeping items 跨 D8..D80) | 🟡 P3, 单日 batch sweep 待安排 (NOT in v3.1) | 累积自 Phase 0 → 3.6 | v3.2+ |

> 这些 Deferred 的 SSOT 仍是 `docs/design/EAASP/DEFERRED_LEDGER.md`(GSD 例外保留),本表只为 STATE.md 单 view 摘要。Phase 5 Mapping 列由 ROADMAP.md Coverage 表 反向回填, 关闭时 SSOT 双向更新 (LEDGER + ROADMAP)。

## Session Continuity

Last session: 2026-05-16 (DeepSeek shakedown + ExecutionMode RFC + implementation)
Stopped at: Phase 5.2 9/19 tasks done; ExecutionMode gate shipped (f1999fb)
Resume file: .planning/phases/05.2-cli-hardening/05.2-01-PLAN.md
Local commits ahead of origin: 0 (all pushed; HEAD == origin/main)

### What 2026-05-16 session delivered

11 commits total (`ac90121..b66e6ed..cedf810`), grouped:

**Phase 5.2 task progress** (`ac90121`):
- T-01.6 streaming JSON output for `grid ask` ✅
- Note: cumulative 5.2 tasks done = 9/19 (T-01.3/4/5/6/8/9/10/11/12/16/17 from this and prior sessions)

**DeepSeek end-to-end support** (4 commits — `25a8534`, `bf74d0a`, `cfcffd6`, `6535c37`):
- `crates/grid-engine/src/providers/deepseek.rs` — dedicated provider, deepseek-chat only; deepseek-reasoner explicitly rejected (Phase 5.3 D-item)
- Env plumbing in `providers/config.rs` + `grid-runtime/config.rs` + `grid-server/config.rs` — `LLM_PROVIDER=deepseek` end-to-end
- `grid-cli/tui/mod.rs` status bar reads `agent_runtime.default_model()` (single source of truth)
- Workspace passes `cargo check` and `make build-studio` cleanly

**Agent loop ExecutionMode gate** (RFC + implementation — `3b4e686`, `f1999fb`):
- Fixed: TUI 主会话 + deepseek-chat + tool call → 反复执行 (D87 Fix 2 误激活)
- New `AgentLoopConfig.execution_mode { Conversational, LongWorkflow }`, default Conversational
- `grid-runtime/main.rs` sets LongWorkflow at startup — EAASP byte-identical
- 1 new regression test (`test_conversational_mode_no_forced_continuation`); full lib suite 1569/1569 PASS
- RFC: `.planning/research/2026-05-16-agent-loop-execution-mode-rfc.md` + STATE NEW-E4

**One mid-session revert** (`3fcd2e7` → `815bba6`): tried to make session_message synchronous; broke fire-and-forget team-collab semantic + caused duplicate prompt injection. Reverted same session. Recorded in commit message as anti-pattern.

**Housekeeping** (`b66e6ed`, `cedf810`): `.gitignore` for `.claude/worktrees/` + `.codegraph/`; committed 4 stranded `.planning/` files (Phase 5.2 plan + Phase 5.0 historical research).

### Resume path (next session)

1. `/clear`
2. `/gsd-resume-work` — STATE frontmatter + this section drives recovery
3. Likely next action options:
   - **Continue Phase 5.2**: T-01.1/2/7/13/14/15/18/19 still ⏳ (10 tasks of 19)
   - **Jump to Phase 5.3 plan-phase**: ExecutionMode RFC is intake; would let TUI×tool-call regression test stay green and start ADR-V2-026 work
   - **Verify deepseek end-to-end locally**: shell `unset DEEPSEEK_API_KEY` (was 9993...), check `grid` TUI status bar shows `deepseek-chat`, ask "查 5月16日 国际要闻" and confirm only ONE web_search call

### Phase 5.2 task ledger (9/19 done, 10/19 pending)

| Task | Status | Commit |
|---|---|---|
| T-01.1 audit dead `grid` subcommands | ⏳ | — |
| T-01.2 `grid ask` stub | ⏳ | — |
| T-01.3 register `grid ask` in main.rs | ✅ | (in repo prior to session) |
| T-01.4 exit code constants | ✅ | bb68e8d |
| T-01.5 wire exit codes | ✅ | (in main.rs prior to session) |
| T-01.6 streaming JSON output | ✅ | **ac90121** (this session) |
| T-01.7 capture INVARIANTS.md before refactor | ✅ (retroactive back-fill, this session) | _pending_ |
| T-01.8-12 TUI key_handler split + studio build fix | ✅ | 92b7710 + **cfcffd6** (this session) |
| T-01.13 unit tests for each mode file (≥21) | ⏳ | — |
| T-01.14 integration tests (≥2) | ⏳ | — |
| T-01.15 INVARIANTS.md completeness verify | ⏳ | — |
| T-01.16 `session kill --purge` | ✅ | b14fca7 |
| T-01.17 `grid doctor` expansion | ✅ | e6bb575 + 3b361da |
| T-01.18 proto-cli-sync-check.sh | ⏳ | — |
| T-01.19 CLI integration tests | ⏳ | — |

### Pending Phase 5.3 inputs

- `.planning/research/2026-05-16-agent-loop-execution-mode-rfc.md` (RFC) → ExecutionMode implementation already landed; ADR-V2-026 supersede-V2-016 still TBD
- STATE Deferred Items table — NEW-E4 (this RFC), D109/D136 (other 5.3 watchlist items)

### Local environment caveat (user side, not code)

User shell environment has `DEEPSEEK_API_KEY=9993...` (some other key) which wins over `.env`'s `sk-...` because CredentialResolver priority is `Vault > env > yaml > .env`. **User must `unset DEEPSEEK_API_KEY`** (and grep ~/.zshrc to find the source) before deepseek-chat will authenticate correctly. This is a shell-state issue, not a Grid bug. (See `crates/grid-engine/src/secret/resolver.rs:56-84`.)
- 结论: GSD 体系在本仓库 brownfield 适配良好,Phase 5 复用同套
