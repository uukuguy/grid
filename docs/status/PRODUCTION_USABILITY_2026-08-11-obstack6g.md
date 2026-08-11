# Production Usability — v3.15.6 6g:OBSTACK L1 emit 真实性验证

> **日期**: 2026-08-11
> **HEAD**: `d39db604` (main)
> **结论**: v3.15.6 6c 声称的 "L1 OTel 死代码激活" **只完成了一半**。6c.1(装 SDK)是真的;6c.2/6c.3(agent loop emit)挂在 Tier 1 runtime 永不经过的代码路径上,是新的死代码。本次(6g)把 emit 移到真实 agent loop 必经之路,并修掉一个更底层的 provider 生命周期缺陷。**修复后经真实 LLM 调用实测,6 条 metric series 中已验证 4 条真实产出数据。**

---

## 1. 起因

`/gsd-resume-work` 恢复后准备执行 6f(真跑 verify + tag v3.15.6)。tag 等于给 `OBSTACK_DESIGN.md` §0.1 的 "23/23 真闭环" 背书,因此先验证 6c 的 4 处 `⚠️→✅` 是否站得住。

---

## 2. 缺陷一:emit 挂错层(V315-WALK-01 未真正关闭)

### 静态证据

`record_tool` / `record_business_flow_outcome` 的调用点(6c.2/6c.3 之后):

| 位置 | 调用者 |
|---|---|
| `harness.rs:968` `GridHarness::on_tool_call` | 全仓唯一调用者 = `service.rs:363`(gRPC handler) |
| `harness.rs:979` `GridHarness::on_tool_result` | 全仓唯一调用者 = `service.rs:387` |
| `harness.rs:990` `GridHarness::on_stop` | 全仓唯一调用者 = `service.rs:405` |

这三个 RPC 是 **L4 平台给 Tier 2/3 runtime(无原生 hook)准备的回调通道**。Grid 是 Tier 1:

- `harness.rs:1124` `native_hooks: true`
- `contract.rs` `requires_hook_bridge: false`
- `contract.rs:114-118` 原文:*"Core events (PRE_TOOL_USE, POST_TOOL_USE, STOP) are already captured by the L4 platform interceptor"*

且 L4 手写代码中 **零处**调用这三个 RPC(仅 `_proto/` 下 protobuf 自动生成的 stub)。

真实 turn 的实际路径:

```
L4 → Send RPC → GridHarness::send (harness.rs:1063)
   → executor_handle.send(AgentMessage::UserMessage)   ← 直接进 grid-engine
   → 原生 AgentLoop 内部 fire PreToolUse/PostToolUse/Stop
   → AgentEvent 广播流 → map_events_to_chunks → ResponseChunk
```

全程不经过 `RuntimeContract` 的那三个方法。

### 运行时证据

启完整栈(5 服务 + grid-runtime),跑出含 tool call 的真实 timeline(14 事件,含 `POST_TOOL_USE_FAILURE`),`grid-runtime.log` 中 OTel 批次:

```json
{"resourceMetrics":{"resource":{...grid-runtime...},"scopeMetrics":[]}}
```

**exporter 活着,`scopeMetrics` 空** —— counter 一次未增。单独再建 session 发真实消息复验,结论相同。

---

## 3. 缺陷二:meter provider 被提前 drop(更底层,6c.1 也未真正生效)

排查缺陷一时发现:即便 counter 被正确调用也不会有输出。

`observability/mod.rs` 原代码在取走 instrument handle 后:

```rust
// Provider is consumed by the reader (held inside the
// PeriodicReader internal state — the SDK keeps it alive ...)
drop(provider);
```

注释的断言与 SDK 实现相反。`opentelemetry_sdk` 0.24.1 `metrics/meter_provider.rs:132`:

```rust
impl Drop for SdkMeterProviderInner {
    fn drop(&mut self) {
        if let Err(err) = self.shutdown() { ... }
    }
}
```

**drop 即 shutdown**:导出循环停止,所有 instrument 静默降为 no-op。

这解释了为什么日志里恰好只有 **1 个批次且为空**:进程启动时 flush 一次空快照,随后管道已死。而 6c.4/6c.5 的证据检查只 grep 日志文本行(`L1 OTel SDK installed` / `tool.total`),数出 `0` 却不判失败 —— **证据检查本身失效**。

### 修复

把 provider 存入 `OnceCell`,生命周期绑定到进程。同时把导出间隔做成 `EAASP_OTEL_INTERVAL_SECS`(便于验证时缩短窗口);按 ADR-V2-028,未设置/空值/非法/0 一律回落到生产默认 30s。

---

## 4. 修复方案(6g)

emit 移到 `map_events_to_chunks` —— 每个真实 turn 必经的 `AgentEvent` 流。**全部改动在 `grid-runtime` 内,未动 `grid-engine`,ADR-V2-023 P1(shared-core rule)保持,无需新 ADR。**

| AgentEvent | 产出 metric |
|---|---|
| `ToolStart` | `tool.total{tool, status="pre"}` |
| `ToolResult{success}` | `tool.total{tool, status="post"}` |
| `ToolResult{!success}` | `tool.total{status="error"}` + `errors.total{tool_failure}` |
| `IterationEnd` | `llm.total{model, status="ok"}` |
| `Completed` / `Done` | `flow.outcome{business_key, status="complete"}`(二者去重为 1 次) |
| `Error` | `errors.total{agent_error}` + `flow.outcome{status="error"}` |
| `EmergencyStopped` / `SecurityBlocked` | 对应 `errors.total` + `flow.outcome` |

**`in_flight` 用 Drop guard 而非成对 inc/dec**:客户端中途断连会直接 drop 流、不产生任何终止事件,成对调用会让 gauge 永久上漂。guard 同时把这种 turn 记为 `abandoned`(lag 路径记 `lagged`)—— 不计数的 turn 与从未发生的 turn 无法区分,而消除这种盲区正是本 milestone 的目的。

三个 hook 方法恢复为纯 no-op,**不重复 emit**:若将来 L4 真对 Grid session 调用它们,重复 emit 会导致同一 turn 双计。

---

## 5. 验证证据(真实 LLM,非 demo ingest)

环境:5 服务 + grid-runtime,`LLM_PROVIDER=deepseek`,`model=deepseek-v4-flash`,`EAASP_OTEL_INTERVAL_SECS=5`。经 gRPC `Send` 直连驱动真实 agent loop。

### 5.1 成功 turn(模型正常回答 "4",14 chunk 以 done 收尾)

```
total batches: 40          (修复前: 1)

l1.runtime.in_flight    {op=turn}                                          = 0
l1.runtime.llm.total    {model=deepseek-v4-flash, status=ok}               = 2
l1.runtime.flow.outcome {business_key=bc56d286-…, status=complete}         = 1
l1.runtime.flow.outcome {business_key=36ed4d39-…, status=complete}         = 1
```

- 2 个真实 turn → `llm.total = 2`
- 2 个独立 flow 各记 1 次 `complete` —— **`Completed`+`Done` 去重生效**
- **`in_flight` 归 0** —— Drop guard 生效,gauge 收支平衡

### 5.2 失败 turn(provider 401)

```
l1.runtime.flow.outcome {business_key=1049db49-…, status=error} = 1
l1.runtime.errors.total {kind=agent_error}                      = 1
l1.runtime.in_flight    {op=turn}                               = 0
```

错误路径按设计分类,gauge 同样归 0。

### 5.3 覆盖度诚实说明

**6 条 series 中已实测 4 条**:`llm.total` / `flow.outcome` / `errors.total` / `in_flight`。

`tool.total` 与 `requests.*` **本次未取得真实数据**:验证用的算术提问没有触发 tool call。其映射由单元测试覆盖(`classify_tool_start_counts_pre` / `classify_tool_result_*`),但**尚无端到端实证**。按本次教训,单测通过不等于线上会动 —— 该项应在 tag 前用一个真实触发 tool 的 skill 补验。

---

## 6. 测试与门禁

- `cargo test -p grid-runtime --lib` — **95/95 PASS**(新增 10)
- `cargo check --workspace` — **0 errors**(修好 `eaasp-goose-runtime` 缺 `business_key` 后;该错误自 6b.2b 起就存在于 main,6b.2b 却声称 "workspace check 0 errors")
- `make rbac-audit` — PASS(134 routes)
- `make v3.10-spec-audit` — PASS(38 rows)

新增测试把 `classify_event` 拆为纯函数后直接断言映射,**不需要进程级 meter provider**。这才是这类 bug 的真正修复:6c 之所以能带病发布,是因为 emit 是否发生**不可观测**,于是 `cargo check` 通过被当成了 metric 生效。

---

## 7. 未决事项

1. **`tool.total` / `requests.*` 端到端实证缺失**(见 §5.3)。
2. **OBSTACK_DESIGN §0.1 数字待复核** —— 6c.7 把 4 处 `⚠️→✅` 升为 23/23,其中至少 `V315-WALK-01` 当时不成立。本次修复后是否够格回到 ✅,应在 tag 前逐条重判。
3. **demo 脚本 9b/9c 证据检查失效** —— 改用 stdout exporter 后仍 grep 旧日志文本行,数到 0 也不失败。应改为解析 `resourceMetrics` JSON 并断言目标 series 非空。
4. **`.env` 影子变量**:shell 中导出的旧 `DEEPSEEK_API_KEY` 会盖住 `.env`(dotenvy 不覆盖已存在的环境变量),表现为 401。排查耗时不短,值得记住。
5. **L4 `/v1/sessions/{id}/message` 挂起** —— 240s 超时无响应,skill-registry 报 `threshold-calibration not found`。与本次改动无关,独立问题。
6. **tag v3.15.6 未打** —— 待 1 与 2 收敛后再议。

---

*本文档记录 2026-08-11 的实测结果。所有数字来自真实运行,未经修饰。*
