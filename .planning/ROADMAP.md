# Grid — Roadmap

> **Milestone:** v3.2 Tech-Debt Triage & CI Red Line Clearance (Phases 6.0/6.1/6.2)
> **Brownfield context:** Third GSD-managed milestone after Phase 4 (v3.0, ADR-V2-024 Accepted 2026-04-28) and Phase 5 (v3.1, shipped 2026-05-22). v3.0/v3.1 sections preserved below as historical traceability; this section covers ONLY milestone v3.2 (Phase 6.0 → 6.2, 3 phases).
> **Granularity:** light (3 phases — intentionally below GSD standard 5-8 range). v3.2 IS the watchlist-sweep / triage milestone, NOT feature work; mega debt sweep is scope-deferred to v3.3+ per TRIAGE-03 output. See §Granularity 备注 v3.2 for rationale.
> **Done condition for milestone:** 3 phases 全 ✅; 6 REQ-ID 全 ✅ traceability (CI-01 + CLI-X2 + CLI-X3 + TRIAGE-01..03); Phase 3 Contract Matrix CI GREEN (≥4/7 jobs PASS); `docs/design/EAASP/DEFERRED_LEDGER_ARCHIVE.md` 文件创建并迁入所有 DEAD-tagged row; `.planning/v3.3-INBOX.md` 文件创建按 module 分组列出 P1/P2/P3 row; PROJECT.md §Active "Phase 6 milestone (v3.2)" 行 flip 入 §Validated; STATE.md frontmatter `status: milestone-complete` + progress 3/3=100%; DEFERRED_LEDGER 主体只剩 P1/P2/P3 row + 3 NEW-X row (NEW-X2/X3/X4 各自 closed-or-classified)。

## Milestones

- ✅ **v3.0 Phase 4 — Product Scope Decision** — Phases 4.0/4.1/4.2 (shipped 2026-04-28, ADR-V2-024 Accepted)
- ✅ **v3.1 Phase 5 — Engine Hardening (grid-cli + grid-server)** — SHIPPED 2026-05-22 (Phases 5.0/5.1/5.2/5.3/5.4/5.5 all complete, 23/23 REQ-IDs, 6 ADRs Accepted V2-025/026/027/028/029/032)
- ✅ **v3.2 Phase 6 — Tech-Debt Triage & CI Red Line Clearance** — SHIPPED 2026-05-26 (Phases 6.0/6.1/6.2 all complete, 6/6 REQ-IDs ✅)

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

- [x] **Phase 6.0: CI Red Clearance** — NEW-X4 `test_chunk_type_contract.py` fixture-scope mismatch 修, Phase 3 Contract Matrix workflow 由 RED 转 GREEN (≥4/7 jobs PASS)
- [x] **Phase 6.1: grid-cli Anti-pattern Sweep** — NEW-X2 sibling kill_session anti-pattern (delete_session + export_session) + NEW-X3 `cargo build --all-features` 12 grid-engine errors 调查 + 决定 fix vs filter
- [x] **Phase 6.2: Debt Ledger Triage** — 93 open main-namespace D-row 一次性 triage 分类 (P1=0 / P2=15 / P3=70 / DEAD=8) + 8 DEAD 物理迁移到 DEFERRED_LEDGER_ARCHIVE.md + `.planning/v3.3-INBOX.md` 按 module 分组喂下轮 (scope methodology correction: 93 actual vs ROADMAP 102 est. vs scout 128 grep-error)

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
- [x] 06.0-01-PLAN.md — Pytest fixture-scope rename (3 sites: runtime_name → expected_runtime) + REQUIREMENTS/ROADMAP wording stretch + LEDGER NEW-X4 closure + Phase 3 Contract Matrix CI verify
**UI hint**: no

### Phase 6.1: grid-cli Anti-pattern Sweep

**Goal**: 收尾 grid-cli 残留 anti-pattern — NEW-X2 sibling kill_session anti-pattern 补全 (`crates/grid-cli/src/commands/session.rs:99-103` `delete_session` + L157 `export_session` 仍用 `anyhow!("Session not found")` 映射到 `ExitCode::General` 1, 应改为 `GridError::session_not_found()` → typed exit code `SessionNotFound = 4`; 与 Phase 5.5 Plan 01 Task B1 修的 `kill_session` 同模式) + NEW-X3 `cargo build -p grid-cli --all-features` 12 grid-engine errors 调查 + 决定 (是真 dead code / 应 feature-gate / 还是只需 doc fix)。两项同属 grid-cli 域, 都是小 scope (NEW-X2 ~10 LOC + 2 integration test; NEW-X3 调查可能 N/A), 自然 pairing 成一个 phase。
**Depends on**: Nothing on 6.0 (NEW-X2/X3 与 NEW-X4 CI fixture 无代码依赖, 可与 6.0 并行执行; 但 GSD 顺序执行规则下排在 6.0 后)
**Requirements**: CLI-X2, CLI-X3
**Success Criteria** (what must be TRUE):
  1. `delete_session` (`crates/grid-cli/src/commands/session.rs:99-103`) + `export_session` (L157) 改用 `GridError::session_not_found()` typed error; `main.rs` 既有的 `downcast_ref::<GridError>` arm (Phase 5.5 Plan 01 Task B1 落地) 自动 catch, 用户敲 `grid session delete <nonexistent-id>` + `grid session export <nonexistent-id>` 都 exit 4 而非 exit 1
  2. `crates/grid-cli/tests/` 下新增 2 个 integration test (`test_delete_nonexistent_session_exits_4` + `test_export_nonexistent_session_exits_4`) 均 PASS; 既有 147 + 6 grid-cli test 全部 no regression (`cargo test -p grid-cli` 全 PASS)
  3. `cargo build -p grid-cli --all-features` 状态 = **(a) 编译 clean** (12 个 grid-engine errors 修复 或 经调查为真 dead code 删除) **OR (b) 矩阵窄化** (`grid-cli` Cargo.toml `--all-features` feature set 显式排除引发错误的 feature, 留一个能 build 的子集), 选择写入 LEDGER NEW-X3 row 的 close-out 注释, 包含 root cause 一句话 + 决策 rationale (per CONTEXT.md D-01: locked to Option (a) Fix-all 全修)
  4. NEW-X2 + NEW-X3 在 DEFERRED_LEDGER 标 ✅ CLOSED 并附 commit hash; D-01 锁定 Option (a) 故 Cargo.toml/Makefile 无 feature 排除注释 (D-04 locked: 无 helper 抽取, 复制 kill_session pattern verbatim)
**Plans:** 1 plan
Plans:
- [x] 06.1-01-PLAN.md — CLI-X2 typed GridError port (delete_session + export_session + 2 integration tests) + CLI-X3 Option (a) fix-all (Bucket A: WIT rename atomic + Bucket B: HashMap import + _config rename + Bucket C: let mut bridge) + phase verify + LEDGER NEW-X2/X3 close-out (D-09 short + D-10 full archaeology)
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
**Plans:** 1 plan
Plans:
- [x] 06.2-01-PLAN.md — TRIAGE-01 inline classify 128 open D-rows (tag schema [P\d-...] + rationale per D-01 + DEAD per D-02 4-criterion) → TRIAGE-02 atomic-commit migrate DEAD rows to DEFERRED_LEDGER_ARCHIVE.md (bidirectional commit hash) → TRIAGE-03 generate .planning/v3.3-INBOX.md (stats header + 12-module taxonomy per D-03 + P1→P2→P3 grouping) → milestone close cascade (LEDGER §状态变更日志 + PROJECT.md §Active→§Validated flip + STATE.md status=milestone-complete + ROADMAP §Progress row ✅ COMPLETE + SUMMARY 128-vs-102 scope-correction note)
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
| 6.1 grid-cli Anti-pattern Sweep | **1/1 ✅** | COMPLETE 2026-05-25 (1 plan, 6 tasks: X2 delete + X2 export + X3 Bucket B+C + X3 Bucket A + verify + LEDGER close) | NEW-X2 @ `0595e31`+`a0a6c28`; NEW-X3 @ `adf2c08`+`97f59e5` |
| 6.2 Debt Ledger Triage | **1/1 ✅** | COMPLETE 2026-05-26 (1 plan, 5 commits: TRIAGE-01 @ `9842dda` + TRIAGE-02 @ `e2a6349`+`835de4e`+`0f600b6` + TRIAGE-03 @ `24ee8ed`) | 4/4 SC PASS; TRIAGE-01 93 main-NS open D-rows tagged (P1=0 / P2=15 / P3=70 / DEAD=8) — scope methodology correction (ROADMAP est. 102; scout claim 128 was grep error; actual 93 = 81 4-col + 12 5-col); TRIAGE-02 8 DEAD rows migrated to `docs/design/EAASP/DEFERRED_LEDGER_ARCHIVE.md` via 2-commit sed-replace bidirectional hash pattern; TRIAGE-03 `.planning/v3.3-INBOX.md` 12-module grouping (9 populated, 3 elided) ready for v3.3 scoping; milestone v3.2 CLOSED |

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

### v3.1 Coverage (closed, preserved for traceability)

| REQ-ID | Phase | Notes |
|--------|-------|-------|
| (preserved verbatim from v3.1 ROADMAP — see git log @ 833e0eb) |

## Granularity 备注 v3.2

3 phases / milestone 是 **intentional light triage**, 不是 GSD standard 5-8 phase milestone scope。理由:

- v3.2 IS the watchlist-sweep / debt-triage milestone — 自 Phase 4 / 5 累积的 LEDGER 红线 + grid-cli 残留 anti-pattern 一次性收尾, 不接 feature work。
- 代码修复 scope 极有限 (CI fixture rename 3 sites + grid-cli delete/export typed-error 2 functions + grid-cli --all-features 12 errors 调查 — 三项加起来 <50 LOC 修)。
- 102 D-row triage 是 doc-only **classify only**, 不修代码 — 修复留给 v3.3+ 按 INBOX P1/P2 立 mega-sweep phase。
- 因此 3 phase 已经足够 cover scope, 不强行拆 ≥5 phase。
- **D-batch sweep** — actual count 102 open D-row, classify in v3.2 TRIAGE-01..03, then schedule P1/P2 sweep phases in v3.3+ per module grouping

下个 milestone (v3.3+ TBD) 走 mega-sweep + INTERFACE-02 + INTERFACE-03 + CONTRACT-03/04, 会回到 standard 5-8 phase 粒度。

| Granularity check | Phase ratio | Verdict |
|--|--|--|
| **Granularity = Light** | 3 phases / milestone | ✓ Intentional, justified above |
| **Granularity = Standard** | 5-8 phases / milestone, 3-5 plans / phase。匹配 Phase 2 / 3 历史粒度 | ✓ Good |

## Milestone Coverage Index

| REQ-ID | Phase | Status (planning-time stub — flip ✅ at phase close) |
|--------|-------|---|
| CI-01 | 6.0 | ✅ (CI-01 NEW-X4 fixture-scope fix, Phase 3 Contract Matrix CI RED → GREEN) |
| CLI-X2 | 6.1 | ✅ (NEW-X2 sibling kill_session → typed GridError exit 4) |
| CLI-X3 | 6.1 | ✅ (NEW-X3 `cargo build --all-features` 12 grid-engine errors fix-all Option (a)) |
| TRIAGE-01 | 6.2 | ✅ (93 main-NS open D-row classify P1=0 / P2=15 / P3=70 / DEAD=8 @ `9842dda`) |
| TRIAGE-02 | 6.2 | ✅ (8 DEAD rows 物理迁移到 DEFERRED_LEDGER_ARCHIVE.md via 2-commit sed-replace bidirectional hash @ `e2a6349`+`835de4e`+`0f600b6`) |
| TRIAGE-03 | 6.2 | ✅ (`.planning/v3.3-INBOX.md` 12-module grouping 9 populated + 3 elided @ `24ee8ed`) |

## v3.2 Done condition flip

**FLIPPED ✅ 2026-05-26 Phase 6.2 Plan 01 Task 4** — 6/6 REQ-ID 全 ✅ + STATE.md frontmatter `status: milestone-complete` + PROJECT.md §Active "Phase 6 milestone (v3.2)" 行 flip 入 §Validated 完成。Milestone section header 已由 🟡 改 ✅, Milestones list 同步改 ✅, Phases section 三 phase checkbox 全 [x]。

---

## Milestone v3.3 — Engine + Platform Debt Sweep (Focused) [🟡 STARTED 2026-06-01]

**Status**: 🟡 STARTED 2026-06-01
**Scope**: 4 phases / 27 REQ-IDs / ~30 D-rows from `.planning/v3.3-INBOX.md` (focused subset of 85 P2/P3 INBOX rows — L4/hooks/eval/grid-server/cross-cutting defer to v3.4+)
**Granularity**: per-module batching (≤10 rows/phase per INBOX guidance); P2 before P3 within each phase
**Skip research** (debt rows concrete with LEDGER references, no domain ecosystem unknowns)
**Done condition for milestone**: 4 phases 全 ✅; 27/27 REQ-ID traceability ✅; ~11 P2 row 全 ✅ CLOSED in DEFERRED_LEDGER.md; ~19 P3 row 视实施时间 selective ✅ (允许部分 carry-forward to v3.4+); PROJECT.md §Active "Phase 7 milestone (v3.3)" 行 flip 入 §Validated; STATE.md frontmatter `status: milestone-complete` + progress 4/4=100%。

### Milestones list update

- ✅ **v3.0 Phase 4 — Product Scope Decision** — shipped 2026-04-28
- ✅ **v3.1 Phase 5 — Engine Hardening** — shipped 2026-05-22
- ✅ **v3.2 Phase 6 — Tech-Debt Triage & CI Red Line Clearance** — shipped 2026-05-26
- 🟡 **v3.3 Phase 7 — Engine + Platform Debt Sweep (Focused)** — STARTED 2026-06-01

### Phases list

- [ ] Phase 7.0 grid-engine harness wiring (6 REQ-IDs: ENGINE-01..06)
- [ ] Phase 7.1 contract observability + bridge (5 REQ-IDs: CONTRACT-01..05)
- [ ] Phase 7.2 L2 connection-pool + Pipeline (8 REQ-IDs: L2-01..08)
- [ ] Phase 7.3 L3 RBAC + hardening (8 REQ-IDs: L3-01..08)

### Phase Details

#### Phase 7.0: grid-engine harness wiring [🟡 STARTED]

**Goal**: 把 `AgentLoopConfig.compaction` 字段贯通 YAML 配置层 (D102 P2), 并顺手清掉 Phase 2 S3.T1 遗留的 harness/pipeline P3 杂项 (D3 / D57 / D58 / D103 / D104), 让 grid-engine harness 内部状态与 ADR-V2-026 ExecutionMode + ADR-V2-028 strict-by-default 两条 lineage 对齐。

**Depends on**: Nothing (milestone 第一个 phase)
**Requirements**: ENGINE-01 (P2, D102) + ENGINE-02..06 (P3, D3/D57/D58/D103/D104)

**Success criteria** (what must be TRUE):
1. `config.yaml` 中 `compaction:` block 经 `crates/grid-server/src/config.rs` YAML→struct 流贯通到 `AgentLoopConfig.compaction`; round-trip test (`cargo test -p grid-server -p grid-engine` targeted) 覆盖 "写 → load → assert struct 值匹配"; 未识别字段按 ADR-V2-028 strict-by-default 报错而非 silent drop
2. `cargo test -p grid-engine` 在 `harness_payload_integration.rs` + `test_initialize_injects_memory_refs_preamble` 套件下 PASS, 且 `build_memory_preamble` 仅在 grid-engine 一处实现 (DRY violation 消除, D57); `test_initialize_injects_memory_refs_preamble` assert Send 全路径 (D58)
3. ENGINE-01..06 全 6 REQ-ID 在 `docs/design/EAASP/DEFERRED_LEDGER.md` 标 ✅ CLOSED 并附 commit hash (允许 ENGINE-02..06 部分以 "decision: defer-with-justification + LEDGER row 保留 P3" 形式收口, 但 ENGINE-01 D102 必须真修)
4. `find_tail_boundary()` 在 long-conversation profile (≥200 turn) 下行为有 measured baseline (D103); 决定要么修 O(N²) 要么落 doc-only warning + rationale 写入 LEDGER row close-out
5. 反应式 guard 位置决策记录 (D104): 维持 harness 或迁 pipeline, 二选一; 若决定迁 pipeline 且涉及 ExecutionMode lineage 跨界则起草 ADR 候选 (check `/adr:trace crates/grid-engine/src/agent_loop/` before plan-phase)

**Notes**: D104 (反应式 guard in pipeline) 是潜在 ADR 候选 — 若 plan-phase 阶段判定迁 pipeline 涉及 ADR-V2-026 ExecutionMode 边界, 走 ADR 流水。D106 (MAX_TURNS_FOR_BUDGET=50 硬编码) 与 D105 (HookPoint::ContextDegraded 字符串别名) 留 INBOX 不入此 phase (P3 stretch, defer to v3.4+ 保持 phase 实操 ≤6 rows 内)。

#### Phase 7.1: contract observability + bridge [🟡 STARTED]

**Goal**: 把 Phase 2.5 S0.T4/T5 遗留的 multi-turn observability + MCP bridge live + PRE_COMPACT 阈值 (D137 P2) + skill-workflow deny-path mock LLM (D138 P2) 落地, 顺带把 contract-v1.2 升级后落下的 telemetry envelope migration + certifier schema 锁定 P3 项 (D5/D6/D55) 收口。让 7-runtime 契约层在 observability 与可重复 deny-path 测试上达到生产就绪。

**Depends on**: Nothing on 7.0 (grid-engine harness 与 contract 层无强代码依赖, 可与 7.0 并行)
**Requirements**: CONTRACT-01 (P2, D137) + CONTRACT-02 (P2, D138) + CONTRACT-03..05 (P3, D5/D6/D55)

**Success criteria** (what must be TRUE):
1. `grid-runtime` 在 multi-turn 场景下吐出 turn-by-turn telemetry chunk (与 nanobot/goose 一致), MCP bridge 在 grid-runtime live, PRE_COMPACT 阈值由 ChunkType 触发而非 hard-coded (D137); contract test `make v2-phase3-e2e` 跑过后, grid-runtime job 新增的 multi-turn observability assertion 全 PASS
2. skill-workflow enforcement 测试支持 mock LLM 复现 deny-path 场景 (D138); `cargo test` 或 `pytest tests/contract/` 下新增可重复 deny-path test 全 PASS, 不依赖 live LLM
3. `tests/grpc_integration*.rs` (或等价测试) 全部用 v2 telemetry envelope; 旧 envelope shape 引用 0 (`rg "telemetry_v1" -t rust crates/ tests/` 0 hit, D5)
4. certifier 套件覆盖 SessionPayload P1-P5 字段断言 (D6); `make verify-dual-runtime` 跑过后 certifier 报告含 SessionPayload schema 断言行
5. proto3 submessage presence 跨 7 runtime 统一用 `HasField` 而非 truthy fallback (D55); cross-runtime parity test 验证 absence 路径 (Python + Rust + TS 三侧一致); CONTRACT-01..05 全 5 REQ-ID 在 LEDGER 标 ✅ CLOSED 附 commit hash

**Notes**: D137 涉及 grid-runtime ↔ MCP bridge ↔ ChunkType 三层交互, 是 phase 内最重 task — plan-phase 阶段考虑微拆 plan。D138 可以 leverage Phase 5.3 OpenAI Quirks 的 mock provider 同套基础设施。D74 (EmitEvent gRPC 反向通道) 与 D139 (双 Terminate 语义) 留 INBOX 不入此 phase (defer to v3.4+ 控规模)。

#### Phase 7.2: L2 connection-pool + Pipeline [🟡 STARTED]

**Goal**: 把 L2 memory-engine 性能与正确性两条主线一次性扫掉 — connection pool (D12+D94 P2 双胞胎) + HNSW tombstone rebuild (D91 P2) + embed_batch 并发 (D93 P2) + HybridIndex.search 重建消除 (D98 P2) 五项 P2 形成本 milestone 的 keystone phase, 顺手清理 L2 P3 三项 (D11/D13/D30)。让 L2 在高并发 + 长 lifetime + 大索引场景下达到生产就绪。

**Depends on**: Nothing 强阻塞 (L2 域代码与 7.0/7.1 解耦), 但建议在 7.0/7.1 后启动以便 P2 重活集中精力
**Requirements**: L2-01..05 (P2, D12/D94/D91/D93/D98) + L2-06..08 (P3, D11/D13/D30)

**Success criteria** (what must be TRUE):
1. `MemoryStore` 改为单例持有 connection pool (sqlite-pool 或等价), 不再 connection-per-call (D12+D94 双胞胎收尾); `pytest tools/eaasp-l2-memory-engine/tests/` 全 PASS, 新增 high-concurrency throughput test (>10 并发 read/write) 跑过后 SQLite `database is locked` 0 命中
2. HNSW 软删 tombstone 达到阈值 (e.g., 30% tombstone) 触发自动 rebuild (D91); `pytest -k "tombstone"` 套件 PASS, rebuild 行为有 measured before/after recall 指标; HybridIndex.search 不再 per-call rebuild HNSWVectorIndex (D98) — pytest benchmark 显示 search latency p99 下降 ≥ 50% (vs Phase 5.5 baseline)
3. `embed_batch` 并发 fan-out (D93) 实施 + respect provider rate limit; `pytest -k "embed_batch"` 套件 PASS, batch=10 场景下耗时不超过 sequential 的 30% (i.e., 真实并发证据); 配 rate-limit-respect test
4. skill-registry `scope` 过滤改为 WHERE 子句 (D11) — `LIMIT` 之前 filter; pytest 覆盖 "scope=X + limit=5 应返回 ≤5 且全 scope=X" assertion PASS; L2 `archive()` 真正 hide rows from FTS (D13) — archived row 在 search 调用下不出现, pytest 覆盖 PASS
5. `busy_timeout` 统一为 const (D30) — L2/L3 不再散落 magic number; L2-01..08 全 8 REQ-ID 在 LEDGER 标 ✅ CLOSED 附 commit hash

**Notes**: 此 phase 是 v3.3 keystone — 5 P2 集中 + 性能 / 并发 / 正确性三条线交织。plan-phase 阶段强烈建议拆为 ≥2 plan: connection-pool + MemoryStore 单例 (D12+D94) 为一 plan, HNSW + embed_batch + HybridIndex (D91+D93+D98) 为另一 plan, P3 三项 (D11+D13+D30) 为第三 plan 收尾。L2 P3 大量 row (D14/D15/D59/D65/D75-D80/D92/D95-D101) 留 INBOX 不入此 phase。

#### Phase 7.3: L3 RBAC + hardening [🟡 STARTED]

**Goal**: 把 L3 governance 三个 RBAC 相关 P2 (D8 access_scope 真实强制 + D9 skill_usage 真实遥测 + D46 Skill namespace 校验) 落地, 顺带把 L3 FastAPI 层 hardening P3 (D17/D18/D22/D23/D26) 收口, 让 L3 在企业 RBAC 场景下可用且 FastAPI 异常行为符合产品规范。

**Depends on**: Nothing 强阻塞, 但 D9 skill_usage 真实遥测需 L2 audit log query 接口 (轻依赖 7.2 connection pool 就绪后查询性能更好, 但不阻塞 7.3 启动)
**Requirements**: L3-01..03 (P2, D8/D9/D46) + L3-04..08 (P3, D22/D23/D17/D18/D26)

**Success criteria** (what must be TRUE):
1. `access_scope` 真实 RBAC 中间件落地 (D8): 用户 token 携带 scope, 调用 skill / memory 时由 middleware 校验; `pytest tools/eaasp-l3-governance/tests/test_rbac.py` (新增) 全 PASS, 覆盖 allow + deny + scope-mismatch 三类路径
2. `skill_usage` endpoint 返回真实遥测 (D9): 从 L2 audit log query 而非 mock; pytest 覆盖 "skill A 调用 N 次后 endpoint 返回 N" 端到端 assertion PASS
3. Skill manifest `access_scope` namespace 部署时校验 (D46): skill registry 注册时 reject 与已部署 skill namespace 冲突的声明; pytest 覆盖 conflict path PASS, 错误信息含冲突 namespace + 已占用方
4. L3 FastAPI 全局 exception handler 落地 (D22) — 5xx 异常不再 leak stack trace, 返回标准 `{"error": {...}}` shape; loguru 初始化 (D23) — 启动时显式配置; `pytest -k "exception_handler or logging"` 套件 PASS
5. `validate_session()` 的 `hook["hook_id"]` 改 `.get()` + 缺失 raise typed error (D17); `session_id` path param 加 UUID/format 校验 (D18); flaky `time.sleep(1.1)` 改 monotonic clock 或 mock time (D26); L3-01..08 全 8 REQ-ID 在 LEDGER 标 ✅ CLOSED 附 commit hash

**Notes**: D8/D46 是 RBAC 双胞胎 — 一个是运行时 enforcement, 一个是部署期 namespace 隔离, plan-phase 可并排做但不同 plan。D9 skill_usage 真实遥测需要 L2 audit log query 接口已 ready — 与 7.2 connection pool 收尾后可获得更好查询性能。L3 P3 大量 row (D10/D16/D19/D20/D21/D25) 留 INBOX 不入此 phase。

### Coverage Index (v3.3)

| REQ-ID | Phase | Status |
|--------|-------|---|
| ENGINE-01 | 7.0 | 🟡 STARTED 2026-06-01 |
| ENGINE-02 | 7.0 | 🟡 STARTED 2026-06-01 |
| ENGINE-03 | 7.0 | 🟡 STARTED 2026-06-01 |
| ENGINE-04 | 7.0 | 🟡 STARTED 2026-06-01 |
| ENGINE-05 | 7.0 | 🟡 STARTED 2026-06-01 |
| ENGINE-06 | 7.0 | 🟡 STARTED 2026-06-01 |
| CONTRACT-01 | 7.1 | 🟡 STARTED 2026-06-01 |
| CONTRACT-02 | 7.1 | 🟡 STARTED 2026-06-01 |
| CONTRACT-03 | 7.1 | 🟡 STARTED 2026-06-01 |
| CONTRACT-04 | 7.1 | 🟡 STARTED 2026-06-01 |
| CONTRACT-05 | 7.1 | 🟡 STARTED 2026-06-01 |
| L2-01 | 7.2 | 🟡 STARTED 2026-06-01 |
| L2-02 | 7.2 | 🟡 STARTED 2026-06-01 |
| L2-03 | 7.2 | 🟡 STARTED 2026-06-01 |
| L2-04 | 7.2 | 🟡 STARTED 2026-06-01 |
| L2-05 | 7.2 | 🟡 STARTED 2026-06-01 |
| L2-06 | 7.2 | 🟡 STARTED 2026-06-01 |
| L2-07 | 7.2 | 🟡 STARTED 2026-06-01 |
| L2-08 | 7.2 | 🟡 STARTED 2026-06-01 |
| L3-01 | 7.3 | 🟡 STARTED 2026-06-01 |
| L3-02 | 7.3 | 🟡 STARTED 2026-06-01 |
| L3-03 | 7.3 | 🟡 STARTED 2026-06-01 |
| L3-04 | 7.3 | 🟡 STARTED 2026-06-01 |
| L3-05 | 7.3 | 🟡 STARTED 2026-06-01 |
| L3-06 | 7.3 | 🟡 STARTED 2026-06-01 |
| L3-07 | 7.3 | 🟡 STARTED 2026-06-01 |
| L3-08 | 7.3 | 🟡 STARTED 2026-06-01 |

**Total v3.3 coverage**: 27/27 REQ-IDs mapped (ENGINE 6 + CONTRACT 5 + L2 8 + L3 8); 0 orphans; 0 double-mapped.

### Progress (v3.3)

**Execution Order:**
Phases execute in numeric order: 7.0 → 7.1 → 7.2 → 7.3 (parallelization allowed per GSD config; 7.0/7.1 strongly decoupled and parallelizable per phase Depends-on analysis; 7.2 keystone benefits from sequential focus; 7.3 lightly depends on 7.2 L2 audit query readiness)

| Phase | Plans Complete | Status | Notes |
|-------|----------------|--------|-------|
| 7.0 grid-engine harness wiring | 0/0 | 🟡 STARTED 2026-06-01 | 6 REQ-IDs (1 P2 + 5 P3); next: `/gsd-discuss-phase 7.0` |
| 7.1 contract observability + bridge | 0/0 | 🟡 STARTED 2026-06-01 | 5 REQ-IDs (2 P2 + 3 P3) |
| 7.2 L2 connection-pool + Pipeline | 0/0 | 🟡 STARTED 2026-06-01 | 8 REQ-IDs (5 P2 + 3 P3) — keystone |
| 7.3 L3 RBAC + hardening | 0/0 | 🟡 STARTED 2026-06-01 | 8 REQ-IDs (3 P2 + 5 P3) |

### Granularity rationale (v3.3)

v3.3 = 4 phases per per-module batching. Module choice (grid-engine + contract + L2 + L3) + ≤10-rows-per-phase budget + P2-before-P3 within each phase follow `.planning/v3.3-INBOX.md` §"Notes for v3.3+ scoping" guidance literally. Compared to v3.1 (6 phases, watchlist-spread across CLI/SERVER/CONTRACT/WATCHLIST/INTERFACE) and v3.2 (3 phases, intentional light triage with code work scope-limited to 3 rows), v3.3 sits between — focused debt sweep on 4 high-yield modules, not full INBOX drain. L4 / hooks / eval / grid-server (1 row) / cross-cutting modules in INBOX (~50 rows) defer to v3.4+ untouched.

| Granularity check | Phase ratio | Verdict |
|--|--|--|
| **Granularity = Light-Standard** | 4 phases / milestone | ✓ Intentional, between v3.2 light (3) and v3.1 standard (6) |
| **Mapping density** | avg ≈6.75 REQ/phase (range 5-8) | ✓ Within "≤10 per phase" cohesion limit per INBOX guidance |
| **P2 distribution** | 11 P2 across 4 phases (1/2/5/3) | ✓ 7.2 keystone identified; 7.0 minimum P2 (single D102) |

下个 milestone (v3.4+ TBD) 由 v3.3 close cascade 决定, 候选方向: L4 / hooks / eval / grid-server / cross-cutting 模块清扫 + INTERFACE-02/03 (V2-030/031 reserved) + CONTRACT-03/04 (新 RPC / SubAgent first-class) + grid-platform / grid-desktop / web* dormant 模块状态评估。

---

*ROADMAP evolves at phase transitions and milestone boundaries.*

如 plan-phase 阶段发现某个 phase task 多于 5 个, 可由 plan-phase 自行考虑微拆 (例 Phase 7.2 keystone 5 P2 + 3 P3 = 8 row 高度推荐拆 ≥2 plan), 但 ROADMAP 阶段不预拆。
