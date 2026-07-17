---
doc_type: project-overview
status: canonical
last_updated: 2026-07-17
purpose: 项目级产品情况同步文档 — 当未来 session 询问"这个仓库到底是什么 / 项目当前状态"时的 single source of truth
audience: 未来 Claude Code session、本团队 contributor、潜在 reviewer
language: 中文(per global CLAUDE.md `docs/` 目录规则)
---

# Grid × EAASP 项目产品情况同步文档

> **TL;DR**: 本仓库 `grid-sandbox`(已重命名 `grid`,2026-06-17)= **EAASP 全栈 + Grid 全栈同仓孵化**。
> 不是 "Grid 接 EAASP",而是 "Grid 引擎 + EAASP L2/L3/L4 平台层 + 7 个 L1 runtime + 完整产品套件" 都在这一个仓里。
>
> 历史文档(ADR-V2-023 / CLAUDE.md 旧版 / 部分 README 段落)用过 "shadow / separate upstream" 措辞描述 `tools/eaasp-*/` — 这是 **过时的**。**准确描述**: `tools/eaasp-*/` 是 EAASP v2.0 的**当前实现**,由本团队同仓孵化,**不存在"上游 EAASP"项目**。
>
> 修正点 = docs sync across CLAUDE.md / README.* / ADR-V2-024 Note / MEMORY.md,本次 PR 一并完成。

---

## 一、这是什么 — 两轴模型 (engine vs data/integration)

权威来源:**ADR-V2-024** (Accepted 2026-04-28, supersedes ADR-V2-023)+ **ADR-V2-029** (Accepted 2026-05-22) + **EAASP_v2_0_EVOLUTION_PATH.md** §二。

### 1.1 一句话定位

> Grid 是 EAASP(Enterprise-Agent-as-a-Service Platform)的**旗舰 L1 runtime + 完整产品套件**。同一仓库既交付 Grid 的 Rust agent 引擎,也交付 EAASP 的 L2 内存 / L3 治理 / L4 编排 / skill registry / MCP orchestrator / certifier / CLI。两条产品线共享一个引擎核心,通过 gRPC L1 contract(16 方法)对内对外都是 substitutable。

### 1.2 双轴模型 (engine vs data/integration) — ADR-V2-024 §1 双轴 substance

| 轴向 | 含义 | 本仓归属 |
|------|------|---------|
| **engine (60% + 30% 工时主战场)** | 可复用的核心组件,user 自做 | 全部 `crates/grid-*` + 全部 `tools/eaasp-*` + `proto/` + `lang/*` |
| **data/integration (他人接手)** | 客户/厂商特定的接入适配 | **本仓内 0 实装**,只在 ADR 列出 categories(SSO / WORM / 信创 LLM / SCADA 行业规则等) |

工时 baseline(per ADR-V2-024 §1 + Open Item #2):
- **Grid 全栈 ≈60%** (`crates/grid-*` 共享核心 + `crates/grid-server/cli/platform/desktop` + `web*`)
- **EAASP 引擎层 ≈30%** (`tools/eaasp-l2-memory-engine` + `eaasp-l3-governance` + `eaasp-l4-orchestration` + `eaasp-skill-registry` + `eaasp-mcp-orchestrator` + `eaasp-cli-v2` + `eaasp-certifier`)
- **元工作(plan/audit/governance) ≈10%**

### 1.3 "Leg A 接 EAASP / Leg B 独立" 旧框架已废止

ADR-V2-024 §1 + ADR-V2-029 §1 都明确 supersede 了 ADR-V2-023 的二元框架。**优先发力组合**(ADR-V2-024 Open Item #3)用 axes 而非 legs 描述:

- engine 侧:grid-cli + grid-server 优先(已完成 v3.1 hardening)
- 其余 component(platform / desktop / web*) 待激活触发 — 但**激活条件在双轴下重新框定**,不再依赖旧的 Leg B P5 触发条件原文

---

## 二、产品矩阵 — 本仓库交付的全部组件

### 2.1 Grid 全栈(Rust crates 12 个 + 2 个 frontend)

| Crate / App | LOC | 状态 | 角色 |
|------------|----:|------|------|
| `crates/grid-engine/` | 92,485 | mature | **共享核心** — agent loop / memory 4-tier / MCP / tools / skills / sandbox / security / audit |
| `crates/grid-runtime/` | 4,807 + 7 tests | mature | L1 gRPC adapter,EAASP L2/L3/L4 主消费者入口 |
| `crates/grid-types/` | — | mature | 零依赖共享类型 |
| `crates/grid-sandbox/` | — | mature | sandbox runtime(native subprocess / wasm / docker) |
| `crates/grid-hook-bridge/` | — | mature | Rust↔L2/L3 hook event bridge |
| `crates/grid-cli/` | 26,338 + 415 单测 + 3 集成 | **9.0 ✅ SHIPPED** | 16 命令 CLI + full TUI + studio dashboard |
| `crates/grid-server/` | 8,956 + 72 handler + 19 单测 + 25 集成 | **9.0 ✅ SHIPPED** | 单用户 workbench HTTP/WS,RBAC + ApiError + hot-reload |
| `crates/grid-eval/` | 16,942 + 208 单测 + 1 集成 | **9.0 ✅ SHIPPED** | 10 scorers + 12 suites + 4 benchmarks(GAIA / SWE-bench / τ-bench)+ CI concurrency group |
| `crates/grid-platform/` | 3,746 + 37 tests | **9.0 ✅ SHIPPED** (dormant 解除) | 多租户 SaaS server,JWT + RBAC + quota + ErrorCode enum + 20 handler |
| `crates/grid-desktop/` | 383 + 8 IPC | **6.5 仍 3/10** | Tauri 2 桌面应用,**仅 IPC 壳,agent/session IPC 未实装** |
| `web/` | 5,950 (8 tabs) | **9.0 ✅** | 单用户 React SPA |
| `web-platform/` | 1,707 (5 pages) | **7.5** | 多租户 React UI |

### 2.2 EAASP 全栈(`tools/eaasp-*` 8 个 + `proto/eaasp/` + `lang/*` 比较 runtime)

> **关键定性**:`tools/eaasp-*/` 是 **EAASP v2.0 平台尚未完整实现前、按平台契约做的"模拟器"级参考实现**。
>
> 准确意思(综合 ADR-V2-023 + ADR-V2-024 + EVOLUTION_PATH + EAASP-Design-Specification-v2.0.docx):
> - ✅ **是 EAASP 全栈**(L1/L2/L3/L4 各层基础组件都在本仓),由本团队自做,**不存在"上游 EAASP"独立项目**
> - ⚠️ **但 EAASP v2.0 设计规范(5 层 + 3 管道 + 4 元范式 + 7 阶段演化)未完整实现**,目前约实现 40-50%(圈 2 + 圈 3 + 部分 Phase 0–2;圈 4–5 + Phase 3–6 待后续 milestone)
> - ❌ **不是 ADR-V2-023 字面说的 "high-fidelity shadow"** — 因为没有上游 EAASP 项目可 shadow
> - ✅ **也不是 "production 完整 EAASP"** — 因为 5 层 + 3 管道 + 4 元范式有大量未交付 capability(L4 A2A / L5 Cowork / OPA 后端 / Sandbox Tiers 验证 / Event Room / Web UI 等)
>
> 推荐的对外说法:**"模拟器级参考实现 per EAASP v2.0 设计规范"** — 既承认按契约做的、也明确未完整、对未来扩展是 open。
>
> **EAASP 平台的设计文档** 同仓在 `docs/design/EAASP/`,**`EAASP-Design-Specification-v2.0.docx` 是规范权威**(per EVOLUTION_PATH §"权威规范")。具体看:
> - 长期演化规划:`docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md` (5 层 + 3 管道 + 4 元范式 + 7 阶段 + 决策登记)
> - MVP 圈 2 范围:`docs/design/EAASP/EAASP_v2_0_MVP_SCOPE.md`
> - L1 Runtime 生态:7 个 `L1_RUNTIME_*.md` 系列 + `L1_RUNTIME_TIER_SPEC_*` 中英对照
> - 各 Phase 设计:`PHASE1_EVENT_ENGINE_DESIGN.md` / `PHASE_3_DESIGN.md` / 等
> - 战略 / 范围 ADR:`docs/design/EAASP/adrs/ADR-V2-024-phase4-product-scope-decision.md` + `ADR-V2-029-engine-data-integration-boundary.md`
>
> ADR-V2-024 §1 明确把 EAASP 引擎层列为 user 主战场之一,工时占比 30% — 这是 **继续推进 EAASP 各层 + 补完未实现 capability** 的总称,不是 "有个 EAASP 我们接它"的含义。

EAASP v2.0 实现进度对照 EVOLUTION_PATH § 3.1(8 Phase 演化路线):

| Phase | 状态 | 已交付 capability |
|-------|------|-------------------|
| 0 Infrastructure Foundation | ✅ 2026-04-12 | 5 层服务骨架 + 16 方法契约 |
| 0.5 MVP 全层贯通 | ✅ 2026-04-13 | L4→L1 真 gRPC + LLM agent 执行 |
| 0.75 L2 MCP 编排 | ✅ 2026-04-13 | 三 runtime 统一 MCP transport |
| 1 Event-driven foundation | ✅ 2026-04-14 | L4 Event Engine + Session Event Stream |
| 2 Memory and evidence | ✅ 2026-04-16 | L2 memory + skill extraction + PreCompact |
| 2.5 L1 Runtime 生态首批 | ✅ 2026-04-17 | 7 个 L1 runtime + 契约测试集 |
| 3 Approval and verification | ⏸ 未启动 | 审批链 + Verifier + OPA + Sandbox Tiers |
| 4 Multi-agent collaboration | ⏸ 未启动 | A2A Router + ReviewSet + T0 Harness |
| 5 Complete collaboration space | ⏸ 未启动 | L5 Web UI(4 卡) + IM bot + 回溯闭环 |
| 6 Ecosystem expansion | ⏸ 未启动 | Marketplace + 多租户 + SDK |

| Tool | LOC | 实现进度 | 角色 |
|------|----:|---------|------|
| `tools/eaasp-l2-memory-engine/` | 2,771 + 22 tests | Phase 2 ✅ 全量交付 | FTS5 + HNSW + time-decay hybrid 检索,7 MCP tools |
| `tools/eaasp-l3-governance/` | 1,259 + 7 tests | Phase 1+ ✅ 基础;**Phase 3 ⏸ OPA 后端 + 完整审批链未做** | Policy DSL + risk classification + shadow/enforce mode |
| `tools/eaasp-l4-orchestration/` | 4,584 + 20 tests | Phase 1 ✅ session 编排 + SSE;**Phase 4 ⏸ A2A Router + Event Room 未做** | Session 编排 + SSE fan-out + governance gates |
| `tools/eaasp-skill-registry/` | 1,637 Rust + 4 tests | Phase 0.75 ✅ 基础 CRUD | Skill manifest + MCP tool bridge(Cargo workspace member) |
| `tools/eaasp-mcp-orchestrator/` | 410 Rust + 1 test | Phase 0.75 ✅ 注册表 + 查询 API;**Phase 1 ⏸ 进程管理未做(ADR-V2-001/002 deferred)** | MCP server lifecycle across sessions(Cargo workspace member) |
| `tools/eaasp-cli-v2/` | 1,284 Py + 12 tests | Phase 0 ✅ L5 endpoint 模拟器;**Phase 5 ⏸ L5 Cowork UI + IM bot 未做** | end-user CLI:`eaasp session run -s <skill> -r <runtime> "<prompt>"` |
| `tools/eaasp-certifier/` | 1,954 Rust + 0 dedicated | Phase 3 ✅ contract harness | contract 认证 harness(Rust, Cargo workspace member) |
| `tools/eaasp-common/` | 31 Py + 1 test | minimal | shared types(SDK) |
| `tools/mock-scada/` | — | mature | 验证 skill 用的外部系统示例(Python 进程,集成 L3 policy / L4 orchestration) |
| `proto/eaasp/runtime/v2/` | 17 + 4 RPC = **21 方法** | frozen | L0 Protocol,runtime.proto(17) + hook.proto(4)+ common.proto |

### 2.3 L1 Runtime 生态(`lang/*` 7 个 + Cargo adapters 3 个)

按 ADR-V2-017 + ADR-V2-029 §1 切分:

| Adapter | 语言 | LOC | 等级 | Phase 3 sign-off |
|---------|------|----:|------|----------------|
| `crates/grid-runtime/` | Rust | 4,807 | **主力** | contract-v1.2.0 |
| `lang/claude-code-runtime-python/` | Py | 4,067 | **样板**(Anthropic SDK baseline) | contract-v1.1.0 |
| `lang/nanobot-runtime-python/` | Py | 2,443 | **样板**(OpenAI-compat provider) | contract-v1.1.0 |
| `crates/eaasp-goose-runtime/` + `crates/eaasp-scoped-hook-mcp/` | Rust | 802 + 456 | **对比**(Block goose via ACP subprocess) | contract-v1.1.0 |
| `lang/pydantic-ai-runtime-python/` | Py | 1,939 | 对比 | contract-v1.1.0 |
| `crates/eaasp-claw-code-runtime/` | Rust | 695 | 对比 | contract-v1.1.0 |
| `lang/ccb-runtime-ts/` | TS(Bun)| 531 | 对照 | contract-v1.1.0 |
| `lang/hermes-runtime-python/` | Py | frozen | **冻结**(ADR-V2-017)| superseded by goose + nanobot |

**Contract 演进**:
- `contract-v1.1.0`(Phase 3,2026-04-18 sign-off):42 PASS / 22 XFAIL × 7 runtime
- `contract-v1.2.0`(Phase 5.3,2026-05-20):ADR-V2-026(ExecutionMode)+ ADR-V2-027(OpenAI-compat Quirks)

**为什么"对比 runtime"存在**:它们是 contract 的活体测试。如果 grid-runtime 偷偷依赖未文档化行为,7 个独立实现中至少一个会拒绝通过同一 contract。这是 contract portability 的可证伪证据。

---

## 三、当前里程碑状态(2026-07-17)

> 本节作为本仓库 2026-07-17 的**产品状态 SSOT**。所有"已完工事项"在此明确列出,与 `.planning/STATE.md` / `.planning/PROJECT.md` 一致;所有"未完事项"在 §四 显式列出。

### 3.0 状态快照(当前五条结论,2026-07-17)

| # | 结论 | 性质 |
|---|------|------|
| 1 | **Grid Activation A.0–A.8 已全部 SHIPPED**(2026-06-17 milestone 关闭) | 已完成 |
| 2 | **EAASP 工程基础 + 契约校验完成**:`tools/eaasp-*` 是 EAASP v2.0 平台尚未完整实现前、按平台契约做的**模拟器级参考实现**(per EVOLUTION_PATH §一 P2);L0/L1/L2/L3/L4 工程骨架 + 7 runtime 全部通过 contract 验证 | 已完成 |
| 3 | **EAASP v2.0 平台演化以下事项仍未实现**:生产级 OPA 审批链 / A2A Router + Event Room(L4)/ L5 Cowork UI / 生态扩展 Marketplace 与 SDK | 未完成(下个 milestone 路线) |
| 4 | **L1 runtime 数量 = 7 总计,其中 6 个 comparison runtime**(`grid-runtime` 主力 + `claude-code-runtime-python` + `nanobot-runtime-python` + `goose-runtime` + `pydantic-ai-runtime-python` + `claw-code-runtime` + `ccb-runtime-ts`;`hermes-runtime-python` per ADR-V2-017 frozen) | 已完成(数量口径) |
| 5 | **contract-v1.1.0 = Phase 3 历史 sign-off**(2026-04-18);**contract-v1.2.0 = 当前最新契约**(Phase 5.3,2026-05-20,ADR-V2-026 + V2-027) | 已完成(版本口径) |

> 上表五点是被 2026-07-17 docs sync 锁定的口径,任何后续修改须走 ADR governance(`/adr:status` + `/adr:new`)。

### 3.1 SHIPPED 里程碑

| Milestone | 关闭日期 | 关键产出 |
|-----------|---------|---------|
| v3.0 Phase 4 — Product Scope Decision | 2026-04-28 | ADR-V2-024 双轴模型 Accepted(supersedes V2-023)|
| v3.1 Phase 5 — Engine Hardening | 2026-05-22 | 6 phases / 23 REQ-IDs / 6 ADRs(V2-025/026/027/028/029/032)|
| v3.2 Phase 6 — Tech-Debt Triage | 2026-05-26 | 93 D-rows triaged,3 fixes + INBOX seed |
| v3.3 Phase 7 — Engine + Platform Debt Sweep | 2026-06-07 | L3 RBAC,8/8 REQ-IDs |
| v3.4 Phase 7/8 — Full INBOX Drain | 2026-06-16 | 10 phases / 67 REQ-IDs / 2 ADRs(V2-033 + V2-017 §2) |
| v3.5 Phase 9 — Debt Finalization | 2026-06-16 | LEDGER 100% ✅ CLOSED(56 rows)|
| **Grid 独立产品 Activation(A.0–A.8)** | **2026-06-17** | 8 phases,Repo rename grid-sandbox→grid,README publish |

### 3.1.1 EAASP Phase 演化路线对应里程碑(2026-07-17 口径)

> 此表把 EVOLUTION_PATH §三 8 Phase 演化路线与本仓库 v3.x milestones 对齐。这是**事实口径**,区别于 §2.2 的"实现进度"表 — 后者只到 Phase 2。

| EAASP Phase | 对应里程碑段 | 状态(2026-07-17) |
|-------------|---------------|------------------|
| Phase 0 — Infrastructure Foundation | v3.0 / Phase 0 系列 | ✅ 完成(2026-04-12) |
| Phase 0.5 — MVP 全层贯通 | v3.0 / Phase 0.5 | ✅ 完成(2026-04-13) |
| Phase 0.75 — L2 MCP 编排 | v3.0 / Phase 0.75 | ✅ 完成(2026-04-13) |
| Phase 1 — Event-driven foundation | v3.0 / Phase 1 | ✅ 完成(2026-04-14) |
| Phase 2 — Memory and evidence | v3.0 / Phase 2 | ✅ 完成(2026-04-16) |
| Phase 2.5 — L1 Runtime 生态首批 | v3.0 / Phase 2.5 | ✅ 完成(2026-04-17) |
| Phase 3 — Approval and verification(OPA 审批链 / Sandbox Tiers) | v3.1 涉及 contract 收尾,OPA 后端未实现 | ⏸ **平台级 OPA 审批链 + 完整审批链 + Sandbox Tiers 未实现** |
| Phase 3.5 — chunk_type 统一 | v3.1 / Phase 5.3 一部分 | ✅ 完成(2026-04-19→20) |
| Phase 3.6 — Tech-debt Cleanup | v3.2 / Phase 6 | ✅ 完成(2026-04-20) |
| Phase 4a — Project review / GSD Bootstrap + Phase 4 主决策(ADR-V2-024 双轴模型) | v3.0 / Phase 4.0/4.1 | ✅ 完成(2026-04-27→28) |
| Phase 4 — Multi-agent collaboration(A2A Router / ReviewSet / T0 Harness) | — | ⏸ **A2A Router + Event Room 未实现** |
| Phase 5 — Complete collaboration space(L5 UI / 4 卡 / IM bot) | — | ⏸ **L5 Cowork UI + IM bot 未实现** |
| Phase 6 — Ecosystem expansion(Marketplace / 多租户 / SDK) | — | ⏸ **生态扩展未实现** |
| **Grid 独立产品 Activation(A.0–A.8)** | v3.5 后紧接的 milestone | **✅ 8/8 完成,2026-06-17 SHIPPED** |

> 后续 hardening / debt work 全部以 v3.x milestone 形式收口(v3.2 tech-debt triage + v3.3 engine/platform debt sweep + v3.4 full INBOX drain + v3.5 Debt Finalization)。

### 3.2 关键 KPI 当前值

| 维度 | 数值 |
|------|------|
| Rust crates 总数 | 12 + 3 eaasp adapters + 3 eaasp-certifier/mcp/skill registries |
| Rust 代码 LOC 总和 | ~178K |
| EAASP Python tools LOC | ~29K |
| Lang comparison runtimes LOC | ~16K |
| **L1 runtime 总数(含比较 runtime)** | **7**(1 主力 + 6 comparison runtimes) |
| ADR Accepted 数量 | 32+(V2-001..V2-032,含 V2-024/V2-029 双轴 substance 锁定)|
| D-items closed (cumulative v3.2–v3.5)| ~200 |
| LEDGER main D-table | 100% ✅ CLOSED |
| Phase 3 certifier sign-off(historical) | 42 PASS / 22 XFAIL × 7 runtime on **contract-v1.1.0** |
| **当前 latest contract 版本** | **contract-v1.2.0**(ADR-V2-026 + V2-027) |
| Pending commits 未 push | 0 |
| **Grid 独立产品 Activation phases** | **8/8 SHIPPED**(A.0–A.8 all closed 2026-06-17) |
| EAASP 平台未来工作(OOS,未实现) | 生产级 OPA 审批链 · A2A Router + Event Room · L5 Cowork UI · 生态扩展 Marketplace/多租户/SDK |

---

## 四、未来方向(展望)

### 4.1 三个明显的薄弱环节(2026-07-17 status)

1. **grid-desktop 6.5/10** — 几乎只是 Tauri 壳子。要做到 9.0 需要:
   - agent/session IPC 命令(start/stop agent / session 列表 / 事件订阅)— 现在只有 1 个真实 action + 7 个 get_*
   - 前端资产打包到 .app
   - 至少 1 个集成测试(Tauri mock-runtime)

2. **web-platform/ 7.5/10** — 视觉到位但 functional gap:
   - chat history 加载稳定性
   - dashboard 数据真实性(不再 placeholder)
   - 至少 3-5 个 vitest 关键 flow(目前 0)

3. **web/ 测试覆盖** — 9.0 评分但实测只有 1 个 vitest 文件。这是隐性债:评分高但回归保护弱,下次大改易踩雷。

### 4.2 strategic 选项(待用户决策)

- 启动全新 milestone:Grid 独立产品 v3.6 — 可以聚焦 web-platform/ 9.0 push / grid-desktop feature / release 打包
- 修三个 1–3 子项补齐质量(累计 2-3 plans)
- 推进 contract-v1.3 或 certifier 升级
- 启动 EAASP 引擎层 v2.1(L4 Event Room / A2A / new memory features,per EVOLUTION_PATH §四)

### 4.3 跨阶段演化原则

- **ADR governance 继续主导战略决策**(`/adr:*` + ADR governance plugin + F1-F5 lint)
- **engine ↔ data/integration 接入面固化** ADR-V2-030/V2-031 reserved(v3.2+ 落地)
- **No live LLM in unit tests**(per CLAUDE.md constraints)
- **Strict-by-default config validation**(per ADR-V2-028)— 任何 config 缺值 = 报错退出,不 fallback

---

## 五、与历史文档的差异(本次 docs sync 修正点)

| 文档 | 旧措辞(错) | 新措辞(对) | 修正原因 |
|------|------------|------------|---------|
| `CLAUDE.md` line 25, 70 | "`tools/eaasp-*/` are high-fidelity local shadows of EAASP's L2/L3/L4... The real production EAASP L2/L3/L4 lives in a separate project" | "`tools/eaasp-*/` 就是 EAASP v2.0 的当前实现,与 `crates/grid-*` 同仓孵化,本团队自做,不依赖外部" | CLAUDE.md 之前没有引用 ADR-V2-024 双轴 substance,沿用了 ADR-V2-023 时点的过时措辞 |
| `CLAUDE.md` line 23 | "engine 接入面 — EAASP 集成 (原 Leg A)" | "engine 侧(原 Leg A 字面表述, see ADR-V2-024 supersedes ADR-V2-023 双轴 substance)" | 旧 Leg A 措辞需要 (see ADR-V2-024) 指向,避免误导 |
| `README.md` line 53-86 架构图 | "Orchestration Layer (EAASP L2/L3/L4 or your own platform)" | 保留(对外文档讲 substitutability 是优点);加注释 "EAASP L2/L3/L4 由本仓 `tools/eaasp-*/` 交付,生产环境可直接本仓部署 `dev-eaasp.sh`;也可对接 customer 自有平台" | 对外表述同时强调本仓可生产部署 + 仍可替换 |
| `ADR-V2-024` line 112 Affected Modules | "`tools/eaasp-*/` shadow vs production 路径取决于 Decision" | Note (2026-07-17) 澄清:`tools/eaasp-*/` 为 EAASP v2.0 当前实现(ADR-V2-024 双轴 substance),不再有 "shadow vs production" 区分 | ADR Accepted 时该句未清干净 |
| `MEMORY.md` | "5 个 EAASP Shadow 工具 L2/L3/L4" | "5 个 EAASP 引擎层 tools/eaasp-*(EAASP v2.0 当前实现,本团队自做)" | MEMORY 是历史记录,新增事实需准确 |

---

## 六、Reference Linkage

### 6.1 EAASP 平台设计文档权威源(同仓 `docs/design/EAASP/`)

> 这是 EAASP 平台层面的设计文档,**`EAASP-Design-Specification-v2.0.docx` 是规范权威**(per EVOLUTION_PATH §"权威规范")。

| 文档 | 作用 |
|------|------|
| `docs/design/EAASP/EAASP-Design-Specification-v2.0.docx` | **规范权威**(4373KB,导出 markdown 2944 行位于 `/tmp/eaasp_v2_spec.md`) |
| `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md` | 长期 cross-phase 决策登记(5 层 + 3 管道 + 4 元范式 + 7 阶段演化路线)|
| `docs/design/EAASP/EAASP_v2_0_MVP_SCOPE.md` | 圈 2 MVP 范围细化 |
| `docs/design/EAASP/EAASP_v2_0_Platform_Product_Forms.docx` | 产品形态蓝图 |
| `docs/design/EAASP/EAASP_v2_Executive_Overview.docx` + `.html` | 高管摘要 / 对外简版 |
| `docs/design/EAASP/PHASE1_EVENT_ENGINE_DESIGN.md` | Phase 1 Event-driven 设计 |
| `docs/design/EAASP/PHASE_3_DESIGN.md` | Phase 3 Approval and verification 设计(⏸) |
| `docs/design/EAASP/L1_RUNTIME_ADAPTATION_GUIDE.md` | L1 runtime adapter 实现指南 |
| `docs/design/EAASP/L1_RUNTIME_STRATEGY.md` + 7 个 R1-R4 eval + TIER_SPEC | L1 Runtime 生态策略 + 4 tier 横切 |
| `docs/design/EAASP/PROVIDER_CAPABILITY_MATRIX.md` | LLM provider matrix |
| `docs/design/EAASP/E2E_VERIFICATION_GUIDE.md` | E2E 验证脚本 living spec |
| `docs/design/EAASP/DEFERRED_LEDGER.md` | 跨 phase D-item SSOT(100% ✅ CLOSED)|

### 6.2 战略 ADR(双轴 substance)

- **ADR-V2-024** — 双轴 substance + Phase 4 product scope 主决定: `docs/design/EAASP/adrs/ADR-V2-024-phase4-product-scope-decision.md`
- **ADR-V2-029** — 双轴 crate-level enforcement 落地: `docs/design/EAASP/adrs/ADR-V2-029-engine-data-integration-boundary.md`
- **ADR-V2-023** — 双腿战略 superseded: `docs/design/EAASP/adrs/ADR-V2-023-grid-two-leg-product-strategy.md`(⚠️ "high-fidelity shadow" 措辞过时,见 ADR-V2-024 §1 + EVOLUTION_PATH "本团队自做")

### 6.3 当前项目管理状态

- **当前 PROJECT 状态**: `.planning/PROJECT.md`(已于 2026-04-26 写入正确叙事,本次 docs sync 跟进)
- **当前 STATE**: `.planning/STATE.md`(Grid 独立产品 Activation SHIPPED 2026-06-17)
- **ROADMAP**: `.planning/ROADMAP.md`
- **CLAUDE.md**: `/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/CLAUDE.md`
- **README**: README.md + README.zh.md

---

*Created: 2026-07-17 by docs-sync PR — 在用户指出 CLAUDE.md 与 PROJECT.md 叙事脱节后写的 single source of truth。
历史 ADR / 老措辞以 ADR-V2-029 / ADR-V2-024 双轴 substance 为正。*
