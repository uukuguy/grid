# OBSTACK 手册 — EAASP 平台级 Observe / Trace / Evaluate / Optimize

> **Audience**: 产品 / 售前 / 客户对接同事,以及刚加入团队的工程师。
> 本手册不假定读者写过代码,也不假定读者了解 EAASP。
>
> **Scope**: v3.15.5(发布于 2026-08-03,tag `v3.15`)。
> 文中所有命令都已在 main 分支的 HEAD 跑通,直接复制就能执行。
>
> **怎么读**:
> - **Part I** 讲 "是什么、为什么" — 读一遍,从上到下。
> - **Part II** 讲 "怎么用" — 用到的时候翻对应章节。
> - **Part III** 讲 "怎么改" — 你要加新功能或排错时翻。

---

## 大纲

### Part I — 是什么、为什么(读一遍)

- **Ch0. EAASP 平台概览** *(给新加入团队的工程师)* — 平台定位、L0–L5
  分层、engine/data 双轴模型、关键能力指标、贯穿全手册的真实业务例子
  (校准变压器阈值)。读完建立对 EAASP 的整体心智模型。
- **Ch1. OBSTACK 30 秒介绍** — OBSTACK 是什么、为什么存在、5 个能力
  维度的全景、business_key 业务键的 wire format 字符串格式。
- **Ch2. 5 个能力维度详解** — 观察 (Observe) / 跟踪 (Trace) / 评估
  (Evaluate) / 优化 (Optimize) / 验证 (Verify) 各一节,带 canonical
  指标 / 表名 / 端点命名规范 (OBSTACK §3 合同)。
- **Ch3. 业务键 (business_key) 与跨层时间线** — 为什么同一个业务请求
  需要一个跨层不变的 ID、它怎么把 L0 协议 + L2/L3/L4 SQLite + L1 Rust
  mirror 串起来。
- **Ch4. OBSTACK 在 EAASP 中的位置** — 每个层 (L0–L5) 哪些文件被
  OBSTACK 触及,crate vs tool/* 的分界。
- **Ch5. 历史背景** — v3.10 → v3.15 每个 milestone 解决了什么问题,
  OBSTACK 为什么在这一窗口期出现,它继承了前序的什么能力。

### Part II — 怎么用(用的时候翻)

- **Ch6. 跑实例演示看 OBSTACK** — `bash scripts/v315-obstack-demo.sh`,
  每一步证明什么,怎么读 walkthrough 证据文件。
- **Ch7. 用 OBSTACK 查一次业务请求** — 已知业务键,从 timeline 查到
  evaluate 报告再查 Optimize 建议的完整路径。
- **Ch8. 给 OBSTACK 加新数据源** — 如果 OBSTACK 没接某个表怎么补。
  改 flow_readers.py + 加测试 + 重启服务 + 验证。
- **Ch9. 加新的自动调优策略** — 新 Optimize executor 怎么写
  (ab_router / alert_manager / resource_scheduler)。
- **Ch10. 出问题怎么查** — 常见 5 类问题 (timeline 空 / evaluate
  失败 / ingest 报错 / OTel 没数据 / dual-gate 红) 的排查步骤。

### Part III — 架构参考(改代码时翻)

- **Ch11. 设计决策 (ADR 引用)** — 每个关键设计决策引到对应的 ADR,
  讲当时为什么这么选 (OBSTACK 不自创 ADR, 站在 ADR-V2-024 / V2-029 /
  V2-034 / V2-035 上)。
- **Ch12. 文件级触点索引** — 每个 crate / tool / script 的 OBSTACK
  触点表 (file path + 做什么)。改 OBSTACK 时代码要碰哪里一目了然。
- **Ch13. 维护手册** — 何时更新哪个文件、双重 gate 强制什么、加
  sub-criterion 到 §0.1 的流程。
- **Refs** — 相关文档链接 (OBSTACK_DESIGN.md、JOURNAL.md、
  RESUME-NEXT-SESSION.md、ADR 索引) 与快速跳转。

---

# Part I — 是什么、为什么

## Ch0. EAASP 平台概览(给新加入团队的工程师)

> **如果已经熟悉 EAASP**,可跳过本节,直接读 Ch1。

### 平台定位

**EAASP (Enterprise AI Agent Support Platform)** 是面向企业的智能体支撑平台。

它解决一个具体问题:**让企业能放心地用 AI 智能体处理真实业务**。

"放心"二字的含义:

| 企业顾虑 | 平台应对 |
|---|---|
| 智能体可能调用错工具、产出错结果 | 每次工具调用前走 L3 **治理关卡 (governance gate)** — 允许 / 拒绝 / 转人工 |
| 业务过程不可审计 | 每一步操作落 L3 `governance_decisions` + L4 `session_events` + L2 `memory_files` 三联审计 |
| 多部门数据需隔离 | **范围 (scope)** 控制:每次调用校验调用方 scope 与技能 / 资源的 scope 是否匹配(ADR-V2-028 严格配置) |
| 同一业务请求跨多层时各层用各自 ID,关联不起来 | **OBSTACK 业务键 (business_key)**:同一个 key 从 L0 协议一路穿透到 L5 协作界面,所有事件可按此 key 拼出时间线 |

### 平台架构

EAASP 采用 **L0–L5 分层架构** + **engine / data-integration 双轴模型**(ADR-V2-024):

```
┌────────────────────────────────────────────────────────────────┐
│ L5  协作界面 (Cowork UI) — 四卡视图(事件 / 证据 / 动作 / 审批)        │
├────────────────────────────────────────────────────────────────┤
│ L4  编排 (Orchestration) — 接收请求、调度智能体、跟踪会话          │
├────────────────────────────────────────────────────────────────┤
│ L3  治理 (Governance) — 工具调用前关卡 + OPA 规则 + 5 段审批链       │
├────────────────────────────────────────────────────────────────┤
│ L2  记忆 (Memory Engine) — FTS5 + HNSW 向量 + 时间衰减混合检索       │
├────────────────────────────────────────────────────────────────┤
│ L1  智能体运行时 (Runtime) — 7 个可替换实现(grid-runtime 是旗舰)   │
├────────────────────────────────────────────────────────────────┤
│ L0  协议 (Proto) — 21 个 RPC + 4 个 Hook(跨层通信合同)             │
└────────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴──────────────┐
              ▼                            ▼
   grid-engine (共享核心)          grid-server / grid-cli / grid-platform
   (engine 轴)                       (独立产品轴)
```

**双轴模型**:engine 轴的代码 (`grid-engine` / `grid-runtime` / `grid-types` / `grid-sandbox` / `grid-hook-bridge`) 任何修改必须同时支持 engine 接入面 + 独立产品。L0–L5 的所有跨层改动都走这一套代码(ADR-V2-029)。

### 关键能力指标(v3.15.5)

EAASP 不是 demo 平台 — 每一项都已经在生产数据上跑通:

| 维度 | 数字 |
|---|---|
| L1 runtime 适配器 | **7 个**(grid-runtime + claude-code / goose / nanobot / pydantic-ai / claw-code / ccb;hermes 已冻结) |
| L1 contract | `contract-v1.2.0`(latest); `contract-v1.1.0` 是 2026-04-18 Phase 3 sign-off 历史快照(42 PASS / 22 XFAIL × 7 runtime) |
| L0 RPC | 21 个 runtime RPC + 4 个 hook(共 25 个方法) |
| L3 治理 | 5 段审批链 + OPA sidecar 生产部署(ADR-V2-034) + 5 状态决策(allow / approve / deny / gate_request / await_human) |
| L4 HTTP 路由 | 134 条(v3.9 RBAC catalog) + 4 条 business-flow 路由(v3.15.5 OBSTACK) |
| OBSTACK 闭环 | **23 / 23 = 100%**(Observe 5 / Trace 5 / Evaluate 6 / Optimize 4 / Verify 3) |
| dual-gate | `make v3.10-spec-audit` PASS(38 行) + `make rbac-audit` PASS(134 路由) |
| EAASP 演化路径 | 8 阶段(Phase 0–6 + Phase 5 L5 Cowork)全部 SHIPPED(EVOLUTION_PATH §三) |

### 真实业务例子(贯穿本手册)

> **业务请求**:"帮我把 Transformer-sla-1785652837 这个变压器的阈值校准一下"

调用栈(从用户视角 → 内部流转):

```
用户 → L4 /v1/sessions/create → 业务键 = "sess_demo|threshold-calibration|Transformer-sla-1785652837"
       │
       ├─→ L4 → L2 memory_search  →  检索这个设备的历史校准经验
       ├─→ L4 → L3 validate_session → 注册会话主体(scope 绑定)
       │
       └─→ L1 grid-runtime /v1/message (agent loop)
              │
              ├─→ 调 L3 /v1/evaluate (每次工具调用前)
              │     "调 scada_read_snapshot,允许吗?"
              │     → L3 查 OPA 规则 + scope 匹配 → 返回 "allow"
              │
              ├─→ 真实调工具:scada_read_snapshot → mock-scada → 返回 telemetry
              ├─→ 调 L3 /v1/evaluate (下一个工具)
              │     "调 scada_write,允许吗?" → L3 → "deny" (硬阻止,见 SKILL.md 安全规则)
              │
              └─→ L1 输出 JSON 结果 → L4 → 用户
```

整单完成时间 8.2 秒;中间 L3 拒绝了一次本想写的工具调用(被业务逻辑 + 安全规则拦下);最终成功。

**OBSTACK 在这个例子里做的事**:

1. **Observe**:记录每次 `l4.session.total` / `l3.governance.decision.total` / `l1.runtime.requests.duration` 调用
2. **Trace**:用同一个 `business_key` 把 L4 的 session、L3 的 decision、L2 的 memory read、L1 的 tool call 都拼成一条时间线
3. **Evaluate**:对这条时间线打报告 — "成功 / 失败 / 中断在哪一层 / 跑了多久"
4. **Optimize**:基于汇总的多条 flow 给出"下次 L1 该选 grid-runtime 还是 nanobot-runtime"(A/B router) / "L3 OPA 决策时长偏高,需要扩容 OPA sidecar"(resource_scheduler)

### 何时读哪个章节

```
你是                            →  读
─────────────────────────────────────────────────────────────────
产品 / 售前 / 客户对接            →  本手册就够了(Part I 全读)
新加入的后端工程师                →  本手册 + 然后跑 Ch6 的 demo
要加新功能 / 加新 LayerReader     →  Part II(Ch6–10) + Part III(Ch11–13)
要理解 OBSTACK 设计来龙去脉       →  Part III(Ch11 ADR lineage)
客户问"OBSTACK 解决什么问题"       →  Ch0 + Ch1 印出来就够
```

---

## Ch1. OBSTACK 30 秒介绍

### 一句话

**OBSTACK (Observe / Trace / Evaluate / Optimize / Verify — Business Stack)** 是 EAASP 平台的**跨层可观测性栈 (cross-layer observability stack)**。

它给业务方回答一个问题:**这次用户请求,跨过平台的每一层之后,发生了什么,以及平台应该据此做什么调整。**

"业务请求"是 OBSTACK 追踪的最小单位。一句"帮我校准 Transformer-sla-1785652837 的阈值"会穿过 L4 编排 → L3 治理 → L2 记忆 → L1 智能体运行时 → L0 协议。OBSTACK 的工作是把每一层的事件按同一个业务键拼成一条时间线,评估这条流做得好不好,然后产出优化建议。

### 为什么需要 OBSTACK(它解决的问题)

没有 OBSTACK 时,同一个业务请求在每层看到的"切片"是这样的:

| 层 | 它眼里看到 | 用什么标识 |
|---|---|---|
| L0 协议 | 一个 `SendMessageRequest` | gRPC metadata,无业务上下文 |
| L1 grid-runtime | 一个会话 + 工具调用日志 | L1 session_id |
| L2 记忆 | 一个 memory_id + 写事件 | memory_id |
| L3 治理 | 一行 `governance_decisions` | session_id + decision_id |
| L4 编排 | 一个 `sessions` 行 + `session_events` 流 | session_id |
| L5 协作 | 四张卡片(事件 / 证据 / 动作 / 审批) | projection 派生的 ID |

**没有任何一个层能单独回答"这次用户请求总共怎样"** — 因为标识不统一。OBSTACK 引入一个**业务键 (business_key)**,让它从 L0 协议一路穿透到 L5 协作界面,所有事件按它做关联。

### 5 个能力维度

OBSTACK 的工作分成 5 个正交维度,每个维度回答一类问题,各自有 canonical 的命名规范(详见 OBSTACK §3):

| 维度 | 回答的问题 | 主要端点 | 命名前缀 |
|---|---|---|---|
| **Observe** 观察 | 平台每个层在跑多少请求、跑多快、出多少错? | OTel SDK + L4 `observability.py` 镜像 | `l*.{runtime,session,event,flow,room}.{total,duration,in_flight,errors}` |
| **Trace** 跟踪 | 把一次业务请求跨层走过的所有事件拼成一条时间线 | `GET /v1/business-flows/{key}/{timeline,summary,sessions,events/stream}` | —(事件级别) |
| **Evaluate** 评估 | 这条业务流做得好不好?成功 / 失败 / 中断在哪一层? | `GET /v1/business-flows/{key}/evaluation` + L3 `/v1/evaluate` | —(计算产出) |
| **Optimize** 优化 | 平台应该基于观察 / 评估做什么改进? | `choose_runtime` / `fire_alerts` / `reconcile_actions` (Python) + `eaasp flow optimize` (CLI) | —(动作) |
| **Verify** 验证 | 这一切端到端还工作吗? | dual-gate (`make v3.10-spec-audit` + `make rbac-audit`) + 实例演示 | —(门禁) |

### 业务键 (business_key) 的线协议格式

业务键是一个单字符串,格式严格:

```
<session_id>|<skill_id>|<business_object_id>
```

三个字段用 `|` 连接。示例:

```
demo-sess-20260803-103238-72749|threshold-calibration|Transformer-sla-20260803-103238-72749
sess_b14197b88f38|threshold-calibration|Transformer-sla-1785652837
```

解析器是严格的 — 必须恰好 3 个字段,任一为空会抛 HTTP 400。规范解析器:

- **Python**:`tools/eaasp-common/src/eaasp_common/business_flow.py` 中的 `parse_business_key_header(raw)`
- **协议**:`proto/eaasp/runtime/v2/common.proto` 中的 `BusinessKey { ... }` 消息(21 个 RPC + 4 个 hook 都挂载了业务键字段,tags 100)

每一层在收到业务键时,把它持久化到自己表的行上,后续时间线查询按它做 JOIN。Ch3 详述跨层传播路径。

### OBSTACK 栈全景

```
┌─────────────────────────────────────────────────────────────┐
│ EAASP v3.15.5 OBSTACK 跨层可观测性栈                       │
├─────────────────────────────────────────────────────────────┤
│ Observe  观察 │ OTel SDK (L1 Rust + L2/L3/L4 Python 镜像)     │
│ Trace    跟踪 │ 5 张表 + L0 proto 上的 business_key 列          │
│ Evaluate 评估 │ flow_timeline + flow_evaluator + 评估报告      │
│ Optimize 优化 │ ab_router + alert_manager + resource_scheduler  │
│ Verify   验证 │ dual-gate + 实例演示                            │
└─────────────────────────────────────────────────────────────┘
                       ▲
                       │ 业务键 (business_key) 把每层串起来
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ EAASP 平台分层                                                │
│  L0 协议 ─ L1 智能体运行时 ─ L2 记忆 ─ L3 治理 ─ L4 编排 ─ L5 协作 │
└─────────────────────────────────────────────────────────────┘
```

### 什么在 OBSTACK 范围内,什么不在

**当前已实现 (v3.15.5)**:
- 跨层时间线聚合(通过业务键)
- L1/L2/L3/L4 的 OpenTelemetry metric + trace 集成
- 评估报告(状态 / 完成率 / 优化建议)
- 三个自动调优执行器(A/B 路由 / 告警 / 资源调度)
- dual-gate CI + 实例演示作为证据

**v3.16+ 才做**:
- 生产级 `opentelemetry-stdout` 导出器(目前用 `InMemoryExporter` 兜底)
- L0 / L5 层级的可观测性(L0 已挂 OTel counters,L5 cards 只是投影)
- EAASP 与外部系统的分布式追踪
- 长期遥测保留(超过 30 天)

---

*下一章:Ch2 — 5 个能力维度详解。每个维度一节,带 canonical 指标 / 表名 / 端点命名规范。*

## Ch2. 5 个能力维度详解

本章展开 Ch1 列出的 5 个维度,每个一节,讲:
- 这个维度回答什么问题
- 实现机制(主要组件 + 文件路径)
- 命名规范(metric 名 / 表名 / 端点)
- 一个真实调用例子
- 当前 v3.15.5 的实现状态

### 2.1 Observe(观察)

**回答的问题**:平台每个层在跑多少请求、跑多快、出多少错?

**实现机制**:每个层有一个 OpenTelemetry(以下简称 OTel)镜像模块,把层内的事件折算成 OTel 标准指标。v3.15.5 完成后 L1/L2/L3/L4 都有镜像。

**OTel 指标命名规范**:`<layer>.<entity>.<measurement>`

| 层 | 模块文件 | 指标前缀 | 关键指标 |
|---|---|---|---|
| L1 (grid-runtime) | `crates/grid-runtime/src/observability/mod.rs` | `l1.runtime.*` | `l1.runtime.requests.total` (Counter) / `l1.runtime.requests.duration` (Histogram) / `l1.runtime.in_flight` (UpDownCounter) / `l1.runtime.errors.total` / `l1.runtime.llm.total` / `l1.runtime.llm.duration` / `l1.runtime.tool.total` |
| L2 (记忆引擎) | `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/observability.py` | `l2.memory.*` | `l2.memory.search.total` / `l2.memory.write.total` / `l2.memory.write.duration` |
| L3 (治理) | `tools/eaasp-l3-governance/src/eaasp_l3_governance/observability.py` | `l3.*` | `l3.requests.total` / `l3.request.duration` / `l3.errors.total` / `l3.in_flight` / `l3.opa.decision.total` / `l3.opa.decision.duration` / `l3.opa.infra_unavailable.total` |
| L4 (编排) | `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/observability.py` | `l4.{session,room,flow,event}.*` | `l4.session.total` / `l4.flow.total` / `l4.event.total` / `l4.errors.total` |

**OTel 集成方式**:
- L1 Rust 用 `opentelemetry` + `opentelemetry_sdk` crate,落地方式是 `SdkMeterProvider` + `PeriodicReader` + `InMemoryExporter`(v3.15.5 现状)。生产 stdout 导出器 (v3.16+)。
- L2/L3/L4 Python 用 `opentelemetry-api` + `opentelemetry-sdk`,导出方式同上。

**调用例子**:直接通过 OTel SDK 查询 L1 runtime 的请求计数。

```python
# crates/grid-runtime 内
from grid_runtime.observability import init_observability, get_handles
init_observability("stdout")  # 激活 SdkMeterProvider
handles = get_handles()
handles.requests_total.add(1)
handles.requests_duration.record(0.123)
```

**当前 v3.15.5 实现状态**:5/5 维度闭环。
- L3:最先落地(2025 年,a18a22ba commit)
- L1:完整 SdkMeterProvider 真实 wiring 在 `e16686d4` (2026-08-02 V315-L1-OTEL-FULL-01)
- L2/L4:Python 镜像模块就位

---

### 2.1.5 设计原则:grid-runtime 主动驱动 OTel(未来)

**当前实现(Phase A 前)**:L1 OTel 镜像模块(`crates/grid-runtime/src/observability/mod.rs`)是**外部加挂**——agent loop 主体(`harness.rs`)不主动 emit 业务事件。镜像模块的 7 个 metric(`l1.runtime.*`)由调用方在 harness 各处手动 `record_*()` 调用触发。

**目标实现(Phase A 后,见 Ch14)**:grid-runtime agent loop **在执行关键动作时主动 emit OTel event**:
- 每个 tool call 前/后自动 emit `l1.runtime.tool.total{tool_name, status}` + `l1.runtime.tool.duration`
- 每个 LLM call 自动 emit `l1.runtime.llm.total{model, status}` + `l1.runtime.llm.duration`
- 每个 hook 执行自动 emit `obstack.event.business_flow.hook_fired`
- 每个 business flow 完成自动 emit `l1.runtime.flow.outcome{business_object_id, status}`

**为什么这是关键**:当前 Phase A 前,OBSTACK 时间线靠外部 demo 脚本手工 ingest 5 个事件来填充。Phase A 后,grid-runtime 真实 agent loop 轨迹会自动出现在时间线——OBSTACK 真正成为**运行时反馈**而不仅是事后查询工具。

**实现位置(Phase A 后)**:
- `crates/grid-runtime/src/harness.rs` agent loop 各关键点加 OTel record 调用
- `crates/grid-runtime/src/observability/mod.rs` 7 个 metric + 新增 4 个 metric
- 验证:`eaasp flow timeline --key <demo-key>` 能看到真实 agent loop 事件(不止 ingest 占位事件)

详见 Ch14 路线图 Phase A。

### 2.2 Trace(跟踪)

**回答的问题**:把一次业务请求跨层走过的所有事件拼成一条时间线。

**实现机制**:每个层在自己的表上加 `business_key` 列;OBSTACK 提供跨层查询端点,用业务键做 JOIN,把每层的事件按时间戳排序后返回。

**关键文件**:

| 角色 | 文件 |
|---|---|
| 业务键解析 + 跨进程传播 | `tools/eaasp-common/src/eaasp_common/business_flow.py` |
| 时间线聚合器 | `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_timeline.py` |
| 跨层读数据源(LayerReader) | `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_readers.py` |
| REST 端点 | `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py` |

**每个层的 `business_key` 列**(v3.15.5 全部就位):

| 层 | 表 | 列 | migration commit |
|---|---|---|---|
| L2 | `memory_files` + `anchors` | `business_key TEXT` | (L2 init_db) |
| L3 | `governance_decisions` + `telemetry_events` | `business_key TEXT` | `db.py:_add_business_key_column` |
| L4 | `sessions` + `event_room_events` | `business_key TEXT` | (L4 `_V315_BUSINESS_KEY_COLUMNS`) |
| L0 | 21 RPC + 4 Hook 全部加 `BusinessKey business_key = N` 字段 | field tag 100 | `1351107c` + `85cd4951` (proto + struct literal fix) |

**REST 端点**(`flow_api.py`,L4 暴露):

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/v1/business-flows/{key}/timeline` | 完整跨层时间线,按 ts 排序 |
| `GET` | `/v1/business-flows/{key}/summary` | 摘要:started_at / completed_at / event_count / layer_counts / interrupted_layer |
| `GET` | `/v1/business-flows/{key}/sessions` | 该业务键下的所有 session_id |
| `GET` | `/v1/business-flows/{key}/events/stream` | SSE,实时推送新事件 |

**调用例子**:

```bash
KEY="sess_demo|threshold-calibration|Transformer-sla-1785652837"
ENCODED=$(printf '%s' "$KEY" | python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.stdin.read()))")
curl "http://127.0.0.1:18084/v1/business-flows/$ENCODED/timeline"
```

**当前 v3.15.5 实现状态**:5/5 维度闭环 — 跨层时间线聚合走的是**跨表 JOIN**(OBSTACK §3.8 设计决策),不引入独立事件表。

---

### 2.3 Evaluate(评估)

**回答的问题**:这条业务流做得好不好?成功 / 失败 / 中断在哪一层 / 跑了多久?

**实现机制**:基于 Trace 拼出来的时间线,跑评估函数,产出结构化报告。

**关键文件**:

| 角色 | 文件 |
|---|---|
| 时间线 → 摘要聚合 | `flow_timeline.py:assemble_business_flow_summary` |
| 摘要 → 评估报告 | `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_evaluator.py` |
| REST 端点 `/evaluation` | `flow_api.py:get_business_flow_evaluation` |

**评估报告字段**:

```python
@dataclass
class FlowEvaluationReport:
    window_seconds: int          # 时间窗口(默认 3600)
    total_flows: int             # 窗口内总业务流数
    status_counts: dict[str, int]  # 各状态计数:{succeeded, failed, aborted, running, unknown}
    completion_rate: float        # 完成率 = succeeded / total
    interruption_heatmap: dict   # 中断点分布: layer → 中断次数
    hints: list[OptimizationHint]  # 给 Optimize 维度的建议清单
```

**状态推断逻辑**(`flow_timeline.py:_infer_status`):从时间线**最后**一个事件推断。

| 最后一个事件 | 状态 |
|---|---|
| `session.closed` 且 payload.status="closed" | succeeded |
| `session.closed` 且 payload.status="failed" | failed |
| `session.closed` 且 payload.status 其他 | aborted |
| `session.failed` | failed |
| `business_flow.ended` 且 payload.status 已知 | 该状态 |
| `governance.decision` 且 decision="deny" 且无后续事件 | aborted |
| 其他 | running |

**REST 调用**:

```bash
curl "http://127.0.0.1:18084/v1/business-flows/$ENCODED/evaluation"
# 返 {"report": {"total_flows": 1, "completion_rate": 0.0, "hints": [...]}}
```

**当前 v3.15.5 实现状态**:6/6 维度闭环 — 包括 4 个 SLA baseline tests(`tests/platform_sla/`)+ 评估器 + REST + CLI + 9 tests。

---

### 2.4 Optimize(优化)

**回答的问题**:平台应该基于观察 / 评估做什么改进?

**实现机制**:评估器产出 `OptimizationHint` 纯函数结果,三个执行器把 hint 翻译成具体动作。

**三个执行器**(`tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/`):

| 执行器 | 文件 | 作用 |
|---|---|---|
| `choose_runtime()` | `ab_router.py` | A/B 路由 — 同一业务对象下不同 runtime 的完成率排序,选最高 |
| `fire_alerts()` | `alert_manager.py` | 把 hint 按 severity 阈值过滤后广播到告警 sinks |
| `reconcile_actions()` | `resource_scheduler.py` | 把 hint 转成 scale-up / scale-down 动作(默认 dry-run) |

**A/B 路由调用例子**:

```python
from eaasp_l4_orchestration.ab_router import choose_runtime, FlowMeta
from eaasp_l4_orchestration.flow_timeline import assemble_business_flow_summary
from eaasp_l4_orchestration.flow_readers import build_default_layer_readers

readers = build_default_layer_readers(l4_conn=l4, l3_conn=l3, l2_conn=l2)
summary = await assemble_business_flow_summary(key, layer_readers=readers)
meta = FlowMeta(business_object_id="Transformer-sla-1785652837", runtime_id="grid-runtime")
decision = choose_runtime(
    "Transformer-sla-1785652837",
    [(summary, meta)],
)
# RouterDecision(runtime_id="grid-runtime", reason="...", sample_size=1, ...)
```

**当前 v3.15.5 实现状态**:4/4 维度闭环 — A/B 路由(10 tests)+ alert_manager(7 tests)+ resource_scheduler(8 tests)+ hint 生成(15 tests)。

---

### 2.5 Verify(验证)

**回答的问题**:这一切端到端还工作吗?

**实现机制**:dual-gate CI(每次 commit 必须跑)+ live demo(手工触发)。

**dual-gate 两个 gate**:

| Gate | 命令 | 检查内容 |
|---|---|---|
| spec-audit | `make v3.10-spec-audit` | EAASP 各层能力是否对齐 v3.10 spec 矩阵(38 行) |
| rbac-audit | `make rbac-audit` | L4 HTTP 路由是否完整登记到 RBAC catalog(134 条) |

**触发位置**:`tools/eaasp-spec-alignment/` + `crates/grid-server/src/bin/route-auditor`。两个 gate 任意一个退出码非零,commit 不能合并。

**live demo**:`scripts/v315-obstack-demo.sh`(约 250 行)。手动跑一次,5 个维度都跑一遍,产出 `.logs/v315-obstack-demo/${RUN_ID}/` 下的证据文件 + `docs/status/PRODUCTION_USABILITY_2026-08-02-obstack-demo.md` 增量更新。

**当前 v3.15.5 实现状态**:3/3 维度闭环 — dual-gate + live demo(2026-08-02 跑通,14 个时间线事件 + 5 OTel 事件 + dual-gate PASS)+ tag `v3.15` push。

---

*下一章:Ch3 — 业务键 (business_key) 与跨层时间线。深入讲业务键的来历、wire format、跨层传播路径。*

## Ch3. 业务键 (business_key) 与跨层时间线

本章深入讲 OBSTACK 的"骨架" — 业务键。它是 Ch1 提到的 5 个维度能跑通的根本。

### 3.1 为什么需要业务键(它解决的真问题)

考虑一个具体场景:**一个用户请求失败,但失败的根因在三层中的哪一层?**

- L4 看到了 `sessions.status = "failed"`,但不知道是哪一步失败
- L3 看到了 `governance_decisions.decision = "deny"`,但不知道这次拒绝对应哪个用户的请求
- L2 看到了 `memory_files` 写入失败,但跟当前请求是否相关需要 JOIN
- L1 看到了工具调用超时,但跟业务语境的关联要绕一大圈

每一层都有自己的 ID(session_id / decision_id / memory_id / tool_call_id),互相对不上。业务键是**所有层共用的一个字符串**,把同一笔业务请求的所有事件串成一条线。

> **设计决策 (OBSTACK §3.8)**:业务键采用 `(session_id, skill_id, business_object_id)` 三元组。三个维度不可压缩 — `session_id` 区分会话,`skill_id` 区分技能,`business_object_id` 区分"哪个业务对象"(设备 / 工单 / 合同等)。

### 3.2 业务键的 wire format(线协议格式)

**字符串格式**:`<session_id>|<skill_id>|<business_object_id>`

```
demo-sess-20260803-103238-72749|threshold-calibration|Transformer-sla-20260803-103238-72749
sess_b14197b88f38|threshold-calibration|Transformer-sla-1785652837
```

**规则**:

| 字段 | 是否必填 | 约束 |
|---|---|---|
| `session_id` | **必填**(空字符串视为无效) | ≤ 256 字符,不含 `\|` |
| `skill_id` | 选填(空字符串 OK) | ≤ 256 字符,不含 `\|` |
| `business_object_id` | 选填(空字符串 OK) | ≤ 256 字符,不含 `\|` |

**约束**:`|` 是 wire separator,不允许出现在任何字段里。Python 解析器(`parse_business_key_header`)在违反时抛 `ValueError`,调用方记录后丢弃(不向上抛用户)。

### 3.3 跨层传播路径(它是怎么穿透每一层的)

业务键从用户请求到最终落表,经过这些环节:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 用户 (或上游 L4)                                                   │
│   X-Business-Key: sess_demo|threshold-calibration|Transformer-...   │
└────────────────┬────────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ L0 协议层 (gRPC / HTTP)                                              │
│   proto/eaasp/runtime/v2/common.proto                                │
│   message BusinessKey {                                              │
│     string session_id = 1;                                           │
│     string skill_id = 2;                                             │
│     string business_object_id = 3;                                   │
│   }                                                                  │
│                                                                       │
│   21 个 RPC + 4 个 hook 全部加 `BusinessKey business_key = 100;`    │
│   (field tag 100 是为向后兼容预留,缺省值是 empty,老 RPC 不受影响)   │
└────────────────┬────────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ L1 Rust 镜像 (crates/grid-runtime/src/business_flow.rs)              │
│   - BusinessKey struct + BusinessKeyError                             │
│   - Mirror of Python eaasp_common.business_flow                      │
│   - 在 tracing::Span 上记录 business_key,跨 await 边界传播             │
└────────────────┬────────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ L2 / L3 / L4 接收层(各自 FastAPI middleware)                          │
│   eaasp_common.business_flow.require_business_key_from_request        │
│   - 从 HTTP header `X-Business-Key` 抽出                              │
│   - 塞入 contextvar (Python 进程内传播)                              │
│   - 各层 handler 在落库时,从 contextvar 读出 + 写入表的业务键列      │
└────────────────┬────────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ SQLite 落表 (每层一张表,business_key 列都到位)                       │
│   L4 sessions.business_key  | L4 event_room_events.business_key       │
│   L3 governance_decisions.business_key | L3 telemetry_events.business_key│
│   L2 memory_files.business_key | L2 anchors.business_key              │
└─────────────────────────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 时间线聚合 (flow_timeline.py + flow_readers.py)                     │
│   SELECT * FROM sessions WHERE business_key = ?                       │
│   UNION ALL                                                          │
│   SELECT * FROM session_events JOIN sessions ON ... WHERE business_key = ?│
│   UNION ALL ...                                                      │
│   ORDER BY ts                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.4 每个层落表的关键文件

| 层 | 表 | 落表入口 | business_key 来源 |
|---|---|---|---|
| L0 | gRPC/HTTP metadata | `proto/eaasp/runtime/v2/*.proto` 字段 100 | 调用方传入 |
| L1 | `tracing::Span` | `crates/grid-runtime/src/business_flow.rs` | L1 收到 L0 业务键后透传 |
| L2 | `memory_files` + `anchors` | `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/api.py` (FastAPI middleware) | `require_business_key_from_request` 解析后写入 |
| L3 | `governance_decisions` + `telemetry_events` | `tools/eaasp-l3-governance/src/eaasp_l3_governance/api.py` | 同 L2 |
| L4 | `sessions` + `event_room_events` | `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/api.py` (会话创建 + ingest 路径) | 同 L2 |
| L5 | (投影,不落表) | L5 Cowork UI 通过 `/v1/business-flows/{key}/*` 端点读 L4 拼好的时间线 | 拉取 |

**关键观察**:**L5 不直接落业务键**,而是从 L4 REST 拉时间线再投影成四卡视图。这样 L5 的失效不会污染审计数据。

### 3.5 跨进程传播机制(为什么不会丢)

OBSTACK 用两套机制保证业务键不丢:

| 层 | 传播机制 | 代码位置 |
|---|---|---|
| L1 (Rust) | `tracing::Span` 字段 + `task_local!` 跨 await 边界 | `crates/grid-runtime/src/business_flow.rs` |
| L2/L3/L4 (Python) | `contextvars.ContextVar` 跨 asyncio 任务边界 | `eaasp_common.business_flow._business_key_var` |

中间件在请求进入时设置 contextvar,handler 退出时清理。handler 不需要在函数签名里逐层传递 business_key — 直接 `get_current_business_key()` 就能读到。

### 3.6 时间线聚合 SQL(它是怎么把每层拼起来的)

L4 `flow_timeline.py:assemble_business_flow_timeline` 的核心是逐个调用 5 个 LayerReader,每个读自己层的表:

```python
async def read_l4_sessions(conn, key):
    """读 L4 sessions + session_events,emit session.created / session.closed 事件。"""
    wire = key.to_header()
    async with conn.execute(
        """
        SELECT session_id, 'session.created', created_at, payload_json, ...
          FROM sessions
         WHERE business_key = ?
        UNION ALL
        SELECT session_id, 'session.closed', COALESCE(closed_at, created_at), ...
          FROM sessions
         WHERE business_key = ? AND status IN ('closed', 'failed')
         ORDER BY 3
        """,
        (wire, wire),
    ) as cur:
        ...
```

5 个 reader 各自返回一组 `BusinessFlowEvent`,然后聚合器按 ts 排序合并。**没有引入新的事件表**,完全靠现有表的 `business_key` 列做 JOIN(OBSTACK §3.8 设计决策)。

### 3.7 真实例子:从业务键到完整时间线

假设用户跑了一次 demo,业务键是 `sess_demo|threshold-calibration|Transformer-sla-1785652837`,完整时间线查询:

```bash
KEY='sess_demo|threshold-calibration|Transformer-sla-1785652837'
ENCODED='sess_demo%7Cthreshold-calibration%7CTransformer-sla-1785652837'
curl "http://127.0.0.1:18084/v1/business-flows/$ENCODED/timeline"
```

**返 14 个事件**,类型分布大致是:

| 层 | 事件类型 | 数量 |
|---|---|---|
| L4 | `session.created` | 1 |
| L4 | `session_event.PRE_TOOL_USE` | 1 |
| L4 | `session_event.POST_TOOL_USE` | 1 |
| L4 | `session_event.APPROVAL` | 1 |
| L4 | `session_event.REQUEST` | 1 |
| L4 | `session_event.MEMORY_WRITE` | 1 |
| L4 | (session log 内的其他事件) | 8 |

时间线里只有 L4 事件 — 因为这次 demo 没真触发 L3 治理判定(走的是 demo 脚本的"快速 ingest"路径,绕过 L3)。真实业务流会有 L3 governance.decision 事件穿插。

### 3.8 边界情况

- **header 缺失**: 业务键**选填**(v3.15.1 设计决策)。L0 proto 缺省值是 empty,L4 sessions 表 `business_key` 列是 NULL。不阻塞业务。
- **header 格式错**: parse 抛 `ValueError`,middleware 记录日志并丢弃,业务请求继续(当作无业务键处理)。不向用户报错(避免一个 header 阻断业务)。
- **业务键冲突**: 同一业务键有多条 session(v3.15 允许,例如 retry)。`/summary` 会把所有事件合并;`/sessions` 列出所有匹配 session_id。
- **L0 proto 字段 100 缺省值**: 老 RPC 客户端不带业务键也能用 — proto3 兼容。

---

*下一章:Ch4 — OBSTACK 在 EAASP 中的位置。讲每个层 (L0–L5) 哪些文件被 OBSTACK 触及,crate vs tool/* 的分界。*

## Ch4. OBSTACK 在 EAASP 中的位置

本章回答:**OBSTACK 代码具体在哪**。Ch3 讲了业务键的传播路径(概念层),本章列每个路径上的具体文件。

### 4.1 顶层位置:跨 crate + cross-tool

OBSTACK 不是一个独立 crate 或独立服务。它的代码分布在:

| 位置 | 类型 |
|---|---|
| `crates/grid-runtime/src/business_flow.rs` | L1 Rust 镜像 |
| `crates/grid-runtime/src/observability/` | L1 OTel SDK wiring |
| `tools/eaasp-common/src/eaasp_common/business_flow.py` | Python 业务键 dataclass + 解析 |
| `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/observability.py` | L2 OTel 镜像 |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/observability.py` | L3 OTel 镜像 |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/api.py` | L3 evaluate endpoint 业务键提取 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/api.py` | L4 sessions + ingest 业务键提取 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_*.py` | L4 5 个 OBSTACK 模块(下文详述) |
| `tools/eaasp-cli-v2/src/eaasp_cli_v2/cmd_flow.py` | `eaasp flow` 子命令(timeline/summary/watch/evaluate) |
| `proto/eaasp/runtime/v2/*.proto` | L0 proto `BusinessKey` 消息 + 25 个 RPC/Hook 字段 100 |

### 4.2 engine vs data 双轴边界

按 **ADR-V2-024 + ADR-V2-029**,EAASP 跨层代码必须在 **engine 轴** 共享:

```
engine 轴(共享)                      data/integration 轴(独立产品)
─────────────────────────────────  ─────────────────────────────────
crates/grid-types/                   crates/grid-server/
crates/grid-engine/                  crates/grid-platform/
crates/grid-runtime/  ← L1 OBSTACK   crates/grid-cli/  ← eaasp flow 子命令
crates/grid-sandbox/                 crates/grid-eval/
crates/grid-hook-bridge/             web/  web-platform/  grid-desktop/
tools/eaasp-common/  ← 业务键模块
tools/eaasp-l2-*/  ← L2 镜像 + schema
tools/eaasp-l3-*/  ← L3 镜像 + endpoint
tools/eaasp-l4-*/  ← L4 flow_* + observability
```

**关键约束**(ADR-V2-029 P1):
- L0-L5 跨层修改走 engine 轴(所有上面左侧的 crate / tool 都必须按此约束走)
- 修改任何 engine 轴 crate 必须同时支持 EAASP 接入面 + grid-server / grid-cli 独立产品
- 不能在 engine 轴里加 product-specific 分支(否则违反 ADR-V2-023 P1)

### 4.3 L4 内部的 OBSTACK 模块分布(5 个文件)

L4 是 OBSTACK 的主要承载层(所有 4 个 REST 端点都在 L4 暴露)。`tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/` 下:

| 文件 | 角色 | 关键 API |
|---|---|---|
| `flow_timeline.py` | 业务流事件模型 + 聚合器 | `BusinessFlowEvent` / `BusinessFlowSummary` / `assemble_business_flow_timeline()` / `summarize_business_flow()` |
| `flow_readers.py` | 跨层数据源(5 个 LayerReader) | `read_l4_sessions()` / `read_l3_*()` / `read_l2_*()` / `build_default_layer_readers()` |
| `flow_sse.py` | 实时事件流 | `FlowEventBus` / `subscribe_to_business_flow()` |
| `flow_api.py` | 4 个 REST 端点 + 1 个 /sessions 端点 | `/v1/business-flows/{key}/{timeline,summary,evaluation,sessions,events-stream}` |
| `flow_evaluator.py` | 评估器(纯函数) | `evaluate_business_flows(summaries)` → `FlowEvaluationReport` |

**调用关系**(数据从下到上):

```
LayerReader (flow_readers.py) 读 SQLite
       ↓
summarize_business_flow (flow_timeline.py) 拼摘要
       ↓
evaluate_business_flows (flow_evaluator.py) 产报告
       ↓
4 个 REST 端点 (flow_api.py) 暴露给 L5 / CLI / 外部
```

### 4.4 跨层的 OTel 镜像一致性

L1 / L2 / L3 / L4 四个 OTel 镜像都遵循同一命名规范 `<layer>.<entity>.<measurement>`。差异在 SDK:

| 层 | SDK | 导出方式 |
|---|---|---|
| L1 | `opentelemetry` + `opentelemetry_sdk` Rust crate | SdkMeterProvider + PeriodicReader + **InMemoryExporter**(v3.15.5) |
| L2/L3/L4 | `opentelemetry-api` + `opentelemetry-sdk` Python | SdkMeterProvider + 同上 |

生产级 `opentelemetry-stdout` 导出器在 v3.16+ 再做(OBSTACK §0.2 标 deferred)。

### 4.5 L5 协作界面不直接落表

按 OBSTACK 设计,L5 Cowork UI **不直接落业务键**到数据库。它通过 L4 暴露的 4 个 REST 端点拉时间线再投影成四卡视图(事件 / 证据 / 动作 / 审批)。

```
L5 Cowork UI
   ↓ HTTP GET
L4 /v1/business-flows/{key}/{timeline,summary,...}
   ↓ SQL JOIN
L4 sessions + L3 governance_decisions + L2 memory_files + ...
```

这样 L5 失效不会污染审计数据,所有数据来源都可追溯到 L0-L4 的具体行。

---

## Ch5. 历史背景

### 5.1 v3.10 → v3.15 的 6 个 milestone

| Milestone | 主要交付物 | 与 OBSTACK 的关系 |
|---|---|---|
| **v3.10** | EAASP v2.0 平台骨架对齐(5 层 + 3 管道 + 4 元范式) | 提供 OBSTACK 落地的"骨骼" |
| **v3.11** | L3 治理 OPA + 5 段审批链 | 提供 L3 metrics 镜像 + `governance_decisions` 表(OBSTACK 跨层 JOIN 的一环) |
| **v3.12** | A2A Router + Event Room(多 session 协调) | 提供 Event Room events + `event_room_events` 表(OBSTACK 跨层 JOIN 的一环) |
| **v3.13** | L5 Cowork 4 卡视图(事件 / 证据 / 动作 / 审批) | 提供 4 卡投影 + retrospective 链路(OBSTACK L5 协作层) |
| **v3.14** | L5 Ecosystem Marketplace + SDK | 独立产品轴,**与 OBSTACK 解耦**(OBSTACK 是 engine 轴观察能力,Marketplace 是 product 表面) |
| **v3.15** | **OBSTACK**(平台级 Observe / Trace / Evaluate / Optimize) | 第一次把所有层的可观测性纵向串成业务流 |

### 5.2 为什么 OBSTACK 在 v3.15 才出现

前序每个 milestone 都解决了平台某一块的具体能力(治理 / 协作 / 生态),但**观察能力是各层散装的**:

| 前序 | 散装的观察 |
|---|---|
| v3.11 | 只有 L3 OTel 镜像 |
| v3.12 | L4 Event Room 的事件能查,但跨 session 关联要绕一大圈 |
| v3.13 | 4 卡视图,但单卡只能看一层 |
| v3.14 | Marketplace metrics,跟业务流无关 |

OBSTACK 的出现(2026-08)是把**所有层的可观测性按业务请求串起来**。前提条件:

1. v3.11 → L3 OTel 镜像存在 → 提供观察基础
2. v3.12 → Event Room 表存在 → 提供跨 session 事件底座
3. v3.13 → 4 卡视图存在 → L5 投影目标存在
4. v3.14 → Marketplace 与 engine 轴解耦 → OBSTACK 可以只关心 engine 轴
5. 用户的反馈("应是纵向业务流绑定,不是各层散装") → 方向校准

### 5.3 v3.15 内部的 6 个 sub-phase

OBSTACK v3.15 不一次性做完,而是分 6 个 sub-phase:

| Sub-phase | 内容 | Commit |
|---|---|---|
| v3.15.0 | 平台级 metrics 底座(L3 OTel 镜像 + 命名规范) | `a18a22ba` |
| v3.15.1 | 业务键 + 跨层 schema migration(5 张表 + L0 proto) | (本批) |
| v3.15.2 | 业务流时间线聚合(跨表 JOIN + REST + CLI) | (本批) |
| v3.15.3 | 业务流持续订阅(SSE 通道) | (本批) |
| v3.15.4 | 业务流评估 + 优化建议(A/B 路由 + alert + scheduler) | `f76be767` / `6aefe295` / `b5475516` |
| v3.15.5 | L1 OTel SDK 真实 wiring + 实例演示 | `e16686d4` / `84cc0680` / 7 个 ingest+session 测试 |

### 5.4 OBSTACK_DESIGN.md §7 — 与 v3.11-v3.14 的关系

OBSTACK 不"覆盖"前序 milestone,而是**继承 + 升级**:

| v3.11 L3 OPA | v3.15 → 保留 + observability.py 已加 + 加 `business_key` 列 |
| v3.12 A2A + Event Room | v3.15 → Event Room events 加 trace_id + business_key;**业务流 SSE 是新通道** |
| v3.13 L5 Cowork | v3.15 → 4 卡视图加 business_key 透出 + 业务流 UI 模式 |
| v3.14 L5 Ecosystem | v3.15 → 不变(独立产品) |

**结论**:v3.15 是**第一个跨层业务流 milestone** — 把之前各层独立做的可观测性升级为**纵向业务流绑定**的持续能力。

---

*Part I(Ch0-Ch5)到此结束。下面进入 Part II(怎么用)。*

## Ch6. 跑实例演示看 OBSTACK

本章教新人怎么**完整跑一次实例演示**,看 OBSTACK 5 个维度都在工作。

### 6.1 演示脚本:scripts/v315-obstack-demo.sh

整个演示由一个 shell 脚本驱动:

```bash
bash scripts/v315-obstack-demo.sh 2>&1 | tee .logs/v315-obstack-demo.log
```

脚本会自动:
1. 生成 RUN_ID(每个 run 独立,避免跨次污染)
2. 在独立目录 `data/v315-demo-${RUN_ID}/` 启动 L1/L2/L3/L4 + L1 grid-runtime
3. 部署一个最小的 L3 managed-hooks policy
4. 用 `X-Business-Key` 头创建一个 L4 session
5. 调用 5 个 ingest 事件(PRE_TOOL_USE / POST_TOOL_USE / APPROVAL / REQUEST / MEMORY_WRITE)
6. 查询 `/timeline` / `/summary` / `/sessions` / `/evaluation`
7. 跑 Optimize executors(ab_router / alert_manager / resource_scheduler)
8. 跑 dual-gate 验证

**整个 run 大约 90 秒**,不需要任何手工 wipe(脚本自带 `V315_DEMO_DATA_DIR` 隔离每个 run)。

### 6.2 看哪几行证据就算"OBSTACK 工作正常"

跑完脚本后,在 `.logs/v315-obstack-demo/${RUN_ID}/run.log` 里查找这些关键输出:

| 维度 | 怎么看 | 期望输出 |
|---|---|---|
| **Observe** | 搜 `grid-runtime lifecycle events captured` | `5` 或更多 |
| **Trace** | 搜 `=== 6.` 然后看 `count` | `event_count: 14`(或更多) |
| **Evaluate** | 看 `report` 字段 | `total_flows: 1` + `completion_rate` + `hints` |
| **Optimize** | 搜 `=== 10. Optimize executors ===` 下面 | `choose_runtime: RouterDecision(...)` + `reconcile_actions: [...]` |
| **Verify** | 看脚本末尾的 `make v3.10-spec-audit` + `make rbac-audit` | 两个都 `PASS` |

### 6.3 跑通后立刻能做什么

跑通一次演示后,你已经有了:
- 一个独立数据目录 `data/v315-demo-${RUN_ID}/`,里面有真实的 L4/L3/L2/L1 SQLite 文件
- 一个 walkthrough 证据文件 `.logs/v315-obstack-demo/${RUN_ID}/run.log`,可直接 `grep` 任何维度
- 一个真实业务键可以拿去查(见 Ch7)

---

### 6.4 未来:grid-cli + grid-runtime 原生接入后的 demo

Ch14 路线图里 Phase A (grid-runtime 原生 OBSTACK) + Phase B (grid-cli 全局接入)落地后,demo 输出会进一步丰富:

**Phase A 之后(预计 v3.16)**:
- LLM-driven message step 不再需要 30s timeout(因为 grid-runtime 自动 emit 业务事件,时间线无需手动 ingest)
- Timeline 查询自然包含 grid-runtime 真实 agent loop 轨迹(不是 demo 脚本手工塞的 PRE_TOOL_USE / POST_TOOL_USE)

**Phase B 之后(预计 v3.16+)**:
- 跑 demo 后,`eaasp session show $SESSION_ID` 第一行就是 `business_key: ...`
- `eaasp skill list` 每行显示 `flows: 12 succeeded / 0 failed`
- `eaasp policy list` 显示每个 hook 的过去 1h 通过/拒绝速率
- 新增 `eaasp flow list` / `eaasp flow top-failed` / `eaasp flow top-slow` 等 OBSTACK 运维入口

**Phase C 之后(预计 v3.17)**:
- 打开 `http://localhost:5180/flows` 看到活跃业务流列表,每行可点击进入详情页
- 详情页 SSE 实时显示新事件,无需手动刷新

详细的 Phase A/B/C 路线图 + 验收标准见 Ch14。

## Ch7. 用 OBSTACK 查一次业务请求

本章给新人一个**完整路径**:已知业务键,怎么从 timeline 查到 evaluate 报告再查 Optimize 建议。

### 7.1 准备:拿到一个业务键

如果跑过 Ch6 的 demo,业务键长这样:

```
demo-sess-20260803-103238-72749|threshold-calibration|Transformer-sla-20260803-103238-72749
```

记下来。或者从数据库反查:

```bash
sqlite3 data/v315-demo-${RUN_ID}/l4.db \
  "SELECT session_id, business_key, status FROM sessions WHERE business_key IS NOT NULL"
```

### 7.2 时间线查询(timeline)

```bash
KEY="demo-sess-20260803-103238-72749|threshold-calibration|Transformer-sla-20260803-103238-72749"
ENCODED=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.stdin.read()))" <<< "$KEY")
curl "http://127.0.0.1:18084/v1/business-flows/$ENCODED/timeline"
```

**返 JSON**:`{"business_key": "...", "events": [...], "count": N}`。每个事件含 `ts` / `layer` / `component` / `event_type` / `payload` 字段。

### 7.3 摘要查询(summary)

```bash
curl "http://127.0.0.1:18084/v1/business-flows/$ENCODED/summary"
```

**返**:`{status, started_at, completed_at, total_duration_ms, event_count, layer_counts, interrupted_layer}`

### 7.4 会话查询(sessions)

```bash
curl "http://127.0.0.1:18084/v1/business-flows/$ENCODED/sessions"
```

**返**:该业务键下的所有 session_id 列表(支持 retry 场景)。

### 7.5 评估报告查询(evaluation)

```bash
curl "http://127.0.0.1:18084/v1/business-flows/$ENCODED/evaluation"
```

**返**:`{report: {window_seconds, total_flows, status_counts, completion_rate, interruption_heatmap, hints}}`。`hints` 是给 Optimize 维度的输入。

### 7.6 实时事件流(SSE)

```bash
timeout 5 curl -N "http://127.0.0.1:18084/v1/business-flows/$ENCODED/events/stream"
```

**返**:`data: {json}\n\n` 持续 5 秒。订阅期间该业务键的所有新事件实时推送。

### 7.7 Python API(直接读 SQLite 跑 Optimize)

如果需要在脚本里批量处理,直接读 SQLite + 调用 OBSTACK 的 Python 模块:

```python
import asyncio
import aiosqlite
from eaasp_l4_orchestration.flow_readers import build_default_layer_readers
from eaasp_l4_orchestration.flow_timeline import assemble_business_flow_summary
from eaasp_l4_orchestration.flow_evaluator import evaluate_business_flows
from eaasp_l4_orchestration.ab_router import choose_runtime, FlowMeta
from eaasp_common.business_flow import parse_business_key_header

key = parse_business_key_header("demo-sess-...|threshold-calibration|Transformer-...")

async def main():
    l4 = await aiosqlite.connect("data/v315-demo-${RUN_ID}/l4.db")
    l3 = await aiosqlite.connect("data/v315-demo-${RUN_ID}/l3.db")
    l2 = await aiosqlite.connect("data/v315-demo-${RUN_ID}/l2.db")
    readers = build_default_layer_readers(l4_conn=l4, l3_conn=l3, l2_conn=l2)
    summary = await assemble_business_flow_summary(key, layer_readers=readers)
    report = evaluate_business_flows([summary])
    meta = FlowMeta(business_object_id=key.business_object_id, runtime_id="grid-runtime")
    decision = choose_runtime(key.business_object_id, [(summary, meta)])
    print(decision)

asyncio.run(main())
```

### 7.8 CLI 子命令

```bash
# 装 venv 后(已预装)
tools/eaasp-cli-v2/.venv/bin/python -m eaasp_cli_v2.main flow timeline --key "$KEY"
tools/eaasp-cli-v2/.venv/bin/python -m eaasp_cli_v2.main flow summary --key "$KEY"
tools/eaasp-cli-v2/.venv/bin/python -m eaasp_cli_v2.main flow evaluate --key "$KEY"
tools/eaasp-cli-v2/.venv/bin/python -m eaasp_cli_v2.main flow watch --key "$KEY"  # 持续
```

---

## Ch8. 给 OBSTACK 加新数据源

本章教新人怎么把 OBSTACK 没接的某个表加进时间线聚合(比如将来 L0 / L5 加了表)。

### 8.1 什么时候需要加

OBSTACK 时间线聚合走的是**跨表 JOIN**(OBSTACK §3.8 设计决策)。如果某张新表里有 `business_key` 列,你想让它出现在时间线里,就加一个 LayerReader。

### 8.2 改哪几个文件

总共 4 个文件:

| 文件 | 改什么 |
|---|---|
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_readers.py` | 新增一个 `async def read_<layer>_<table>(conn, key)` 函数 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_readers.py` `build_default_layer_readers` | 新增一项 `"<layer>_<table>": reader_wrapper` |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/api.py` `lifespan` | 新增一项 DB 连接(如果新表在不同 DB 文件) |
| `tools/eaasp-l4-orchestration/tests/test_flow_readers.py` | 新增对应单测 |

### 8.3 函数模板

```python
async def read_my_new_table(
    conn: aiosqlite.Connection, key: BusinessKey,
) -> list[BusinessFlowEvent]:
    """读 my_new_table 行,tagged with business_key。
    
    复用 _row_to_event 做 row → event 映射(见 flow_timeline.py)。
    时间戳用 _to_epoch_ms 兼容 L3 TEXT datetime('now') 和 L4 INTEGER 两种格式。
    """
    wire = key.to_header()
    events: list[BusinessFlowEvent] = []
    async with conn.execute(
        "SELECT my_col, my_ts, my_payload FROM my_new_table "
        "WHERE business_key = ? ORDER BY my_ts",
        (wire,),
    ) as cur:
        async for row in cur:
            d = dict(row)
            d["my_ts"] = _to_epoch_ms(d.get("my_ts"))  # 如果是 L3 TEXT datetime
            events.append(
                _row_to_event(
                    d,
                    layer="L_NEW",
                    component="my_component",
                    ts_field="my_ts",
                ),
            )
    return events
```

### 8.4 注册到 lifespan

```python
# tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/api.py
async def _l_new_table_reader(key: BusinessKey) -> list[BusinessFlowEvent]:
    return await read_my_new_table(app.state.l_new_db_conn, key)

app.state.flow_layer_readers = build_default_layer_readers(
    l4_conn=app.state.l4_db_conn,
    l3_conn=app.state.l3_db_conn,
    l2_conn=app.state.l2_db_conn,
    l_new_conn=app.state.l_new_db_conn,  # 新增
)
# build_default_layer_readers 内新增:
# readers["L_NEW_my_table"] = _l_new_table_reader  # 如果新表叫 my_table
```

### 8.5 测试

```python
@pytest.mark.asyncio
async def test_read_my_new_table() -> None:
    conn = await _make_db(MY_NEW_TABLE_SCHEMA)
    wire = _key().to_header()
    await conn.execute(
        "INSERT INTO my_new_table (my_col, my_ts, my_payload, business_key) "
        "VALUES (?, ?, ?, ?)",
        ("v1", 1000, "{}", wire),
    )
    await conn.commit()
    events = await read_my_new_table(conn, _key())
    assert len(events) == 1
    assert events[0].layer == "L_NEW"
```

### 8.6 跑 demo 验证

```bash
bash scripts/v315-obstack-demo.sh
# 查 timeline 看新表事件是否出现
grep -c "L_NEW" .logs/v315-obstack-demo/${RUN_ID}/timeline.json
# 应 > 0
```

---

## Ch9. 加新的自动调优策略

本章教新人怎么新加一个 Optimize executor(类似 ab_router / alert_manager / resource_scheduler)。

### 9.1 什么时候需要加

OBSTACK 当前的 3 个执行器覆盖:

| 执行器 | 适用场景 |
|---|---|
| `ab_router.choose_runtime()` | 选 L1 runtime(完成率排序) |
| `alert_manager.fire_alerts()` | 把 hint 推到告警 sink |
| `resource_scheduler.reconcile_actions()` | scale-up / scale-down 决策 |

如果需要新的优化类型(如缓存预热 / 限流降级 / 路由权重调整),加新执行器。

### 9.2 改哪几个文件

| 文件 | 改什么 |
|---|---|
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/my_executor.py` (NEW) | 新执行器 |
| `tools/eaasp-l4-orchestration/tests/test_my_executor.py` (NEW) | 对应单测 |
| (可选) `tools/eaasp-cli-v2/src/eaasp_cli_v2/cmd_flow.py` | 新 CLI 子命令 |

### 9.3 函数模板

```python
"""My new Optimize executor — does X based on evaluator hints."""
from __future__ import annotations

from eaasp_l4_orchestration.flow_evaluator import FlowEvaluationReport

def my_optimize_action(report: FlowEvaluationReport, threshold: float = 0.5) -> list[MyAction]:
    """Pure function: takes report, returns list of actions.
    
    Same contract as ab_router / alert_manager / resource_scheduler:
    - 接收 FlowEvaluationReport
    - 产出 typed actions
    - 纯函数(无副作用),由调用方执行
    """
    actions: list[MyAction] = []
    for hint in report.hints:
        if hint.severity == "critical" and hint.metric == "my_metric":
            actions.append(MyAction(layer=hint.layer, ...))
    return actions


__all__ = ["MyAction", "my_optimize_action"]
```

### 9.4 测试模板

```python
from eaasp_l4_orchestration.flow_evaluator import FlowEvaluationReport, OptimizationHint
from eaasp_l4_orchestration.my_executor import my_optimize_action

def test_my_optimize_triggers_on_critical_hint() -> None:
    report = FlowEvaluationReport(
        window_seconds=3600,
        total_flows=10,
        status_counts={"failed": 3},
        completion_rate=0.7,
        interruption_heatmap={},
        hints=[
            OptimizationHint(layer="L1", metric="my_metric", severity="critical",
                             recommendation="...", evidence={}),
        ],
    )
    actions = my_optimize_action(report, threshold=0.5)
    assert len(actions) == 1
```

### 9.5 跑 demo 验证

新执行器加进 `scripts/v315-obstack-demo.sh` 的"Optimize executors" 步骤(脚本末尾的 Python heredoc)。运行后看输出确认 actions 列表。

---

## Ch10. 出问题怎么查

5 类常见故障 + 排查步骤。

### 10.1 timeline 空(永远返 `count: 0`)

**症状**:`curl /v1/business-flows/{key}/timeline` 返 `{events: [], count: 0}`。

**可能原因**:

1. **business_key 没传到表里**:检查 `sessions.business_key` 是否有值
   ```bash
   sqlite3 data/orchestration.db "SELECT session_id, business_key FROM sessions"
   ```
   如果 `business_key` 是 NULL,说明 L4 没接到 header(看 L4 server log)。

2. **LayerReader 没注册**:看 L4 startup log 有没有 `flow_layer_readers = build_default_layer_readers(...)`。如果有但 timeline 还空,说明 reader 没找到匹配行。

3. **业务键格式错**:L4 endpoint 收到坏格式会返 400,看 L4 log。

4. **跨层 DB 没接上**:如果 L3 或 L2 的 DB 文件路径错(改 init 后没重启),reader 会用 None conn,实际退化到 noop。检查 `app.state.l3_db_conn` 和 `app.state.l2_db_conn` 不为 None。

### 10.2 evaluate 失败(422 或 500)

**症状**:`/evaluation` 返 422 或 500。

**可能原因**:

1. **evaluate 内部错误**:看 L4 log 完整 stack trace,通常 SQL 错误(列名错 / 时间戳格式错)。
2. **report 序列化失败**:FlowEvaluationReport 的 Pydantic 模型改过但 `flow_api.py` 没跟。

### 10.3 ingest 报错(`/v1/events/ingest` 失败)

**症状**:`curl POST /v1/events/ingest` 返 500。

**可能原因**:

1. **session_id 不存在**:先创建 session 再 ingest。`POST /v1/sessions/create` 然后用返回的 session_id。
2. **payload JSON 不合法**:检查 event_type / payload 字段。

### 10.4 OTel 没数据(L1 metrics 全空)

**症状**:`handles.requests_total.add(1)` 调用后看不到 metric。

**可能原因**:

1. **init_observability 没调**:L1 binary 启动时检查 stdout log 有没有 `init_observability ... SdkMeterProvider`。
2. **InMemoryExporter 没读**:v3.15.5 用的是 InMemoryExporter,数据在内存里。要看 metric,得写集成测试(见 `crates/grid-runtime/src/observability/mod.rs` 7/7 tests)。
3. **生产 stdout 导出器还没接**:OBSTACK §0.2 标 deferred。v3.16+ 做。

### 10.5 dual-gate 红

**症状**:`make v3.10-spec-audit` 或 `make rbac-audit` 退出非零。

**可能原因**:

1. **spec-audit 红**:通常是新加文件没在 EAASP spec 矩阵里登记。改 `tools/eaasp-spec-alignment/`。
2. **rbac-audit 红**:通常是新加路由没在 `crates/grid-server/src/` 的 RBAC catalog 里登记。
3. **两个都红**:合并冲突或环境问题。看 stdout 详细错误。

---

*Part II(Ch6-Ch10)到此结束。下面进入 Part III(架构参考,改代码时翻)。*

### 10.6 grid-cli 看不到业务键

**症状**:`eaasp session show <session_id>` 输出里没有 `business_key` 字段。

**Phase 状态**:这是 **Phase B(路线图)落地前**的预期行为——`eaasp session` 子命令目前不展示业务键。

**临时 workaround**(Phase B 前):
```bash
# 直接从 L4 SQLite 查
sqlite3 data/v315-demo-${RUN_ID}/l4.db \
  "SELECT session_id, business_key, status FROM sessions WHERE session_id = '<session_id>'"
```

**Phase B 落地后**:`eaasp session show` 会原生输出 `business_key` + 时间线摘要。

### 10.7 grid-runtime OTel exporter 配置错

**症状**:OBSTACK demo 跑通,但 grid-runtime log 里看不到任何 OTel metric record 输出(应该是 `InMemoryExporter` 接收的,目前是 test-grade capture)。

**Phase 状态**:这是 **Phase E(路线图)落地前**的预期行为——`opentelemetry-stdout` 导出器 deferred v3.16。

**临时验证方式**(在 L1 集成测试里查 InMemoryExporter):
```rust
// crates/grid-runtime 内
use grid_runtime::observability::{init_observability, take_recorded_for_test};
init_observability(Some("stdout"));
handles.requests_total.add(1);
let recorded = take_recorded_for_test();
assert!(!recorded.is_empty());
```

**Phase E 落地后**:grid-runtime 启动时读 `EAASP_OTEL_EXPORTER` 环境变量,可选 `stdout` / `otlp` / `none`,导出到 stdout / OTLP collector。

### 10.8 grid-runtime 主动 emit 失败(Phase A 前)

**症状**:OBSTACK demo 跑完,但 timeline 只有 demo 脚本手工 ingest 的事件(PRE_TOOL_USE / POST_TOOL_USE 等),没有 grid-runtime 真实 agent loop 的事件。

**Phase 状态**:这是 **Phase A(路线图)落地前**的预期行为——grid-runtime agent loop 主体不主动 emit OBSTACK 事件,OBSTACK 数据靠外部 demo 脚本 ingest。

**临时 workaround**(Phase A 前):OBSTACK demo 脚本用 5 个手工 ingest 事件模拟 grid-runtime agent loop 行为(见 `scripts/v315-obstack-demo.sh` step 4)。

**Phase A 落地后**:grid-runtime agent loop 每个 tool call / LLM call / hook 自动 emit OBSTACK event,无需外部 ingest。

### 10.9 OBSTACK 路由被新组件覆盖

**症状**:`make rbac-audit` 红,新加的 HTTP 路由没登记到 RBAC catalog。

**Phase 状态**:任何新加 OBSTACK 端点的常见问题。

**修复**:
- 检查 `crates/grid-server/src/` 的路由 catalog 文件
- 新路由必须 `@app.post("/v1/business-flows/{key}/...")` 这种风格 + 在 catalog 里登记
- 跑 `make rbac-audit` 验证

### 10.10 web-platform dashboard 不接 OBSTACK

**症状**:打开 web-platform dashboard 看不到任何 OBSTACK 实时数据(业务流列表、时间线)。

**Phase 状态**:Phase C(路线图)落地前的预期行为——web-platform 当前 OBSTACK 集成未完成。

**临时 workaround**(Phase C 前):
- 直接 curl L4 OBSTACK REST 端点看数据(见 Ch7)
- 用 `eaasp flow` 子命令查 CLI 视角

**Phase C 落地后**:`/flows` + `/flows/:key` + `/flows/:key/optimize` 路由 + SSE 实时推数据(见 Ch14.3 Phase C)。

## Ch11. 设计决策 (ADR 引用)

OBSTACK **不自创 ADR**。它站在已有 ADR 的肩上,引用而非重新发明。本章列出每个 OBSTACK 关键设计决策对应的 ADR + 当时的选择理由。

| OBSTACK 设计决策 | 引用的 ADR | 当时的选择理由 |
|---|---|---|
| **engine / data-integration 双轴模型**(OBSTACK 跨层代码必须走 engine 轴) | [ADR-V2-024](../adrs/ADR-V2-024-phase4-product-scope-decision.md) | 双轴模型替代 Leg A/B 二元框架 — engine 轴共享,data 轴独立产品。OBSTACK 是 engine 轴能力。 |
| **OBSTACK 不引入新的审计 / 事件表**(OBSTACK §3.8 时间线存储决策) | (OBSTACK 设计决策,无 ADR) | 避免 audit complexity 加剧 — 直接用现有表的 `business_key` 列做 JOIN。 |
| **业务键采用 `(session_id, skill_id, business_object_id)` 三元组** | (OBSTACK 设计决策,无 ADR) | 三个维度不可压缩 — session 区分会话,skill 区分能力,object 区分业务对象。 |
| **业务键是选填,不是必填**(老 RPC 客户端不带也能用) | (OBSTACK 设计决策,无 ADR) | proto3 兼容,字段 100 缺省值是 empty,老 RPC 不受影响。 |
| **业务流 SSE 是新通道,不复用 L4 Event Room** | (OBSTACK 设计决策,无 ADR) | 生命周期不同 — Event Room 是单 session 事件,业务流是跨 session / 跨调用的同一业务对象事件。 |
| **业务流达成率窗口默认 1h** | (OBSTACK 设计决策,无 ADR) | 平衡响应速度与样本量。 |
| **OPA sidecar 拓扑** | [ADR-V2-034](../adrs/ADR-V2-034-opa-backend-deployment-topology.md) | sidecar 部署 + in-repo Rego 模板 + 用户包原子化 + 失败时 fail-closed。OBSTACK Optimize 维度的 resource_scheduler 读 OPA metrics。 |
| **A2A Router + ReviewSet 冲突检测** | [ADR-V2-035](../adrs/ADR-V2-035-a2a-router-conflict-detection.md) | OBSTACK Optimize 维度的 hint 输入之一。 |
| **strict-by-default 配置验证** | [ADR-V2-028](../adrs/ADR-V2-028-strict-config-validation.md) | L3/L4 strict-by-default 行为,fail-closed 错误抛出 — OBSTACK 跨层 ingest 路径依赖 strict-by-default 不退化。 |

---

## Ch12. 文件级触点索引

本章列**每个被 OBSTACK 触及的文件** + 它做什么。改 OBSTACK 时代码要碰哪里一目了然。

### 12.1 L0 (proto 层)

| 文件 | OBSTACK 触点 |
|---|---|
| `proto/eaasp/runtime/v2/common.proto` | `message BusinessKey { ... }`(line 179-183) |
| `proto/eaasp/runtime/v2/runtime.proto` | 21 个 RPC 加 `BusinessKey business_key = 100` 字段 |
| `proto/eaasp/runtime/v2/hook.proto` | 4 个 hook 加 `BusinessKey business_key = 100` 字段 |

### 12.2 L1 (Rust, grid-runtime)

| 文件 | OBSTACK 触点 |
|---|---|
| `crates/grid-runtime/src/business_flow.rs` | `BusinessKey` struct + `BusinessKeyError` + parse/serialize + tracing::Span 字段 |
| `crates/grid-runtime/src/observability/mod.rs` | OTel SDK wiring(SdkMeterProvider + PeriodicReader + InMemoryExporter)+ 7 个 metric |
| `crates/grid-runtime/src/observability/{mod.rs → 5 metric name constants}` | `l1.runtime.requests.total` 等命名规范 |
| `crates/grid-runtime/src/harness.rs` | 调 `init_observability("stdout")` 启动 OTel SDK |
| `crates/grid-runtime/src/lib.rs` | mod 声明:`business_flow` + `observability` |

### 12.3 L2 (Python, eaasp-l2-memory-engine)

| 文件 | OBSTACK 触点 |
|---|---|
| `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/db.py` | `_add_business_key_column(path, table)` 迁移(`memory_files` + `anchors`) |
| `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/api.py` | FastAPI middleware 抽 `X-Business-Key` header → 落 `memory_files.business_key` |
| `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/observability.py` | OTel mirror(`l2.memory.*` metric) |
| (L2 调用方) `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_readers.py` | `read_l2_memory_files()` 读 memory_files |

### 12.4 L3 (Python, eaasp-l3-governance)

| 文件 | OBSTACK 触点 |
|---|---|
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/db.py` | `_add_business_key_column(path, table)` 迁移(`governance_decisions` + `telemetry_events`) |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/api.py` | `/v1/evaluate` 抽 `X-Business-Key` header → 落 `governance_decisions.business_key` |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/observability.py` | OTel mirror(`l3.*` metric) |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/audit.py` | `record_governance_decision(..., business_key=...)` 把 business_key 写 INSERT |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/policy_engine.py` | `evaluate_gate(..., business_key=...)` + `evaluate_with_opa(..., business_key=...)` |
| (L3 调用方) `flow_readers.py` | `read_l3_governance_decisions()` 读 governance_decisions + `read_l3_telemetry_events()` |

### 12.5 L4 (Python, eaasp-l4-orchestration)

| 文件 | OBSTACK 触点 |
|---|---|
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/api.py` | `/v1/sessions/create` + `/v1/intents/dispatch` 抽 `X-Business-Key`;`lifespan` 开 L4/L3/L2 DB 连接 + 注册 `flow_layer_readers` |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/db.py` | `_V315_BUSINESS_KEY_COLUMNS`(sessions + event_room_events) |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/session_orchestrator.py` | `create_session(..., business_key=...)` 落 `sessions.business_key` |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_timeline.py` | `BusinessFlowEvent` 模型 + `LayerReader` 类型 + 聚合器 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_readers.py` | 5 个 reader + `build_default_layer_readers()` 工厂 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_sse.py` | `FlowEventBus` + SSE 通道 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_api.py` | 4 个 REST 端点 + `/sessions` 端点 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/flow_evaluator.py` | `evaluate_business_flows()` + `FlowEvaluationReport` |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/ab_router.py` | Optimize: A/B 路由 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/alert_manager.py` | Optimize: 告警 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/resource_scheduler.py` | Optimize: 资源调度 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/observability.py` | OTel mirror(`l4.*` metric) |

### 12.6 CLI (`tools/eaasp-cli-v2`)

| 文件 | OBSTACK 触点 |
|---|---|
| `tools/eaasp-cli-v2/src/eaasp_cli_v2/main.py` | 注册 `cmd_flow` typer app |
| `tools/eaasp-cli-v2/src/eaasp_cli_v2/cmd_flow.py` | `eaasp flow timeline/summary/evaluate/watch` 4 个子命令 |

### 12.7 公共模块(`tools/eaasp-common`)

| 文件 | OBSTACK 触点 |
|---|---|
| `tools/eaasp-common/src/eaasp_common/business_flow.py` | `BusinessKey` dataclass + `parse_business_key_header` / `serialize_business_key` + `BusinessFlowContext` contextvar + FastAPI dependency `require_business_key_from_request` |

### 12.8 脚本

| 文件 | OBSTACK 触点 |
|---|---|
| `scripts/v315-walk-services.sh` | 启动 5 服务 + L1 grid-runtime(`V315_DEMO_DATA_DIR` 支持 per-run 隔离) |
| `scripts/v315-obstack-demo.sh` | 跑 11 步 OBSTACK 实例演示(约 250 行) |

### 12.9 文档

| 文件 | OBSTACK 触点 |
|---|---|
| `docs/design/EAASP/OBSTACK_DESIGN.md` | 权威设计文档(OBSTACK §0-§9) |
| `docs/design/EAASP/OBSTACK_INDEX.md` | 主题索引(§0 / §3 / §4 / §5 / §7 跳转入口) |
| `docs/design/EAASP/OBSTACK_HANDBOOK.md` | 本手册(执行手册,Ch0-Ch13 + Refs) |
| `docs/status/PRODUCTION_USABILITY_2026-08-02-obstack-demo.md` | 实例演示 walkthrough 证据 |
| `docs/status/PRODUCTION_USABILITY_2026-08-02-walk.md` | v3.15.5 早一轮 walkthrough(空 wire-format round-trip) |
| `docs/status/JOURNAL.md` | 每次 commit 的 event log |
| `docs/status/RESUME-NEXT-SESSION.md` | session 接力 baton |

---

## Ch13. 维护手册

### 13.1 何时更新哪个文件

| 改动类型 | 更新文件 |
|---|---|
| 修了 OBSTACK bug | `docs/status/JOURNAL.md`(append 一行)+ commit message |
| 加了新的 OBSTACK 子能力(例:V315-L1-OTEL-FULL-01 加了 L1 OTel SDK) | `docs/design/EAASP/OBSTACK_DESIGN.md §0.1` + `§0.2`(更新闭环率)+ `docs/status/JOURNAL.md` |
| 加了新的 LayerReader(新表) | `docs/design/EAASP/OBSTACK_HANDBOOK.md Ch8`(本手册)+ 内部 doc 不变(架构参考不需要每次更新) |
| 加了新的 ADR | `docs/design/EAASP/adrs/ADR-V2-XXX-...md` + `OBSTACK_HANDBOOK.md Ch11` 加一行引用 |
| 改了 OTel 命名规范(例:`l1.runtime.*` 改成 `l1.rt.*`) | `OBSTACK_DESIGN.md §3.3` + 所有镜像模块(影响所有层) |
| 改了 dual-gate 的检查项 | `OBSTACK_DESIGN.md §0.3 Milestone Close Gate` + Makefile |

### 13.2 dual-gate 强制什么

两个 gate 任意一个失败,commit 不能合:

| Gate | 命令 | 检查内容 |
|---|---|---|
| spec-audit | `make v3.10-spec-audit` | EAASP 各层能力是否对齐 v3.10 spec 矩阵(38 行) |
| rbac-audit | `make rbac-audit` | L4 HTTP 路由是否完整登记到 RBAC catalog(134 条) |

**绕过 dual-gate** 不允许(OBSTACK §0.3 写明)。

### 13.3 加 sub-criterion 到 §0.1 的流程

每次新增 OBSTACK 子能力(例:V315-XXX-NNN),需要 5 步:

1. **改代码 + 加测试**(本批必跑:`make v3.10-spec-audit && make rbac-audit` 仍 PASS)
2. **改 `OBSTACK_DESIGN.md §0.1`** — 在对应维度下加一行(sub-criterion + state + commit + tests)
3. **改 `OBSTACK_DESIGN.md §0.2`** — 维度闭环率 +1(直到 100% / N/N)
4. **改 `OBSTACK_HANDBOOK.md`** — 对应章节补细节(例:加新 LayerReader 改 Ch8)
5. **commit** — message 必含 `feat(l4): ...` / `fix(l3): ...` 等 prefix + commit body 写 WHY(不写 WHAT,diff 已经告诉你 what)
6. **JOURNAL append** — 一行 ≤ 20 字(WHAT changed + WHY + commit hash)

### 13.4 何时重新跑 dual-gate

- 任何改 `crates/` / `tools/` / `lang/` 的 commit **都必须** 跑 dual-gate(本地预跑)
- 改了 spec 矩阵文件(spec-audit 的输入) → spec-audit 自动失效,必须修
- 改了 RBAC catalog 文件(rbac-audit 的输入) → rbac-audit 自动失效,必须修
- dual-gate 已在 `make` 顶层集成,跑 `make verify` 会一并跑

---

## Ch14. OBSTACK 的真正定位 + 未来路线图

Ch1–Ch13 讲了 OBSTACK **现在是什么、怎么用**。本章讲 **OBSTACK 应该是什么、接下来怎么走**——这是本手册最高一层视角,产品 / 架构师 / 想参与 OBSTACK 下一步演进的人都该读这一章。

### 14.1 OBSTACK 的根本定位:反盲盒

**一句话**:**OBSTACK 的根本目的是让任何 AI 任务成为可观察 / 可追踪 / 可评估 / 可优化的对象,不成为盲盒。**

企业敢不敢把核心业务交给 AI 智能体,关键不在于智能体能不能做对,而在**做错了能不能发现、能不能定位、能不能复盘、能不能优化**。没有可观测性的智能体 = 盲盒 = 企业不敢用。

OBSTACK 解决的就是这个问题。它不是一个"监控告警"工具(那是 Prometheus + Grafana 的事),它是**业务层的因果追踪 + 性能优化**层,锚定在"**一次用户请求**"这个业务单元上,纵向穿透每一层。

> **设计哲学**:OBSTACK 应当是 EAASP 平台**第一公民(first-class)**——任何新组件出生即接 OBSTACK,不是事后补。就像一个产品从一开始就接日志 SDK,而不是出 bug 后再补日志。

### 14.2 现状 vs 真正目标(差距分析)

对照 OBSTACK 的根本定位,现状(v3.15.5)与"第一公民"目标还有明显差距:

| 能力 | 现状 (v3.15.5) | 真正目标 (反盲盒) |
|---|---|---|
| **数据基础** | 5 个表 + 1 个 L0 proto 字段 + L1 OTel SDK 已就位 | ✅ 数据层闭环 |
| **REST API 暴露** | 4 个端点(`/timeline` `/summary` `/evaluation` `/events-stream`)+ 1 个 `/sessions` | ✅ API 闭环,但**端点都是手动调用**——还没成为开发者默认的诊断入口 |
| **CLI 接入** | `grid-cli` 5 个 subcommand 中只有 `eaasp flow` 真接 OBSTACK;其他 4 个 (`session`/`memory`/`skill`/`policy`) 看不到业务键 / 时间线 | ❌ **grid-cli 应天生具备 OBSTACK 入口**——`eaasp session list` 自动带 `business_key` 列,`eaasp skill promote` 显示该 skill 的业务流健康度 |
| **grid-runtime 接入** | L1 OTel mirror 是"外部镜像模块",`crates/grid-runtime/src/observability/mod.rs` 是独立 module,agent loop 主体不主动 emit 业务事件 | ❌ **grid-runtime 应自带 OBSTACK**——agent loop 每个 tool call 应自动 emit OBSTACK event (带 business_key),hook envelope 默认 emit PreToolUse/PostToolUse OBSTACK event |
| **Dashboard 可视化** | web-platform 有 `RecentSessions.tsx` + `StatsCard.tsx`,但未确认接 OBSTACK REST;L5 Cowork UI 仍是 dormant | ❌ 需要业务流实时总览页 + 实时 SSE 推数据 |
| **tool 生态接入** | `grid-eval` / `grid-platform` / `web-platform` / `grid-desktop` 都没有 OBSTACK 入口 | ❌ OBSTACK 应是 grid-eval 的评估输入、grid-platform 多租户视图、web/desktop 的用户可见状态 |
| **生态高度集成** | OBSTACK 被动接收各层的数据;没有"主动驱动"的入口 | ❌ grid-runtime 应能 query OBSTACK 自身("我刚才跑了什么业务流")+ 让 agent 在 loop 中基于 OBSTACK 反馈调整行为 |

**核心差距**:目前 OBSTACK 是"事后查询"的工具,而真正目标是"贯穿每个组件的第一公民"—— grid-cli / grid-runtime / grid-eval / grid-platform / web / desktop 都该**天生具备 OBSTACK 视角**,而不是开发者额外调用 OBSTACK API。

### 14.3 路线图:5 个阶段


### 14.3 路线图:5 个阶段(Phase C 入口先行)

**层次结构(关键)**:

```
Phase C (入口点)   ← 第一优先级,先把"全局可观察性"做出来
   ↓ 填充数据
Phase A (运行时)    ← grid-runtime 真实数据填到 dashboard
Phase B (CLI)       ← grid-cli 也接 OBSTACK,补全使用面
   ↓ 深度补全
Phase D (多租户)    ← 平台层隔离 + 工具生态接入
Phase E (主动驱动)  ← grid-runtime 主动 query OBSTACK 自我感知
```

**为什么不先做 Phase C(而不是 Phase A 或 B)**:

**核心问题**:现在 OBSTACK 数据基本 ready,但**没有一个全局入口让运营者"一开始就能看到全貌"**——开发者必须自己 `curl` 或者 `eaasp flow timeline --key <x>`,且只能看到单个业务流。

如果直接做 Phase A(grid-runtime 真实数据):数据填进了 L4 SQLite,但**没有 dashboard 看**—— 还是盲盒。

如果先做 Phase C:**先把 dashboard 入口做出来(全局总览 + 多维过滤),开发者打开 web 就能看到所有业务流的状态**——即使后台数据还是 demo 阶段的占位事件,运营者**已经能全局掌握可观察性**。然后 Phase A/B 往这个 dashboard 填真实数据,Phase D/E 深度补全。

**这意味着 Phase C 不是一个"中期"任务,而是 Phase 0**——任何 Phase A/B 的开发,运营者都能立即在 dashboard 看到效果。

#### Phase C — Dashboard + API 全景化(Phase 0,首位实现)

**目标**:**一开始就能全局掌握可观察性**——打开浏览器看到所有业务流的实时状态,不需要查命令行。

**为什么是入口**:Phase C 提供 dashboard 总览页 + 多维过滤 + 实时 SSE 推数据,这是"反盲盒"的可见部分。Phase A/B 在下面填运行时数据,Phase D/E 深度补全。

**交付物(逐步实现,先核心后完整)**:

**Phase C.0 — 最小可用 dashboard(进入条件)**:
- web-platform 新增 `/flows` 路由 — 业务流总览列表(活跃数、成功率、平均时长)
- 列表数据源:L4 `/v1/business-flows/{key}/summary` 聚合 + `/v1/business-flows/{key}/sessions`
- 时间线数据源:L4 `/v1/business-flows/{key}/timeline`
- 实时推数据:L4 `/v1/business-flows/{key}/events/stream`(SSE)

**Phase C.1 — 多维过滤 + drill-down**:
- 按 `business_object_id` 过滤(看某个变压器的所有业务流)
- 按 `status` 过滤(只看失败 / 中断的)
- 按时间窗口(过去 1h / 24h / 7d)
- 点击某条流进入 `/flows/:key` 详情页,显示时间线 + 评估报告

**Phase C.2 — Optimize 入口**:
- `/flows/:key/optimize` 路由,显示 Optimize executor 输出(A/B 路由推荐 / 资源调度建议)
- 运维人员能据此手动调整

**Phase C.3 — L5 Cowork UI 真正落地**:
- 4 卡视图(事件 / 证据 / 动作 / 审批)从 OBSTACK REST 拉数据
- L5 投影真正可用

**Phase C.4 — 实时告警看板**:
- `/alerts` 路由,显示 fire_alerts() 输出的活跃告警
- 按 severity 排序(info / warn / critical)
- 跳转到对应业务流详情

**Phase C.5 — 多维统计**:
- `/stats` 路由,按 `business_object_id` / `runtime_id` / `skill_id` 聚合
- 用于看"哪些设备的失败率高 / 哪些 skill 的成功率高"

**验收标准(Phase C.0 即可满足"一开始就能全局掌握")**:
- 打开 `http://localhost:5180/flows` 看到业务流总览列表(可以暂用 demo 数据)
- 点击某条流看到时间线
- 时间线 SSE 实时显示新事件,无需手动刷新
- 不需要查 curl / CLI

**预估工作量**:中(UI 工作为主,L4 REST 已就位,只需前端集成)

#### Phase A — grid-runtime 原生 OBSTACK(数据填充阶段)

**问题**:OBSTACK demo 跑完,但 timeline 只有 demo 脚本手工 ingest 的事件(PRE_TOOL_USE / POST_TOOL_USE 等),没有 grid-runtime 真实 agent loop 的事件。

**目标**:grid-runtime agent loop 主体**主动 emit OBSTACK 事件**——不需要外部 ingest 脚本来填充。

**交付物**:
- grid-runtime `harness.rs` 在每个 tool call 前/后自动 emit `l1.runtime.tool.total{tool_name, status}` + `l1.runtime.tool.duration`
- 每个 LLM call 自动 emit `l1.runtime.llm.total{model, status}` + `l1.runtime.llm.duration`
- 每个 hook 执行自动 emit OBSTACK event
- 每个 business flow 完成自动 emit `l1.runtime.flow.outcome{business_object_id, status}`

**验证(跟 Phase C 联动)**:
- 跑一次真实 LLM-driven 业务,Phase C 的 dashboard 立即看到完整的 agent loop 轨迹(不是 demo 脚本塞的事件)
- 不再需要 `scripts/v315-obstack-demo.sh` 手工 ingest 5 个占位事件

**预估工作量**:中等(grid-runtime 是 Rust,改动需要 unit + integration test)

#### Phase B — grid-cli 全局接入 OBSTACK(数据填充阶段)

**问题**:grid-cli 5 个 subcommand 中,只有 `eaasp flow` 真接 OBSTACK。其他 4 个 (`session`/`memory`/`skill`/`policy`) 看不到业务键 / 时间线。

**目标**:**grid-cli 每个 subcommand 都天生具备 OBSTACK 视角**——开发者用 CLI 操作时,OBSTACK 信息自动可见。

**交付物**:
- `eaasp session list/show/events`:每个 session 自动带 `business_key` 列、status、duration
- `eaasp session run`:实时打印 OBSTACK 时间线事件流
- `eaasp memory search/read`:结果列表每行带 `business_key` 标签
- `eaasp skill submit/promote/list`:显示每个 skill 的业务流统计
- `eaasp policy list`:显示每个 hook 的实时决策速率
- (新) `eaasp flow list` / `eaasp flow top-failed` / `eaasp flow top-slow`

**验证(跟 Phase C 互补)**:
- 运维者可以在 CLI 里查询,也可以在 web dashboard 里查询,两路都能看到 OBSTACK 数据

**预估工作量**:中等(grid-cli 是 Python typer,5 个 subcommand 每个加 OBSTACK 列)

#### Phase D — 工具生态补齐(深度补全)

**问题**:`grid-eval` / `grid-platform` / `web-platform` / `grid-desktop` 还没有把 OBSTACK 当成默认诊断输入。

**目标**:OBSTACK 是 EAASP 其他组件的**默认诊断输入**——评估、多租户、状态栏都从 OBSTACK 拉数据。

**交付物**:
- `grid-eval` 默认接 OBSTACK — 评估 baseline 用 `evaluate_business_flows()`,而不是手写指标
- `grid-platform` 多租户视图下,业务键带 `tenant_id` 隔离
- `web-platform` / `grid-desktop` 的状态栏显示"过去 1h 业务流成功率"+ "活跃 session 数"
- `eaasp marketplace` 显示每个上架 skill 的业务流健康度

**预估工作量**:中等(每个组件加 OBSTACK 入口是局部改动)

#### Phase E — grid-runtime 主动驱动 OBSTACK(深度补全,远期)

**问题**:OBSTACK 是"查询工具",grid-runtime 跑完一轮后,**自己都不知道**这次跑得怎么样。

**目标**:**grid-runtime 主动 query OBSTACK,用 OBSTACK 反馈调整 agent 行为**——让 AI 任务"自我感知 + 自我优化"。

**交付物**:
- grid-runtime 启动时拉 OTel collector 配置(不止 InMemoryExporter),接 OpenTelemetry Collector / Jaeger / Tempo 生产链路
- grid-runtime stdout 导出器生产化(OBSTACK §0.2 标 deferred v3.16)
- grid-runtime `record_business_flow_outcome(key, status)` API — agent loop 跑完后主动 emit 完整业务流结果
- grid-runtime "我刚才跑得怎么样" 内省 API — 跑完后调 OBSTACK `/evaluation` 自我评估
- 业务流达成率自调优 — grid-runtime 根据 `choose_runtime()` 输出自动重试失败的业务流

**预估工作量**:大(需要 grid-runtime 的"自省 + 自调"逻辑设计)

### 14.4 角色 → 路线图对应章节

| 你是 | 关心哪个阶段 |
|---|---|
| 产品 / 售前 / 客户对接 | Ch14.1 + Ch14.2(为什么 OBSTACK 是反盲盒核心)— 给客户讲故事 |
| 新加入的工程师 | Ch14.2(看现状)+ Phase C(挑一个具体的 dashboard 组件开始贡献)— 入口低、可见性高 |
| EAASP 平台架构师 | Ch14.2(差距分析)+ Ch14.3 层次结构图(Phase C 入口先行)— 排优先级 |
| 想参与 OBSTACK 演进 | Ch14.5(下面) — 看怎么贡献 |
| 关心 web / dashboard 的工程师 | **Phase C**(你的活最多)— 把 dashboard 全景化做出来 |
| 关心 grid-cli / grid-runtime 的工程师 | Phase A + Phase B(数据填充)— 跟 Phase C 联动 |
| 关注运行时智能体自省 | Phase E(远期) |

### 14.5 怎么贡献

OBSTACK 演进目前是**开放贡献**状态(2026-08-02 起)。贡献流程:

1. **挑一个 phase**(看 Ch14.3 路线图,优先选 Phase C — 入口可见、立刻出效果)
2. **跟团队对齐范围** — 在 `docs/status/JOURNAL.md` 末尾加一行 "Phase X start" + commit 计划
3. **按 OBSTACK 现有 commit 节奏**:原子 commit + dual-gate 必须绿 + JOURNAL append
4. **OBSTACK_DESIGN.md §0.1 + §0.2** 同步更新(子能力 + 闭环率 +1)
5. **本手册对应章节补强**(本手册 Ch8/Ch9/Ch11/Ch12 是开发者入口)

### 14.6 跟 v3.16+ 候选的对接

`docs/status/RESUME-NEXT-SESSION.md` 列出的 v3.16 候选中,有 3 个跟 OBSTACK 路线图直接对接:

| v3.16 候选 | 对接 Phase |
|---|---|
| **opentelemetry-stdout exporter**(V315-L1-OTEL-STDOUT-01) | Phase E 的第一步(L1 生产化) |
| **grid-server multi-user (data/integration axis)** | Phase D(grid-platform 多租户视角) |
| **CLI walkthrough replay**(V315-WALK-01.sustained) | Phase B 的入门 demo(grid-cli OBSTACK 接入的 smoke test) |

**重点**:虽然 Phase C 在 OBSTACK 路线图里是 Phase 0,但**它也是 v3.16 的高优先级候选** — 如果团队有人力,v3.16 应优先做 Phase C(全局 dashboard + 多维过滤),让运营者立即能看到 v3.15.5 落地的 OBSTACK 数据。

---


### 14.4 角色 → 路线图对应章节

| 你是 | 关心哪个阶段 |
|---|---|
| 产品 / 售前 / 客户对接 | Ch14.1 + Ch14.2(为什么 OBSTACK 是反盲盒核心)— 给客户讲故事 |
| 新加入的工程师 | Ch14.2(看现状)+ 你要修的阶段(挑一个 phase 开始贡献) |
| EAASP 平台架构师 | Ch14.2(差距分析)+ Ch14.3(路线图)— 排优先级 |
| 想参与 OBSTACK 演进 | Ch14.5(下面) — 看怎么贡献 |
| 关心 grid-cli / grid-runtime 的工程师 | Phase A + Phase B + Phase E — 你的活最多 |
| 关心 web / dashboard 的工程师 | Phase C — 你的活最多 |

### 14.5 怎么贡献

OBSTACK 演进目前是**开放贡献**状态(2026-08-02 起)。贡献流程:

1. **挑一个 phase**(看 Ch14.3 路线图,挑你最熟的)
2. **跟团队对齐范围** — 在 `docs/status/JOURNAL.md` 末尾加一行 "Phase X start" + commit 计划
3. **按 OBSTACK 现有 commit 节奏**:原子 commit + dual-gate 必须绿 + JOURNAL append
4. **OBSTACK_DESIGN.md §0.1 + §0.2** 同步更新(子能力 + 闭环率 +1)
5. **本手册对应章节补强**(本手册 Ch8/Ch9/Ch11/Ch12 是开发者入口)

### 14.6 跟 v3.16+ 候选的对接

`docs/status/RESUME-NEXT-SESSION.md` 列出的 v3.16 候选中,有 3 个跟 OBSTACK 路线图直接对接:

| v3.16 候选 | 对接 Phase |
|---|---|
| **opentelemetry-stdout exporter**(V315-L1-OTEL-STDOUT-01) | Phase E 的第一步(L1 生产化) |
| **grid-server multi-user (data/integration axis)** | Phase D(grid-platform 多租户视角) |
| **CLI walkthrough replay**(V315-WALK-01.sustained) | Phase B 的入门 demo(grid-cli OBSTACK 接入的 smoke test) |

---

*手册 Part III(Ch11-Ch13 + Ch14)到此结束。下面是 Refs(已更新,见末尾)。*
## Refs

### 权威文档

| 文档 | 何时读 |
|---|---|
| [OBSTACK_DESIGN.md](OBSTACK_DESIGN.md) | 权威设计文档(§0-§9);改 OBSTACK 前必读 §3(架构)+ §4(集成点) |
| [OBSTACK_INDEX.md](OBSTACK_INDEX.md) | 主题索引;按主题跳转 §0 / §3 / §4 / §5 |
| [OBSTACK_HANDBOOK.md](OBSTACK_HANDBOOK.md) | 本手册(执行手册);Ch0-Ch13 + Refs |

### 工作过程文档

| 文档 | 何时读 |
|---|---|
| [docs/status/JOURNAL.md](../../status/JOURNAL.md) | append-only event log;每次 commit 的 commit-hash + 一句话描述 |
| [docs/status/RESUME-NEXT-SESSION.md](../../status/RESUME-NEXT-SESSION.md) | session 接力 baton;上次做到哪 + 下次从哪开始 |
| [docs/status/CURRENT-STATE.md](../../status/CURRENT-STATE.md) | 当前结构快照 |
| [docs/status/PRODUCTION_USABILITY_2026-08-02-obstack-demo.md](../../status/PRODUCTION_USABILITY_2026-08-02-obstack-demo.md) | v3.15.5 实例演示 walkthrough(OBSTACK 100% 验证证据) |
| [docs/status/PRODUCTION_USABILITY_2026-08-02-walk.md](../../status/PRODUCTION_USABILITY_2026-08-02-walk.md) | v3.15.5 早一轮(空 wire-format round-trip)— 历史快照 |

### ADR 索引

| ADR | 与 OBSTACK 关系 |
|---|---|
| [ADR-V2-024](../adrs/ADR-V2-024-phase4-product-scope-decision.md) | 双轴模型(engine vs data/integration)— OBSTACK 跨层代码走 engine 轴 |
| [ADR-V2-028](../adrs/ADR-V2-028-strict-config-validation.md) | strict-by-default 配置验证 — L3/L4 fail-closed |
| [ADR-V2-029](../adrs/ADR-V2-029-engine-data-integration-boundary.md) | crate-level 双轴 enforce |
| [ADR-V2-034](../adrs/ADR-V2-034-opa-backend-deployment-topology.md) | OPA sidecar 拓扑 — OBSTACK Optimize resource_scheduler 读 OPA metrics |
| [ADR-V2-035](../adrs/ADR-V2-035-a2a-router-conflict-detection.md) | A2A Router + ReviewSet — OBSTACK Optimize hint 来源 |

### 相关文档

| 文档 | 何时读 |
|---|---|
| [EAASP_v2_0_EVOLUTION_PATH.md](../EAASP_v2_0_EVOLUTION_PATH.md) | 8 Phase 演化路径;OBSTACK 在 v3.15 落地 |
| [EAASP_v2_0_MVP_SCOPE.md](../EAASP_v2_0_MVP_SCOPE.md) | MVP 范围;OBSTACK 不在 MVP 范围(平台扩展) |
| [L1_RUNTIME_ADAPTATION_GUIDE.md](../L1_RUNTIME_ADAPTATION_GUIDE.md) | L1 runtime 适配指南;OBSTACK 跨层 hook 协议在此 |

### 仓库级

| 文档 | 何时读 |
|---|---|
| [CLAUDE.md](../../../CLAUDE.md) | 仓库全局约定(L1 路径 + build 命令 + commit 规范) |
| `tools/eaasp-spec-alignment/` | spec-audit 工具源码 |
| `crates/grid-server/src/bin/route-auditor.rs` | rbac-audit 工具源码 |

---

*手册完。共 Ch0-Ch13 + Refs,覆盖 EAASP 平台概览 / OBSTACK 5 个维度 / 业务键跨层传播 / 5 大 OBSTACK 文件 / 历史背景 / 跑演示 / 查业务流 / 加数据源 / 加调优策略 / 排错 / 设计决策 / 文件索引 / 维护手册。*
