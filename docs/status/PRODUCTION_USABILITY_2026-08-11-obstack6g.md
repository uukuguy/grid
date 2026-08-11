# Production Usability — v3.15.6 6g + 6h:OBSTACK L1 emit 真实性验证

> **日期**: 2026-08-11 → 2026-08-12
> **HEAD**: `09c82d35` (main)
> **结论(6g)**: v3.15.6 6c 声称的 "L1 OTel 死代码激活" **只完成了一半**。6c.1(装 SDK)是真的;6c.2/6c.3(agent loop emit)挂在 Tier 1 runtime 永不经过的代码路径上,是新的死代码。6g 把 emit 移到真实 agent loop 必经之路,并修掉一个更底层的 provider 生命周期缺陷 —— 实测 6 条 series 中 4 条出数。
> **结论(6h)**: 补齐 `requests.*`(该 helper **自落地起从未被调用过**,顺带修掉一个会让 gauge 变负的潜伏 bug + 一个 metric-cardinality DoS),并改造 demo 脚本 —— 它此前有 4 个独立缺陷,叠加后能在**什么都没证明**的情况下 exit 0。**6/6 series 全部真跑验证,且关键检查有负控证明它能失败。**
>
> **§1–§7 = 6g(2026-08-11);§8 = 6h(2026-08-12)。**

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

## 7 未决事项(6g 时点;§8 记录 6h 的收敛结果)

1. **`tool.total` / `requests.*` 端到端实证缺失**(见 §5.3)。→ **6h 已闭环**
2. **OBSTACK_DESIGN §0.1 数字待复核**。→ **6h 已回到 23/23,且带负控**
3. **demo 脚本 9b/9c 证据检查失效**。→ **6h 已改为 JSON 断言 + 负控**
4. **`.env` 影子变量**:shell 中导出的旧 `DEEPSEEK_API_KEY` 会盖住 `.env`(dotenvy 不覆盖已存在的环境变量),表现为 401。排查耗时不短,值得记住。→ 已写入 demo 脚本头部注释
5. **L4 `/v1/sessions/{id}/message` 挂起** —— 240s 超时无响应,skill-registry 报 `threshold-calibration not found`。→ **6h 定位为 root cause 之一**:per-run registry 是空目录;已加自动 seed
6. **tag v3.15.6 未打** —— 待 1 与 2 收敛后再议。→ **6h 后两项前置均已满足**

## 8. 6h 续篇(2026-08-12)— 补齐 `requests.*` 与 demo 改造

6g 留下两项未决(原 §5.3 + §7.1/7.3),6h 全部收敛。

### 8.1 `requests.*` 从未被调用过

排查发现 `record_request` / `record_request_duration` / `time_block` 三个 helper **自 OTel 模块落地起就没有任何生产调用点** —— 无论跑多少流量,`l1.runtime.requests.total` 恒为 0。

**修复** (`b1d3585e`):以 tower layer 接在 tonic 服务的 HTTP 层,19 个 RPC 一处统一计数。不逐个包 handler,是因为那要在每个新方法、每条 early-return 上重复审计。

**同时修掉一个潜伏 bug**:`TimeBlock::record_request` 按值接收 `self`、显式调 `in_flight_dec`,函数结束时 `self` 析构又触发 `Drop` **再减一次** —— 首次真正使用就会让 gauge 变负。因为此前无人调用,这个 bug 一直没暴露。

**两个诚实标注的语义边界**(写进模块文档,不含糊):
- server-streaming 的 `Send`,HTTP 响应在 headers 就绪时即返回,故 `requests.duration{op="Send"}` 是 **time-to-first-response**,不是整轮时长;整轮由 `flow.outcome` + `in_flight{op="turn"}` 负责。
- gRPC 应用层错误走 `grpc-status` 而非 HTTP status;streaming 的最终状态在 trailers,本 layer 不等待。

### 8.2 安全:metric-cardinality DoS(自动审查发现)

初版 `op` label 直接取 URL 路径尾段。**任何能连到 gRPC 端口的对端都可以用 `/x/aaa`、`/x/aab`… 无限制地制造新 time series**,meter 会为每个不同值永久保留一条,构成免认证的内存耗尽路径。

更讽刺的是:模块文档当时**已经写着**"unrecognised paths 记为 unknown",而代码只在空串时才这么做 —— 正是本 milestone 一路在批判的"文档说一套代码做一套",这次出现在我自己的 commit 里。

**修复** (`9022b3e9`):`op_label` 对照 proto 声明的 21 个 RPC 做 allowlist,其余一律 `unknown`,返回 `&'static str`,label 集上界 = 22。

**实测**:对运行中的进程发 5 条恶意路径(含目录穿越、500 字符段),`requests.total` 的 label 集保持 `{Initialize, Send}` 不变。

### 8.3 demo 脚本:能在什么都没证明的情况下 exit 0

逐项查下来,v3.15.5 版 demo 有 **4 个独立缺陷**,叠加起来让它成为一个"永远成功"的仪式:

| # | 缺陷 | 后果 |
|---|---|---|
| 1 | per-run skill-registry 是空目录,L4 handshake 报 `skill-registry:not_found` | session-create 仍返 **200**(降级),失败完全不可见 |
| 2 | LLM 步 30s 超时 —— 短于一次 reasoning turn;且失败**不致命** | 每次都静默超时,然后继续往下跑 |
| 3 | 5 个事件手工 POST `/v1/events/ingest` | timeline 看着很健康,**恰恰在第 3 步已死的时候** |
| 4 | Observe 检查 grep `tool.total` 等日志文本 —— 6c.1 换 stdout exporter 后这些文本不再出现;且只打印计数**从不失败** | 在管道彻底死掉的运行里报 `0`,demo 依然 exit 0 |

**修复** (`09c82d35`):skill 自动 seed(失败即 abort)、`LLM_TIMEOUT` 默认 300s 且失败致命、**删除手工 ingest**、Observe 改为解析 OTel JSON 批次并在 required series 缺失时 exit 1。

### 8.4 双向验证(这次不只验 PASS)

**正向 —— 真跑 exit 0**:

```
chunks: 560  (thinking=388, text_delta=169, tool_start=1, tool_result=1, done=1)
tool calls observed in stream: ['memory_search']
timeline events: 16   (PRE_TOOL_USE / POST_TOOL_USE / STOP / RESPONSE_CHUNK×7 / …)

l1.runtime.requests.total  {op=Initialize, ok} = 1
l1.runtime.requests.total  {op=Send, ok}       = 1
l1.runtime.requests.duration{op=Initialize|Send}
l1.runtime.llm.total       {model=deepseek-v4-flash, ok} = 8
l1.runtime.tool.total      {tool=memory_search, pre}     = 1
l1.runtime.tool.total      {tool=memory_search, post}    = 1
l1.runtime.flow.outcome    {business_key=b36ed362-…, complete} = 1
l1.runtime.in_flight       {op=turn} = 0
PASS: 4/4 required L1 series emitted by the real agent loop
```

**负向 —— 喂 6g 之前的日志形态**(单个 `"scopeMetrics":[]` 空批次):

```
OTel batches exported: 1
FAIL: expected series absent after a real turn:
  - l1.runtime.requests.total
  - l1.runtime.llm.total
  - l1.runtime.tool.total
  - l1.runtime.flow.outcome
exit 1
```

**这条负控是本次最重要的一行证据**:它说明这套检查**能抓住当初那个 bug**。只会 PASS 的检查等于没有检查 —— 那正是 6c 能带病发布的原因。

### 8.5 过程中自己踩的两个坑(一并记录)

1. `| head -30` 在真实响应变大后触发 SIGPIPE,`set -o pipefail` 下变成 exit 141 —— 改为汇总统计而非 `head`。
2. 折叠指标时用 `max()`,对 gauge 是错的(报峰值),导致已归零的 `in_flight` 被误报为泄漏 —— 改为取末次值。

### 8.6 6h 后状态

- **6/6 L1 series 全部有真跑证据**(6g 时为 4/6)
- **§0.1 回到 23/23**,但这次每项都有证据,且关键项有负控
- `V315-WALK-01` ✅ CLOSED;`V315-L1-OTEL-FULL-01` ✅ CLOSED
- 测试 100/100;dual-gate PASS(134 routes / 38 rows)
- **tag v3.15.6 的两项前置条件均已满足**

---

*本文档记录 2026-08-11 → 08-12 的实测结果。所有数字来自真实运行,未经修饰。*
