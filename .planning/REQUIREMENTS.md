# Grid — Requirements

> **Brownfield context**: 14 archived phases (Phase BA → Phase 4a) under dev-phase-manager already shipped EAASP v2.0 functional baseline. Phase 4 milestone v3.0 (3 phases: 4.0 / 4.1 / 4.2) closed 2026-04-28 with ADR-V2-024 Accepted (双轴模型 supersedes ADR-V2-023). v3.1 Phase 5 Engine Hardening closed 2026-05-22 (6 phases, 23 REQ-IDs, 6 ADRs Accepted). This REQUIREMENTS.md now scopes **milestone v3.2 — Tech-Debt Triage & CI Red Line Clearance**.

---

## v3.2 Requirements (Milestone: Tech-Debt Triage & CI Red Line Clearance)

> **Per ADR-V2-024 §1 双轴模型 + Open Item #3**: 优先发力组合 grid-cli + grid-server 不变; 其余 (grid-platform / grid-desktop / web*) 保持 dormant. 工时 baseline: Grid 全栈 ≈60% / EAASP 引擎 ≈30% / 元工作 ≈10%.
>
> **Scope shape**: minimum-viable triage milestone. 代码修复 ONLY 3 个具体 P2/P3 row (NEW-X4 + NEW-X2 + NEW-X3); 102 D-row 仅做分类不做修复; mega debt sweep 留给 v3.3+ 按 triage 结果决定。

### A. CI — Phase 3 Contract Matrix CI Red Line Clearance

- [ ] **CI-01**: NEW-X4 pytest **parametrize-layer** fixture-scope mismatch 修 — 3 parametrize sites across 2 files (`tests/contract/cases/test_chunk_type_contract.py:139` + `tests/contract/cases/test_hook_event_contract.py:203` (`test_subagent_start_envelope_live`) + `tests/contract/cases/test_hook_event_contract.py:238` (`test_task_checkpoint_envelope_live`)) all decorate with `@pytest.mark.parametrize("runtime_name", ADR_V2_025_ACTIVE_RUNTIMES)`, shadowing the session-scoped `runtime_name(request)` fixture at `tests/contract/conftest.py:113`. Rename the parametrize identifier to `expected_runtime` at all 3 sites (session fixture UNTOUCHED) so pytest no longer raises `ScopeMismatch: You tried to access the function scoped fixture runtime_name with a session scoped request object`. Fixture装配通过后, 跨 7 个 L1 runtime (claude-code / goose / nanobot / pydantic-ai / claw-code / ccb / grid) 都能进入实际 assert (PASS / FAIL / XFAIL by runtime, 不再是 fixture-装配-阶段-error)。Phase 3 Contract Matrix workflow 由 RED 转 GREEN (≥4 of 7 jobs PASS, 因为 reference-tier runtimes 允许 XFAIL per ADR-V2-025)。

### B. CLI — grid-cli Anti-pattern Sweep

- [ ] **CLI-X2**: NEW-X2 sibling kill_session anti-pattern 补全 — `crates/grid-cli/src/commands/session.rs:99-103` (`delete_session`) + L157 (`export_session`) 仍用 `anyhow!("Session not found")` 映射到 `ExitCode::General` (1); 应该用 `GridError::session_not_found()` 走 typed exit code `SessionNotFound = 4` 路径 (同 NEW-A3 在 Phase 5.5 已 Plan 01 Task B1 修的模式)。每处 ~5 LOC, 加 2 个 integration test (delete + export 各一)。
- [ ] **CLI-X3**: NEW-X3 `cargo build -p grid-cli --all-features` 12 grid-engine errors 调查 + 决定 — 当前 default + studio 两 feature set build 全清; `--all-features` 路径触发 grid-engine hooks module 12 个 pre-existing errors (E0596 borrow-checker + E0412/E0425/E0433)。任务 = 调查根因 (是否真的 dead code? 是否某个 feature flag 应该 gate 它?), 然后两选一 fix: (a) 修真错; (b) 从 grid-cli `--all-features` 矩阵移除引发错的 feature, 保留 `--all-features` 在小一点的集合上能 build。**结果可能是 N/A** — 如果 hooks module 是 grid-server only 那就只需 doc fix。

### C. TRIAGE — Debt Ledger Triage Pass

- [ ] **TRIAGE-01**: 102 open D-row + 3 NEW-X row 一次性 triage 分类 — 每一行 row 加分类 tag (P1-actionable-now / P2-next-milestone / P3-async-when-touched / DEAD-archived) + 一行 rationale (引用代码/ADR/历史 commit)。**DEAD** tag 适用于: Phase BA Grid 重命名后引用 `octo_*` 不再存在的 row; 引用 deleted code 的 row; 决策已被 ADR superseded 的 row (e.g., 2026-03 时期 hermes-runtime 相关 row 在 V2-017 hermes Frozen 后)。
- [ ] **TRIAGE-02**: DEAD-archived row 物理迁移 — 把所有 TRIAGE-01 标 DEAD 的 row 移到 `docs/design/EAASP/DEFERRED_LEDGER_ARCHIVE.md` 新文件, LEDGER 主体只留 P1/P2/P3 row。Archive 文件保留 row 原文 + 移除时间 + DEAD rationale, 不可再追加。
- [ ] **TRIAGE-03**: TRIAGE 结果汇总写入 `.planning/v3.3-INBOX.md` — P1 row 列表 + P2 row 列表 + P3 row 列表, 喂未来 milestone scoping。每一类按 module (grid-engine / grid-cli / grid-server / L2 / contract / etc) 分组方便 v3.3+ 按 module 立 phase。

---

## v3.1 Requirements (CLOSED 2026-05-22 — historical reference)

> v3.1 = Phase 5 Engine Hardening, shipped 2026-05-22. All 23 REQ-IDs traced ✅. Section kept for traceability lineage.

> **Per ADR-V2-024 §1 双轴模型 + Open Item #3**: 优先发力组合 grid-cli + grid-server; 其余 (grid-platform / grid-desktop / web*) 保持 dormant. 工时 baseline: Grid 全栈 ≈60% / EAASP 引擎 ≈30% / 元工作 ≈10%.

### A. CLI — grid-cli 硬化

- [x] **CLI-01**: `grid` 命令树整理 — 统一 subcommand 命名 / help 输出 / exit code, 现有 `cli` / `cli-ask` / `cli-session` / `cli-config` / `cli-doctor` / `studio-tui` / `studio-dashboard` UX 一致性提升, 用户敲 `grid --help` 能看到清晰的命令分类。
- [x] **CLI-02**: Streaming output 改善 — `grid cli-ask` 渲染 ChunkType (TEXT_DELTA / TOOL_START / TOOL_RESULT / WORKFLOW_CONTINUATION / 等) 的 UX 优化, 流式打字机效果 + tool call 折叠 + error 高亮。
- [x] **CLI-03**: Error message + exit code 一致性 — provider 错误 / network timeout / config 缺失 / API key invalid 等场景的错误信息有统一格式, exit code 符合 sysexits.h 约定 (EX_USAGE=64 / EX_NOINPUT=66 / EX_UNAVAILABLE=69 / EX_SOFTWARE=70 / EX_CONFIG=78)。
- [x] **CLI-04**: TUI key_handler.rs 拆分 — Phase 4a NEW-C2 deferred 项, key_handler.rs 单文件过大, 拆分为 dispatcher + per-mode handler 子模块以便后续扩展 (Phase 5 提优先级到本 milestone)。
- [x] **CLI-05**: Session lifecycle 命令端到端打磨 — `grid session list / resume / kill` 的 UX 验证, 包括 SQLite session record 显示 / 恢复 turn-by-turn / 清理孤儿 session record。
- [x] **CLI-06**: `grid doctor` 检查清单扩展 — 添加 EAASP_DEPLOYMENT_MODE / GRID_HOOKS_FILE / hook bundle 健康度 / L2 memory engine 可达性 / L1 runtime gRPC 可达性 等检查项。

### B. SERVER — grid-server 硬化

- [x] **SERVER-01**: WebSocket 流式渲染成熟度 — Axum 0.8 + axum-extra 0.10 WebSocket 端点对 ChunkType stream 的端到端流式输出, 含 backpressure / reconnect / message ordering 验证。
- [x] **SERVER-02**: L1 runtime gRPC 集成端到端验证 — grid-server (`:3001`) 调 grid-runtime (`:50051`) 16-method RuntimeService 全部 RPC 端到端跑通 (Initialize / SendResponse / Terminate / etc), 含 session id 传递 / chunk relay / hook envelope 透传。
- [x] **SERVER-03**: Session 持久化 + L2 内存集成 — `data/grid.db` SQLite + tokio-rusqlite schema 演进, session record + turn record + L2 memory FTS5+HNSW+time-decay 索引, Stop hook fire 时把 trajectory 写入 L2 memory engine。
- [x] **SERVER-04**: Auth 路径打磨 — GRID_AUTH_MODE / GRID_API_KEY / GRID_API_KEY_USER / HMAC (ADR-003) 端到端验证 + audit log + rate limit 基础。
- [x] **SERVER-05**: Config hot-reload — config.yaml 改动 + GRID_* env vars 在 server 运行时优雅 reload (排除 GRID_HOST / GRID_PORT 必须重启的字段), 含 hot-reloadable vs require-restart 字段白名单。

### C. CONTRACT — L1 runtime contract 中等扩展

- [x] **CONTRACT-00**: 7 runtime 分级 review + 契约执行强度策略 ADR — 新 ADR 候选 `ADR-V2-025-l1-runtime-contract-tier-strategy.md` (type: strategy), 评估 7 runtime 现状, 划分 **主力档** (强制 v1.2 全 PASS) / **样板档** (鼓励但允许 xfail) / **参考档** (可降级到 v1.1 baseline) / **冻结档** (免审, 现 hermes-runtime); ADR-V2-017 三轨产品策略基础上增加契约执行强度差异化策略。
- [x] **CONTRACT-01**: ChunkType 扩展点 (1-2 新 enum 值) — 评估并落地新 ChunkType (例如 `THINKING_TRACE` / `ATTACHMENT_REF`), 走完 proto 改动 + codegen + 主力档 runtime 实现 + L4 mapper + CLI whitelist + contract test + ADR-V2-021 增量更新流程; 升级到 contract-v1.2.0 (主力档强制, 样板/参考档按 ADR-V2-025 策略)。
- [x] **CONTRACT-02**: Hook event 扩展 (1-2 新 event) — 例如 `SubagentStart` / `TaskCheckpoint` (对接 Phase 4.1 §F.Q3 audit ⚫ 6 项接入位 ADR 候选之一), 走完 proto 改动 + envelope schema + 主力档 runtime fire site + L3 governance trigger + cross-runtime parity test + 新 ADR (V2-026 候选)。

### D. WATCHLIST — 分散到相关 phase 顺手解决 (spread strategy)

- [x] **WATCH-00**: D120 Rust HookContext schema 补全 — 现 `HookContext::to_json/to_env_vars` 缺 `event` / `skill_id` 字段 + 缺 `GRID_EVENT` / `GRID_SKILL_ID` env, ADR-V2-006 §2-§3 envelope shape 不完整。Phase 5 早期 phase 必修 (D134 修的前置)。
- [x] **WATCH-01**: D109 — workflow.required_tools 不变量文档化 (CONTRACT phase 顺手)。
- [x] **WATCH-02**: D134 — Shipped skill hooks `.payload.output.X` → `.output.X` 改正 (per ADR-V2-006 §2.3 top-level), 修 7 个 example skill hook 脚本; 锁定 must-fix per 用户 Phase 5 决策 (D120 修完后顺接)。
- [x] **WATCH-03**: D136 — grid-runtime hook 在 probe turn 不触发 (3 contract xfails) 修正 (CONTRACT phase 顺手, 跟 ADR-V2-016 capability matrix probe turn 协同)。
- [x] **WATCH-04**: D142 + D143 — grid-runtime + claude-code-runtime EAASP_DEPLOYMENT_MODE 接入 + max_sessions=1 gate (~20 LOC each, SERVER phase 顺手)。
- [x] **WATCH-05**: NEW-D2 — test_chunk_type_contract.py 7-runtime 参数化 (现 仅 3 tests, CONTRACT phase 顺手, 与 CONTRACT-00 runtime 分级 review 同步用)。
- [x] **WATCH-06**: NEW-E2 — F3 ADR enforcement.trace 33 (corrected from 29) missing items 补 (advisory, 任一 phase 顺手) — ✅ COMPLETE 2026-05-22 Phase 5.5 Plan 01 @ `2303b3d`+`e84a57e` (5-contract trace fill + 4-strategy rationale; F3 WARN 33 → 12 explicit-strategic; F1/F2 0 FAIL)
- [x] **WATCH-07**: NEW-E3 — ADR-V2-019 enforcement.trace fill (status was already Accepted 2026-04-20; closes after WATCH-04, SERVER phase 收尾 — per Phase 5.4 Q9 correction this is trace fill, not status flip)。

### E. INTERFACE — Data/integration 横切层接入面规约 (ADR-only)

- [x] **INTERFACE-01**: data/integration boundary contract ADR 起草 — 新 ADR `ADR-V2-029-engine-data-integration-boundary.md` (type: strategy, crate-level), 描述 engine (user 60%+30%) 与 data/integration 横切层 (他人 10%) 之间的 boundary contract: customer data ingestion / SSO / third-party API / WORM 存储 / 信创 LLM 适配 / hook-out 接入面 categories; ADR-only, **不写 trait / proto skeleton** (per 用户 Phase 5 决策, V2-030 + V2-031 reserved for v3.2+). ✅ COMPLETE 2026-05-22 Phase 5.5 Plan 01 @ `0b23a01` (Accepted, F1-F4 lint PASS, §1 2-column table, §3 future-proofing rules). Note: ROADMAP/REQ originally cited V2-026 but V2-026/027/028 consumed in Phase 5.3/5.4 — renumbered to V2-029.

---

## Future Requirements (deferred to v3.3+)

> v3.2 (Triage milestone) PULLED IN: NEW-X4 → CI-01, NEW-X2 → CLI-X2, NEW-X3 → CLI-X3. Remaining items below STILL deferred. **D-batch count corrected**: real count = 102 open D-row (not ~40 from earlier estimate). v3.2 TRIAGE pass will classify these into P1/P2/P3/DEAD; v3.3+ scoping draws from the TRIAGE inbox.

- **CONTRACT-03**: 新 RPC method (Probe / Capabilities / MemorySync) — defer, premature 风险高
- **CONTRACT-04**: SubAgent first-class 协议 — defer 至 second consumer 出现
- **INTERFACE-02**: Rust trait + gRPC service skeleton — defer (V2-031 placeholder reserved in ADR-V2-029 §References)
- **INTERFACE-03**: EAASP / Grid 双产品 boundary 代码层 enforcement — defer (V2-030 placeholder reserved in ADR-V2-029 §References)
- **NEW-C1 / C3**: harness.rs / grid-eval 大文件拆分 — defer until second consumer (per Phase 4a project review)
- **D-batch sweep** — actual count 102 open D-row, classify in v3.2 TRIAGE-01..03, then schedule P1/P2 sweep phases in v3.3+ per module grouping
- **EAASP 与 Grid 分仓** — 分仓时点由后续 milestone 决定
- **grid-platform / grid-desktop / web* 增量功能开发** — dormant per ADR-V2-024 双轴 framework

---

## Out of Scope

- **`grid-sandbox` 仓库改名** — per ADR-V2-023 §P6, Grid 独立产品 (原 Leg B, see ADR-V2-024) 激活前不动
- **`git push origin main` 累积 push 控制** — Phase 4.2 期间已 push, Phase 5 期间继续累积, push 时机由人决策
- **Phase 0–2.5 历史 sign_off_commit retrofit** — 历史不完美接受, git history 为准
- **132 个历史 plan + 14 archived phase 迁入 GSD ROADMAP.md** — 冻结只读历史
- **F4 lint 52 module-overlap 警告 reconcile** — advisory-only 接受
- **`docs/dev/WORK_LOG.md` 替换为 STATE.md** — 二者并存 (GSD 例外)
- **DEFERRED_LEDGER 迁入 GSD backlog** — ledger SSOT 保留 (GSD 例外)
- **新 RPC method 与 SubAgent 协议** — defer 到 v3.2+ (CONTRACT-03/04 已 defer)
- **Data/integration 真实现** — Phase 5 仅 ADR (INTERFACE-01), trait/skeleton/code 全部 defer

---

## Traceability

> Filled by `/gsd-roadmapper` after Step 10 (✅ filled 2026-04-29 via `/gsd-roadmapper` for v3.1; ✅ extended 2026-05-23 for v3.2 — 6 new rows mapped to Phases 6.0/6.1/6.2). 每条 REQ-ID 1-to-1 映射到 ROADMAP.md `Phase Details` 中一个 phase。

| REQ-ID | Phase | Notes |
|--------|-------|-------|
| CLI-01 | 5.2 | |
| CLI-02 | 5.2 | |
| CLI-03 | 5.2 | |
| CLI-04 | 5.2 | |
| CLI-05 | 5.2 | |
| CLI-06 | 5.2 | |
| SERVER-01 | 5.4 | |
| SERVER-02 | 5.4 | |
| SERVER-03 | 5.4 | |
| SERVER-04 | 5.4 | |
| SERVER-05 | 5.4 | |
| CONTRACT-00 | 5.1 | (ADR-V2-025 候选) |
| CONTRACT-01 | 5.3 | (ChunkType 扩展, contract-v1.2.0 升级) |
| CONTRACT-02 | 5.3 | (Hook event 扩展, ADR-V2-026 候选) |
| WATCH-00 | 5.0 | (D120 — Phase 5 早期 phase 必修, D134 前置) |
| WATCH-01 | 5.3 | (D109) |
| WATCH-02 | 5.0 | (D134 — must fix, D120 修完后顺接) |
| WATCH-03 | 5.3 | (D136) |
| WATCH-04 | 5.4 | (D142 + D143) |
| WATCH-05 | 5.1 | (NEW-D2) |
| WATCH-06 | 5.5 | ✅ (NEW-E2) — closed 2026-05-22 Plan 01 @ `2303b3d`+`e84a57e`; F3 WARN 33 → 12 explicit-strategic |
| WATCH-07 | 5.4 | (NEW-E3 — D142/D143 关闭后顺接) |
| INTERFACE-01 | 5.5 | ✅ (ADR-only, ADR-V2-029 Accepted) — closed 2026-05-22 Plan 01 @ `0b23a01`; V2-030 + V2-031 reserved v3.2+ |
| CI-01 | 6.0 | (NEW-X4 pytest fixture-scope fix — Phase 3 Contract Matrix CI RED → GREEN) |
| CLI-X2 | 6.1 | (NEW-X2 sibling kill_session anti-pattern — delete_session + export_session typed GridError + exit 4) |
| CLI-X3 | 6.1 | (NEW-X3 --all-features grid-engine 12 errors investigation + fix vs filter decision) |
| TRIAGE-01 | 6.2 | (102 D-row + 3 NEW-X classify P1/P2/P3/DEAD) |
| TRIAGE-02 | 6.2 | (DEAD row 物理迁移到 DEFERRED_LEDGER_ARCHIVE.md) |
| TRIAGE-03 | 6.2 | (v3.3-INBOX.md 按 module 分组汇总 P1/P2/P3) |

**Total v3.1 requirements:** 23 REQ-IDs (CLI 6 + SERVER 5 + CONTRACT 3 + WATCHLIST 8 + INTERFACE 1) — ✅ CLOSED 2026-05-22
**Total v3.2 requirements:** 6 REQ-IDs (CI 1 + CLI 2 + TRIAGE 3) — mapped 2026-05-23 to Phases 6.0/6.1/6.2 ✓
**Granularity:** v3.1 = 6 phases; v3.2 = 3 phases (Phase 6.0 / 6.1 / 6.2, mapped by `/gsd-roadmapper` 2026-05-23 — intentional light triage milestone, see ROADMAP §Granularity 备注 v3.2)
**Mapping density:** v3.2 = 1 REQ/phase (6.0) + 2 REQ/phase (6.1) + 3 REQ/phase (6.2), avg 2 — light, intentional for triage milestone

---

*v3.1 Requirements 来源: Phase 4 milestone close + ADR-V2-024 §1 双轴 framework + Open Item #2/#3 工时 baseline + 优先发力组合 + 用户 Phase 5 决策. Defined 2026-04-29 via `/gsd-new-milestone` Step 9 conversation-mode (no research).*

*Milestone v3.1 ✅ CLOSED 2026-05-22 — all 23 REQ-IDs traced to completed phases. Closed via Plan 05.5-02 close cascade (Task 02.04).*

*v3.2 Requirements 来源: v3.1 close cascade carry-over (NEW-X4 P2 from Phase 3 Contract Matrix CI scan post-push 2026-05-23; NEW-X2/X3 P3 from Phase 5.5 Plan 01 scope-limit) + LEDGER 102 D-row 实际计数 surprise (REQUIREMENTS 原 ~40 估算严重低估). Defined 2026-05-23 via `/gsd-new-milestone` Step 9 conversation-mode (no research — scope concrete & pre-locked). Phase mapping 完成 2026-05-23 via `/gsd-roadmapper` Step 10 — 6/6 REQ-IDs ✓, 0 orphans, 0 double-mapped.*
