---
id: ADR-V2-029
title: "Engine vs Data/Integration Boundary Contract (双轴模型 crate-level enforcement)"
type: strategy
status: Accepted
date: 2026-05-22
accepted_at: 2026-05-22
phase: "Phase 5.5 — Interface ADR + Milestone Close"
author: "Jiangwen Su"
supersedes: []
superseded_by: null
deprecated_at: null
deprecated_reason: null
enforcement:
  level: strategic
  # trace=[] intentional: strategic ADR, no concrete code to trace.
  # Decisions in this ADR shape product direction; code-level enforcement
  # is deferred to ADR-V2-030 (reserved, v3.2+).
  trace: []
  review_checklist: "docs/design/EAASP/adrs/ADR-V2-029-engine-data-integration-boundary.md"
affected_modules:
  - "crates/grid-engine/"
  - "crates/grid-runtime/"
  - "crates/grid-cli/"
  - "crates/grid-server/"
  - "crates/grid-types/"
  - "crates/grid-sandbox/"
  - "crates/grid-hook-bridge/"
  - "crates/grid-eval/"
  - "crates/grid-platform/"
  - "crates/grid-desktop/"
  - "tools/eaasp-l2-memory-engine/"
  - "tools/eaasp-l3-governance/"
  - "tools/eaasp-l4-orchestration/"
  - "tools/eaasp-skill-registry/"
  - "tools/eaasp-mcp-orchestrator/"
  - "tools/eaasp-cli-v2/"
  - "tools/eaasp-certifier/"
  - "proto/eaasp/runtime/v2/"
related:
  - ADR-V2-023
  - ADR-V2-024
  - ADR-V2-025
---

# ADR-V2-029 — Engine vs Data/Integration Boundary Contract (双轴模型 crate-level enforcement)

**Status:** Accepted
**Date:** 2026-05-22
**Accepted At:** 2026-05-22
**Phase:** Phase 5.5 — Interface ADR + Milestone Close
**Author:** Jiangwen Su
**Related:** ADR-V2-023 (双腿战略 superseded), ADR-V2-024 (Phase 4 双轴模型 — engine vs data/integration), ADR-V2-025 (L1 runtime 契约执行强度差异化)

---

## Context / 背景

ADR-V2-024 (Accepted 2026-04-28, supersedes V2-023) 落盘 **双轴模型 (engine vs data/integration)** 作为 Phase 4 product scope 主框架, audit §5 双轴 substance 与 audit §4.2 三选一推荐 (两腿都推进) co-equal 并存。但 V2-024 §1 双轴 substance 在文字描述层面给出"engine = 可复用的核心组件 / data/integration = 场景特定的横切关注", 并未在 crate / tool / proto 层给出明确清单, 也未约束未来新增 crate 在两轴上的归属判定。

Phase 4.1 PRE-AUDIT-NOTES §C.1 落盘 **5+3 字段切分** (engine 内置 5 项 + 厂商写 3 项) 作为 vertical 字段层的具体实例化, 但同样未推到 module-level boundary 描述。

Phase 5.0 → 5.4 (v3.1 milestone) 期间, 多次出现的现象佐证了 module-level boundary 文档化的必要性:

1. **同仓孵化期边界模糊**: EAASP L2/L3/L4 与 grid-* crates 都在 `grid-sandbox` 单仓内迭代, 多次 PR 审查中浮现"这个 fix 应该在 engine 还是 data/integration 侧"的争议 (例: NEW-L1 HNSW disk leak — Python L2 code, engine 侧 still; NEW-F1..F4 cascade — TUI / logging / config, engine 侧)。
2. **未来 V2-030/V2-031 ADR 候选锁定不下来**: 一旦 user 想推进 code-level boundary enforcement (Cargo dep-graph rule / import lint / F4 module-overlap reconcile) 或 data/integration 适配器 trait + gRPC service skeleton, 缺少一份 "现状 engine 包含 X+Y+Z, data/integration 包含 A+B+C" 的文档化清单作为 baseline。
3. **PROJECT.md / ROADMAP.md / REQUIREMENTS.md 三处对 "engine" / "数据集成" 措辞不一致** — 没有 single source of truth 让 future agents 反复 校验。

WATCH-06 / NEW-E2 (Phase 4a project review 发现的 enforcement.trace gap 修复, 33 WARN baseline) 与 INTERFACE-01 (Phase 5.5 scope item) 是同源问题的两个分支: WATCH-06 修 F3 trace 形式层, INTERFACE-01 写 boundary substance 层。本 ADR 处理 INTERFACE-01 — V2-030/V2-031 reserved 等到 v3.2+ 实施 code-level 配套。

---

## Decision / 决策

**采纳 crate-level documentation-only boundary**, 不在本 ADR 引入 code-level 强制 (Cargo dep-graph rule / import lint / F4 module-overlap 自动 reconcile 等 — 全部 reserved 给 ADR-V2-030 v3.2+)。本 ADR 仅锁定 **现状 engine 与 data/integration 各自包含哪些 crates / tools / proto / hook-out 接入面**, 提供 future ADR 与 PR 审查时的 single source of truth。

### §1. 双轴模型 crate-level 切分

| 轴向 | Engine (user 60% + 30% 工时主战场) | Data/Integration (他人 10%, 客户/厂商接手) |
|---|---|---|
| **Rust crates (`crates/`)** | `crates/grid-engine/` (agent loop / context / memory / MCP / providers / tools / skills / security / audit / metrics) <br/> `crates/grid-runtime/` (L1 gRPC runtime adapter) <br/> `crates/grid-cli/` (CLI binary `grid` — engine 接入面) <br/> `crates/grid-server/` (single-user workbench HTTP/WS) <br/> `crates/grid-types/` (zero-dep type defs) <br/> `crates/grid-sandbox/` (sandbox runtime adapters; native subprocess / wasm / docker) <br/> `crates/grid-hook-bridge/` (hook event bridge Rust ↔ L2/L3) <br/> `crates/grid-eval/` (evaluation harness — suites / scorers / benchmarks) <br/> `crates/grid-platform/` (multi-tenant platform server — dormant per ADR-V2-024) <br/> `crates/grid-desktop/` (Tauri desktop — dormant) <br/> `crates/eaasp-goose-runtime/` + `crates/eaasp-claw-code-runtime/` + `crates/eaasp-scoped-hook-mcp/` (L1 adapter comparison runtimes) | (无 — 所有 Rust crates 均为 engine 侧) |
| **EAASP tools (`tools/`)** | `tools/eaasp-l2-memory-engine/` (FTS5 + HNSW + time-decay memory engine) <br/> `tools/eaasp-l3-governance/` (policy DSL + risk classification) <br/> `tools/eaasp-l4-orchestration/` (session lifecycle + SSE streaming + governance gates) <br/> `tools/eaasp-skill-registry/` (skill manifest storage + MCP tool bridge) <br/> `tools/eaasp-mcp-orchestrator/` (MCP server lifecycle) <br/> `tools/eaasp-cli-v2/` (end-user EAASP CLI) <br/> `tools/eaasp-certifier/` (contract certification harness) | (无 — 所有 EAASP tools/* 均为 engine 侧, 蓝图 hook-out 见下) |
| **Protocol (`proto/`)** | `proto/eaasp/runtime/v2/common.proto` <br/> `proto/eaasp/runtime/v2/runtime.proto` <br/> `proto/eaasp/runtime/v2/hook.proto` | (无 — proto 全部 engine; data/integration 走 hook-out + skill 接入面, 不动 proto) |
| **Comparison runtimes (`lang/`)** | `lang/claude-code-runtime-python/` <br/> `lang/nanobot-runtime-python/` <br/> `lang/pydantic-ai-runtime-python/` <br/> `lang/ccb-runtime-ts/` <br/> `lang/hermes-runtime-python/` (frozen per ADR-V2-017) | (无 — 比较 runtime 全部 engine; 它们是契约的活体测试 per V2-017) |
| **Data/Integration categories (he人接手)** | (无 — 不在 engine 侧) | **客户数据 ingestion 适配器** (customer corpus / 工作流数据 / vector store 接入) <br/> **SSO 契约** (OAuth / SAML / OIDC 接入) <br/> **第三方 API gateway** (政府 / 厂商 系统集成) <br/> **WORM 存储 接入** (合规归档接入面) <br/> **信创 LLM 适配** (通义 / 星火 / 文心 等国产模型接入, 走 OpenAI-compat + Quirks per ADR-V2-027) <br/> **Hook-out 接入面** (per ADR-V2-006 envelope, PreToolUse / PostToolUse / Stop hook 接入位 — vendor skill / Path D) <br/> **业务 KPI / SCADA / 行业合规表** (per Phase 4.1 5+3 字段切分: 厂商写 3 项) |

### §2. 边界模式 (Boundary Mode)

本 ADR 采纳 **documentation-only crate boundary**:

- **Engine 侧**: user 主战场, 全部 crates 与 tools 均按 §1 表归属 engine 侧, 任何归属调整需新 ADR。
- **Data/Integration 侧**: **本 repo 内不存在 data/integration 实装 crate** — 该类适配器/契约在 production 由客户/厂商在各自 repo 实装, 通过 ADR-V2-006 hook envelope + EAASP skill registry + V2-027 OpenAI-compat 适配位接入。本 ADR 仅枚举 data/integration 的 **categories** (类目), 不枚举具体实装。
- **Code-level enforcement 不在本 ADR 范围** — engineer 自我约束 + PR review 把关 + ADR-V2-030 (reserved) 落实自动化。

### §3. Future-proofing rules (新增 crate / tool 归属判定)

新增 `crates/<name>/` 或 `tools/<name>/` 时, 按以下规则判定归属:

1. **若新组件复用 engine 核心 (依赖 grid-engine / grid-types / grid-runtime / grid-sandbox)** → engine 侧, 加入 §1 表 + 在新组件的 README / CLAUDE.md 注明 ADR-V2-029 §1 engine 侧归属。
2. **若新组件是 customer/vendor 特定的接入适配器 (单一客户专用 / 单一厂商 LLM / 单一合规框架)** → data/integration 侧, 按 §1 表"Data/Integration categories" 列出类目; 该实装不应进入 `grid-sandbox` 主 repo, 应在 customer/vendor 各自 repo 内实装, 通过 hook envelope / skill registry / OpenAI-compat 接入面 与 engine 侧对接。
3. **若边界模糊 (e.g., 同一组件既包含 engine 抽象又含 customer 特化)** → 拆为两个 component: engine 侧抽象进 `tools/eaasp-*` 或 `crates/grid-*`, data/integration 实装走 customer repo。**禁止在 engine 侧 crates 内 hard-code customer-specific 逻辑。**

---

## Rationale / 决策理由

为何 crate-level documentation-only 足够 v3.1, 不立刻引入 code-level enforcement:

1. **同仓孵化期内 engine 侧组件高速演化**: Phase 5.0 → 5.4 引入 / 重构了 ExecutionMode (V2-026) / OpenAI Quirks (V2-027) / Strict Config (V2-028) 等多个 cross-crate 改动, 任何 code-level boundary enforcement (Cargo dep-graph rule / import lint) 会反复触发"白名单加一条"的低价值 ADR, 拖慢 engine 演化速度。
2. **Data/integration 实装尚未启动 (本 repo 内为 0)**: §1 表中 data/integration 侧为空 — 没有实际"违规"的 crate 需要被 enforcement 检出。先有违规, 再有 enforcement, 而不是先 enforcement 后限制 future PR。
3. **V2-024 双轴 substance + 本 ADR §1 表 + ADR-V2-006 hook envelope + ADR-V2-027 OpenAI Quirks + ADR-V2-019 deployment model 五位一体, 已经文档化了 engine ↔ data/integration 间所有 已知 接入面** — code-level enforcement 在 v3.2+ 单独 ADR (V2-030) 落地不会丢失任何已经文档化的信息。
4. **F4 module-overlap reconcile 是独立工作**: F4 (`adr_conflict_detect.py`) 已经在 audit 链路上, 检测 Accepted ADR 之间 `affected_modules` 重叠; 本 ADR 的 17 个 affected_modules 项不会与现有 contract ADRs (V2-001/006/018/020/027/028) 的 affected_modules 产生 F4 conflict, 因为它们各自描述 同一 crate 在不同维度上的 责任, 不矛盾。

---

## Consequences / 后果

### Positive

- **Single source of truth**: 任何 future PR review / ADR 起草 / 新组件归属判定都可以引用本 ADR §1 表, 不再依赖散落在 PROJECT.md / ROADMAP.md / V2-024 §1 substance 文字描述间的隐式 mapping。
- **未来 ADR (V2-030 / V2-031) 自然继承本 carve**: V2-030 (code-level enforcement) 可以直接基于 §1 表生成 Cargo dep-graph rule / import lint 规则; V2-031 (Rust trait + gRPC service skeleton) 可以直接基于 §1 "Data/Integration categories" 表生成 trait 形状。
- **新增 crate / tool 归属规则 (§3) 让 future agents 自助判定**, 不需反复 ping user。
- **WATCH-06 / NEW-E2 配套**: 本 ADR 的 boundary substance 与 NEW-E2 F3 trace 形式 fix 结合, 让 ADR landscape 的 "形式 + substance" 在 v3.1 milestone 同步收敛。

### Negative

- **无 immediate code-level 保护**: engineers 需自我约束, 直到 V2-030 v3.2+ 落地。本 ADR 完全依赖 PR review 把关; 一旦失守, 不会有自动告警。
- **§1 表是 snapshot, 需 future ADR maintenance**: 新增 crate / tool 必须按 §3 规则 + 新 ADR 修订 §1 表, 否则 §1 会 drift, 失去 single source of truth 价值。
- **Data/integration 侧"为空"的现状可能让人误以为本 ADR 提前**: 实际是 future-proofing — 等 customer/vendor 接入实装出现时, §1 表已经有位置接收, 而不是临时补 ADR。

### Risks

- **§3 边界判定规则可能在边缘 case 失效**: 比如"一个组件既包含 engine 抽象又含 customer 特化"的拆分, 本 ADR §3.3 给出"必须拆为两个 component"原则, 但具体怎么拆需 case-by-case; 风险是 cleanup 工作量大于预期。Mitigation: V2-030 (v3.2+) 落地后, Cargo dep-graph rule 会强制 detect "engine crate 依赖 customer repo" 的违规, 倒逼拆分。
- **冻结 vs dormant vs active 状态变化触发本 ADR 修订**: 例如 grid-platform / grid-desktop 由 dormant 转 active, 或新增 EAASP tools/ component。Mitigation: ADR governance plugin 的 quarterly audit 已经覆盖此类 staleness 检测; review-checklist 字段指本 ADR 自身。

---

## Affected Modules / 影响范围

见 frontmatter `affected_modules` 列表 — 17 项, 覆盖 §1 表 engine 侧 全部 crates + tools + proto。Data/integration 侧 categories 不进入 `affected_modules` (因为本 repo 内无实装)。

---

## Alternatives Considered / 候选方案

### Option A: ADR-only crate-level documentation (本 ADR 采纳)

**Pros**: 落盘速度快; engineer 自我约束 + PR review 已经覆盖; future ADR (V2-030 / V2-031) 有 base 可继承。
**Cons**: 无 immediate code-level 保护; §1 表需 future ADR maintenance。
**Verdict**: ✅ Accepted — Phase 5.5 scope 适配, 不引入新的 enforcement 机制以免拖慢 engine 演化。

### Option B: ADR + 立刻 Cargo dep-graph rule (rejected)

**Pros**: code-level 保护立刻 active; engineer 不需自我约束。
**Cons**: Cargo dep-graph rule 配置高 (`cargo-deny` 集成 + 白名单)、维护成本不可忽略; 同仓孵化期内 engine 侧组件高速演化, 每个 PR 都可能触发 dep-graph rule 修订, 反而拖慢; Data/integration 侧本 repo 内为空, "保护"的对象不存在。
**Verdict**: ❌ Rejected — 推到 ADR-V2-030 v3.2+ 落地。

### Option C: ADR + Rust trait + gRPC service skeleton (rejected)

**Pros**: data/integration 适配器 trait + service skeleton 立刻可用; customer/vendor 可以基于 skeleton 实装。
**Cons**: customer/vendor 实装尚未启动, trait 形状未经实战验证; 落盘的 skeleton 容易 drift, 失去价值; 与 ADR-V2-006 hook envelope + V2-027 Quirks 形成 三重接入面 (hook envelope + Quirks + trait), 增加 mental model 复杂度。
**Verdict**: ❌ Rejected — 推到 ADR-V2-031 v3.2+ 落地, 等第一个 customer/vendor 实装案例出现后再固化 trait 形状。

---

## References / 参考

- **ADR-V2-024 §1 双轴模型 substance** — 本 ADR §1 表的 substance 源头
- **ADR-V2-023 §P1 shared-core rule** — 共享核心 crate 改动必须 work for 两腿, 本 ADR §3.2 拆分原则继承此原则
- **Phase 4.1 PRE-AUDIT-NOTES §C.1 5+3 字段切分** — engine 内置 5 项 + 厂商写 3 项, 本 ADR §1 表 "Data/Integration categories" 中"业务 KPI / SCADA / 行业合规表"对应厂商写 3 项
- **ADR-V2-025 §四档** — L1 runtime 契约执行强度差异化 (主力 / 样板 / 参考 / 冻结); 本 ADR §1 表 "Comparison runtimes" 行隐含此分档, 但本 ADR 不重述
- **ADR-V2-006 §2 hook envelope** — data/integration "hook-out 接入面" 走此契约
- **ADR-V2-027 OpenAI-compat Quirks** — data/integration "信创 LLM 适配" 走此适配位
- **ADR-V2-019 L1 runtime deployment model** — engine 侧 grid-runtime / runtime adapters 部署语义

### Reserved future ADRs

- **ADR-V2-030 (reserved, v3.2+)** — Code-level boundary enforcement: Cargo dep-graph rule (`cargo-deny` 集成) + F4 module-overlap reconcile 自动化 + import-block lint。落地条件: 出现第一个 data/integration 实装 crate (无论在本 repo 还是 customer repo), 或 §1 表 drift 频率超出 ADR governance quarterly review 可接受范围。
- **ADR-V2-031 (reserved, v3.2+)** — Rust trait + gRPC service skeleton for data/integration hook-out sites: `trait DataIntegrationAdapter` 定义 + gRPC service stub 在 `proto/eaasp/data_integration/v1/`。落地条件: 第一个 customer/vendor 实装案例上线, trait 形状经过实战验证。

---

*Phase 5.5 — INTERFACE-01 closure; pairs with NEW-E2 / WATCH-06 F3 trace sweep (Task 01.A3).*
