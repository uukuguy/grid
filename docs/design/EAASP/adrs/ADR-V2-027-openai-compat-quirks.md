---
id: ADR-V2-027
title: "OpenAI-Compat Provider Quirks Framework (F1/F2 split rule)"
type: contract
status: Accepted
date: 2026-05-20
accepted_at: 2026-05-20
phase: "Phase 5.3 — Contract Evolution"
author: "Jiangwen Su"
supersedes: []
superseded_by: null
deprecated_at: null
deprecated_reason: null
enforcement:
  level: contract-test
  trace:
    - "crates/grid-engine/tests/openai_quirks_test.rs"
    - "crates/grid-engine/src/providers/quirks.rs"
  review_checklist: null
affected_modules:
  - "crates/grid-engine/src/providers/openai.rs"
  - "crates/grid-engine/src/providers/deepseek.rs"
  - "crates/grid-engine/src/providers/quirks.rs"
  - "crates/grid-engine/src/providers/ling.rs"
  - "crates/grid-engine/src/providers/chain.rs"
related: [ADR-V2-025]
---

# ADR-V2-027 — OpenAI-Compat Provider Quirks Framework (F1/F2 split rule)

**Status:** Accepted (2026-05-20)
**Date:** 2026-05-20
**Phase:** Phase 5.3 — Contract Evolution
**Author:** Jiangwen Su
**Related:** ADR-V2-025 (L1 Runtime Contract Tier Strategy)

---

## Context / 背景

`crates/grid-engine/src/providers/openai.rs` 是 Grid 的 OpenAI-compat 主入口,
被 OpenAI / DeepSeek / Qwen / MiniMax / SiliconFlow / OpenRouter / ant-ling 等多家
"OpenAI-API-兼容" provider 共用。但所谓 "OpenAI-compat" 在生产环境从来不是干净的契约:

- **DeepSeek** 把 reasoning 内容塞到 `delta.reasoning_content`,标准 OpenAI 没有这个字段
- **Qwen / MiniMax / SiliconFlow** 用 `delta.thinking` 或 `delta.reasoning`
- **ant-ling Ling-2.6** 流末不发 `data: [DONE]` marker
- **ant-ling** 还在 continuation chunk 里把 `tool_calls[].id` 字段设为 `null`
- **deepseek-reasoner** 要求 history 回传 `reasoning_content` 字段 (HTTP 400 反例)

历史上这些"兼容性 quirk"被以 hot-fix 形式直接堆进 `openai.rs`:

- 2026-05-15 加了 `reasoning_content` / `thinking` / `reasoning` 三字段扫描 (line 834)
- 2026-05-19 加了 `Poll::Ready(None)` 无 `[DONE]` 兜底 flush (lines 981-1018)

两次 hot-fix 都解决了眼前的可用性问题, 但都引入新的"OpenAI 兼容性税":

1. **共用 parser 现在 "宽进严出 都不到位"** —— 三字段 reasoning 扫描在严格 OpenAI 也跑;
   `[DONE]` 缺失兜底在严格 OpenAI 也悄悄放行了断流。Strict-OpenAI assertion 强度被弱化。

2. **没有判断"什么 quirk 进 shared parser, 什么 quirk 拆 dedicated provider"的原则** ——
   `DeepseekProvider` 单独存在 (因为 deepseek-reasoner 的 history-requirement),
   但其他 quirk 全部堆在 `OpenAIProvider`, 边界模糊。新 provider 加入时只能继续堆。

3. **用户在 2026-05-19 反馈** ("你很爱用 fallback, 出问题找都没法找") 揭示了"silent
   tolerance" 让 debug 极其困难 —— 出问题时不知道是 LLM 错、provider 错、还是 parser 静默吞掉。

Phase 5.3 需要在 `OpenAIProvider` 引入 quirks 层时立一个清晰的判定原则,
以及一个落地原型来防止"ADR 写完原则、代码没跟" 的失败模式。

---

## Decision / 决策

### D1 — Quirks struct shape

引入 `crates/grid-engine/src/providers/quirks.rs` 里的 `Quirks` struct 持有 quirks
config, 通过 `OpenAIProvider::with_base_url_and_quirks(api_key, url, quirks)` 注入。
默认 `Quirks::default()` 全 false / `None` —— **strict OpenAI baseline**, 不偷偷宽容。

Phase 5.3 prototype 2 个字段:

```rust
pub struct Quirks {
    pub reasoning_content_field: ReasoningContentField,
    pub no_done_marker: bool,
}

pub enum ReasoningContentField {
    None,         // strict OpenAI (default)
    MultiField,   // ["reasoning_content", "thinking", "reasoning"] scan
}
```

未来加 quirk = 加 struct field, 不引入 trait objects / 动态 dispatch / 反射 —— 因为:

- 静态 struct field 在 grep / 代码审计可见
- 静态 struct field 在编译期 exhaustive (调用方必须想清楚是否需要)
- Trait object 倾向于"加 quirk 就是加 impl"的隐式增长

### D2 — F1 promotion rule (进入 shared Quirks)

**判定标准: ≥2 个真实 provider 出现同一 quirk → 进 `Quirks`**。

Phase 5.3 起始的 F1 quirks:

| 字段 | 共享 provider | 历史 hot-fix 位点 |
|---|---|---|
| `reasoning_content_field` | DeepSeek + Qwen + MiniMax + SiliconFlow | `openai.rs:834` 三字段扫描 |
| `no_done_marker` | ant-ling Ling-2.6 (单家, 但行为是"流末兜底", 是通用 shape) | `openai.rs:981-1018` Poll::Ready(None) flush |

注: `no_done_marker` 此刻仅 ant-ling 一家确认, 但 *behavior shape* ("流末没 [DONE] 时
怎么办") 是通用问题 —— 任何未来 OpenAI-compat provider 如果遇到同样行为, 直接 set
`no_done_marker: true` 复用 shared parser 即可。这个 "提前 F1 化" 是 D2 规则的合理弹性,
因为它避免了"出第二家时再翻 F2 → F1 的搬家成本"。

### D3 — F2 split rule (拆 dedicated provider)

**判定门槛: 行为差异 ≥3 处 OR 破坏 shared parser 的 common path 复杂度 →
拆 dedicated `<Vendor>Provider`** (per `crates/grid-engine/src/providers/deepseek.rs`
98 LOC precedent)。

Phase 5.3 起始的 F2 split:

| Vendor | Reason | Implementation |
|---|---|---|
| `DeepseekProvider` (existing) | `deepseek-reasoner` 要求 history 回传 `reasoning_content` 字段 (only deepseek-reasoner exhibits this) — single-provider quirk + breaks common-path multi-turn schema | `crates/grid-engine/src/providers/deepseek.rs` rejects `deepseek-reasoner*` with explicit error; `deepseek-chat` flows through `OpenAIProvider` with `reasoning_content_field: MultiField` |
| `LingProvider` (NEW Phase 5.3) | ant-ling continuation chunks set `tool_calls[].id = null` —— 只 ant-ling 一家, 且不进入 common-path 解析逻辑 | `crates/grid-engine/src/providers/ling.rs` 98 LOC mirror of deepseek.rs; sets `Quirks { no_done_marker: true, .. }` + inline `normalize_null_tool_ids` hook |

Promote F2 → F1 trigger: 第二家 provider 出现同一 quirk → struct field 加 5 LOC + 删除 dedicated provider 中的 inline 处理。

### D4 — Anti-silent-fallback (preserved)

Default `Quirks::default()` 全 false —— strict OpenAI 不静默宽容。`Poll::Ready(None)`
在 `no_done_marker: false` 路径明确 `return Poll::Ready(Some(Err("stream ended
without [DONE]")))`, 不悄悄合成 MessageStop。这是 Pitfall 5 (per RESEARCH §F2)
的核心 —— hot-fix 时偷偷把宽容默认开启, 是后续 debug 困难的根源。

---

## Implementation Record

Phase 5.3 Plan B (this plan) 落地了下列改动 (per task 顺序):

| Task | File | Change |
|---|---|---|
| 5.3-02-02 | `crates/grid-engine/src/providers/quirks.rs` | NEW —— `Quirks` struct (2 fields) + `ReasoningContentField` enum |
| 5.3-02-02 | `crates/grid-engine/src/providers/mod.rs` | NEW `pub mod quirks;` + factory dispatch arm for ling |
| 5.3-02-02 | `crates/grid-engine/tests/openai_quirks_test.rs` | NEW —— 5 unit tests covering default / ling profile / deepseek profile / Clone+Debug / enum default |
| 5.3-02-03 | `crates/grid-engine/src/providers/openai.rs` | ADD `quirks: Quirks` field on `OpenAIProvider` + `OpenAISseStream`; NEW `with_base_url_and_quirks` constructor; gate reasoning scan via `match self.quirks.reasoning_content_field` |
| 5.3-02-03 | `crates/grid-engine/src/providers/deepseek.rs` | Construct inner `OpenAIProvider` via `with_base_url_and_quirks` with `Quirks { reasoning_content_field: MultiField, .. }` |
| 5.3-02-04 | `crates/grid-engine/src/providers/openai.rs` | Gate `Poll::Ready(None)` flush via `this.quirks.no_done_marker`; default-false path returns `Err("stream ended without [DONE]")` |
| 5.3-02-05 | `crates/grid-engine/src/providers/ling.rs` | NEW —— `LingProvider` 98-LOC mirror of `deepseek.rs`; F1 sets `no_done_marker: true`; F2 inline `normalize_null_tool_ids` placeholder for future grid-types mutator |
| 5.3-02-05 | `crates/grid-engine/src/providers/chain.rs` | Add module-header doc block referencing all 4 vendor factories; add test `test_chain_dispatch_routes_to_ling` |

Regression tests run (per `--test-threads=1`):

- `cargo test -p grid-engine --test openai_quirks_test` → 5/5 PASS
- `cargo test -p grid-engine --lib providers::ling` → 4/4 PASS
- `cargo test -p grid-engine --lib providers::deepseek` → 3/3 PASS (no regression)
- `cargo test -p grid-engine --test d87_multi_step_workflow_regression` → 3/3 PASS
  (ExecutionMode behavior locked by commit `f1999fb` still holds — Task 4 changes
  don't affect harness control flow)

---

## Consequences / 后果

### Positive

- ✅ Strict-OpenAI default preserves assertion strength — broken streams now
  fail loudly with `stream ended without [DONE]` instead of silently flushing
- ✅ Quirks struct fields grep-discoverable —— code审计能直接看出"哪几个非
  标准行为已被纳入"
- ✅ F1 vs F2 边界清晰 —— ADR-V2-027 D2 + D3 给出一行判定规则, 不再每次新 quirk
  讨论一遍
- ✅ `DeepseekProvider` + `LingProvider` 两个 F2 precedent —— 后续 vendor split 有
  现成模板

### Negative

- ⚠️ 加新 quirk 需要改三处 (struct field + 调用方 wiring + ADR Implementation
  Record 记录) —— 比"直接 hard-code 在 openai.rs"略多步, 但这是设计预期的成本
- ⚠️ `LingProvider::normalize_null_tool_ids` 当前是 placeholder —— 等 grid_types
  暴露 `messages_mut()` 才能完整生效。Stream hang 已被 F1 `no_done_marker` 覆盖,
  所以 placeholder 不影响实际运行

### Risks (mitigated)

- 🚨 Vendor 把 `Quirks { no_done_marker: true, .. }` 用在不该用的 endpoint
  → 静默吞 broken stream。**缓解**: T-5.3-07 (threat register) 要求 yaml config
  validation 加固 (defer 到 Phase 5.4 NEW-F3 fail-fast cluster)
- 🚨 第三种 quirk 不知道走 F1 还是 F2 → ADR-V2-027 D2/D3 决策可能歧义。**缓解**:
  D2 用 "≥2 provider" 数量阈值, D3 用 "≥3 行为差异 OR 破坏 common-path" 复杂度
  阈值, 都是可数标准, 歧义点尽量少

---

## Migration / 迁移路径

Migration 已完成 —— Phase 5.3 Plan B 落地全部 7 个 task。后续 vendor 接入:

### 新 quirk 出现时的 checklist

1. 同一 quirk 已在 ≥2 个真实 provider 确认? → F1 路径: 加 `Quirks` 字段
2. 单家 provider, 但行为差异 ≥3 处? → F2 路径: 拆 `<Vendor>Provider`
3. 单家, 差异 ≤2 处? → 单家 dedicated provider 内 inline 处理, 不进 shared 也不拆
4. 任何 F1 字段, **default value MUST 保持 strict-OpenAI 语义** —— 不允许"为了
   该 vendor 方便, 把 default 翻过来"

### 测试要求

每个新 quirk 必须在 `crates/grid-engine/tests/openai_quirks_test.rs` 加一个 case
exercising default + activated 两条路径。

---

## Test / CI

- Unit: `cargo test -p grid-engine --test openai_quirks_test -- --test-threads=1`
- Integration regression: `cargo test -p grid-engine --lib providers -- --test-threads=1`
  (≥130 PASS 守护 wired quirks 没回归 shared parser)
- D87 regression: `cargo test -p grid-engine --test d87_multi_step_workflow_regression -- --test-threads=1`
  (3/3 PASS 守护 ExecutionMode behavior 没回归)

未来 quirk 添加 PR 必须 (per F3 enforcement):

1. 新增至少 1 个 test case 在 `openai_quirks_test.rs`
2. 在本 ADR Implementation Record 表加一行
3. 不允许在 PR 同时改 `Quirks::default()` 字段默认值 (除非另发 ADR)

---

## References / 参考

- Source feedback: 用户 2026-05-19 反馈 ("你很爱用 fallback, 出问题找都没法找")
- DEFERRED_LEDGER §NEW-F1 + §NEW-F2 (2026-05-19 引入)
- ADR-V2-026 (Phase 5.3 同 phase, Agent Loop Execution Mode supersedes V2-016)
- `crates/grid-engine/src/providers/quirks.rs` —— Phase 5.3 prototype
- `crates/grid-engine/src/providers/ling.rs` —— F2 split reference
- `crates/grid-engine/src/providers/deepseek.rs` —— F2 precedent (98 LOC)
- `crates/grid-engine/tests/openai_quirks_test.rs` —— enforcement trace test file
