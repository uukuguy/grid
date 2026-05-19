---
id: ADR-V2-026
title: "Agent Loop Execution Mode (Conversational vs LongWorkflow)"
type: strategy
status: Accepted
date: 2026-05-20
accepted_at: 2026-05-20
phase: "Phase 5.3 — Contract Evolution"
author: "Jiangwen Su"
supersedes: [ADR-V2-016]
superseded_by: null
deprecated_at: null
deprecated_reason: null
enforcement:
  level: strategic
  trace:
    - "crates/grid-engine/tests/d87_multi_step_workflow_regression.rs"
  review_checklist: "docs/design/EAASP/adrs/ADR-V2-026-agent-loop-execution-mode.md"
affected_modules:
  - "crates/grid-engine/src/agent/loop_config.rs"
  - "crates/grid-engine/src/agent/harness.rs"
  - "crates/grid-runtime/"
  - "crates/grid-cli/"
  - "crates/grid-server/"
related: [ADR-V2-016, ADR-V2-024]
---

# ADR-V2-026 — Agent Loop Execution Mode (Conversational vs LongWorkflow)

**Status:** Accepted (2026-05-20)
**Date:** 2026-05-20
**Phase:** Phase 5.3 — Contract Evolution
**Author:** Jiangwen Su
**Supersedes:** ADR-V2-016 (Accepted 2026-04-14) — retroactive 合法化 + 加 mode gate
**Related:** ADR-V2-024 (双轴模型), ADR-V2-016 (Agent Loop 通用性原则)

---

## TL;DR

`grid-engine` 的 agent loop 在 D87 Fix 2 (commit `c0f98f9`) 之后,实际行为**已经超出 ADR-V2-016 决策范围**,变成了 "non-interactive 长工作流模式"。这套行为对 EAASP skill 执行是正确的,但在 grid-cli TUI / grid-server WS 这种 **REPL 对话场景**会导致 LLM 调完一次工具就被强制再调一次工具(`tool_choice=Required`)而无法回到自然语言回答。

本 ADR 为 `AgentLoopConfig` 加 `execution_mode: ExecutionMode { Conversational, LongWorkflow }` 显式标识,把 ADR-V2-016 的"漂移"在新 ADR 里 retroactively 合法化,并按调用方区分默认值。**不改变 EAASP 当前已通过的 Phase 2/2.5/3 E2E 行为**,只是把"REPL 误命中长工作流逻辑"这条路径堵上。

实现已落地于 commit `f1999fb` (2026-05-16);本 ADR 是 retroactive write-up。

---

## Context / 背景

### 1.1 现象

`2026-05-16` 在 grid-cli TUI 主会话用 `LLM_PROVIDER=deepseek` + `deepseek-chat` 问"查今天的国际要闻",观察到:

> "grid 会重复不断执行『查询今天的国际要闻』,感觉停不下来" — 用户反馈
>
> "感觉是执行了两遍" — 用户精确描述

实际行为:LLM 调一次 `web_search` 拿到结果 → 想用自然语言回答 → 被 harness 强制 `tool_choice=Required` 再调一次工具 → 循环到 `MAX_WORKFLOW_CONTINUATIONS=3` 停止。

### 1.2 根因 chain (依照 CLAUDE.md §2 chain-first diagnosis)

```
用户输入 → executor.rs:312 收到 UserMessage → 调 run_agent_loop
  → harness.rs main loop 第一轮:LLM 调 web_search
  → tool_result 注入 history
  → 第二轮:LLM 自然语言总结结果("最新新闻是...")
  → stop_reason = EndTurn, tool_uses.is_empty(), total_tool_calls > 0
  → harness.rs:1452 触发 D87 Fix 2:
      assert "LLM paused mid-workflow", 强制 tool_choice=Required
  → 第三轮:LLM 被迫再调 web_search(同样 query)
  → 又一轮自然语言总结
  → 第四轮再被强制 ...
  → workflow_continuation_count 达到 3,LoopGuard fallback,停
```

### 1.3 设计文档 vs 实现的脱节

| 决策来源 | 原文 | 实现 |
|---|---|---|
| `AGENT_LOOP_ROOT_CAUSE_ANALYSIS.md:92-99` | 明确区分 "REPL" 与 "non-interactive skill 执行" 两个模式 | **代码层面没区分** |
| `ADR-V2-016 §Decision` (line 70-84) | "**仅修一行判断逻辑**:`if tool_uses.is_empty() { exit }`" | **实际改了 ~150 LOC**,加了 D87 Fix 2 `tool_choice=Required` 续航 |
| `ADR-V2-016 §Decision/不做的事` (line 98-105) | "❌ 不注入 Continue user message" | D87 Fix 1 注入过,后被 Fix 2 替代为 `tool_choice` 续航 — 同样违反 spirit |
| `ADR-V2-016 §Affected Modules` (line 146-153) | 只列 `harness.rs:1169` 一行修改 + 一个 regression test | 实际改了 `harness.rs:70-90`(MAX 常量+注释)、`L474-477`(counter state)、`L1423-1560`(全部 Fix 2 逻辑)、`events.rs::WorkflowContinuation`、capability matrix、L1 skill metadata 集成等多处 |

**结论**:ADR-V2-016 在文字上是 "保守的退出条件简化",实际实现是 "激进的长工作流强制续航"。属于典型的 **快补丁 + 慢漂移** — 实现为达成 E2E 目标偷偷扩展授权,然后扩展出的逻辑在新场景反噬。

### 1.4 为什么之前没发现

| 场景 | 模型行为 | D87 Fix 2 触发? |
|---|---|---|
| EAASP threshold-calibration skill + grid-runtime + OpenAI/GPT | 调 1 个 tool 就停问"是否继续?" — **必须强制续航** | ✅ Fix 2 正中其位,E2E PASS |
| grid-cli TUI + claude-sonnet | 主动连续调工具,基本不触发 EndTurn-mid-workflow | ❌ Fix 2 几乎不激活,无感 |
| grid-cli TUI + deepseek-chat + web_search ← **2026-05-16 新场景** | 调一次工具就用自然语言回答 — **不该续航** | ✅ Fix 2 误激活 |

Phase 2 验收时 `claude-code-runtime + claude-sonnet` 主导,Phase 2.5+ EAASP 验收时 `grid-runtime + OpenAI` 主导,**REPL TUI × non-Claude 模型** 这个组合从来没真正跑过。直到 2026-05-16 加了 deepseek-chat 才暴露。

---

## Decision / 决策

### 2.1 新增枚举

```rust
// crates/grid-engine/src/agent/loop_config.rs

/// Execution mode for the agent loop.
///
/// Different callers (REPL TUI vs non-interactive skill harness) want
/// fundamentally different behavior when the LLM emits an EndTurn with
/// no tool_use mid-workflow. This enum makes that branch explicit
/// instead of relying on heuristics over `required_tools` presence.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ExecutionMode {
    /// REPL-style: every LLM EndTurn is a legitimate completion. The
    /// user (or another caller) will drive the next turn. Used by
    /// grid-cli TUI, grid-server WebSocket conversations, ad-hoc
    /// `grid ask` invocations.
    #[default]
    Conversational,

    /// Non-interactive skill execution: an EndTurn with no tool_use
    /// after tools were called is likely the LLM "asking the user to
    /// confirm" when there is no user. Harness should force continuation
    /// via `tool_choice=Required` (or `Specific(next_required_tool)` if
    /// the skill declared one). Used by grid-runtime when an EAASP skill
    /// is being executed against an L4 orchestrator.
    LongWorkflow,
}
```

### 2.2 `AgentLoopConfig` 新字段

```rust
pub struct AgentLoopConfig {
    // ... existing fields
    pub execution_mode: ExecutionMode,
}
```

Default = `Conversational` — **safer default that doesn't hijack tool_choice**.

### 2.3 `harness.rs:1452` 触发条件加 gate

```rust
if execution_mode == ExecutionMode::LongWorkflow      // ← NEW
    && stop_reason == StopReason::EndTurn
    && tool_uses.is_empty()
    && total_tool_calls > 0
    && workflow_continuation_count < MAX_WORKFLOW_CONTINUATIONS
    && config.tool_choice_supported
{
    // ... existing D87 Fix 2 logic unchanged
}
```

### 2.4 调用方默认值

| 调用方 | 默认 ExecutionMode | 备注 |
|---|---|---|
| `grid-cli` (TUI / `grid ask`) | `Conversational` | **修复本 RFC 的触发场景** |
| `grid-server` (HTTP/WS) | `Conversational` | 服务于 web 端,本质对话 |
| `grid-runtime` (EAASP gRPC) | `LongWorkflow` | **保持 Phase 2.5/3 已通过行为** |
| `grid-platform` (multi-tenant) | dormant — `Conversational` 暂定 | 跟随 Leg B activation 决策 |

### 2.5 Skill metadata 兼容

EAASP skill 通过 frontmatter 声明 `workflow.required_tools` 是 LongWorkflow 的最强信号。**保留 D87 Fix 2 内部的 "required_tools 全部满足则不续航" 逻辑** (`harness.rs:1480-1484`) — 这是合理的细粒度退出,不变。

但 **`required_tools.is_some()` 不再作为唯一开关** — 上层调用方设 `ExecutionMode::LongWorkflow` 才是。这避免了 "EAASP skill 漏写 required_tools 时静默回退到 Conversational" 这种 ADR-V2-016 漂移期遗留的暗坑。

### 2.6 No third "Auto" mode

显式两模式设计 — 没有第三种 "Auto" 推断模式。Caller MUST 显式声明 intent。这是 anti-silent-fallback 原则(per 用户反馈 2026-05-19: "你很爱用 fallback, 出问题找都没法找")。

---

## 不做的事 / Explicit Non-Goals

- ❌ **不删 D87 Fix 2 代码** — `LongWorkflow` 模式下的行为必须 byte-identical 于今天的实现,Phase 2/2.5/3 E2E 不能回归
- ❌ **不改 ADR-V2-016 实质内容** — 它已 Accepted,改文字相当于篡改历史。本 ADR supersede + 注脚说明 V2-016 实际授权范围
- ❌ **不改 skill frontmatter schema** — `workflow.required_tools` 语义不变
- ❌ **不改 `MAX_WORKFLOW_CONTINUATIONS=3` 常量** — LongWorkflow 模式行为不变
- ❌ **不动 LoopGuard / StuckDetector / max_rounds 三层防死锁** — 都正交,继续生效
- ❌ **不引入新的运行时检测启发** — 模式由调用方显式声明,不由 harness 推断

---

## Migration / 迁移路径

本 ADR 是 retroactive — 实现已落地于 commit `f1999fb` (2026-05-16)。Migration 步骤已完成:

### 4.1 代码层

1. `loop_config.rs`:加 `ExecutionMode` 枚举 + `execution_mode` 字段 (default `Conversational`) ✅
2. `harness.rs`:在 D87 Fix 2 触发条件最前面加 `execution_mode == LongWorkflow &&` ✅
3. `grid-cli/src/commands/run.rs` / `tui/mod.rs` / `ask.rs`:构造 `AgentLoopConfig` 时不设(走 default `Conversational`) ✅
4. `grid-server/src/handlers/*`:同上 ✅
5. `grid-runtime/src/service.rs`:构造时显式设 `ExecutionMode::LongWorkflow` ✅
6. `grid-engine/tests/d87_multi_step_workflow_regression.rs`:测试 fixture 加 `execution_mode: LongWorkflow`,确保 D87 行为锁定 ✅

### 4.2 测试矩阵

| 场景 | 模型 | 预期 | 状态 |
|---|---|---|---|
| TUI × deepseek-chat × web_search × Conversational | deepseek-chat | 调一次 web_search 后自然语言总结 → 退出,等下一个 user input | ✅ 修复后(commit f1999fb) |
| TUI × claude-sonnet × 多 tool 任务 × Conversational | claude-sonnet | 连续调多个 tool (Claude 主动性),完成后退出 | ✅ |
| EAASP skill × grid-runtime × LongWorkflow | OpenAI/GPT-4o | threshold-calibration ≥4 PRE_TOOL_USE 完整跑通 (D87 regression PASS) | ✅ `d87_multi_step_workflow_regression.rs` |

---

## Consequences / 后果

### Positive

- ✅ 解决 2026-05-16 报告的 deepseek-chat 在 TUI 反复执行问题
- ✅ 把 ADR-V2-016 漂移合法化 — 未来 ADR 审计不会再看到 "决策一行、实现 150 行" 的异常
- ✅ 显式 mode 比启发式 (`required_tools.is_some()`) 更可推理,符合 "surface assumptions" 原则
- ✅ 为未来可能的第三种模式 (例如 batch/cron) 留 enum extension 口子

### Negative

- ⚠️ `AgentLoopConfig` 多一个字段 — 序列化兼容需要 `#[serde(default)]`
- ⚠️ 3 个调用方入口都要改 — 涉及 grid-cli / grid-server / grid-runtime,但都是单行设置
- ⚠️ 默认值是 `Conversational` — 现有 grid-runtime 不显式设的话会回归;**必须在 grid-runtime 的 service 层显式设 LongWorkflow,这是 must-have**

### Risks (mitigated)

- 🚨 **migration regression**:grid-runtime 漏改 → EAASP E2E 回归。**缓解**:`d87_multi_step_workflow_regression.rs` 锁 LongWorkflow 行为 + grid-runtime `main.rs` 显式 `set_execution_mode(LongWorkflow)` 强制
- 🚨 **ExecutionMode 后续变成"什么都丢进去"的杂物袋** (autonomous mode、dual-mode、planning mode...):**缓解**:本 ADR 限定枚举只能扩展为新 variant,不允许加正交 bool flag

---

## Alternatives Considered

### Option A: 仅靠 `required_tools.is_some()` gate

**否决理由**:这是 D87 Fix 2 现状,已经被实证不够 — EAASP skill 漏写 required_tools 时静默回退,grid-cli TUI 永远不会有 required_tools 但用户偶尔想跑长任务也无路可走。

### Option B: harness 启发式检测 ("调用方是 TUI 还是 gRPC?")

**否决理由**:harness 不该感知调用栈 → 违反分层。Single responsibility 原则也排斥。

### Option C: 完全删除 D87 Fix 2,回到 ADR-V2-016 原始一行版本

**否决理由**:EAASP Phase 2.5/3 整个验收建立在 D87 Fix 2 之上,删除等于退回 ADR-V2-016 失败状态,违反 ADR-V2-024 双轴 "engine 接入面优先" 的工时投入决策。

### Option D: 上层在 prompt 里塞 "不要中途问用户" 指令

**否决理由**:ADR-V2-016 第 99-103 行明确否决了 system prompt 修正 — "prompt 不该承担 loop 控制责任"。本 ADR 同意。

---

## Implementation Note

实现已落地于 commit **`f1999fb`** (2026-05-16):

- `crates/grid-engine/src/agent/loop_config.rs`:`ExecutionMode` 枚举 + `execution_mode` 字段 (default `Conversational`) + `AgentLoopConfigBuilder::execution_mode(mode)` setter
- `crates/grid-engine/src/agent/harness.rs`:D87 Fix 2 触发条件加 `execution_mode == LongWorkflow` gate
- `crates/grid-runtime/src/main.rs`:显式 `set_execution_mode(LongWorkflow)` 保 EAASP E2E
- `crates/grid-engine/tests/d87_multi_step_workflow_regression.rs`:fixture 加 `execution_mode: LongWorkflow`

Regression test `crates/grid-engine/tests/d87_multi_step_workflow_regression.rs` 锁定 LongWorkflow 行为;任何回退该 mode gate 的 PR 会触发该测试失败。

---

## References / 参考

- Source RFC: `.planning/research/2026-05-16-agent-loop-execution-mode-rfc.md`
- Implementation commit: `f1999fb` (2026-05-16)
- ADR-V2-016 (Accepted 2026-04-14): superseded by this ADR — `superseded_by: ADR-V2-026` in V2-016 frontmatter
- ADR-V2-024 (Accepted 2026-04-28): 双轴 model framing for engine/data-integration leg priorities
- `crates/grid-engine/tests/d87_multi_step_workflow_regression.rs`:regression test that locks LongWorkflow behavior
- `docs/design/EAASP/AGENT_LOOP_ROOT_CAUSE_ANALYSIS.md`:original D87 root-cause analysis
