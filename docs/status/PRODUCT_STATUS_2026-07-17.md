---
doc_type: project-status-snapshot
status: canonical (2026-07-17 快照)
sibling_ssot: docs/PROJECT_PRODUCT_OVERVIEW.md
purpose: |
  不可变审计快照(本文件)锁住 2026-07-17 docs sync 时刻的 5 个 canonical 事实 +
  4 个 EAASP 平台演化缺口 + 7 L1 runtime + 32+ ADR + contract-v1.1.0 / v1.2.0 baseline。
  本文件与 docs/PROJECT_PRODUCT_OVERVIEW.md(可维护 SSOT)必须严格一致;
  任何对 SSOT 的后续修改 **必须** 触发同日期或后续日期的新快照,本文件 **不可修改**。
verification_baseline_sha: 05c6d7db9cedd242a9beaf082a6ed0c59ae9ff8b
verification_ssot_commit_sha: 79b6f80f
verification_date: 2026-07-17
audience: 未来 Claude Code session、本团队 contributor、潜在 reviewer、外部审计
language: 中文(per global CLAUDE.md `docs/` 目录规则)
---

# Grid × EAASP 项目产品情况 — 2026-07-17 不可变审计快照

## 🔒 IMMUTABLE 声明

**本文件是不可变快照(immutable audit snapshot)。** 它记录 2026-07-17 docs sync 时刻的项目产品情况。本文件 **不应被修改、补充或删除** — 修改会导致与 SSOT / 历史恢复点的可信度丢失。

如需更新:

1. **修改 SSOT**:`docs/PROJECT_PRODUCT_OVERVIEW.md`(可维护 single source of truth)
2. **建新快照**:`docs/status/PRODUCT_STATUS_<YYYY-MM-DD>.md`
3. **不要触碰本文件** — 本文件保留作历史锚点(historical anchor)

---

## 一、Executive conclusion — 5 canonical 事实 + 4 future gaps

### 1.1 5 canonical 事实(2026-07-17 时刻)

| # | 事实 | 状态 |
|---|------|------|
| 1 | Grid 独立产品 Activation 全 8 阶段(A.0–A.8)✅ SHIPPED 2026-06-17,repo 已重命名 grid-sandbox → grid | ✅ |
| 2 | L1 contract 当前版本 = `contract-v1.2.0`(Phase 5.3 2026-05-20 引入 ADR-V2-026 ExecutionMode + ADR-V2-027 OpenAI-compat Quirks);Phase 3 sign-off baseline = `contract-v1.1.0`(42 PASS / 22 XFAIL × 7 runtime) | ✅ |
| 3 | L1 runtime 生态 = 1 主力(grid-runtime)+ 6 comparison(7 个 adapter 含 hermes frozen);L1 contract 16 方法 = 12 MUST + 4 Optional | ✅ |
| 4 | `tools/eaasp-*/` 是 **EAASP v2.0 平台尚未完整实现前、按平台契约做的模拟器级参考实现**;不存在"上游 EAASP"独立项目;EAASP 平台设计文档权威源同仓 `docs/design/EAASP/`(`EAASP-Design-Specification-v2.0.docx` 为规范权威) | ✅ |
| 5 | EAASP 平台 v2.0 设计规范的 5 层 + 3 管道 + 4 元范式 + 7 阶段演化已实现约 40–50%(圈 2 + 圈 3 + Phase 0–2.5);4 个 EAASP 平台演化缺口(Phase 3 OPA 审批链 / Phase 4 A2A Router + Event Room / Phase 5 L5 Cowork UI / Phase 6 生态扩展 Marketplace + 多租户 + SDK)⏸ 待后续 milestone 推进 | 🟡 STARTED |

### 1.2 4 future gaps(详见 §五)

| # | Gap | Phase | Future milestone 入口 |
|---|-----|-------|---------------------|
| 1 | 生产级 OPA 后端 + 5 阶段审批链 | Phase 3 | v3.7+ EAASP Phase 3 实施 |
| 2 | A2A Router + Event Room | Phase 4 | v3.7+ EAASP Phase 4 实施 |
| 3 | L5 Cowork UI(4 卡)+ IM bot + 回溯闭环 | Phase 5 | v3.7+ EAASP Phase 5 实施 |
| 4 | 生态扩展(Marketplace + 多租户 + SDK) | Phase 6 | v3.7+ EAASP Phase 6 实施 |

---

## 二、Grid 产品完成表(A.0–A.8,2026-06-17 全部 SHIPPED)

| Phase | 名称 | 关闭日 | 关键交付 | Quality 评分 |
|-------|------|-------|---------|-----------|
| **A.0** | Audit & Scoping | 2026-06-16 | 7-crate gap analysis + Activation 评分 | — |
| **A.1** | grid-server Hardening | 2026-06-16 | budget fix, ApiError adoption, legacy WS removal, RBAC middleware | grid-server **9.0** ✅ |
| **A.2** | web/ Production Polish | 2026-06-16 | mocks removed, errors standardized, 9 vitest tests | web/ **9.0** ✅ |
| **A.3** | grid-cli Final Polish | 2026-06-16 | config persistence, doctor repair expansion | grid-cli **9.0** ✅ |
| **A.4** | Cross-Cutting Foundation | 2026-06-17 | ApiClient + cn() + design tokens + branding | cross-cutting |
| **A.5** | grid-platform Hardening | 2026-06-17 | ErrorCode enum, quota middleware, 20 new tests | grid-platform **9.0** ✅ |
| **A.6** | web-platform/ Production | 2026-06-17 | ErrorBoundary + Toast + Markdown + dashboard fix | web-platform/ **7.5** |
| **A.7** | grid-desktop Feature Work | 2026-06-17 | icon assets, 3 new IPC commands, Grid rebrand, updater fix | grid-desktop **6.5** |
| **A.8** | grid-eval CI Enhancement | 2026-06-17 | CI concurrency group, test summary reporting | grid-eval **9.0** ✅ |
| **合计** | **A.0–A.8 8 phases** | **2026-06-17** | Repo rename + README publish | **5/7 组件 9.0+** |

**质量基线(2026-06-17 Activation 后)**:5 个 9.0+ 组件(grid-cli / web/ / grid-server / grid-eval / grid-platform);1 个 7.5(web-platform/);1 个 6.5(grid-desktop)。

---

## 三、EAASP Phase 演化路线(已完成 + 仍开缺口)

| Phase | 关闭日 | 状态 |
|-------|--------|------|
| Phase 0 — Infrastructure Foundation | 2026-04-12 | ✅ 完成 |
| Phase 0.5 — MVP 全层贯通 | 2026-04-13 | ✅ 完成 |
| Phase 0.75 — L2 MCP 编排 | 2026-04-13 | ✅ 完成 |
| Phase 1 — Event-driven foundation | 2026-04-14 | ✅ 完成 |
| Phase 2 — Memory and evidence | 2026-04-16 | ✅ 完成 |
| Phase 2.5 — L1 Runtime 生态首批 | 2026-04-17 | ✅ 完成 |
| Phase 3 — Approval and verification | — | ✅ contract validation 收口 / ⏸ OPA + 完整审批链 未实现 |
| Phase 3.5 — chunk_type Unification | 2026-04-20 | ✅ 完成(ADR-V2-021 Accepted) |
| Phase 3.6 — Post-Activation Docs Sync | 2026-07-17 STARTED | docs sync,本项目当前 phase |
| Phase 4a — Project review / GSD Bootstrap | 2026-04-28 | ✅ 完成(ADR-V2-024 Accepted) |
| Phase 4 — Multi-agent collaboration | — | ⏸ A2A Router + Event Room 未实现 |
| Phase 5 — Complete collaboration space | — | ⏸ L5 Cowork UI 未实现 |
| Phase 6 — Ecosystem expansion | — | ⏸ Marketplace + SDK 未实现 |

### 3.1 后续 hardening / debt 里程碑(v3.2–v3.5)

| Milestone | 关闭日 | 关键产出 |
|-----------|---------|---------|
| v3.2 Tech-Debt Triage(Phase 6) | 2026-05-26 | 93 D-rows triaged |
| v3.3 Engine + Platform Debt Sweep(Phase 7) | 2026-06-07 | L3 RBAC 8/8 REQ-IDs |
| v3.4 Full INBOX Drain(Phase 7/8) | 2026-06-16 | 10 phases / 67 REQ-IDs / 2 ADRs |
| v3.5 Debt Finalization(Phase 9) | 2026-06-16 | LEDGER 100% ✅ CLOSED(56 rows) |

---

## 四、L0/L1/L2/L3/L4 已交付 capability(EAASP 全栈 8 Phase 路线)

| 层 | 组件 | 状态 | 关键能力 |
|---|------|------|---------|
| L4 Orchestration | `tools/eaasp-l4-orchestration/` | ✅ Phase 1 收口 | session lifecycle + SSE fan-out + governance gates;**A2A / Event Room ⏸ Phase 4 未实现** |
| L3 Governance | `tools/eaasp-l3-governance/` | ✅ Phase 1 收口 | policy DSL + risk classification + shadow/enforce mode;**OPA 后端 + 完整审批链 ⏸ Phase 3 未实现** |
| L2 Memory & Skills | `tools/eaasp-l2-memory-engine/` + `tools/eaasp-skill-registry/` + `tools/eaasp-mcp-orchestrator/` | ✅ 全量 | FTS5 + HNSW + time-decay hybrid; 7 MCP tools; skill manifest + MCP tool bridge |
| L1 Runtime | `crates/grid-runtime/` + 6 comparison runtimes | ✅ Phase 3 sign-off(7/7 × 42 PASS / 22 XFAIL on `contract-v1.1.0`);`contract-v1.2.0` current | substitutable L1 runtime via 12 MUST + 4 Optional contract |
| L0 Protocol | `proto/eaasp/runtime/v2/` = runtime.proto(17 RPC) + hook.proto(4 RPC) = **21 RPC total** | frozen | 16/17/21 RPC 口径区分详见 SSOT §2.2 L0 Protocol split |

---

## 五、显式平台演化缺口(explicit platform-evolution gaps)

| # | 缺口 | 关联 Phase | 当前 in-repo 状态 | 未来 milestone 入口 |
|---|------|------------|------------------|------------------|
| 1 | **生产级 OPA 后端 + 5 阶段审批链** | Phase 3 | `tools/eaasp-l3-governance/` Phase 1 基础 ✅;**OPA 后端 + 完整审批链 ⏸ 未实现** | v3.7+ 启动 EAASP Phase 3 实施 |
| 2 | **A2A Router + Event Room** | Phase 4 | `tools/eaasp-l4-orchestration/` Phase 1 基础 ✅;**A2A Router + ReviewSet + T0 Harness ⏸ 未实现** | v3.7+ 启动 EAASP Phase 4 实施 |
| 3 | **L5 Cowork UI(4 卡)+ IM bot + 回溯闭环** | Phase 5 | `tools/eaasp-cli-v2/` Phase 0 ✅;**L5 Cowork UI ⏸ 未实现** | v3.7+ 启动 EAASP Phase 5 实施 |
| 4 | **生态扩展(Marketplace + 多租户 + SDK)** | Phase 6 | **全部 ⏸ 未实现** | v3.7+ 启动 EAASP Phase 6 实施 |

---

## 六、关键术语口径(canonical terminology)

| 术语 | 精确含义 |
|------|---------|
| **`tools/eaasp-*` = 模拟器级参考实现** | EAASP v2.0 平台尚未完整实现前、按平台契约做的参考实现;**不存在"上游 EAASP"独立项目**(per EVOLUTION_PATH §一 P2 + ADR-V2-024 §1 + ADR-V2-029 §1) |
| **L1 contract = 16 方法 / 运行时 17 RPC / 协议总 21 RPC** | 三者口径不同,务必区分:① L1 contract 16 方法 = 12 MUST + 4 Optional(v2.0 spec §8.5 锁定,Certifier 验 12 MUST);② `runtime.proto` 17 RPC = 16 spec + 1 EmitEvent(OPTIONAL per ADR-V2-001 Accepted Phase 1);③ 协议总 21 RPC = 17 runtime + 4 hook(`hook.proto` 独立 RPC service) |
| **`contract-v1.1.0` = Phase 3 历史 sign-off** | 2026-04-18;42 PASS / 22 XFAIL × 7 runtime;deprecated by v1.2.0 后仍保留为历史版本 |
| **`contract-v1.2.0` = 当前 latest** | 2026-05-20,Phase 5.3;ADR-V2-026(ExecutionMode)+ ADR-V2-027(OpenAI-compat Quirks) |
| **7 L1 runtime = 1 主力 + 6 comparison** | grid-runtime + claude-code / goose / nanobot / pydantic-ai / claw-code / ccb(`hermes` frozen per ADR-V2-017) |
| **Grid Activation = 8 phases A.0–A.8** | 2026-06-17 SHIPPED,repo rename `grid-sandbox` → `grid`,Activation 是 post-Activation scope 的基础 |

### 6.1 EAASP 平台设计文档权威源(同仓 `docs/design/EAASP/`)

- `EAASP-Design-Specification-v2.0.docx` — **规范权威**
- `EAASP_v2_0_EVOLUTION_PATH.md` — 长期 cross-phase 决策登记
- `EAASP_v2_0_MVP_SCOPE.md` — 圈 2 MVP 范围
- `EAASP_v2_0_Platform_Product_Forms.docx` — 产品形态蓝图
- `PHASE1_EVENT_ENGINE_DESIGN.md` / `PHASE_3_DESIGN.md` — 各 Phase 设计
- `L1_RUNTIME_ADAPTATION_GUIDE.md` — L1 runtime adapter 实现指南
- `L1_RUNTIME_STRATEGY.md` + 7 个 R1-R4 eval + `L1_RUNTIME_TIER_SPEC_*` — L1 Runtime 生态策略
- `PROVIDER_CAPABILITY_MATRIX.md` — LLM provider matrix
- `E2E_VERIFICATION_GUIDE.md` — E2E 验证脚本 living spec
- `DEFERRED_LEDGER.md` — 跨 phase D-item SSOT(2026-06-16 100% ✅ CLOSED)
- `adrs/ADR-V2-*.md` 32+ ADR — 战略 + 契约 ADR

### 6.2 战略 ADR(双轴 substance)

- `ADR-V2-024-phase4-product-scope-decision.md` — Accepted 2026-04-28(双轴 substance: engine vs data/integration)
- `ADR-V2-029-engine-data-integration-boundary.md` — 双轴 crate-level enforcement

### 6.3 当前项目管理状态

- **当前 milestone**:v3.6 Post-Activation Docs Sync(2026-07-17 STARTED)
- **GSD planning state**:`.planning/STATE.md` + `.planning/PROJECT.md` + `.planning/ROADMAP.md`
- **本项目使用 GSD 体系管理**:`.planning/phases/<n>-<slug>/<n>-CONTEXT.md` + `<n>-<plan>-PLAN.md` + `<n>-<plan>-SUMMARY.md`(do NOT mix superpowers / project-state / lwm artifacts into `.planning/`)

---

## 七、Verification date + commit SHA range

- **快照生成日期**:2026-07-17
- **快照固定内容**:SSOT 5 canonical 事实 + Grid A.0–A.8 完成表 + EAASP Phase 0–4a 完成表 + L0/L1/L2/L3/L4 已交付 capability + 4 类显式 GAP + 关键术语口径 + 源链接
- **commit 锚点**:
  - 验证锚点 SHA:`05c6d7db9cedd242a9beaf082a6ed0c59ae9ff8b`(主题 `wip: docs-sync-2026-07-17 paused at completed+verified`,SSOT 提交之前的 HEAD)
  - SSOT 提交 SHA:`79b6f80f`(SSOT 提交含 §3.0 状态快照扩展;位于本快照之前)
- **一致性验证(必需 token,见 §1.1 + §6.1)**:`2026-06-17`、`A.8`、`7`、`6 comparison`、`contract-v1.1.0`、`contract-v1.2.0`、`模拟器级参考实现`、`A2A`、`Cowork` 共 9 个 token 在 SSOT + 本快照两份文档都必须出现
- **未被本快照影响的文件**:`AGENTS.md` / `CLAUDE.md` / `README.md` / `README.zh.md` / `.planning/STATE.md` / `.planning/PROJECT.md` 在本次 docs sync 中单独处理(由 GSD v3.6 phase 后续 plan 覆盖)
