---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: Phase 5 — Engine Hardening (grid-cli + grid-server)
status: executing
stopped_at: "Phase 5.5 Plan 01 COMPLETE 2026-05-22 — 8 commits (3fb9e2b W0 + 0b23a01 V2-029 + 1b9afd1 V2-032 + 2303b3d+e84a57e F3 sweep + 8c25223 NEW-A3 + ba3ba26 NEW-F4 code + 0bdf70c NEW-L1; B3 mod output verify-only no commit); ADR-V2-029 + V2-032 Accepted; F3 WARN 33 → 12 explicit-strategic; phase gate ALL GREEN (210 ADR PASS / 0 FAIL, grid-cli 147+6 tests PASS, vector_index 12/12 PASS, cargo check workspace Finished). Plan 02 milestone close cascade next."
last_updated: "2026-05-22T00:00:00Z"
last_activity: 2026-05-22 -- Phase 5.5 Plan 01 COMPLETE (7 task commits)
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 10
  completed_plans: 8
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-29)

**Core value:** Grid 作为 substitutable L1 runtime,通过 16-method gRPC contract 被 EAASP L2-L4 调用,且任何符合 contract-v1.1 的对比 runtime 都能替换它。
**Current focus:** Phase 5.5 — Interface ADR + Milestone Close

## Current Position

Phase: 5.5 (Interface ADR + Milestone Close) — EXECUTING
Plan: 1/2 COMPLETE; Plan 2/2 next (milestone close cascade)
Next plan: 05.5-02 — Milestone v3.1 Close Cascade (PROJECT.md flip + ROADMAP all-complete + STATE.md milestone-complete + REQUIREMENTS Traceability + DEFERRED_LEDGER 18-row sweep)
Status: Executing Phase 5.5 (Plan 01 done; Plan 02 awaiting orchestrator)
Last activity: 2026-05-22 -- Phase 5.5 Plan 01 COMPLETE

Progress: [▓▓▓▓▓▓░░░░] 88% (5/6 milestone phases + 1/2 Phase 5.5 plans complete — 5.0 + 5.1 + 5.2 + 5.3 + 5.4 + 5.5 Plan 01)

**Previous milestone closure**: Phase 4 milestone v3.0 ✅ CLOSED 2026-04-28 — 3/3 phases (4.0/4.1/4.2), ADR-V2-024 Accepted (双轴模型), 16 commits pushed to origin/main.

## Performance Metrics

**Velocity:**

- Total plans completed (executed): 4 ✅ (05.4-01 added 2026-05-21)
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
| 5.2 CLI Hardening | **1/1 ✅** | COMPLETE 2026-05-17 (19/19 tasks) | T-01.14 cross-mode integration tests (3) + T-01.19 CLI smoke tests (5) closed sub-plan; 575/575 PASS under --features studio; pre-existing vim_normal/vim_insert test bugs fixed inline |
| 5.3 Contract Evolution | **2/2 ✅** | COMPLETE 2026-05-20 (Plan A 11 + Plan B 7 tasks, 20 commits) | All 4 SCs PASS, 5 deferred items closed (D109/D136/NEW-E4/NEW-F1/NEW-F2), 2 ADRs Accepted (V2-026 + V2-027), L1 contract-v1.2.0 live across 7 runtimes |
| 5.4 Server Hardening | **2/2 ✅** | COMPLETE 2026-05-21 (Plan 01: 9 commits + Plan 02: 12 commits + 2 closures = 23 commits) | All 5/5 SC PASS, all 7/7 REQ-IDs covered (SERVER-01..05 + WATCH-04 + WATCH-07); ADR-V2-028 Accepted (Strict-by-default Config Validation); ADR-V2-019 enforcement.trace filled (status UNCHANGED 2026-04-20 per Q9); 5-row LEDGER close (D142+D143+NEW-A2+NEW-E3+NEW-F3); phase gate 2698 release tests PASS + ADR audit 164/0/0 + schema-coverage gate sessions+turns; W0-03 spike Verdict YES (tracing_subscriber::reload viable); 2 advisory drift items (ROADMAP SC#4 "4 modes" stale wording vs Q3-correction 3-mode; NEW-F4 LEDGER row needs retag to Phase 5.5) — non-blocking |
| 5.5 Interface ADR + Milestone Close | **1/2 ✅ (Plan 01)** | Plan 01 COMPLETE 2026-05-22 (8 commits total: 3fb9e2b W0 + 7 task commits); Plan 02 next | ADR-V2-029 (engine vs data/integration boundary, strategy) + ADR-V2-032 (TUI log path convention, record) Accepted; F3 WARN 33 → 12 explicit-strategic (target was ≤13); NEW-A3 + NEW-F4 + NEW-L1 closed; grid-cli mod output verified clean (verify-only); Plan 01 phase gate ALL GREEN (210 ADR PASS / 0 FAIL, 147+6 grid-cli tests PASS, 12/12 vector_index pytest PASS, cargo check workspace Finished); 2 P3 inbox rows for Plan 02 (NEW-X2 kill anti-pattern siblings, NEW-X3 grid-cli --all-features grid-engine 12 errors) |

**Recent Trend:**

- Last 5 plans: [05.5-01 ✅ 2026-05-22, 05.4-02 ✅ 2026-05-21, 05.4-01 ✅ 2026-05-21, 05.3-02 ✅ 2026-05-20, 05.3-01 ✅ 2026-05-20]
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
| Functional | D142 — grid-runtime 不读 EAASP_DEPLOYMENT_MODE | ✅ **CLOSED** 2026-05-21 Phase 5.4 Plan 02 @ `d12f6ec` (5.4-02-07) — grid-runtime/config.rs deployment_mode + service.rs create_session per_session gate; 2 tests PASS | ADR-V2-019 audit (历史) | 5.4 (closed) |
| Functional | D143 — claude-code-runtime 不读 EAASP_DEPLOYMENT_MODE + 无 max_sessions=1 gate | ✅ **CLOSED** 2026-05-21 Phase 5.4 Plan 02 @ `2453447` (5.4-02-08) — service.py __init__._deployment_mode + Initialize gate; 2 pytest PASS | ADR-V2-019 audit (历史) | 5.4 (closed) |
| Contract | NEW-D2 — test_chunk_type_contract.py 仅 3 tests,not 7-runtime parametric | 🟠 P1, mapped to Phase 5.1 (WATCH-05) | Phase 4a project review | 5.1 |
| ADR | NEW-E2 — F3 reports 29 missing `enforcement.trace` items (corrected to 33 baseline 2026-05-22; closed at 12 explicit-strategic) | ✅ **CLOSED** 2026-05-22 Phase 5.5 Plan 01 @ `2303b3d`+`e84a57e` — 5-contract ADR trace fills (V2-006/018/020/027/028 in phase3-contract.yml + eval-ci.yml) + 4-strategy ADR rationale comments (V2-001/002/003/005); F3 WARN 33 → 12; ADR statuses UNCHANGED; F1/F2 0 FAIL | Phase 4a session-04-26 audit | 5.5 (closed) |
| ADR | NEW-E3 — ADR-V2-019 enforcement.trace empty (corrected per Q9: status was already Accepted 2026-04-20) | ✅ **CLOSED** 2026-05-21 Phase 5.4 Plan 02 @ `70b5e94` (5.4-02-10) — enforcement.trace filled with 4 anchors (D142+D143 impl points); ADR lint 7 PASS / 0 FAIL; status UNCHANGED | Phase 4a session-04-26 audit | 5.4 (closed) |
| ADR/Functional | NEW-E4 — ADR-V2-016 实现漂移:D87 Fix 2 强制 tool_choice=Required 续航 在 TUI 对话场景误命中 (deepseek-chat × web_search 反复执行)。需 `ExecutionMode { Conversational, LongWorkflow }` + ADR-V2-026 retroactive supersede。RFC 草稿:`.planning/research/2026-05-16-agent-loop-execution-mode-rfc.md` | 🟠 P1, mapped to Phase 5.3 (WATCH-08) | 2026-05-16 deepseek shakedown | 5.3 |
| Refactor | NEW-C2 — TUI key_handler.rs 大文件拆分 | ✅ **CLOSED** 2026-05-04 (commits `92b7710`+`cfcffd6`) — split into 10 files, INVARIANTS.md SoT + verifier @ 7176b4b | Phase 4a review | 5.2 (closed) |
| Refactor | NEW-C1/C3 — harness.rs / grid-eval 大文件 | 🟡 P3 deferred 直到 second consumer (NOT in v3.1) | Phase 4a review | v3.2+ |
| Tech-debt | D-batch (~40 P3 / housekeeping items 跨 D8..D80) | 🟡 P3, 单日 batch sweep 待安排 (NOT in v3.1) | 累积自 Phase 0 → 3.6 | v3.2+ |
| Functional | NEW-A2 — `migrate()` in `grid-engine/src/db/mod.rs:29` 非原子 | ✅ **CLOSED** 2026-05-21 Phase 5.4 Plan 02 @ `74e6472`+`bf26cb8` (5.4-02-01+02) — BEGIN EXCLUSIVE + double-check user_version; 4-process race regression test PASS, no duplicate column panic, user_version → 13 | 2026-05-16 NEW-A1 forensics | 5.4 (closed) |
| Functional | NEW-A3 — `kill_session` in `commands/session.rs:117` returns `anyhow::Error` for "Session not found", which `main.rs:88` maps to `ExitCode::General` (1). Should return `GridError::SessionNotFound` → exit 4. | ✅ **CLOSED** 2026-05-22 Phase 5.5 Plan 01 @ `8c25223` — session.rs::kill_session returns typed GridError::session_not_found; main.rs adds downcast_ref::<GridError> arm to preserve typed exit code; regression test test_kill_nonexistent_session_exits_4 PASSES; 147 + 6 grid-cli tests PASS, no regression. Filed NEW-X2 (sibling delete_session + export_session same anti-pattern) as P3 inbox for Plan 02 | 2026-05-17 T-01.19 smoke test discovery | 5.5 (closed) |
| Functional | NEW-F4 — TUI log path moved to `./logs/tui.log` + `GRID_TUI_LOG` env override (2026-05-19 hot fix); ADR + dead `dirs::data_local_dir()` fallback delete still pending | ✅ **CLOSED** 2026-05-22 Phase 5.5 Plan 01: ADR @ `1b9afd1` (ADR-V2-032 TUI Log Path Convention, type=record, Accepted) + code @ `ba3ba26` (studio_main.rs::resolve_tui_log_path L57-60 dead branch deleted, docstring cross-links V2-032, `dirs` crate dep retained for path_shortener.rs); both default + studio builds PASS | 2026-05-19 NEW-F1..F4 cascade | 5.5 (closed) |
| Functional | grid-cli `mod output` E0583 — pre-existing compile error observed during Phase 5.3 OOS | ✅ **CLOSED (verified clean)** 2026-05-22 Phase 5.5 Plan 01 Task 01.B3 — verify-only; both `cargo build -p grid-cli` and `--features studio` Finished clean; output/ module structure intact (mod.rs+json.rs+stream_json.rs+text.rs); no code edit needed (resolved by prior commit, root cause unknown); no commit per plan spec | 2026-05-20 Phase 5.3 OOS | 5.5 (closed) |
| Functional | NEW-L1 — HNSW disk leak (94GB index from unbounded max_elements doubling) + meta.json schema gap | ✅ **CLOSED** 2026-05-22 Phase 5.5 Plan 01 @ `0bdf70c` — vector_index.py adds HNSW_HARD_CAP=1_000_000 module constant + caps doubling at min(new_max, HNSW_HARD_CAP) + raises RuntimeError on cap-hit + persists max_elements in meta.json save() + restores max_elements in _try_load_sync(); 12/12 vector_index pytest PASS (10 existing + 2 new W0 stubs); atomic write_text preserved (V14.1.5) | 2026-05-20 Phase 5.3 OOS forensics | 5.5 (closed) |
| ADR | INTERFACE-01 — ADR-V2-029 engine vs data/integration boundary contract (ADR-only, type=strategy, crate-level) | ✅ **CLOSED** 2026-05-22 Phase 5.5 Plan 01 @ `0b23a01` — ADR-V2-029 Accepted; §1 2-column table enumerates engine-side 17 modules vs data/integration categories; §3 future-proofing rules; V2-030 + V2-031 reserved in §References for v3.2+; F1/F2/F3/F5 PASS (F4 module overlap WARN advisory-only, expected for boundary ADR) | Phase 5.5 ROADMAP scope | 5.5 (closed) |

> 这些 Deferred 的 SSOT 仍是 `docs/design/EAASP/DEFERRED_LEDGER.md`(GSD 例外保留),本表只为 STATE.md 单 view 摘要。Phase 5 Mapping 列由 ROADMAP.md Coverage 表 反向回填, 关闭时 SSOT 双向更新 (LEDGER + ROADMAP)。

## Session Continuity

Last session: 2026-05-22T00:00:00Z
Stopped at: Phase 5.5 Plan 01 COMPLETE 2026-05-22 — 7 task commits (0b23a01..0bdf70c) atop W0 (3fb9e2b); ADR-V2-029 + V2-032 Accepted; F3 sweep 33 → 12 explicit-strategic; NEW-A3 + NEW-F4 + NEW-L1 closed; grid-cli mod output verified clean; phase gate ALL GREEN. Next: Plan 02 milestone close cascade (PROJECT.md flip + ROADMAP all-complete + STATE.md milestone-complete + REQUIREMENTS Traceability + DEFERRED_LEDGER 18-row sweep + close-cascade phase gate per D-10).
Resume file: .planning/phases/05.5-interface-adr-milestone-close/05.5-02-PLAN.md
Local commits ahead of origin: 8 awaiting push (3fb9e2b W0 + ee7b008 STATE start + 7 Plan 01 task commits)
Worktrees: cleaned (no active worktrees this session — sequential execution per recovery context)

Prior sessions:

- 2026-05-19: LLM provider fix + Phase 5.3 plan-phase (`/gsd-discuss-phase 5.3` + `/gsd-plan-phase 5.3`)
- 2026-05-17: Phase 5.2 closure (T-01.14/19) — 19/19 PASS
- 2026-05-16: DeepSeek shakedown + ExecutionMode RFC + commit `f1999fb` impl

Detailed narratives below.

### What 2026-05-20 session delivered (THIS session)

**Single-day full Phase 5.3 execution + 1 cross-session LLM provider hot fix.** 26 commits total `e346ffd..a3851f0` (1 pre-phase + 25 within Phase 5.3 boundary).

**Pre-phase (2026-05-19 evening, carried into 2026-05-20)** — LLM provider unblock:

- `e346ffd` fix(llm-providers): unblock TUI with ant-ling + record provider-system debt (NEW-F1..F4)
- Root cause cascade discovered: (1) macOS Clash proxy fails on ~57KB POST bodies (small `grid ask` OK, TUI 47-tool body fails); (2) ant-ling Ling-2.6-1T doesn't emit `data: [DONE]` (parser hangs); (3) stale `.env` `RUST_LOG=octo_*` (pre-Phase-BA rename leftover) silently filters all `grid_*` log → debugged for hours; (4) `make studio-tui` Makefile didn't pass `--verbose` flag
- Mitigations landed: `OPENAI_NO_PROXY=1` / `ANTHROPIC_NO_PROXY=1` / `GRID_LLM_NO_PROXY=1` env switches in providers; OpenAIProvider parser flushes pending tool_calls on `Poll::Ready(None)` (unconditional hot fix; later gated by ADR-V2-027 Quirks.no_done_marker); TUI log path moved to `./logs/tui.log`; LLM_PROVIDER default flipped anthropic → openai
- Filed NEW-F1..F4 deferred items for follow-up

**Phase 5.3 Discuss → Plan → Execute → Verify → Close, all in one day**:

1. **Discuss** (2026-05-19 night): `/gsd-discuss-phase 5.3`. 10 user decisions locked in CONTEXT.md including:
   - Plan structure: 2 plans (CONTRACT main + ADR/Quirks)
   - CONTRACT-01: BOTH THINKING_TRACE (wire 8) + ATTACHMENT_REF (wire 9) added
   - CONTRACT-02: BOTH SubagentStart + TaskCheckpoint added
   - NEW-E4 → ADR-V2-026 supersede V2-016 (lock f1999fb impl)
   - NEW-F1/F2 → ADR-V2-027 (Quirks framework + LingProvider F2 split)
   - NEW-F3/F4 → pushed to Phase 5.4
   - ATTACHMENT_REF backend storage → deferred to next milestone (wire-only in 5.3)

2. **Plan** (2026-05-20 morning): `/gsd-plan-phase 5.3`. Research → Validation → Patterns → 2 PLANs. plan-checker took 3 iterations (3 BLOCKERS → 1 BLOCKER → PASS). Key revisions:
   - iter-1: RESEARCH Open Questions resolved at planning time (esp. Q3 = F2 path), missing test file retargeted, deepseek.rs added to files_modified
   - iter-2: nanobot/pydantic-ai mapper.py paths don't exist — retargeted to service.py direct-emission (parallel to goose/claw-code Rust pattern)
   - iter-3: PASS all 12 dimensions

3. **Execute Wave 1** (Plan A, 2h35min, 12 commits `ad04e57..95f1b6a`): proto + 7-runtime impl + parity tests + D109 doc + D136 fix + ADR-V2-021/006 amendments + LEDGER closes. All targeted tests PASS, ADR lint 16/16 PASS each. Worktree merged ff-only.

4. **Out-of-scope discovery mid-Wave-2**: user disk audit found `data/l2-memory/hnsw-mock-bge-m3-fp16/index.bin` at 94GB (expected ~4MB). Forensics traced to `vector_index.py:189-192` unbounded max_elements doubling + meta.json schema gap. User deleted directory; code fix → NEW-L1 mapped to Phase 5.4.

5. **Execute Wave 2** (Plan B, 51min, 8 commits `2e7b2b9..501f31d`): ADR-V2-026 + ADR-V2-027 Accept + Quirks struct + LingProvider F2 + DeepseekProvider wiring + LEDGER closes. 5/5 + 4/4 + 3/3 + 132/132 tests PASS. Worktree was already on main (planner's commits had directly written there during Wave 1 ff-merge; not a concern). 

6. **Verify** (orchestrator inline): gsd-verifier subagent socket dropped at 14 min (Anthropic infra hiccup). Orchestrator completed goal-backward spot checks via grep/Read in ~5 min. VERIFICATION.md written manually. All 4 ROADMAP SCs PASS + 5 deferred items closed.

7. **Close** (commit `a3851f0`): VERIFICATION.md + STATE.md + ROADMAP.md + deferred-items.md, single commit. Pushed.

**Test counts (all PASS, per-Plan SUMMARY + verifier spot-check)**:

- chunk_emit 4/4 · subagent_start_hook 2/2 · task_checkpoint_hook 2/2 · d87_multi_step_workflow_regression 3/3
- openai_quirks 5/5 · ling 4/4 · chain dispatch 1/1
- test_chunk_type_contract 1/1 · test_hook_event_contract 5/5 · test_chunk_type_whitelist 2/2
- test_cmd_session_chunk_types::test_whitelist_has_exactly_nine_values 1/1
- test_chunk_coalescing::test_chunk_type_to_wire_known_variants 1/1
- check-ccb-types-ts-sync.sh PASS · ADR-V2-021 lint 16/16 · ADR-V2-006 lint 16/16
- providers lib 127/127

**Out-of-scope discoveries logged in `.planning/phases/05.3-contract-evolution/deferred-items.md`**:

1. grid-cli `mod output` pre-existing E0583 — Phase 5.4 inbox
2. NEW-L1 L2 HNSW 94GB disk leak — data ✅ deleted; code fix → Phase 5.4 NEW-L1

**Key lessons captured to memory**:

- macOS Clash + reqwest fails on ≳50KB POST bodies (mitigated via OPENAI_NO_PROXY env)
- dotenvy + stale RUST_LOG (pre-Phase-BA `octo_*` keys) silently drops all grid logs
- OpenAI-compat `[DONE]` not guaranteed (ant-ling specifically)
- hnswlib save_index dumps full pre-allocated arena, not just live vectors
- Planner disk-verification sweeps must explicitly include parallel categories (Rust vs Python tier-mirror discovery)
- Verifier socket drop is recoverable inline via grep/Read in ~5 min when SUMMARY.md files exist
- 2-plan structure cohesion-justified despite scope warning (contract-v1.2.0 needs all-or-nothing landing)

### Resume path (next session)

Phase 5.3 closed 2026-05-20 at `origin/main` HEAD `a3851f0`. Next action: **`/gsd-discuss-phase 5.4`** — SERVER hardening.

Phase 5.4 anchors carried into the new session:

- **SERVER-01..05** main scope (ROADMAP §Phase 5.4): WebSocket / L1 gRPC integration / session+L2 persistence / auth+audit / config hot-reload
- **WATCH-04** (D142+D143 — EAASP_DEPLOYMENT_MODE接入 + max_sessions=1 gate per ADR-V2-019)
- **WATCH-07** (NEW-E3 — ADR-V2-019 Proposed → Accepted after D142+D143 close)
- **NEW-A2** (migrate() race in grid-engine/db) — 2026-05-16 forensics
- **NEW-A3** (kill_session exit code 1 vs expected 4) — 2026-05-17 Phase 5.2 smoke test
- **NEW-F3** (silent-fallback removal: LLM_PROVIDER / OPENAI_NO_PROXY / RUST_LOG / logger) — 2026-05-19
- **NEW-F4** (./logs/tui.log + GRID_TUI_LOG ADR) — 2026-05-19
- **grid-cli mod output E0583** — 2026-05-20 Phase 5.3 OOS
- **NEW-L1** (HNSW disk leak code fix; data already reclaimed) — 2026-05-20 Phase 5.3 OOS

That's 9 candidate items for Phase 5.4 plan-phase to weigh against SERVER-01..05. plan-phase will fold what fits cohesion, push rest to Phase 5.5 or next milestone.

### Phase 5.5 prep note carried forward

ADR-V2-026 + ADR-V2-027 numbers consumed in Phase 5.3 → Phase 5.5 INTERFACE-01's ADR (currently reserved as V2-026 in ROADMAP) must renumber to **V2-028** when Phase 5.5 plan-phase runs. Documented in `.planning/phases/05.3-contract-evolution/05.3-02-PLAN.md` § Cross-Phase Note.

### Local environment caveat (user side, still valid from 2026-05-19)

- `.env` cleaned of stale `RUST_LOG=octo_*` 2026-05-19; should now be `RUST_LOG=grid_engine=debug,grid_cli=info,tower_http=debug` (or unset — `--verbose` will provide a fallback filter)
- `OPENAI_NO_PROXY=1` set in `.env` for Clash-environment users; OpenRouter users should NOT have this set
- `LLM_PROVIDER=openai` is the new code-level default (changed from `anthropic`); explicit `.env` value still overrides
- `data/l2-memory/hnsw-mock-bge-m3-fp16/` deleted 2026-05-20; test fixtures will rebuild if needed (will likely re-trigger NEW-L1 bug unless code fixed first)

### What 2026-05-17 session delivered

2 commits (`a312761`, `ccaf36e`) — closes Phase 5.2 at 19/19.

**Phase 5.2 closure** (T-01.14 + T-01.19 sub-plan from `616ad89`):

- **`a312761` fix(grid-cli/tui-tests): repair pre-existing studio test bugs blocking T-01.14/19** —
  3 latent test-only bugs since 2026-05-04 key_handler split (`92b7710`).
  None affected production. Fixed because they blocked
  `cargo test -p grid-cli --features studio`:

  1. 5 wrong `super::super::` paths in `vim_normal.rs` + `vim_insert.rs`
     (need one more `super::` to reach `tui::widgets::figures::VimMode`)

  2. `test_dollar_goes_to_end` missing SHIFT modifier (real `$` = Shift+4)
  3. `test_x_deletes_character` wrong cursor expectation (test bug, impl
     matches real vim semantics — cursor only retreats on EOL overshoot)

- **`ccaf36e` test(grid-cli): T-01.14 + T-01.19 close Phase 5.2 at 19/19** —
  - `tests/key_handler_integration.rs` — 3 cross-mode integration tests
    locking INVARIANTS.md asymmetry items #4 (Esc cascade), #5 (slash
    overlay reuse), #8 (ModelSelector dual nav)

  - `tests/cli_integration.rs` — 5 CLI smoke tests via `CARGO_BIN_EXE_grid`
    (ask --help / invalid sub / missing arg / doctor exit codes / NO_COLOR)

  - `tests/common/mod.rs` — shared `fresh_state()` / `key()` / `ctrl()` helpers
  - `TuiState::new_for_test` `#[cfg(test)]` → `#[doc(hidden)]` (external
    integration tests need visibility across compilation-unit boundary)

  - PLAN T-01.14/19 marked ✅; STATE → COMPLETE; SUMMARY.md written
  - **New deferred NEW-A3** filed: `kill_session` returns exit 1, should be
    4 per `EXIT_SESSION_NOT_FOUND`. P2, mapped to Phase 5.4.

**Test counts after closure**:

- `cargo test -p grid-cli` (default features): 147/147 PASS
- `cargo test -p grid-cli --features studio`: **575/575 PASS**
- `cargo check --workspace`: clean
- `scripts/check-key-handler-invariants.sh`: PASS

**Key lessons**:

- External integration tests need `#[doc(hidden)]`, NOT `#[cfg(test)]`,
  when a helper crosses compilation-unit boundaries.

- Studio-feature lib tests had latent bugs because nobody ran them between
  2026-05-04 and 2026-05-17. Add `--features studio` to CI matrix or
  accept the drift.

- PLAN spec drift is normal at execution time. T-01.16 wrote
  "EXIT_SESSION (71)" but the catalog has `SessionNotFound = 4`. Smoke
  tests are how you catch this. File a deferred, don't retrofit.

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

Phase 5.2 closed 2026-05-17. Next action: **`/gsd-discuss-phase 5.3`** —
Contract Evolution. Phase 5.3 anchors:

- **NEW-E4 → ADR-V2-026 supersede-V2-016** — ExecutionMode RFC is already
  intake at `.planning/research/2026-05-16-agent-loop-execution-mode-rfc.md`;
  implementation already landed in `f1999fb`. 5.3 must promote the RFC to an
  Accepted ADR that retroactively supersedes V2-016.

- **WATCH-01 (D109)** — workflow.required_tools 不变量未文档化
- **WATCH-03 (D136)** — grid-runtime hook 在 probe turn 不触发 (3 contract xfails)
- **WATCH-08 (NEW-E4)** — same as ADR-V2-026 above; track until Accepted

Sub-plan path that worked for 5.2 closure (in case 5.3 is also bisected):
infra-then-tests with a shared `tests/common/` harness, and inline-fix
pre-existing test bugs that block your test path rather than skipping them
(NEW-A1 lesson + 2026-05-17 vim_normal/vim_insert lesson).

**Don't try to also close NEW-A2 (production migrate() race) or NEW-A3
(kill_session exit code) in 5.3** — both mapped to Phase 5.4 server
hardening per DEFERRED LEDGER.

5. **Local environment caveat (still valid):** shell
   `DEEPSEEK_API_KEY=9993...` wins over `.env`'s `sk-...` per
   CredentialResolver priority (Vault > env > yaml > .env). `unset` it
   before deepseek e2e tests (`crates/grid-engine/src/secret/resolver.rs:56-84`).

### Phase 5.2 task ledger (16/19 done, 3/19 pending — revised 2026-05-16 audit)

| Task | Status | Commit |
|---|---|---|
| T-01.1 audit dead `grid` subcommands | ✅ (audit pass = no-op, 16/16 wired) | ac0cfb5 |
| T-01.2 `grid ask` stub | ✅ (super-set: full impl, `ask.rs` 270+ LOC) | (in repo prior to session) |
| T-01.3 register `grid ask` in main.rs | ✅ | (in repo prior to session) |
| T-01.4 exit code constants | ✅ | bb68e8d |
| T-01.5 wire exit codes | ✅ | (in main.rs prior to session) |
| T-01.6 streaming JSON output | ✅ | **ac90121** (this session) |
| T-01.7 capture INVARIANTS.md before refactor | ✅ (retroactive, 98 bindings × 10 files) | e1cbed6 + ac0cfb5 |
| T-01.8-12 TUI key_handler split + studio build fix | ✅ (actual: 10 files, not 7 per PLAN) | 92b7710 + **cfcffd6** (this session) |
| T-01.13 unit tests for each mode file (≥21) | ✅ **far exceeded** (130 tests across 10 files) | (cumulative pre-Phase-5.2 + during) |
| T-01.14 integration tests (≥2) | ✅ (3 cross-mode tests; INVARIANTS asymmetry #4 + #5 + #8) | _Phase 5.2 closure_ |
| T-01.15 INVARIANTS.md completeness verify | ✅ (`scripts/check-key-handler-invariants.sh` PASS) | 7176b4b |
| T-01.16 `session kill --purge` | ✅ | b14fca7 |
| T-01.17 `grid doctor` expansion | ✅ | e6bb575 + 3b361da |
| T-01.18 proto-cli-sync-check.sh | ✅ (PASS + FAIL=73 both verified) | 7176b4b |
| T-01.19 CLI integration tests | ✅ (5 smoke tests; ask --help, invalid-sub exit=2, ask missing-arg exit=2, doctor exit ∈ {0,73} + 3 required labels, NO_COLOR=1 zero ANSI) | _Phase 5.2 closure_ |

**Phase 5.2 progress: 19/19 ✅ (100%).** Closure 2026-05-17 — 3+5 integration tests landed, `crates/grid-cli/tests/` directory bootstrapped with shared `common/` harness. Pre-existing studio test compile bugs in `vim_normal.rs`/`vim_insert.rs` (5 wrong `super::super::` paths + 1 missing SHIFT modifier in `test_dollar_goes_to_end` + 1 wrong cursor expectation in `test_x_deletes_character`) fixed inline so `--features studio` test path works end-to-end. Filed NEW-A3 (kill_session exit code mismatch — currently 1, should be 4) → mapped to Phase 5.4.

### NEW-A1 ✅ RESOLVED (2026-05-16, this session)

`cargo test -p grid-cli --lib` **147 PASSED / 0 FAILED**.

**Root cause:** `repl/slash.rs:994-1001` `make_test_state` used a per-process
tempdir (`/tmp/octo-test-{pid}`) so all 10 parallel test threads shared the
same SQLite file. Each thread independently ran `migrate()` from
`grid-engine/src/db/mod.rs`. `migrate()` reads `user_version` PRAGMA, runs
non-idempotent `ALTER TABLE ADD COLUMN user_id` (`migrations.rs:212`), then
bumps `user_version`. Threads 2-N all saw `user_version = 0` at read time
(before thread 1's bump) and tried to re-add the column → 10× duplicate-column
panic.

**Fix:** Per-test unique tempdir via `AtomicU64` counter in `make_test_state`.
Each test now gets `/tmp/grid-cli-slash-test-{pid}-{counter}/test.db`.
Surgical 1-function patch; no new dependencies.

**Spawned follow-up D-item (NEW-A2):** `migrate()` itself has a production
race — two processes calling `migrate()` against the same db file
simultaneously can hit the same bug. Lower priority (single-process grid-cli
is the dominant deployment) but should be wrapped in a `BEGIN EXCLUSIVE`
transaction + re-check `user_version` inside the txn. Filed under §Deferred
Items for Phase 5.4 (server hardening) or later.

### Pending Phase 5.3 inputs

- `.planning/research/2026-05-16-agent-loop-execution-mode-rfc.md` (RFC) → ExecutionMode implementation already landed; ADR-V2-026 supersede-V2-016 still TBD
- STATE Deferred Items table — NEW-E4 (this RFC), D109/D136 (other 5.3 watchlist items)

### Local environment caveat (user side, not code)

User shell environment has `DEEPSEEK_API_KEY=9993...` (some other key) which wins over `.env`'s `sk-...` because CredentialResolver priority is `Vault > env > yaml > .env`. **User must `unset DEEPSEEK_API_KEY`** (and grep ~/.zshrc to find the source) before deepseek-chat will authenticate correctly. This is a shell-state issue, not a Grid bug. (See `crates/grid-engine/src/secret/resolver.rs:56-84`.)

- 结论: GSD 体系在本仓库 brownfield 适配良好,Phase 5 复用同套
