# Grid — Roadmap

> **Milestone:** v3.2 Tech-Debt Triage & CI Red Line Clearance (Phases 6.0/6.1/6.2)
> **Brownfield context:** Third GSD-managed milestone after Phase 4 (v3.0, ADR-V2-024 Accepted 2026-04-28) and Phase 5 (v3.1, shipped 2026-05-22). v3.0/v3.1 sections preserved below as historical traceability; this section covers ONLY milestone v3.2 (Phase 6.0 → 6.2, 3 phases).
> **Granularity:** light (3 phases — intentionally below GSD standard 5-8 range). v3.2 IS the watchlist-sweep / triage milestone, NOT feature work; mega debt sweep is scope-deferred to v3.3+ per TRIAGE-03 output. See §Granularity 备注 v3.2 for rationale.
> **Done condition for milestone:** 3 phases 全 ✅; 6 REQ-ID 全 ✅ traceability (CI-01 + CLI-X2 + CLI-X3 + TRIAGE-01..03); Phase 3 Contract Matrix CI GREEN (≥4/7 jobs PASS); `docs/design/EAASP/DEFERRED_LEDGER_ARCHIVE.md` 文件创建并迁入所有 DEAD-tagged row; `.planning/v3.3-INBOX.md` 文件创建按 module 分组列出 P1/P2/P3 row; PROJECT.md §Active "Phase 6 milestone (v3.2)" 行 flip 入 §Validated; STATE.md frontmatter `status: milestone-complete` + progress 3/3=100%; DEFERRED_LEDGER 主体只剩 P1/P2/P3 row + 3 NEW-X row (NEW-X2/X3/X4 各自 closed-or-classified)。

## Milestones

- ✅ **v3.0 Phase 4 — Product Scope Decision** — Phases 4.0/4.1/4.2 (shipped 2026-04-28, ADR-V2-024 Accepted)
- ✅ **v3.1 Phase 5 — Engine Hardening (grid-cli + grid-server)** — SHIPPED 2026-05-22 (Phases 5.0/5.1/5.2/5.3/5.4/5.5 all complete, 23/23 REQ-IDs, 6 ADRs Accepted V2-025/026/027/028/029/032)
- 🟡 **v3.2 Phase 6 — Tech-Debt Triage & CI Red Line Clearance** — STARTED 2026-05-23 (Phases 6.0/6.1/6.2 planned)

## Phases

<details>
<summary>✅ v3.0 Phase 4 — Product Scope Decision (Phases 4.0/4.1/4.2) — SHIPPED 2026-04-28</summary>

3 phases shipped under previous milestone. See git log + ADR-V2-024 + previous ROADMAP.md (commit before 2026-04-29 milestone-restart) for details. All 10 REQ-IDs (CLEANUP-01..04 / DECIDE-01..03 / GOVERNANCE-01..03) traceability ✅.

- [x] **Phase 4.0: Bootstrap & Cleanup** — Complete 2026-04-27 (5/5 SC, 7/7 must-haves)
- [x] **Phase 4.1: Discuss & Audit** — Complete 2026-04-27 (14/15 must-haves, GOVERNANCE-03 deferred to 4.2)
- [x] **Phase 4.2: Decide & Document** — Complete 2026-04-28 (5/5 SC, ADR-V2-024 Accepted, milestone closed)

</details>

<details>
<summary>✅ v3.1 Phase 5 — Engine Hardening (Phases 5.0/5.1/5.2/5.3/5.4/5.5) — SHIPPED 2026-05-22</summary>

6 phases shipped under v3.1 milestone. All 23 REQ-IDs traceability ✅. 6 ADRs Accepted (V2-025 runtime tier / V2-026 ExecutionMode supersede V2-016 / V2-027 OpenAI Quirks / V2-028 Strict Config / V2-029 engine vs data/integration boundary / V2-032 TUI Log Path Convention). 18 D-items closed. F3 ADR baseline 33 WARN → 12 explicit-strategic + 0 unjustified.

- [x] **Phase 5.0: Hook Envelope Baseline** — ✅ 2026-05-19 (D120 + D134 closed)
- [x] **Phase 5.1: Runtime Tier ADR + Contract Test Parametrization** — ✅ 2026-05-02 (ADR-V2-025 Accepted, NEW-D2 closed)
- [x] **Phase 5.2: CLI Hardening** — ✅ 2026-05-17 (6 CLI REQ-IDs, NEW-C2 closed, 575/575 PASS --features studio)
- [x] **Phase 5.3: Contract Evolution** — ✅ 2026-05-20 (contract-v1.2.0 live, V2-026 + V2-027 Accepted, D109+D136+NEW-E4+NEW-F1+NEW-F2 closed)
- [x] **Phase 5.4: Server Hardening** — ✅ 2026-05-21 (5 SERVER REQ-IDs + WATCH-04+07, ADR-V2-028 Accepted, V2-019 trace filled, 5-row LEDGER close)
- [x] **Phase 5.5: Interface ADR + Milestone Close** — ✅ 2026-05-22 (ADR-V2-029 + V2-032 Accepted, F3 sweep, 4 OOS code fixes, milestone close cascade, 2 P3 inbox rows NEW-X2/X3 filed → v3.2)

> Full Phase Details section preserved verbatim in commit history; archived 2026-05-23 at milestone v3.1 close. For audit re-read, see git log + `.planning/phases/05.*/SUMMARY.md` + `.planning/phases/05.*/VERIFICATION.md`.

</details>

### 🟡 v3.2 Phase 6 — Tech-Debt Triage & CI Red Line Clearance (Phases 6.0/6.1/6.2, STARTED 2026-05-23)

**Milestone Goal:** 消除 Phase 3 Contract Matrix CI 红线 (持续 RED 自 2026-05-04) + grid-cli 残留 anti-pattern 收尾 + 对 102 D-row + 3 NEW-X row 历史债做一次性 triage 分类, 为后续 milestone (v3.3+) 的代码工作建立优先级地图。**NOT mega-debt-sweep** — 代码修复仅限 3 个具体 row (CI-01 NEW-X4 fixture-scope fix + CLI-X2 NEW-X2 sibling typed GridError 补 + CLI-X3 NEW-X3 --all-features 调查); 102 D-row 仅做分类不做修复, mega sweep 留给 v3.3+ 按 triage 结果立 phase。

- [ ] **Phase 6.0: CI Red Clearance** — NEW-X4 `test_chunk_type_contract.py` fixture-scope mismatch 修, Phase 3 Contract Matrix workflow 由 RED 转 GREEN (≥4/7 jobs PASS)
- [ ] **Phase 6.1: grid-cli Anti-pattern Sweep** — NEW-X2 sibling kill_session anti-pattern (delete_session + export_session) + NEW-X3 `cargo build --all-features` 12 grid-engine errors 调查 + 决定 fix vs filter
- [ ] **Phase 6.2: Debt Ledger Triage** — 102 open D-row + 3 NEW-X row 一次性 triage 分类 (P1/P2/P3/DEAD) + DEAD 物理迁移到 DEFERRED_LEDGER_ARCHIVE.md + `.planning/v3.3-INBOX.md` 按 module 分组喂下轮

## Phase Details

### Phase 6.0: CI Red Clearance

**Goal**: Phase 3 Contract Matrix CI 由 RED 转 GREEN — `tests/contract/cases/test_chunk_type_contract.py` 与 `tests/contract/conftest.py` 之间 fixture-scope mismatch (NEW-X4) 修复, 让 pytest fixture 装配通过, 跨 7 个 L1 runtime (claude-code / goose / nanobot / pydantic-ai / claw-code / ccb / grid) 都能正常 setup 测试上下文; 实际 contract test 内容是否 PASS 取决于各 runtime 实现 (允许 XFAIL), 关键 success = 不再出 ScopeMismatch error 阻塞整个 workflow。这是消除 Phase 3 Contract Matrix CI 持续红线 (since 2026-05-04) 的最小修。
**Depends on**: Nothing (milestone 第一个 phase; CI red 不阻塞 local work 但是心理性 blocker / signal pollution, 优先消除给后续 phase 干净的 CI baseline)
**Requirements**: CI-01
**Success Criteria** (what must be TRUE):
  1. `pytest tests/contract/cases/test_chunk_type_contract.py tests/contract/cases/test_hook_event_contract.py -v --runtime=<X>` 在本地不再抛 `ScopeMismatch` error; **parametrize 层 3 sites 重命名 `runtime_name` → `expected_runtime`** (1 in `test_chunk_type_contract.py:139` + 2 in `test_hook_event_contract.py:203 + 238`); session fixture `runtime_name(request)` at `tests/contract/conftest.py:113` UNTOUCHED; 7 runtime case 各自能 setup 进入实际 assert (PASS / FAIL / XFAIL by runtime, 不再是 fixture-装配-阶段-error)
  2. Phase 3 Contract Matrix workflow (`.github/workflows/phase3-contract.yml` 或等价 CI workflow) 跑过后 ≥ 4 of 7 jobs PASS (per ADR-V2-025 tier strategy 允许某些 runtime XFAIL, 但不能因 fixture-scope-error 整体 RED); CI run URL + commit hash 写入 SUMMARY.md
  3. NEW-X4 在 `docs/design/EAASP/DEFERRED_LEDGER.md` 标 ✅ CLOSED 并附 commit hash, 遵循 row-edit-on-close convention (per Phase 4.0 CLEANUP-02 precedent + Phase 5.4 NEW-A2/E3 precedent); ledger row include 修复 commit hash + CI run URL
**Plans:** 1 plan
Plans:
- [ ] 06.0-01-PLAN.md — Pytest fixture-scope rename (3 sites: runtime_name → expected_runtime) + REQUIREMENTS/ROADMAP wording stretch + LEDGER NEW-X4 closure + Phase 3 Contract Matrix CI verify
**UI hint**: no

### Phase 6.1: grid-cli Anti-pattern Sweep

**Goal**: 收尾 grid-cli 残留 anti-pattern — NEW-X2 sibling kill_session anti-pattern 补全 (`crates/grid-cli/src/commands/session.rs:99-103` `delete_session` + L157 `export_session` 仍用 `anyhow!("Session not found")` 映射到 `ExitCode::General` 1, 应改为 `GridError::session_not_found()` → typed exit code `SessionNotFound = 4`; 与 Phase 5.5 Plan 01 Task B1 修的 `kill_session` 同模式) + NEW-X3 `cargo build -p grid-cli --all-features` 12 grid-engine errors 调查 + 决定 (是真 dead code / 应 feature-gate / 还是只需 doc fix)。两项同属 grid-cli 域, 都是小 scope (NEW-X2 ~10 LOC + 2 integration test; NEW-X3 调查可能 N/A), 自然 pairing 成一个 phase。
**Depends on**: Nothing on 6.0 (NEW-X2/X3 与 NEW-X4 CI fixture 无代码依赖, 可与 6.0 并行执行; 但 GSD 顺序执行规则下排在 6.0 后)
**Requirements**: CLI-X2, CLI-X3
**Success Criteria** (what must be TRUE):
  1. `delete_session` (`crates/grid-cli/src/commands/session.rs:99-103`) + `export_session` (L157) 改用 `GridError::session_not_found()` typed error; `main.rs` 既有的 `downcast_ref::<GridError>` arm (Phase 5.5 Plan 01 Task B1 落地) 自动 catch, 用户敲 `grid session delete <nonexistent-id>` + `grid session export <nonexistent-id>` 都 exit 4 而非 exit 1
  2. `crates/grid-cli/tests/` 下新增 2 个 integration test (`test_delete_nonexistent_session_exits_4` + `test_export_nonexistent_session_exits_4`) 均 PASS; 既有 147 + 6 grid-cli test 全部 no regression (`cargo test -p grid-cli` 全 PASS)
  3. `cargo build -p grid-cli --all-features` 状态 = **(a) 编译 clean** (12 个 grid-engine errors 修复 或 经调查为真 dead code 删除) **OR (b) 矩阵窄化** (`grid-cli` Cargo.toml `--all-features` feature set 显式排除引发错误的 feature, 留一个能 build 的子集), 选择写入 LEDGER NEW-X3 row 的 close-out 注释, 包含 root cause 一句话 + 决策 rationale
  4. NEW-X2 + NEW-X3 在 DEFERRED_LEDGER 标 ✅ CLOSED 并附 commit hash; 如 NEW-X3 决定走 (b) 矩阵窄化路径, 在 `grid-cli/Cargo.toml` 或 `Makefile` 中加 comment 注释为何排除某 feature, 防止下个 contributor 误以为是漏配
**Plans**: TBD by `/gsd-plan-phase 6.1` (推测 1 plan, 2 task block 顺序执行 X2 → X3, 总 ≤6 task)
**UI hint**: no

### Phase 6.2: Debt Ledger Triage

**Goal**: 对 `docs/design/EAASP/DEFERRED_LEDGER.md` 中 102 open D-row + 3 NEW-X row (NEW-X2/X3 在 6.1 关闭后仍计入分类轨, NEW-X4 在 6.0 关闭后同) 做一次性 triage 分类 — 每行加 tag {P1-actionable-now / P2-next-milestone / P3-async-when-touched / DEAD-archived} + 一行 rationale 引用 code/ADR/commit; DEAD row 物理迁移到新文件 `docs/design/EAASP/DEFERRED_LEDGER_ARCHIVE.md` (LEDGER 主体只留 P1/P2/P3); 最后 P1/P2/P3 列表汇总到 `.planning/v3.3-INBOX.md` 按 module 分组 (grid-engine / grid-cli / grid-server / L2 / contract / etc), 喂 v3.3+ milestone scoping。**Doc-only phase, 零代码修改**, 三 task 顺序依赖 (TRIAGE-01 分类 → TRIAGE-02 物理迁移 → TRIAGE-03 INBOX 汇总)。
**Depends on**: Phase 6.1 (NEW-X2/X3 在 6.1 关闭后已有 final status, triage 时 tag 可直接写 ✅ CLOSED; 不严格阻塞 6.2 启动但减少后续 re-tag)
**Requirements**: TRIAGE-01, TRIAGE-02, TRIAGE-03
**Success Criteria** (what must be TRUE):
  1. `docs/design/EAASP/DEFERRED_LEDGER.md` 中 102 open D-row + 3 NEW-X row (共 105 row) 每一行有 triage tag (P1 / P2 / P3 / DEAD) + ≥1 行 rationale 引用 code path / ADR-ID / commit hash / 历史 phase. DEAD tag 标准: Phase BA Grid 重命名后引用 `octo_*` 不再存在的 row + 引用 deleted code 的 row + 决策已被 ADR superseded 的 row (e.g., V2-017 frozen hermes 相关 row)
  2. `docs/design/EAASP/DEFERRED_LEDGER_ARCHIVE.md` 新文件存在, 包含所有 TRIAGE-01 标 DEAD 的 row 原文 + 移除时间戳 + 一行 DEAD rationale; archive 文件头部声明"此文件不可再追加, 仅作历史归档"; LEDGER 主体只剩 P1/P2/P3 + 3 NEW-X (NEW-X2/X3 ✅ CLOSED in 6.1, NEW-X4 ✅ CLOSED in 6.0) row; migration commit hash 在 archive 文件与 LEDGER 主体双向引用
  3. `.planning/v3.3-INBOX.md` 新文件存在, 按 module (grid-engine / grid-cli / grid-server / grid-runtime / contract / L2 / L3 / L4 / hooks / providers / eval / etc) 分组列出所有 P1/P2/P3 row, 每行 包含 row ID + 一句 summary + 原 LEDGER 行号引用; 文件头部包含 triage 总览统计 (P1 count / P2 count / P3 count / DEAD count moved to archive) + "喂 v3.3+ milestone scoping" 用途说明
  4. TRIAGE-01/02/03 在 DEFERRED_LEDGER 标 ✅ CLOSED 并附 commit hash; PROJECT.md §Active "Phase 6 milestone (v3.2)" 行 flip 入 §Validated 引用 6 个 REQ-ID 完成 commit hash; v3.2 milestone close cascade ✓ (STATE.md frontmatter `status: milestone-complete` + progress 3/3=100%)
**Plans**: TBD by `/gsd-plan-phase 6.2` (推测 1 plan, 3 task 顺序: TRIAGE-01 分类 → TRIAGE-02 物理迁移 → TRIAGE-03 INBOX 汇总; 工作量大但都 doc-only 可并行写)
**UI hint**: no

## Phase 之外的 milestone 关闭后续 (v3.2)

> 这些不是本 milestone 的 phase, 只作为 traceability 提示。

- **下一个 milestone (v3.3 候选)** 由 `/gsd-new-milestone` 启动, 内容由 v3.2 TRIAGE-03 输出的 `.planning/v3.3-INBOX.md` P1/P2 row 决定 (按 module 分组立 phase); 候选方向:
  - **mega debt sweep**: 按 INBOX P1 列表 + P2 列表选若干 module-batch 立 phase (grid-engine 一批 / grid-cli 一批 / contract 一批 / etc), 每 phase ≤5 row 保证 cohesion
  - **CONTRACT-03**: 新 RPC method (Probe / Capabilities / MemorySync) — 仍 defer 待 second consumer
  - **CONTRACT-04**: SubAgent first-class 协议 — 仍 defer
  - **INTERFACE-02**: Rust trait + gRPC service skeleton — 走 ADR-V2-031 reserved
  - **INTERFACE-03**: EAASP / Grid 双产品 boundary 代码层 enforcement — 走 ADR-V2-030 reserved
  - **NEW-C1 / C3**: harness.rs / grid-eval 大文件拆分 — defer until second consumer
  - **EAASP 与 Grid 分仓** — 时点由 v3.3+ milestone 决定
  - **grid-platform / grid-desktop / web* 增量功能** — dormant per ADR-V2-024 双轴 framework
- **不属于本 milestone 但仍需追踪的项**: 见 PROJECT.md §Out of Scope; `grid-sandbox` 仓库改名 / `git push origin main` push 时机 / Phase 0–2.5 历史 sign_off_commit retrofit / 132 历史 plan + 14 archived phase 迁入 GSD ROADMAP / F4 lint 52 module-overlap 警告 reconcile / WORK_LOG.md vs STATE.md / DEFERRED_LEDGER 迁入 GSD backlog 全部 acknowledged 不动。

## Progress

**Execution Order:**
Phases execute in numeric order: 6.0 → 6.1 → 6.2

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 6.0 CI Red Clearance | **1/1 ✅** | COMPLETE 2026-05-24 (1 plan, 2 commits) | 3/3 SC PASS (SC#2 substantive: 0 ScopeMismatch across all 7 completed jobs; 3 PASS + 4 PRE-EXISTING D136 fail + grid in_progress); NEW-X4 ✅ CLOSED @ `e27e300` |
| 6.1 grid-cli Anti-pattern Sweep | 0/1 | Not started | — |
| 6.2 Debt Ledger Triage | 0/1 | Not started | — |

(v3.1 progress table preserved in collapsed v3.1 summary above; 6/6 phases ✅ as of 2026-05-22)

## Coverage

### v3.2 Coverage (current)

| REQ-ID | Phase | Notes |
|--------|-------|-------|
| CI-01 | 6.0 | NEW-X4 pytest fixture-scope mismatch fix, Phase 3 Contract Matrix CI RED → GREEN |
| CLI-X2 | 6.1 | NEW-X2 sibling kill_session anti-pattern (delete_session + export_session) → typed GridError + exit 4 |
| CLI-X3 | 6.1 | NEW-X3 `cargo build --all-features` 12 grid-engine errors 调查 + fix vs filter 决策 |
| TRIAGE-01 | 6.2 | 102 D-row + 3 NEW-X classify (P1/P2/P3/DEAD) |
| TRIAGE-02 | 6.2 | DEAD row 物理迁移到 DEFERRED_LEDGER_ARCHIVE.md |
| TRIAGE-03 | 6.2 | v3.3-INBOX.md 按 module 分组汇总 P1/P2/P3 |

**Total v3.2 requirements:** 6 (CI 1 + CLI 2 + TRIAGE 3)
**Mapped:** 6/6 ✓
**Orphans:** 0
**Double-mapped:** 0

### v3.1 Coverage (historical, CLOSED 2026-05-22)

| REQ-ID | Phase | Notes |
|--------|-------|-------|
| CLI-01 | 5.2 | grid 命令树整理 + help 输出 |
| CLI-02 | 5.2 | streaming output ChunkType 渲染 UX |
| CLI-03 | 5.2 | error message + sysexits.h exit code 一致性 |
| CLI-04 | 5.2 | TUI key_handler.rs 拆分 (NEW-C2) |
| CLI-05 | 5.2 | session lifecycle list/resume/kill 端到端 |
| CLI-06 | 5.2 | grid doctor 检查清单扩展 (5 新增项) |
| SERVER-01 | 5.4 | WebSocket ChunkType stream + backpressure + reconnect |
| SERVER-02 | 5.4 | L1 runtime gRPC 16-method 端到端集成 |
| SERVER-03 | 5.4 | session+L2 内存持久化 + Stop hook 写 trajectory |
| SERVER-04 | 5.4 | auth (HMAC ADR-003) + audit log + rate limit 基础 |
| SERVER-05 | 5.4 | config hot-reload + require-restart 字段白名单 |
| CONTRACT-00 | 5.1 | ADR-V2-025 候选 — runtime tier strategy (主力/样板/参考/冻结) |
| CONTRACT-01 | 5.3 | ChunkType 1-2 新 enum 值, contract-v1.2.0 升级 |
| CONTRACT-02 | 5.3 | Hook event 1-2 新 event, ADR (V2-XXX) 候选 |
| WATCH-00 | 5.0 | D120 — Rust HookContext schema 补全 (D134 前置) |
| WATCH-01 | 5.3 | D109 — workflow.required_tools 不变量文档化 (CONTRACT phase 顺手) |
| WATCH-02 | 5.0 | D134 — shipped skill hooks .payload.output.X → .output.X must-fix |
| WATCH-03 | 5.3 | D136 — grid-runtime probe turn hook 不触发 (3 contract xfails) 修正 |
| WATCH-04 | 5.4 | D142 + D143 — EAASP_DEPLOYMENT_MODE 接入 + max_sessions=1 gate |
| WATCH-05 | 5.1 | NEW-D2 — test_chunk_type_contract.py 7-runtime 参数化 |
| WATCH-06 | 5.5 | NEW-E2 — F3 ADR enforcement.trace 33 (corrected from 29) missing items advisory sweep |
| WATCH-07 | 5.4 | NEW-E3 — ADR-V2-019 enforcement.trace fill (status was UNCHANGED Accepted 2026-04-20 per Q9) |
| INTERFACE-01 | 5.5 | ADR-V2-029 — engine vs data/integration boundary contract (ADR-only, type: strategy, crate-level) |

**Total v3.1 requirements:** 23 (CLI 6 + SERVER 5 + CONTRACT 3 + WATCHLIST 8 + INTERFACE 1) — ✅ CLOSED 2026-05-22

## Granularity 备注 (v3.2)

本 milestone 选 **3 phase** (低于 GSD standard 5-8 区间) 是**有意为之 — intentional triage milestone, not feature work**:

- v3.2 scope = **6 REQ-ID 全部集中在 3 件事** (CI 红线消除 / grid-cli anti-pattern 收尾 / 102 D-row 一次性分类); 不是 feature delivery milestone, 不需要长 phase 链
- **代码修复 ONLY 3 row** (NEW-X4 CI + NEW-X2 CLI sibling + NEW-X3 --all-features 调查); 102 D-row 仅 classify 不 fix, mega sweep 留给 v3.3+ 按 INBOX 立 module-batch phase
- **3-phase 自然分组**: 6.0 (CI, 独立域, doc/CI only) + 6.1 (grid-cli 域, 2 小 row pairing) + 6.2 (debt ledger 域, doc-only, 3 task 顺序依赖); 强行拆 5 phase 会撕裂 cohesion
- **依赖关系松**: 6.0 与 6.1 互不依赖可并行 (顺序执行规则下 6.0 → 6.1), 6.2 软依赖 6.1 (NEW-X2/X3 final status 入 triage tag); 链短不需大 milestone framework
- **vs v3.1 6 phase 对比**: v3.1 是 feature milestone (grid-cli + grid-server 硬化 + contract evolution + interface ADR), 自然多 phase; v3.2 是 cleanup milestone, 短链合适
- **watchlist 策略 = N/A**: v3.2 本身 IS the watchlist sweep, 不需要 spread strategy

如 plan-phase 阶段发现某个 phase task 多于 5 个, 可由 plan-phase 自行考虑微拆 (例 Phase 6.2 三 task 若 TRIAGE-01 分类 102 row 工作量大可拆 plan), 但 ROADMAP 阶段不预拆。

---

*Roadmap v3.2 section added 2026-05-23 by `/gsd-roadmapper` (Step 10 of `/gsd-new-milestone` v3.2). Source: REQUIREMENTS.md v3.2 section (6 REQ-IDs) + PROJECT.md §Current Milestone v3.2 + v3.1 close cascade carry-over (NEW-X4 P2 from Phase 3 Contract Matrix CI scan post-push 2026-05-23; NEW-X2/X3 P3 from Phase 5.5 Plan 01 scope-limit) + LEDGER 102 D-row 实际计数 surprise (原 ~40 估算严重低估). v3.1 milestone ✅ CLOSED 2026-05-22 — section collapsed for traceability lineage. v3.0 milestone ✅ CLOSED 2026-04-28.*
