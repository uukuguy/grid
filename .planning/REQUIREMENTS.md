# Grid — Requirements

> **Brownfield context**: 14 archived phases (Phase BA → Phase 4a) under dev-phase-manager already shipped EAASP v2.0 functional baseline. Phase 4 milestone v3.0 (3 phases: 4.0 / 4.1 / 4.2) closed 2026-04-28 with ADR-V2-024 Accepted (双轴模型 supersedes ADR-V2-023). v3.1 Phase 5 Engine Hardening closed 2026-05-22 (6 phases, 23 REQ-IDs, 6 ADRs Accepted). v3.2 Phase 6 Tech-Debt Triage & CI Red Line Clearance closed 2026-05-26 (3 phases, 6 REQ-IDs, 0 ADRs — intentional light triage). This REQUIREMENTS.md now scopes **milestone v3.3 — Engine + Platform Debt Sweep (Focused)**.

---

## v3.3 Requirements (Milestone: Engine + Platform Debt Sweep — Focused)

> **Per ADR-V2-024 §1 双轴模型 + Open Item #3**: 优先发力组合 grid-cli + grid-server 不变; 其余 (grid-platform / grid-desktop / web*) 保持 dormant. 工时 baseline: Grid 全栈 ≈60% / EAASP 引擎 ≈30% / 元工作 ≈10%.
>
> **Scope shape**: focused debt sweep across 4 high-yield modules (grid-engine + contract + L2 + L3). ~30 rows total = 11 P2 (must) + ~19 P3 (selective stretch). NOT full INBOX drain — L4 / hooks / eval / grid-server (1 row) / cross-cutting modules defer to v3.4+ untouched in `.planning/v3.3-INBOX.md`. 0 P1 rows surfaced in INBOX, so milestone is "should-fix" not "must-fix"; new P1 surfacing during execution allowed to interrupt/insert.
>
> **Per phase**: ≤10 rows for cohesion (per INBOX scoping guidance). P2 before P3 within each phase.

### A. ENGINE — grid-engine harness wiring (Phase 7.0)

- [ ] **ENGINE-01**: D102 — `AgentLoopConfig.compaction` 字段接入 YAML 配置层 (P2). 当前 `crates/grid-engine/src/agent_loop/config.rs` 定义 `compaction` 字段但 `crates/grid-server/src/config.rs` YAML→struct 流不传透; Result: 用户在 `config.yaml` 写 `compaction:` block 后 silent ignore. Fix: 沿用 ADR-V2-028 strict-by-default 模式; YAML 字段未识别 → 报错; 字段识别但缺失 → use default; 测试覆盖 round-trip。LEDGER L232。
- [ ] **ENGINE-02**: D3 — harness 接入 `payload.user_preferences` (P5) + `trim_for_budget()` (P3). 当前 harness 没有 surface user preferences 到 agent loop; trim 在 turn 边界手动调用而非 budget-driven。LEDGER L106。
- [ ] **ENGINE-03**: D57 — `harness_payload_integration.rs` 复制 `build_memory_preamble` 函数 (P3). DRY violation — 应该 import grid-engine 的实现。LEDGER L177。
- [ ] **ENGINE-04**: D58 — `test_initialize_injects_memory_refs_preamble` 不走 Send 全路径 (P3). 测试漏掉真实流; 补全 Send 路径 assertion。LEDGER L178。
- [ ] **ENGINE-05**: D103 — `find_tail_boundary()` O(N²) 重估风险 (P3). hot path scanning; 长会话下可能 N² 退化。Profile + benchmark + 决定 fix 或 doc-only warning。LEDGER L233。
- [ ] **ENGINE-06**: D104 — 反应式 guard 在 harness 而非 pipeline (P3). architecture drift — guard 应该住在 pipeline 而非 harness; 这是 ADR-V2-026 ExecutionMode 思路的延续。LEDGER L234。

### B. CONTRACT — contract observability + bridge (Phase 7.1)

- [ ] **CONTRACT-01**: D137 — Phase 2.5 S0.T4/T5 multi-turn observability + MCP bridge live + PRE_COMPACT 阈值触发 (P2). 当前 multi-turn turn-by-turn metric 在 grid-runtime 残缺; MCP bridge 在 nanobot/goose 有但 grid-runtime 没接; PRE_COMPACT 阈值 hard-coded 没接 ChunkType。LEDGER L249。
- [ ] **CONTRACT-02**: D138 — skill-workflow enforcement 测试可脚本化 deny-path mock LLM (P2). 当前 deny-path 测试要 live LLM 走过去看 reject; 没有 mock 让 skill 强制 deny scenario 可重复。LEDGER L250。
- [ ] **CONTRACT-03**: D5 — grpc_integration 测试迁移到 v2 telemetry envelope (P3). 测试仍用旧 envelope shape, 跟 contract-v1.2 (Phase 5.3 升级) 漂移。LEDGER L108。
- [ ] **CONTRACT-04**: D6 — certifier 补充 SessionPayload P1-P5 字段断言 (P3). certifier 不验 SessionPayload 内层字段, 通过 P1-P5 通信但 schema 不锁定。LEDGER L109。
- [ ] **CONTRACT-05**: D55 — proto3 submessage presence 统一用 `HasField` (P3). 跨 7 runtime 当前用 truthy fallback (始终 true) 而非 `HasField`; 加测试 + ADR-V2-021 lineage 风格 doc。LEDGER L175。

### C. L2 — L2 connection-pool + Pipeline (Phase 7.2)

- [ ] **L2-01**: D12 — L2 memory-engine connection-per-call 延迟浪费 (P2). 每个 read/write 重新 open SQLite connection; high-concurrency 下 throughput 严重退化。Connection pool 重构。LEDGER L115。
- [ ] **L2-02**: D94 — MemoryStore 单例 + 共享连接 (D12 收尾, P2). MemoryStore 设计目前 transient; 应该 singleton 持久持有 connection pool。与 L2-01 一起做。LEDGER L224。
- [ ] **L2-03**: D91 — HNSW 软删 tombstone rebuild 策略 (P2). 当前 delete 只 mark tombstone, index 越来越脏; 需要 trigger rebuild 阈值 (e.g., 30% tombstone → rebuild)。LEDGER L221。
- [ ] **L2-04**: D93 — `embed_batch` 顺序实现 (P2). 当前 batch embed 内部仍 sequential; 应该并发 fan-out (但要 respect rate limit)。LEDGER L223。
- [ ] **L2-05**: D98 — `HybridIndex.search()` 每次重建 HNSWVectorIndex (P2). 每次 search rebuild 是 hot path 重建 — 严重性能 bug。Cache rebuild 或改成 incremental。LEDGER L228。
- [ ] **L2-06**: D11 — skill-registry `scope` 过滤在 `LIMIT` 之后 (P3). bug — 先 LIMIT 再 filter 可能返回少于 limit 的结果。Order 反一下。LEDGER L114。
- [ ] **L2-07**: D13 — L2 `archive()` 创建 "archive of archive" + FTS 仍可搜 (P3). archived rows 应该从 FTS 移除 (或 filter); 不然 archive 没有实际隔离效果。LEDGER L116。
- [ ] **L2-08**: D30 — L2/L3 `busy_timeout=5000` 未统一 (P3). 散落 magic number; 提到 config 或常量。LEDGER L142。

### D. L3 — L3 RBAC + hardening (Phase 7.3)

- [ ] **L3-01**: D8 — `access_scope` 真实 RBAC 执行 (P2). 当前 access_scope 字段记录但不强制; user role/scope 通过 token 携带但没有 enforcement gate。Implement RBAC middleware。LEDGER L111。
- [ ] **L3-02**: D9 — `skill_usage` 返回真实遥测 (P2). 当前 endpoint 返回 mock 数据; 接真实 audit log query。LEDGER L112。
- [ ] **L3-03**: D46 — Skill `access_scope` 无 RBAC / 命名空间校验 (P2). skill manifest 声明 access_scope 但部署/调用时不验; 与 L3-01 关联。LEDGER L161。
- [ ] **L3-04**: D22 — L3 无全局 FastAPI exception handler (P3). 异常 leak 内部 stack trace 给客户端; 加 global handler 返回标准 error shape。LEDGER L130。
- [ ] **L3-05**: D23 — L3 无 loguru/logging 初始化 (P3). 启动时没显式配置 logging; 跟 grid-server 配置惯例不一致。LEDGER L131。
- [ ] **L3-06**: D17 — L3 validate_session() `hook["hook_id"]` KeyError 风险 (P3). 字典 access 假设 key 存在; 用 `.get()` + 缺失 raise typed error。LEDGER L125。
- [ ] **L3-07**: D18 — L3 validate_session() 对 `session_id` path param 不校验 (P3). 接受任意字符串 session_id; 应该 validate UUID/format。LEDGER L126。
- [ ] **L3-08**: D26 — L3 tests 用 `time.sleep(1.1)` 防撞秒 (P3). flaky 测试 anti-pattern; 改成 monotonic clock 或 mock time。LEDGER L134。

---

## v3.2 Requirements (CLOSED 2026-05-26 — historical reference)

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
| TRIAGE-03 | 6.2 | ✅ (v3.3-INBOX.md 按 module 分组汇总 P1/P2/P3 @ `24ee8ed`) |
| ENGINE-01 | 7.0 | 🟡 STARTED 2026-06-01 (D102 AgentLoopConfig YAML wiring) |
| ENGINE-02 | 7.0 | 🟡 STARTED 2026-06-01 (D3 harness payload.user_preferences + trim_for_budget) |
| ENGINE-03 | 7.0 | 🟡 STARTED 2026-06-01 (D57 build_memory_preamble DRY) |
| ENGINE-04 | 7.0 | 🟡 STARTED 2026-06-01 (D58 test_initialize_injects_memory_refs_preamble Send path) |
| ENGINE-05 | 7.0 | 🟡 STARTED 2026-06-01 (D103 find_tail_boundary O(N²)) |
| ENGINE-06 | 7.0 | 🟡 STARTED 2026-06-01 (D104 反应式 guard in pipeline) |
| CONTRACT-01 | 7.1 | 🟡 STARTED 2026-06-01 (D137 multi-turn observability + MCP bridge + PRE_COMPACT 阈值) |
| CONTRACT-02 | 7.1 | 🟡 STARTED 2026-06-01 (D138 skill-workflow deny-path mock LLM) |
| CONTRACT-03 | 7.1 | 🟡 STARTED 2026-06-01 (D5 grpc_integration v2 telemetry envelope migration) |
| CONTRACT-04 | 7.1 | 🟡 STARTED 2026-06-01 (D6 certifier SessionPayload P1-P5 字段断言) |
| CONTRACT-05 | 7.1 | 🟡 STARTED 2026-06-01 (D55 proto3 submessage HasField 统一) |
| L2-01 | 7.2 | 🟡 STARTED 2026-06-01 (D12 connection-per-call 延迟) |
| L2-02 | 7.2 | 🟡 STARTED 2026-06-01 (D94 MemoryStore 单例 + 共享连接) |
| L2-03 | 7.2 | 🟡 STARTED 2026-06-01 (D91 HNSW 软删 tombstone rebuild) |
| L2-04 | 7.2 | 🟡 STARTED 2026-06-01 (D93 embed_batch 并发) |
| L2-05 | 7.2 | 🟡 STARTED 2026-06-01 (D98 HybridIndex 重建消除) |
| L2-06 | 7.2 | 🟡 STARTED 2026-06-01 (D11 skill-registry scope after LIMIT bug) |
| L2-07 | 7.2 | 🟡 STARTED 2026-06-01 (D13 L2 archive() FTS 仍可搜) |
| L2-08 | 7.2 | 🟡 STARTED 2026-06-01 (D30 busy_timeout 统一) |
| L3-01 | 7.3 | 🟡 STARTED 2026-06-01 (D8 access_scope 真实 RBAC) |
| L3-02 | 7.3 | 🟡 STARTED 2026-06-01 (D9 skill_usage 真实遥测) |
| L3-03 | 7.3 | 🟡 STARTED 2026-06-01 (D46 Skill access_scope namespace 校验) |
| L3-04 | 7.3 | 🟡 STARTED 2026-06-01 (D22 L3 global FastAPI exception handler) |
| L3-05 | 7.3 | 🟡 STARTED 2026-06-01 (D23 L3 loguru/logging 初始化) |
| L3-06 | 7.3 | 🟡 STARTED 2026-06-01 (D17 hook_id KeyError 风险) |
| L3-07 | 7.3 | 🟡 STARTED 2026-06-01 (D18 session_id path param 校验) |
| L3-08 | 7.3 | 🟡 STARTED 2026-06-01 (D26 time.sleep flaky 测试) |

**Total v3.1 requirements:** 23 REQ-IDs (CLI 6 + SERVER 5 + CONTRACT 3 + WATCHLIST 8 + INTERFACE 1) — ✅ CLOSED 2026-05-22
**Total v3.2 requirements:** 6 REQ-IDs (CI 1 + CLI 2 + TRIAGE 3) — ✅ CLOSED 2026-05-26
**Total v3.3 requirements:** 27 REQ-IDs (ENGINE 6 + CONTRACT 5 + L2 8 + L3 8) — 🟡 STARTED 2026-06-01 via `/gsd-roadmapper` (Phase 7.0 / 7.1 / 7.2 / 7.3); 27/27 mapped, 0 orphans, 0 double-mapped
**Granularity:** v3.1 = 6 phases; v3.2 = 3 phases; v3.3 = 4 phases (Phase 7.0 / 7.1 / 7.2 / 7.3) per per-module batching
**Mapping density v3.3:** 6 REQ/phase (7.0) + 5 REQ/phase (7.1) + 8 REQ/phase (7.2) + 8 REQ/phase (7.3), avg ≈7 — within "≤10 per phase" cohesion limit per INBOX guidance

---

*v3.1 Requirements 来源: Phase 4 milestone close + ADR-V2-024 §1 双轴 framework + Open Item #2/#3 工时 baseline + 优先发力组合 + 用户 Phase 5 决策. Defined 2026-04-29 via `/gsd-new-milestone` Step 9 conversation-mode (no research).*

*Milestone v3.1 ✅ CLOSED 2026-05-22 — all 23 REQ-IDs traced to completed phases. Closed via Plan 05.5-02 close cascade (Task 02.04).*

*v3.2 Requirements 来源: v3.1 close cascade carry-over (NEW-X4 P2 from Phase 3 Contract Matrix CI scan post-push 2026-05-23; NEW-X2/X3 P3 from Phase 5.5 Plan 01 scope-limit) + LEDGER 102 D-row 实际计数 surprise (REQUIREMENTS 原 ~40 估算严重低估). Defined 2026-05-23 via `/gsd-new-milestone` Step 9 conversation-mode (no research — scope concrete & pre-locked). Phase mapping 完成 2026-05-23 via `/gsd-roadmapper` Step 10 — 6/6 REQ-IDs ✓, 0 orphans, 0 double-mapped. ✅ CLOSED 2026-05-26.*

*v3.3 Requirements 来源: v3.2 close cascade output `.planning/v3.3-INBOX.md` (TRIAGE-03 2026-05-26 @ commit `24ee8ed`) — 85 P2/P3 rows across 9 modules. Defined 2026-06-01 via `/gsd-new-milestone` Step 9 conversation-mode (skip research per user — debt rows concrete with LEDGER references). Module selection: grid-engine + contract + L2 + L3 (4 highest-yield buckets, all P2 prioritized + selective P3 stretch). Phase mapping ✅ completed 2026-06-01 via `/gsd-roadmapper` Step 10 — 27/27 REQ-IDs covered across 4 phases (7.0/7.1/7.2/7.3), 0 orphans, 0 double-mapped.*
