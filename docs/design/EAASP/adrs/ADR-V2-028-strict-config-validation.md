---
id: ADR-V2-028
title: "Strict-by-default Configuration Validation (no silent env fallbacks)"
type: contract
status: Accepted
date: 2026-05-21
accepted_at: 2026-05-21
phase: "Phase 5.4 — Server Hardening"
author: "Jiangwen Su"
supersedes: []
superseded_by: null
deprecated_at: null
deprecated_reason: null
enforcement:
  level: contract-test
  trace:
    - "crates/grid-engine/src/providers/config.rs"
    - "crates/grid-runtime/src/config.rs"
  review_checklist: null
affected_modules:
  - "crates/grid-engine/src/providers/config.rs"
  - "crates/grid-runtime/src/config.rs"
  - "crates/grid-server/src/config.rs"
related: [ADR-V2-019, ADR-V2-026, ADR-V2-027]
---

# ADR-V2-028 — Strict-by-default Configuration Validation (no silent env fallbacks)

**Status:** Accepted (2026-05-21)
**Date:** 2026-05-21
**Phase:** Phase 5.4 — Server Hardening
**Author:** Jiangwen Su
**Related:** ADR-V2-019 (L1 Runtime Deployment Model), ADR-V2-026 (Agent Loop ExecutionMode), ADR-V2-027 (OpenAI-Compat Quirks)

---

## Context / 背景

Phase 5.3 末期 (2026-05-19) 出现的 NEW-F1..F4 级联事故暴露了一条系统性问题:
**Grid 各处 config 读取层在 env var 缺失时悄悄走 fallback,production code path 把
"漏配" 当作 "默认配置" 一并接受**。具体三条:

1. **`crates/grid-engine/src/providers/config.rs:19`** (NEW-F3) —
   ```rust
   let name = std::env::var("LLM_PROVIDER").unwrap_or_else(|_| "openai".to_string());
   ```
   LLM_PROVIDER 不存在时静默落回 "openai", 但 OPENAI_API_KEY 也可能不存在 →
   Default impl 仍然返回一个 `name="openai"` 的 ProviderConfig, 调用方拿到的是
   "看起来合法但跑不通" 的对象。用户最后看到的是模糊的 401 而不是 "config 缺失"。

2. **`dotenvy::dotenv()` 不会覆盖已经在进程环境的变量** + 一份 stale `.env`
   `RUST_LOG=octo_*` (Phase-BA `octo` → `grid` 改名前的遗留 key) → 进程的
   tracing-subscriber 用 `EnvFilter::try_from_default_env()` 成功 parse 了
   `octo_*`,但跟新的 `grid_*` 模块名一个都不匹配 → **subscriber 静默写 0 字节**。
   debug 一整个 session 才定位到。

3. **ant-ling Ling-2.6 流末不发 `data: [DONE]`** → OpenAIProvider 的 SSE
   parser 收到 `Poll::Ready(None)` 走兜底逻辑 flush pending tool_calls,
   然后 *悄悄退出*。"流断了但 stream end 信号没到" 在 strict OpenAI 里其实
   应该是 error 而不是 success。

三件事的共同模式:**production 入口的 config 读取层默认"宽进",出问题不报错就走默认值**,
但默认值通常不是用户想要的;由此产生的失败发生在 *后面* 的 LLM / parser / log 层,
症状跟 root cause 隔了几跳, debug 极其困难。

ADR-V2-027 (Quirks 框架) 已经在 LLM provider 层立了 strict-default + 显式 opt-in 的
原则。这条 ADR 把同样的原则推广到所有 production config 入口 —— **没有 fallback,
缺什么就报什么、写明哪个 env var 没设**。

---

## Decision / 决策

### D1 — Production code path 必须使用 Result-returning 严格 API,不可使用 Default

每个 config 类型必须暴露一个 `try_from_env()`(或等价命名)的 Result-returning API。
production 入口 (grid-server, grid-runtime, grid-cli 的 binary main) **必须** 调用
这个 API,缺失任何一个必需 env var 立刻 `Err(ConfigError::MissingEnv(<var_name>))` 退出。

`Default` impl **可以保留**, 用途仅限:
- serde reconstruction (反序列化 yaml/json config 到内存)
- 测试 fixture
- 文档示例

production code path 引用 `Default::default()` 视为违规。

### D2 — 错误必须指名具体 env var 名

ConfigError 至少必须有这两个枚举变体:

```rust
#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    #[error("required env var {0} is not set")]
    MissingEnv(&'static str),
    #[error("unknown LLM_PROVIDER value: {0}")]
    UnknownProvider(String),
}
```

不允许返回 generic `anyhow::Error` 或 string `"config invalid"`。用户报 bug 时
应该能直接复制错误信息里的 env var 名去 `.env` 里检查。

### D3 — Logging filter 必须显式包含 grid_* 模块作为兜底

`RUST_LOG` / `GRID_LOG` 配置层在 parse 完用户提供的 filter 之后,**必须** 再
显式加一条 `grid_*=info` 兜底, 防止 stale env var (e.g. `octo_*` 历史遗留)
让所有 grid 模块的 log 被静默丢弃。

实现位置: `crates/grid-cli/src/logging.rs` (Phase 5.4 follow-on) +
`crates/grid-server/src/config.rs::init_tracing()`。本 ADR 只立规, NEW-F3
Phase 5.4 task 03 已经在 `ProviderConfig` 上落地了 D1+D2;logging 兜底拆到
Phase 5.5 NEW-F4 follow-on (ADR scope 不扩到 logging, 待 NEW-F4 单独 ADR)。

### D4 — Strict-OpenAI / strict-config 走相同原则

ADR-V2-027 Quirks struct `default()` 全 false / None 是这条原则的 LLM 层实例化。
ADR-V2-028 在 config 层立同一规则: 默认应该是 **拒绝**, 而不是 **接受并降级**。
新 provider / 新 config 字段加入时, 默认值不应该是"看起来合理的兜底",
而应该是 `Option<T>::None` + production 入口显式 Err.

---

## Consequences / 影响

### 正面

- **Debug 时间下降**: env var 缺失从 "401 / 0-byte log / 流断没报错" 这种隔层
  症状, 变成进程一启动就喊出具体 var 名。
- **Audit 可追踪**: production binary 在 `.env`/shell 出问题时立刻显式 fail,
  而不是悄悄跑出一个不可复现的"看起来在工作"状态。
- **ADR-V2-027 + V2-028 形成"strict-by-default 原则"的双拼**: provider quirks 层
  (V2-027) + config 输入层 (V2-028) 共同消除了 silent tolerance 路径。
- **T-04 mitigation** (per Phase 5.4 plan threat_model): NEW-F3 silent
  fallback → wrong-provider exfiltration 路径切断。

### 负面 / 接受成本

- 凡是依赖 "环境变量缺失也能跑" 的脚本 (含 CI 半残环境) **必须** 显式 set 所需 var,
  否则启动失败。这是 by design — production / CI hygiene 现在被强制执行。
- Default impl 不能删除 (serde + tests 仍依赖), 所以代码 review 时仍可能误用;
  靠 ADR + code review + F3 trace lint 维持纪律。

### 不影响

- 现有测试用 `ProviderConfig::default()` 的路径不受影响 (Default impl 保留)。
- 用 `try_from_env()` 取代 `Default::default()` 的迁移 **不在本 ADR scope**;
  此 ADR 立规则, 后续 plan 渐进式 migrate 调用点。当下 Phase 5.4 task 03 只
  landing 了 API (`try_from_env`) + 测试 + 这条 ADR; production binaries 仍
  用 Default 直到 Phase 5.5 migration plan 执行。

---

## Implementation / 落地

Phase 5.4 Plan 02 Task 03 (commit landing in same plan):
- `crates/grid-engine/src/providers/config.rs` —
  + `ConfigError { MissingEnv, UnknownProvider }` enum
  + `ProviderConfig::try_from_env() -> Result<Self, ConfigError>`
  + 6 unit tests (5 plan-mandated + 1 deepseek smoke) all PASS
- `Default for ProviderConfig` impl 保留 (serde + test 路径), 但 doc
  string 警告 production 不要直接调。

后续 (Phase 5.5+):
- 把 `grid-runtime/src/config.rs::from_env()` 内部 `.expect(...)` 改成
  返回 ConfigError (目前 panic, 已经 strict, 但应该统一错误类型)。
- `grid-server/src/config.rs` 检视 silent fallbacks (e.g. 默认 port 3001
  这种 OK; 但 default API key fallback 不 OK)。
- D3 logging 兜底拆出独立 ADR (NEW-F4 follow-on)。

---

## Alternatives Considered / 备选

### Alt 1: 不立 ADR, 只 fix NEW-F3 一处

NEW-F3 是 silent fallback 的代表案例, 但同样模式还散在多处 (logging filter,
SSE [DONE] marker 兜底, …)。逐个 fix 不立规则, 下一次新增 config 又会
重复同样错误。立 ADR 比单点 fix 更稳。

### Alt 2: 完全删除 Default impl

理论上最干净。但实操中 serde 依赖 Default::default() (yaml 字段缺失时填默认),
测试 fixture 也都用 Default()。删除会引发大规模 ripple, 收益不抵成本。
保留 Default + 限制 production 不可使用, 是 pragmatic 的折中。

### Alt 3: 把规则直接写进 ADR-V2-027

V2-027 谈的是 *LLM provider* 层的 quirks. V2-028 谈的是 *config* 层的 strict
原则, 主体不同(前者讲 provider behavior compatibility, 后者讲 input
validation discipline)。混在一起会模糊 V2-027 的 scope。两条独立 ADR + 在
`related:` 互链是清晰做法。

---

## References / 参考

- 案例 1: `crates/grid-engine/src/providers/config.rs:19` (NEW-F3, 2026-05-19 trace)
- 案例 2: `crates/grid-cli` logging stale `RUST_LOG=octo_*` (2026-05-19 forensics, NEW-F4)
- ADR-V2-027 D1 (strict-default Quirks pattern, 2026-05-20)
- ADR-V2-019 (Deployment Model) — Phase 5.4 WATCH-04 同 plan 关闭 D142+D143, 共享 strict-config 精神
- Phase 5.4 Plan 02 Task 03 commit `9007935` — try_from_env 实现 + 6 tests
- Phase 5.4 threat model T-04 (silent fallback masking missing credentials)
