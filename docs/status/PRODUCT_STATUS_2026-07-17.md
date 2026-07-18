---
doc_type: project-status-snapshot
status: canonical (2026-07-17 快照)
sibling_sssot: docs/PROJECT_PRODUCT_OVERVIEW.md (持续维护的 SSOT)
purpose: 2026-07-17 docs sync 时点的产品状态固化快照 — 锁定当时事实口径,后续以 SSOT 为准
audience: 未来 Claude Code session(冷启动优先读)、本团队 contributor、潜在 reviewer
language: 中文(per global CLAUDE.md `docs/` 目录规则)
created: 2026-07-17
verification_date: 2026-07-17
verification_commit_sha: 05c6d7db9cedd242a9beaf082a6ed0c59ae9ff8b
verification_commit_subject: wip: docs-sync-2026-07-17 paused at completed+verified
verification_commit_note: 此 SHA 是 Task 1 提交(`1de93a9f docs: record Grid and EAASP product status`)之前的 HEAD;docs sync PR 把本快照连同 SSOT 一起收录
verification_documents:
  - docs/PROJECT_PRODUCT_OVERVIEW.md (持续维护 SSOT)
  - docs/status/PRODUCT_STATUS_2026-07-17.md (本快照,一次性 immutable)
related_adrs: ADR-V2-024, ADR-V2-029, ADR-V2-026, ADR-V2-027
---

# Grid × EAASP 产品状态快照 — 2026-07-17

> **本文档是一次性快照**(date-stamped audit),固化 2026-07-17 docs sync 时点的产品状态结论。**持续维护 SSOT 仍在 [docs/PROJECT_PRODUCT_OVERVIEW.md](../../PROJECT_PRODUCT_OVERVIEW.md)**;后续任何变更先改 SSOT,再重新生成一份新日期快照,而不是修改本文档。
>
> 历史快照(`PRODUCT_STATUS_YYYY-MM-DD.md`)一旦生成即视为 immutable,不得事后改写。
>
> 文档语言:中文(`docs/` 目录规则,见 global CLAUDE.md §4)。

---

## 1. 一、执行结论(Executive conclusion)

本仓库(2026-06-17 由 `grid-sandbox` 改名为 `grid`)是 **EAASP 全栈 + Grid 全栈的同仓孵化体**。2026-07-17 的总体状态由以下五条结论共同决定:

1. **Grid 独立产品 Activation 已经 SHIPPED**(`A.0` 通过 `A.8` 全部完成),关闭日 **2026-06-17**。这意味着 `grid-server` / `grid-cli` / `grid-platform` / `web/` 等组件不再是 "dormant/scaffolding only" — 它们已通过 Activation 8 phases 的硬化验收(详见第 2 节)。
2. **EAASP 工程基础已经完成(L0/L1/L2/L3/L4 骨架)**:本仓 `tools/eaasp-*/` 是 EAASP v2.0 平台尚未完整实现前、按平台契约做的**模拟器级参考实现**,EAASP 引擎层基础 + 契约校验 + Phase 0–4a 全部已交付清单见第 4 节;Phase 0–2.5 + 3 + 3.5 + 3.6 + 4a 与后续 hardening/debt work(v3.2–v3.5)整合视为整体已完成。
3. **EAASP v2.0 平台演化仍开缺口**,以下 4 类工作**未实现**(逐项见 §5):
   - 生产级 OPA 审批链(Phase 3 OPA backend + 完整审批链)
   - A2A / Event Room(Phase 4)
   - L5 Cowork UI(Phase 5,4 卡界面 + IM bot)
   - 生态扩展 Market/Multi-tenant/SDK(Phase 6)
4. **L1 runtime 数量 = 7**(主力 1 + comparison 6);`hermes-runtime-python` per ADR-V2-017 已 frozen。
5. **contract 版本口径**:`contract-v1.1.0` 是 Phase 3 历史 sign-off(2026-04-18,42 PASS / 22 XFAIL × 7 runtime);`contract-v1.2.0` 是当前 latest(2026-05-20,Phase 5.3,ADR-V2-026 + V2-027)。

本快照的内部一致性已经过 §6.1 列出的 9 个必需 token 比对验证(详见 §7)。

> 注:结论 #3 中的 4 类工作 = §5 表的 4 行;除此之外无其他"未完工子项"。其他仍在路上的项目(Grid web-platform/ 7.5/10、grid-desktop 6.5/10、web/ 测试覆盖)属 Grid 组件质量细节,不是 EAASP 平台演化缺口,见 `docs/PROJECT_PRODUCT_OVERVIEW.md` §4。

---

## 2. Grid 产品完成表(A.0–A.8)

> 来源:`.planning/STATE.md` §Audit Findings Summary + §Completed Milestones §Quality Improvements(Phase B — 2026-06-17)。
> Activation SHIPPED 日期:**2026-06-17**。

| Phase | 名称 | 关闭日 | 关键交付物 | Activation 评分 / Quality 评分 |
|-------|------|-------|----------|-------------------------------|
| **A.0** | Audit & Scoping | 2026-06-16 | 7-crate gap analysis + Activation 评分 | — |
| **A.1** | grid-server Hardening | 2026-06-16 | budget fix,ApiError adoption,legacy WS removal,RBAC middleware | grid-server 6/10→Quality **9.0** ✅ |
| **A.2** | web/ Production Polish | 2026-06-16 | mocks removed,errors standardized,9 vitest tests | web/ 7/10→Quality **9.0** ✅ |
| **A.3** | grid-cli Final Polish | 2026-06-16 | config persistence,doctor repair expansion | grid-cli 8/10→Quality **9.0** ✅ |
| **A.4** | Cross-Cutting Foundation | 2026-06-17 | ApiClient + cn() + design tokens + branding | cross-cutting |
| **A.5** | grid-platform Hardening | 2026-06-17 | ErrorCode enum,quota middleware,20 new integration tests | grid-platform 6/10→Quality **9.0** ✅ |
| **A.6** | web-platform/ Production | 2026-06-17 | ErrorBoundary + Toast + Markdown + dashboard fix + loading skeletons | web-platform/ 3/10→Quality **7.5** |
| **A.7** | grid-desktop Feature Work | 2026-06-17 | icon assets,3 new IPC commands,Grid rebrand,updater fix | grid-desktop 3/10→Quality **6.5** |
| **A.8** | grid-eval CI Enhancement | 2026-06-17 | CI concurrency group,test summary reporting | grid-eval 7/10→Quality **9.0** ✅ |
| **合计** | **A.0–A.8 8 phases** | **2026-06-17** | Repo rename `grid-sandbox` → `grid`,README publish | 5 组件 9.0+ / 1 组件 7.5 / 1 组件 6.5(见下)|

**质量基线(2026-06-17 Activation 后,7 个受评组件逐项列举)**:

| 组件 | Quality 分 | 测试覆盖 |
|------|-----------|---------|
| grid-cli | 9.0 ✅ | 140+ tests,16 commands,full TUI |
| web/ | 9.0 ✅ | 9 vitest tests,8 tabs,no mocks(评分与覆盖不均衡 — 见 §5) |
| grid-server | 9.0 ✅ | 25 integration test files,HMAC/JWT,~130 endpoints |
| grid-eval | 9.0 ✅ | 10 scorers,12 suites,CI workflow,parallel runner |
| grid-platform | 9.0 ✅ | 37 tests,ErrorCode enum,quota wired,5MB limits |
| web-platform/ | 7.5 | 0 vitest 文件(UI 组件) |
| grid-desktop | 6.5 | 9(仅 IPC 命令,无 agent/session 端到端) |

→ **7 个组件逐项计数:5 个 9.0+ / 1 个 7.5 / 1 个 6.5**。
→ 注:`.planning/STATE.md` §Audit Findings Summary 末段写作 "4/7 components at 9.0+";逐项对照上表应为 **5/7**。该 prose 数字与同表列出的 web/ Quality 9.0 自相矛盾;**本快照以逐项表为准**,STATE.md 数字属于历史打字遗留,待 Task 3 修 `.planning/STATE.md` 时一并 reconcile。

---

## 3. EAASP 完成表(Phase 0–4a + 后续 hardening)

> 来源:`docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md` §三 + 本仓 `.planning/STATE.md` 已 SHIPPED 里程碑清单。

### 3.1 EAASP 演化 8 Phase + 后续 hardening 整体口径

| Phase | 名称 | 关闭日 | 完成度(2026-07-17) | 备注 |
|-------|------|-------|------------------|------|
| **0** | Infrastructure Foundation | 2026-04-12 | ✅ 完成 | 5 层服务骨架 + **L1 contract 16 方法契约**(12 MUST + 4 Optional,per v2.0 spec §8.5;详见 §4 L0 Protocol 行) |
| **0.5** | MVP — 全层贯通 | 2026-04-13 | ✅ 完成 | L4→L1 真 gRPC + LLM agent 执行 |
| **0.75** | L2 MCP 编排 | 2026-04-13 | ✅ 完成 | 三 runtime 统一 MCP transport |
| **1** | Event-driven foundation | 2026-04-14 | ✅ 完成 | L4 Event Engine + Session Event Stream |
| **2** | Memory and evidence | 2026-04-16 | ✅ 完成 | L2 memory + skill extraction + PreCompact |
| **2.5** | L1 Runtime 生态首批 | 2026-04-17 | ✅ 完成 | 7 个 L1 runtime + 契约测试集 |
| **3** | Approval and verification | 2026-04-18(contract 部分)| ✅ **contract-v1.1.0 校验收尾**(42 PASS / 22 XFAIL × 7 runtime,详见 §3.1.1);**⏸ 生产级 OPA/Rego 后端 + 5-stage 审批链 + Verifier + Sandbox Tiers 全部未实现**(见 §5 第 1 行) | Phase 3 拆分:contract validation 已收口(由 `crates/eaasp-certifier/` 实装);platform-level approval chain / OPA backend / Sandbox Tiers 仍 ⏸ |
| **3.5** | chunk_type 统一 | 2026-04-19→20 | ✅ 完成 | ADR-V2-021 Accepted,8 wire 值跨 7 runtime 1:1 |
| **3.6** | Tech-debt Cleanup | 2026-04-20 | ✅ 完成 | D140/D145–D147/D150 已 closed |
| **4a** | Project review / GSD Bootstrap + Phase 4 主决策 | 2026-04-27→28 | ✅ 完成 | ADR-V2-024 双轴模型 Accepted + GSD 治理 |
| **4** | Multi-agent collaboration | — | ⏸ 未实现 | **A2A Router + Event Room 未实现** |
| **5** | Complete collaboration space | — | ⏸ 未实现 | **L5 Cowork UI + IM bot 未实现** |
| **6** | Ecosystem expansion | — | ⏸ 未实现 | **Marketplace + 多租户 + SDK 未实现** |

### 3.1.1 Phase 3 拆分说明:contract validation ✅ vs platform OPA ⏸

Phase 3 在本快照里被刻意拆为两部分以避免歧义:

| Phase 3 子项 | 状态(2026-07-17) | 关键证据 |
|---|---|---|
| **L1 contract 校验**(contract-v1.1.0 sign-off)| ✅ 完成(2026-04-18) | 7 runtime × 42 PASS / 22 XFAIL;`crates/eaasp-certifier/` 实装 |
| **L1 contract 升级**(contract-v1.2.0)| ✅ 完成(2026-05-20,Phase 5.3)| ADR-V2-026 + ADR-V2-027 |
| **生产级 OPA/Rego 后端** | ⏸ 未实现 | `tools/eaasp-l3-governance/` 仅含 Policy DSL + risk classification + shadow/enforce mode,无 OPA/Rego 后端 |
| **5-stage 完整审批链** | ⏸ 未实现 | EVOLUTION_PATH §2.2 四元范式 I 列出的 5-stage approval chain 尚未实装 |
| **Verifier / Sandbox Tiers** | ⏸ 未实现 | EVOLUTION_PATH §三 Phase 3 行的 verifier / sandbox tiers 未交付 |

→ 因此本快照 §3.1 Phase 3 行的"✅ contract 收尾"**仅指 L1 contract 校验 + 升级两部分**;**不**包含 OPA/审批链/Verifier/Sandbox Tiers。这部分未完工内容由 §5 第 1 行显式承接。

### 3.2 后续 hardening / debt 里程碑(v3.2–v3.5)

| Milestone | 关闭日 | 关键产出 |
|-----------|---------|---------|
| v3.2 — Tech-Debt Triage(Phase 6) | 2026-05-26 | 93 D-rows triaged,3 fixes + INBOX seed |
| v3.3 — Engine + Platform Debt Sweep(Phase 7) | 2026-06-07 | L3 RBAC,8/8 REQ-IDs |
| v3.4 — Full INBOX Drain(Phase 7/8) | 2026-06-16 | 10 phases / 67 REQ-IDs / 2 ADRs(V2-033 + V2-017 §2) |
| v3.5 — Debt Finalization(Phase 9) | 2026-06-16 | LEDGER 100% ✅ CLOSED(56 rows) |

→ 4 个后续 hardening 里程碑全部 SHIPPED,与 Phase 0–4a 整合视为整体已完成。

---

## 4. 已交付 EAASP capability — L0/L1/L2/L3/L4 横切

> 来源:`docs/design/EAASP/EAASP-Design-Specification-v2.0.docx` + `EAASP_v2_0_EVOLUTION_PATH.md` + `DEFERRED_LEDGER.md`(100% ✅ CLOSED)。

| 层 | 已交付 capability(2026-07-17) | 关键证据 |
|----|------------------------|---------|
| **L0 Protocol** | `proto/eaasp/runtime/v2/` = runtime.proto(**17 RPC** = 12 MUST + 4 Optional + 1 EmitEvent OPTIONAL per ADR-V2-001)+ hook.proto(**4 RPC**)= **21 RPC total**;common.proto。<br>**与 "L1 16 方法 contract" 的关系**:L1 contract = `12 MUST + 4 Optional = 16`(per v2.0 spec §8.5 + EVOLUTION_PATH §2.4);运行时 `runtime.proto` 实装 17 RPC = 16 spec + 1 EmitEvent(OPTIONAL per ADR-V2-001);hook.proto 的 4 RPC 独立于 L1 contract,用于 L4↔L1 钩子事件。Certifier **只验 12 MUST core**,4 Optional 报告为 bonus,EmitEvent 默认 no-op。 | `proto/eaasp/runtime/v2/` |
| **L1 Runtime** | 7 个 runtime(详见 §6)+ contract-v1.1.0 历史 sign-off + contract-v1.2.0 当前 latest | `crates/eaasp-certifier/` + Phase 3 验收 + Phase 5.3 升级 |
| **L2 Memory & Skills** | L2 memory(FTS5 + HNSW + time-decay hybrid,7 MCP tools:search/read/write_file/write_anchor/confirm/list/delete)+ skill registry(skill manifest + MCP tool bridge)+ MCP orchestrator | `tools/eaasp-l2-memory-engine/` + `tools/eaasp-skill-registry/` + `tools/eaasp-mcp-orchestrator/` |
| **L3 Governance** | Policy DSL + risk classification + shadow/enforce mode;**OPA 后端 + 完整审批链未实现**(仍 ⏸ 见 §5) | `tools/eaasp-l3-governance/` |
| **L4 Orchestration** | Session 编排 + SSE fan-out + governance gates;**A2A Router + Event Room 未实现**(仍 ⏸ 见 §5) | `tools/eaasp-l4-orchestration/` |
| **工具链 / 用户侧** | `tools/eaasp-cli-v2/` = end-user CLI(`eaasp session run -s <skill> -r <runtime> "<prompt>"`)+ `tools/eaasp-certifier/` = contract harness + `tools/mock-scada/` = 验证 skill 外部系统示例 | Phase 0.5 MVP + Phase 1 验收 |
| **Pipeline A: Hook** | 14 lifecycle events + scoped-hook executor(Pre/Post/Stop 真实触发)| Phase 0.5 S3 + Phase 2 |
| **Pipeline B: Data-flow** | SessionPayload P1–P5 下行 + 4 类上行 + evidence anchors | Phase 2(全部已交付)|
| **Pipeline C: Session-control** | L4 Event Engine + Session Event Stream(SSE)+ 事件 ingest → clustering 可查;**长寿 Event Room + 跨 session A2A 仍未实现**(仍 ⏸ 见 §5) | Phase 1(基础交付),Phase 4 ⏸ |
| **契约 validation** | contract-v1.1.0 42 PASS / 22 XFAIL × 7 runtime(2026-04-18);contract-v1.2.0 升级(Phase 5.3) | `crates/eaasp-certifier/` E2E |

总结:EAASP 全栈工程基础(L0–L4)+ Hook/Data-flow/Session-control 三管道基础 + 契约双版本(v1.1.0 历史 / v1.2.0 当前)已全部就位且实证验证。

---

## 5. 显式未完工 — EAASP v2.0 平台演化剩余 GAP

> 明确未实现;**已 SHIPPED 清单见 §3.1**。以下事项不在 2026-07-17 关闭状态中,由下个 milestone 路线承担。

| 缺口 | 隶属 Phase | 关键待交付 capability | 已有部分 |
|------|-----------|------------------------|---------|
| **生产级 OPA 审批链** | Phase 3 | 完整审批链(5-stage approval chain per EVOLUTION_PATH §2.2 四元范式 I)+ OPA/Rego 后端 + Verifier + Sandbox Tiers | Policy DSL + risk classification + shadow/enforce mode(Phase 1 已交付);Hook 14 events 与 deny-always-wins 已就位 |
| **A2A / Event Room** | Phase 4 | A2A Router + ReviewSet + T0 Harness + 长寿 Event Room(Phase 4 多智能体协作)| Session 编排 + SSE fan-out(Phase 1 已交付) |
| **L5 Cowork UI** | Phase 5 | 4 卡界面(Event Room · Four Cards · Admin Console)+ IM bot + 回溯闭环 | `tools/eaasp-cli-v2/` L5 endpoint 模拟器(已交付);Web UI 未做 |
| **生态扩展 Marketplace/多租户/SDK** | Phase 6 | Marketplace + 多租户 + SDK | Grid 独立产品路径下 `grid-platform`(JWT + RBAC + quota)已就位;EAASP platform 路径下 Marketplace/SDK 未做 |

> 注:`docs/PROJECT_PRODUCT_OVERVIEW.md` §4 列出 Grid 组件的 1–3 个薄弱环节(web-platform/ 7.5/10 + grid-desktop 6.5/10 + web/ 测试覆盖),与本节 EAASP 平台缺口不重叠,两者共同构成 2026-07-17 的"剩余工作"全景。

---

## 6. 规范术语与源链接(Canonical terminology and source links)

### 6.1 关键术语(2026-07-17 locked)

| 术语 | 含义 |
|------|------|
| **engine vs data/integration 双轴** | ADR-V2-024 双轴模型;engine axis(`crates/grid-*` + `tools/eaasp-*` + `proto/` + `lang/*`)= user 主战场 ~60% + ~30%;data/integration axis = 0 实装在仓,只在 ADR 列出 |
| **`tools/eaasp-*` = 模拟器级参考实现** | EAASP v2.0 平台尚未完整实现前、按平台契约做的参考实现;**不存在 "上游 EAASP" 独立项目**(per EVOLUTION_PATH §一 P2 + ADR-V2-024 §1 + ADR-V2-029 §1)|
| **L1 runtime 数量 = 7(主力 1 + comparison 6)** | 主力 = `grid-runtime`;comparison 6 = `claude-code-runtime-python` + `nanobot-runtime-python` + `goose-runtime` + `pydantic-ai-runtime-python` + `claw-code-runtime` + `ccb-runtime-ts` |
| **L1 contract = 16 方法 / 运行时 17 RPC / 协议总 21 RPC** | 三者口径不同,务必区分(详见 §4 L0 Protocol 行 + 脚注):<br>①**L1 contract 16 方法** = 12 MUST + 4 Optional(v2.0 spec §8.5 锁定,Certifier 验 12 MUST)<br>②**runtime.proto 17 RPC** = 16 spec + 1 EmitEvent(OPTIONAL per ADR-V2-001 Accepted Phase 1)<br>③**协议总 21 RPC** = 17 runtime + 4 hook(hook.proto 独立 RPC 服务) |
| **contract-v1.1.0 = Phase 3 历史 sign-off** | 2026-04-18;42 PASS / 22 XFAIL × 7 runtime;deprecated by v1.2.0 后仍保留为历史版本 |
| **contract-v1.2.0 = 当前 latest** | 2026-05-20,Phase 5.3;ADR-V2-026(ExecutionMode)+ ADR-V2-027(OpenAI-compat Quirks) |
| **Grid Activation(A.0–A.8)SHIPPED 2026-06-17** | 8 phases,Repo rename `grid-sandbox` → `grid`,README publish |

### 6.2 源链接(EAASP 平台设计文档同仓 `docs/design/EAASP/`)

> EAASP 平台的设计文档同仓在 `docs/design/EAASP/`;**`EAASP-Design-Specification-v2.0.docx` 是规范权威**(per EVOLUTION_PATH §权威规范)。

| 文档 | 路径 | 作用 |
|------|------|------|
| 规范权威 | `docs/design/EAASP/EAASP-Design-Specification-v2.0.docx` | EAASP v2.0 设计规范(导出 markdown `/tmp/eaasp_v2_spec.md` 2944 行)|
| 演化路径 | `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md` | 5 层 + 3 管道 + 4 元范式 + 7 阶段演化路线 + 决策登记 |
| MVP 范围 | `docs/design/EAASP/EAASP_v2_0_MVP_SCOPE.md` | 圈 2 MVP 范围细化 |
| 产品形态蓝图 | `docs/design/EAASP/EAASP_v2_0_Platform_Product_Forms.docx` | — |
| 高管摘要 | `docs/design/EAASP/EAASP_v2_Executive_Overview.docx` + `.html` | 对外简版 |
| Phase 1 设计 | `docs/design/EAASP/PHASE1_EVENT_ENGINE_DESIGN.md` | — |
| Phase 3 设计(⏸) | `docs/design/EAASP/PHASE_3_DESIGN.md` | Phase 3 已交付部分 + 未实现 OPA 后端对照 |
| L1 适配指南 | `docs/design/EAASP/L1_RUNTIME_ADAPTATION_GUIDE.md` | L1 runtime adapter 实现指南 |
| L1 生态策略 | `docs/design/EAASP/L1_RUNTIME_STRATEGY.md` + 7 个 R1–R4 eval + `L1_RUNTIME_TIER_SPEC_*` | L1 生态策略 + 4 tier 横切 |
| Provider 矩阵 | `docs/design/EAASP/PROVIDER_CAPABILITY_MATRIX.md` | LLM provider matrix |
| E2E living spec | `docs/design/EAASP/E2E_VERIFICATION_GUIDE.md` | `scripts/eaasp-e2e.sh` + Makefile `v2-phase*-e2e` targets living spec |
| 跨 phase D-item SSOT | `docs/design/EAASP/DEFERRED_LEDGER.md` | 100% ✅ CLOSED |

### 6.3 战略 ADR

| ADR | 状态 | 路径 |
|-----|------|------|
| **ADR-V2-024** | Accepted 2026-04-28(supersedes V2-023)| `docs/design/EAASP/adrs/ADR-V2-024-phase4-product-scope-decision.md` |
| **ADR-V2-029** | Accepted 2026-05-22 | `docs/design/EAASP/adrs/ADR-V2-029-engine-data-integration-boundary.md` |
| ADR-V2-026 | Accepted 2026-05-20 | Phase 5.3 ExecutionMode |
| ADR-V2-027 | Accepted 2026-05-20 | Phase 5.3 OpenAI-compat Quirks |
| ADR-V2-017 | Accepted 2026-04-17(hermes frozen)| Phase 2.5 |
| ADR-V2-023 | Superseded by ADR-V2-024 | 旧双腿战略 ⚠️ "high-fidelity shadow" 措辞过时 |

### 6.4 同级 / 当前 SSOT

| 文件 | 角色 |
|------|------|
| **[docs/PROJECT_PRODUCT_OVERVIEW.md](../../PROJECT_PRODUCT_OVERVIEW.md)** | 持续维护 SSOT(本仓库项目级单一真相)|
| [`.planning/STATE.md`](../../../.planning/STATE.md) | GSD planning state(Activation SHIPPED 2026-06-17) |
| [`.planning/PROJECT.md`](../../../.planning/PROJECT.md) | GSD project reference |
| [`CLAUDE.md`](../../../CLAUDE.md) | agent instruction entrypoint |
| `README.md` / `README.zh.md` | 双语对外 README |

---

## 7. 验证日期与 commit 范围(Verification date and repository commit range)

- **快照生成日期**:2026-07-17
- **快照固定内容**:GRID/EAASP 产品状态五条结论 + Grid A.0–A.8 完成表(§2)+ EAASP Phase 0–4a 完成表(§3)+ L0–L4 已交付 capability(§4)+ 4 类显式 GAP(§5)+ 术语口径(§6.1)+ 源链接(§6.2-6.4)
- **commit 锚点**:
  - 验证锚点 SHA:`05c6d7db9cedd242a9beaf082a6ed0c59ae9ff8b`(主题 `wip: docs-sync-2026-07-17 paused at completed+verified`,Task 1 提交 `1de93a9f docs: record Grid and EAASP product status` 之前的 HEAD)
  - Task 1 提交 SHA:`1de93a9fc4edca5de600c8380281a22ca63b84b4`(本快照连同 SSOT 由该 commit 引入)
- **一致性验证(必需 token,见 §6.1)**:`'2026-06-17'`、`'A.8'`、`'7'`、`'6 comparison'`、`'contract-v1.1.0'`、`'contract-v1.2.0'`、`'模拟器级参考实现'`、`'A2A'`、`'Cowork'` 共 9 个 token 在 SSOT + 本快照两份文档都必须出现
- **未被本快照影响的文件**:`CLAUDE.md` / `README.md` / `README.zh.md` / `.planning/PROJECT.md` / `.planning/STATE.md` 在本次 docs sync 中单独处理(plan Task 2 + Task 3),未被本快照固化

> 一致性验证过的输出留存在 `/tmp/status-doc-task1-report.md`。

---

*Created: 2026-07-17 by docs-sync PR — 一次性固化快照,持续维护在 [docs/PROJECT_PRODUCT_OVERVIEW.md](../../PROJECT_PRODUCT_OVERVIEW.md)。*
