---
name: OBSTACK topic index
type: index
doc: OBSTACK_DESIGN.md
audience: maintainers, contributors
---

# OBSTACK 主题索引

> **OBSTACK** = EAASP 平台级 Observe / Trace / Evaluate / Optimize 跨 L0–L5 技术栈。
> 本文件是 **OBSTACK_DESIGN.md 的入口索引**，避免读者重读 500 行正文。OBSTACK_DESIGN.md
> 仍是 What / Why / Now / Not-yet 的唯一权威源；本文件只做"按主题跳转"。

## 权威文档

| 文档 | 章节定位 | 何时读 |
|---|---|---|
| [OBSTACK_DESIGN.md §0](OBSTACK_DESIGN.md) | Goal 实现 Status（4 维度 × 子项状态表） | 想知道"OBSTACK 现在到哪儿了" |
| [OBSTACK_DESIGN.md §1–§3](OBSTACK_DESIGN.md) | Context / Scope / Architecture（含业务流主线） | 想理解设计原理 |
| [OBSTACK_DESIGN.md §4](OBSTACK_DESIGN.md) | Integration Points + Component Inventory | 想改代码、查 file-level 索引 |
| [OBSTACK_DESIGN.md §4.4](OBSTACK_DESIGN.md) | Component Inventory（file × 状态） | 想精确知道每个文件 impl/partial/planned |
| [OBSTACK_DESIGN.md §5](OBSTACK_DESIGN.md) | Verification（单测 / 集测 / walkthrough） | 想跑测试 / 验证闭环 |
| [OBSTACK_DESIGN.md §6](OBSTACK_DESIGN.md) | Open Items | 想查未决 |
| [OBSTACK_DESIGN.md §7](OBSTACK_DESIGN.md) | 与 v3.11–v3.14 的关系 | 想看 OBSTACK 在 evolution path 哪一步 |
| [OBSTACK_DESIGN.md §8](OBSTACK_DESIGN.md) | 历史决策记录 | 想查当年为什么这样设计 |
| [OBSTACK_DESIGN.md §9](OBSTACK_DESIGN.md) | Changelog（权威文档自身的修订） | 想看 OBSTACK_DESIGN.md 本身改了什么 |

## 工作过程文档（carry OBSTACK 出处）

| 文档 | 职责 | 与 OBSTACK 关系 |
|---|---|---|
| `docs/status/JOURNAL.md` | append-only event log（何时发生） | 用 commit hash 反向链 OBSTACK_DESIGN.md §9 |
| `docs/status/RESUME-NEXT-SESSION.md` | session 接力 baton | Key References 表链 OBSTACK_DESIGN.md |
| `docs/status/CURRENT-STATE.md` | structural snapshot | 章节中"哪个 milestone"链 OBSTACK |
| `docs/status/PRODUCTION_USABILITY_2026-XX-XX.md` | 单次 live walkthrough 实证 | 引用 OBSTACK §5 / §6，**不复制**设计章节 |

## 关联 ADR（OBSTACK 不自创 ADR，但站在谁的肩上）

| ADR | 提供什么 | OBSTACK 引用点 |
|---|---|---|
| [ADR-V2-024](../adrs/ADR-V2-024-phase4-product-scope-decision.md) | 双轴模型（engine vs data/integration） | OBSTACK_DESIGN.md §1 / §4.3 |
| [ADR-V2-029](../adrs/ADR-V2-029-engine-data-integration-boundary.md) | crate-level 双轴 enforce | OBSTACK_DESIGN.md §4.2 兼容性 |
| [ADR-V2-034](../adrs/ADR-V2-034-opa-backend-deployment-topology.md) | OPA sidecar 拓扑 | OBSTACK_DESIGN.md §3.7 (Optimize 调度) |

## Goal 闭环当前快照（与 §0 同步 — 2026-08-09 v3.15.6a 文档诚实化）

| 维度 | 闭环率 (v3.15.6a) | 关键缺口 |
|---|---|---|
| **Observe** | 4/5 (80%) ⚠️ | L3 observability partial (1 record × 4 claimed); L1 OTel SDK dead code (init_observability 未接 main.rs) |
| **Trace** | 4/5 (80%) ⚠️ | L0 proto 13/21 RPC 挂载 (8 RPC 漏 business_key 字段) |
| **Evaluate** | 5/6 (83%) ⚠️ | `tests/business_flow/` 目录缺 — 4 集成测试 (timeline_e2e / interrupted / sse_subscribe / evaluator) 未写 |
| **Optimize** | 4/4 (100%) ✅ | 干净 — ab_router + alert_manager + resource_scheduler + flow_evaluator hint 全部 impl |
| **Verify** | 3/3 (100%) ✅ | dual-gate + live walkthrough + tag v3.15 (demo 走 ingest workaround) |

**总判定: 20/23 = 87%**;v3.15.6c 死代码激活 + 6b 测试补完后预期升 23/23。

**详细 commit / task 引用见 [OBSTACK_DESIGN.md §0.1](OBSTACK_DESIGN.md)** — v3.15.6 阶段任务清单见 `docs/superpowers/plans/2026-08-09-obstack-v3-15-6-completion.md`。

## 何时更新本文件

- OBSTACK_DESIGN.md 新增/删除顶级章节时
- 工作过程文档新增类别时
- OBSTACK 引入新 ADR 引用时

**不更新场景**：仅子章节内容调整、bug fix、单文件重排 — 这些只动 OBSTACK_DESIGN.md，本索引条目不变。
