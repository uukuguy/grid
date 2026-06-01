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

*ROADMAP evolves at phase transitions and milestone boundaries.*

如 plan-phase 阶段发现某个 phase task 多于 5 个, 可由 plan-phase 自行考虑微拆 (例 Phase 6.2 三 task 若 TRIAGE-01 分类 102 row 工作量大可拆 plan), 但 ROADMAP 阶段不预拆。
