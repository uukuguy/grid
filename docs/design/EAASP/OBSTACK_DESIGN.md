# EAASP 平台级 Observe / Trace / Evaluate / Optimize 技术栈

**日期**: 2026-08-01（第二次方向校准：增 §3.1 业务流主线）
**阶段**: v3.15 候选（跨 L0–L5 平台层）
**主题**: EAASP 仿真环境层级关系复杂（L0/L1/L2/L3/L4/L5），需要**稳定可靠**的生产级四项保证能力，且必须**纵向跨层业务流绑定**（不是各层散装）
**Status**: Design locked（基于 2026-08-01 session 对 v3.11/v3.12/v3.13/v3.14 跨层审计 + 用户对"纵向业务流绑定"反馈）
**Author**: Jiangwen Su + Claude
**预计周期**: 6 phases (v3.15.0–v3.15.5)
**预计任务量**: 24-32 REQ-IDs / 6 categories

---

## 1. Context / 背景

### 1.1 关键设计原则（v3.15 第二次方向校准 — 2026-08-01）

> "平台级观察、跟踪、评估、优化能力不应该仅是各层各点散装的功能，更关键的是**纵向跨层的业务数据流相绑定的持续观察跟踪等能力**。"

v3.15 的**真正核心**不是各层各加 metrics / trace —— 那是**散装**。核心是：

- **业务流 (Business Flow)**：一次端到端业务请求的完整生命周期（用户提示词 → skill 执行 → tool chain → 治理决策 → 状态变更 → 业务结果）
- **业务主键 (Business Key)**：`(session_id, skill_id, business_object_id)` —— 把所有跨层事件绑到一条流
- **纵向绑定**：各层 OTel 事件、SSE 事件、数据库行**都携带 business_key**，可按业务主键聚合为完整时间线
- **持续观察**：业务流状态可被持续订阅（SSE 业务流），不是"一次查询后查不到"

**两套并行 ID**：

| ID 类型 | 作用层 | 用途 |
|---------|-------|------|
| `trace_id` (W3C) | L0–L5 技术层 | 一次调用的全链路追踪（Otel 标准） |
| `business_key` | L0–L5 业务层 | 一次业务请求的所有跨层事件聚合（平台级抽象） |

两套 ID 互相对照：trace_id 解决"这次请求在某层慢了"，business_key 解决"这次业务请求的中断点在哪"。

### 1.2 EAASP 分层

```
L0 Protocol       (proto/eaasp/runtime/v2/*.proto, 21 RPC)
L1 Runtime        (7 adapters: grid-runtime + claude-code/goose/nanobot/pydantic-ai/claw-code/ccb)
L2 Memory & Skills (eaasp-l2-memory-engine + eaasp-skill-registry + eaasp-mcp-orchestrator)
L3 Governance     (eaasp-l3-governance + OPA sidecar ADR-V2-034)
L4 Orchestration  (eaasp-l4-orchestration + Event Room + A2A + multi-session)
L5 UI             (eaasp-l5-cowork + eaasp-ecosystem/marketplace)
```

### 1.3 当前跨层能力现状（2026-08-01 审计）

| 能力 | L1 Rust | L2 Python | L3 Python | L4 Python | L5 UI | 跨层 |
|------|---------|-----------|-----------|-----------|-------|------|
| **Observe (metrics)** | ⚠️ tracing crate, 无 OTel | ❌ 无 | ✅ L3 OTel baseline (v3.15.0 SHIPPED) | ⚠️ L4 SSE event 类型 5 | ❌ | ⚠️ 散装 |
| **Trace (技术)** | ❌ 无 traceparent 注入 | ❌ DB 无 trace 列 | ⚠️ 单 request_id 5 阶段 (v3.11.2) | ⚠️ event_room_events 缺 trace | ❌ | ❌ 无全链路 |
| **Business Flow (业务)** | ❌ 无 business_key | ❌ | ❌ | ❌ | ❌ | ❌ **完全缺失** |
| **Evaluate (SLA)** | ❌ 无基线 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Optimize** | ❌ 无 A/B 路由 | ❌ | ❌ shadow→enforce 手动 | ❌ | ❌ | ❌ |

**关键差距**：business flow 列完全为 ❌——这是 v3.15 的核心新增。

---

## 2. Scope Boundaries / 范围边界

### 2.1 In Scope（重排后 — 业务流为主线）

| Phase | 主题 | 核心交付 | 跨层 |
|-------|------|---------|------|
| **v3.15.0** ✅ | 各层 OTel metrics 底座 | 各层 `observability.py` (默认 no-op + 可选 stdout) | L1/L2/L3/L4 |
| **v3.15.1** | **业务流标识与跨层绑定** | `business_flow.py` 核心库 + L0 metadata 透传 + L1-L5 events 加 `business_key` 列 | L0–L5 |
| **v3.15.2** | **业务流时间线聚合** | `flow_timeline.py` 按 business_key 聚合跨层事件 + 业务流视图 API | L4 (聚合) + L1/L2/L3 (源头) |
| **v3.15.3** | **业务流持续订阅** | SSE 业务流事件流（区别于 L4 Event Room 一次性） + L5 业务流 UI | L4 + L5 |
| **v3.15.4** | **业务流评估与优化** | 业务流达成率 + 中断点分析 + 跨层联合优化建议 | L1–L5 |
| **v3.15.5** | Live walkthrough + tag v3.15 | 真实跑通 + spec-audit + rbac-audit + tag | 全部 |

### 2.2 Out of Scope（v3.16+）

| Deferred | 内容 | 归属 |
|----------|------|------|
| 完整 Grafana dashboard | 可视化 Web 面板 | v3.16 |
| 跨 cluster 业务流聚合 | 多 L4 实例的 flow 合并 | v3.16 |
| Auto-scaling | 基于业务流指标自动扩缩 | v3.17+ |
| Cost optimization | LLM token 成本分析 | v3.17+ |
| 业务 KPI 看板 | 业务效果指标 | v3.16+ 业务层 |

### 2.3 关键非 goal

- **不**替换 L3 OPA — 只补 L3 之上的跨层能力
- **不**强加 OTel collector — 默认 stdout
- **不**改 EAASP L1 contract 21 RPC
- **不**在 v3.15 做业务 KPI 看板 — 仅提供数据 + API

---

## 3. Architecture / 架构

### 3.1 业务流 (Business Flow) 概念

**业务流定义**：

```
BusinessFlow := {
  business_key:  (session_id, skill_id, business_object_id),
  trace_id:      W3C trace_id (关联技术层),
  started_at:    ISO-8601 timestamp,
  completed_at:  ISO-8601 timestamp | null,
  status:        running | succeeded | failed | aborted,
  events:        [BusinessFlowEvent, ...]   # 按时间序
  layer_timeline: { L0: [...], L1: [...], ..., L5: [...] }
}

BusinessFlowEvent := {
  ts:            ISO-8601,
  layer:         L0|L1|L2|L3|L4|L5,
  component:     runtime|governance|memory|orchestration|ui|...,
  event_type:    request.start | request.end | tool.invoke |
                 decision.allow | decision.deny | memory.write |
                 sse.chunk | ...,
  payload:       dict (event-specific),
  duration_ms:   int | null,
  error:         string | null,
  trace_id:      W3C trace_id,
  span_id:       W3C span_id
}
```

**业务主键语义**：

- `session_id` — 一次 L4 session
- `skill_id` — 执行的 skill
- `business_object_id` — 业务对象（电力调度：设备 ID 如 `Transformer-001`；金融：账户 ID；制造：工单 ID）

业务对象 ID 是**业务域相关**的——v3.15 不做域抽象，由 skill author 通过 L1 hook envelope 传入。

### 3.2 业务流纵向绑定路径

```
┌─────────────────────────────────────────────────────────────────────┐
│  L5 UI / CLI                                                       │
│    └─ eaasp-cli-v2: 业务对象 ID (--target-device=Transformer-001)   │
└─────────────────────────────────────────────────────────────────────┘
                              │ HTTP (X-Business-Key header)
┌─────────────────────────────────────────────────────────────────────┐
│  L4 Orchestration                                                   │
│    ├─ SessionCreate 接收 business_key → 持久化到 sessions.business_key│
│    ├─ 每个跨层调用在 gRPC metadata / SSE event 携带 business_key   │
│    └─ Event Room 事件 payload 加 business_key 列                    │
└─────────────────────────────────────────────────────────────────────┘
                              │ gRPC metadata (x-business-key)
┌─────────────────────────────────────────────────────────────────────┐
│  L3 Governance                                                     │
│    ├─ /v1/governance/check 接受 X-Business-Key header              │
│    ├─ governance_decisions 表加 business_key 列                    │
│    └─ 治理决策事件 SSE 携带 business_key                            │
└─────────────────────────────────────────────────────────────────────┘
                              │ gRPC metadata (x-business-key)
┌─────────────────────────────────────────────────────────────────────┐
│  L1 Runtime (7 adapters)                                           │
│    ├─ grid-runtime (Rust): L1 hook envelope 注入 business_key      │
│    ├─ tool_call MCP invoke: metadata 携带 business_key             │
│    └─ Agent loop: 每个 tool_call / LLM call 打点 + business_key    │
└─────────────────────────────────────────────────────────────────────┘
                              │ stdio JSON-RPC
┌─────────────────────────────────────────────────────────────────────┐
│  L2 Memory & Skills                                                │
│    ├─ eaasp-l2-memory-engine: 接受 X-Business-Key header           │
│    ├─ memory_files 表加 business_key 列                            │
│    └─ 写入事件携带 business_key                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │ (跨进程 — metadata / header)
┌─────────────────────────────────────────────────────────────────────┐
│  L0 Protocol                                                       │
│    └─ 21 RPC 全部支持 metadata 透传 (X-Business-Key 在 metadata)   │
└─────────────────────────────────────────────────────────────────────┘
```

**关键约束**：

- business_key 是**可选**的——没传则该事件不属于任何业务流（平台 metric 仍记录但不聚合）
- 一条业务流至少需要 session_id（必填）；skill_id 与 business_object_id 至少有一个非空
- L5 UI 按 business_key 聚合展示时间线

### 3.3 v3.15.0 — 平台级 Metrics 底座 ✅ SHIPPED

Per L3 已有 [a18a22ba] commit：默认 no-op，stdout/otlp 可选，命名规范 `<layer>.<entity>.<measurement>`。

后续子 phase 把这个模式镜像到 L1 (Rust) / L2 / L4。

### 3.4 v3.15.1 — 业务流标识与跨层绑定

**核心交付物**：

1. **`tools/eaasp-common/business_flow.py`** （新模块，跨工具共享）
   - `BusinessKey` dataclass: `(session_id, skill_id, business_object_id)`
   - `BusinessFlowContext`: 跨进程透传的 contextvar（Python）+ task-local（Rust via tracing span）
   - `serialize_business_key()` / `parse_business_key_header()` — 编码为 `X-Business-Key` header
   - 各层 FastAPI / middleware 拦截器，从 incoming request 提取并塞入 context

2. **L0 协议层**：
   - `proto/eaasp/runtime/v2/common.proto` 加 `BusinessKey` message:
     ```protobuf
     message BusinessKey {
       string session_id = 1;
       string skill_id = 2;
       string business_object_id = 3;
     }
     ```
   - 21 RPC 全部支持 `BusinessKey business_key = N;` 字段（向后兼容：缺省 = empty）

3. **L1 hook envelope 扩展**：
   - 现有 envelope 加 `business_key` 字段
   - grid-runtime (Rust) 在 `tracing::Span` 上记录 `business_key` 字段

4. **L2/L3/L4 schema migration**（每层加 `business_key TEXT` 列）：
   - `governance_decisions` (L3)
   - `telemetry_events` (L3)
   - `event_room_events` (L4)
   - `memory_files` (L2)
   - `sessions` (L4) — 主表，必填

5. **L5 UI**：
   - 4-card view 加 business_key 透出 + 业务流跳转链接

### 3.5 v3.15.2 — 业务流时间线聚合

**核心交付物**：

1. **`tools/eaasp-l4-orchestration/flow_timeline.py`**：
   - `get_business_flow_timeline(business_key) -> list[BusinessFlowEvent]`
   - SQL 跨 4 个表 JOIN：sessions / governance_decisions / memory_files / event_room_events
   - 按时间戳排序，按 layer 标记

2. **REST API**（L4 新增）：
   - `GET /v1/business-flows/{business_key}/timeline` — 完整时间线 JSON
   - `GET /v1/business-flows/{business_key}/summary` — 摘要（开始/结束/状态/各层事件数/中断点）

3. **CLI**：
   - `eaasp flow timeline --business-key <key>`
   - `eaasp flow summary --business-key <key>`

### 3.6 v3.15.3 — 业务流持续订阅

**核心交付物**：

1. **业务流 SSE 通道**（区别于 L4 Event Room 的"一次性"事件）：
   - `GET /v1/business-flows/{business_key}/events/stream` — SSE
   - 客户端订阅后，**所有**新产生的该 business_key 事件实时推送
   - 区别于 L4 Event Room：Event Room 是"session 内的全部事件"，业务流是"跨 session/跨调用的同一业务对象的事件"

2. **L5 业务流 UI**：
   - 4-card view 切换为 "business flow mode"
   - 显示业务流时间线 + 实时新事件滚动

3. **CLI 实时模式**：
   - `eaasp flow watch --business-key <key>` — 持续打印新事件，Ctrl-C 退出

### 3.7 v3.15.4 — 业务流评估与优化

**核心交付物**：

1. **业务流达成率**：
   - `flow_evaluator.py` 计算：`status=succeeded / total` over 时间窗口
   - 中断点分析：在哪一层失败的频率最高

2. **跨层联合优化建议**：
   - 例：业务流 80% 在 L3 governance OPA 决策超时 → 建议 L3 扩容
   - 例：业务流 60% 在 L1 grid-runtime LLM 慢响应 → 建议切到 anthropic provider
   - 输出 JSON 报告 + stdout 日志

3. **业务流 A/B 路由**：
   - L4 入口根据"过去 1h 业务流达成率"选 L1 runtime
   - 不只单层 metrics，是业务流整体效果

### 3.8 关键技术决策（业务流部分）

| 决策点 | 选项 | 选定 | 理由 |
|--------|------|------|------|
| Business key 字段 | session_id+skill_id+object_id 三元组 | 三元组 | 三个维度不可压缩 |
| 业务对象 ID 来源 | CLI 参数 / L1 hook / 自动生成 | 显式传入 (--target-device) | 业务语义由 skill author 决定 |
| Business key 必填性 | 必填 / 选填 | 选填 | 早期迁移不强制 |
| 时间线存储 | 跨表 JOIN / 独立 event 表 | 跨表 JOIN | 不增加新表（避免 audit complexity） |
| SSE 业务流通道 | 新建 / 复用 L4 Event Room | 新建 | 生命周期不同（跨 session vs 单 session） |
| 业务流达成率窗口 | 1h / 24h / 7d | 1h（默认） + 可配 | 平衡响应速度与样本量 |

---

## 4. Integration Points / 集成点

### 4.1 修改文件清单（预估）

| 文件 | 范围 | 备注 |
|------|------|------|
| `tools/eaasp-common/business_flow.py` | **新增** 业务流核心 | 必加 |
| `proto/eaasp/runtime/v2/common.proto` | 加 BusinessKey message | 必加 |
| `crates/grid-runtime/src/business_flow.rs` | **新增** Rust 业务流 helper | 必加 |
| `crates/grid-runtime/src/observability/` | L1 OTel 接入（v3.15.0 已定模式） | 必加 |
| `tools/eaasp-l2-memory-engine/.../observability.py` | **新增** 镜像 v3.15.0 模式 | 必加 |
| `tools/eaasp-l2-memory-engine/.../db.py` | memory_files 加 business_key 列 | 必改 |
| `tools/eaasp-l3-governance/.../db.py` | governance_decisions + telemetry_events 加 business_key 列 | 必改 |
| `tools/eaasp-l3-governance/.../api.py` | /v1/governance/check 接收 X-Business-Key | 必改 |
| `tools/eaasp-l4-orchestration/.../observability.py` | **新增** 镜像 v3.15.0 模式 | 必加 |
| `tools/eaasp-l4-orchestration/.../db.py` | event_room_events + sessions 加 business_key 列 | 必改 |
| `tools/eaasp-l4-orchestration/.../flow_timeline.py` | **新增** 时间线聚合 | 必加 |
| `tools/eaasp-l4-orchestration/.../flow_sse.py` | **新增** 业务流 SSE 通道 | 必加 |
| `tools/eaasp-l4-orchestration/.../flow_evaluator.py` | **新增** 业务流评估 | 必加 |
| `tools/eaasp-l4-orchestration/.../api.py` | 业务流 REST + SSE 路由 | 必改 |
| `tools/eaasp-l5-cowork/` | 业务流 UI 模式 | 必改 |
| `tools/eaasp-cli-v2/` | `eaasp flow` 子命令 | 必改 |
| `docs/design/EAASP/BUSINESS_FLOW_NAMING.md` | **新增** 业务流规范 | 必加 |
| `tests/business_flow/` | **新增** 业务流测试 | 必加 |
| `Makefile` | 加 4 个 target (flow-timeline / flow-summary / flow-watch / flow-evaluate) | 必改 |

### 4.2 兼容性

- 所有改动**向后兼容**：
  - business_key 选填，缺省 = 不属于业务流
  - schema 加列 NULL 默认
  - 现有 gRPC contract 加 optional 字段（proto3 兼容）
- W3C trace_id 与 business_key **并行不冲突**：
  - trace_id 解决"调用层慢在哪"
  - business_key 解决"业务流中断在哪"

### 4.3 ADR 状态

- **不**需要新 ADR — 全部在 ADR-V2-024（双轴）+ ADR-V2-034（OPA 拓扑）框架下
- v3.15.5 收口时记 `V315-BUSINESS-FLOW-01` / `V315-OBSERVABILITY-01` / `V315-SLA-01` / `V315-OPT-01` 4 个 deferred items

---

## 5. Verification / 验证

### 5.1 单元测试

- `tools/eaasp-common/tests/test_business_flow.py` — BusinessKey 序列化/反序列化/校验 (8 cases)
- `crates/grid-runtime/src/business_flow.rs` — Rust 镜像 (4 cases)
- 各层 observability 镜像 (L1/L2/L4 各 4 cases) = 12
- 各层 schema business_key 列写入测试 (4 cases × 4 层 = 16)

### 5.2 集成测试

- `tests/business_flow/test_timeline_e2e.py` — 一次业务流 6 层都有事件，时间线完整 (1 case)
- `tests/business_flow/test_timeline_interrupted.py` — 业务流在 L3 中断，时间线正确标 status=failed (1 case)
- `tests/business_flow/test_sse_subscribe.py` — 业务流 SSE 实时推送 (1 case)
- `tests/business_flow/test_evaluator.py` — 业务流达成率 + 中断点分析 (1 case)
- `tests/platform_sla/test_grid_runtime_llm.py` — L1 SLA (1 case)
- `tests/platform_sla/test_l2_memory.py` — L2 SLA (1 case)
- `tests/platform_sla/test_l3_opa.py` — L3 SLA (1 case)
- `tests/platform_sla/test_l4_orchestration.py` — L4 SLA (1 case)
- `tests/platform_optimize/test_runtime_ab.py` — A/B 路由 (1 case)

### 5.3 Live walkthrough (v3.15.5)

- 真实跑 `threshold-calibration` skill（业务对象 = `Transformer-001`）
- 验证 business_key 6 层都出现
- `eaasp flow timeline --business-key <key>` 返回完整时间线
- `eaasp flow watch` 实时打印新事件
- `eaasp flow evaluate` 输出 24h 业务流达成率报告
- `make v3.10-spec-audit` + `make rbac-audit` 全 PASS
- Tag `v3.15` force-push

---

## 6. Open Items / 待决策

| # | 内容 | 选项 | 默认 |
|---|------|------|------|
| 1 | business_key 必填 | 必填 / 选填 | 选填（早期迁移） |
| 2 | business_object_id 来源 | CLI 参数 / L1 hook / 自动生成 | 显式传入 |
| 3 | 时间线 JOIN 跨表 | 跨表 / 独立 event 表 | 跨表 |
| 4 | 业务流 SSE 通道 | 新建 / 复用 L4 Event Room | 新建 |
| 5 | 业务流达成率窗口 | 1h / 24h / 7d | 1h（默认） + 可配 |
| 6 | 业务流 A/B 路由粒度 | session / 业务对象 | 业务对象 |

---

## 7. 与 v3.11–v3.14 的关系

| 已有 milestone | v3.15 的处理 |
|----------------|--------------|
| **v3.11 L3 OPA** | ✅ 保留 + observability.py 已加 + 后续加 business_key 列 |
| **v3.12 A2A + Event Room** | Event Room events 加 trace_id + business_key 列；业务流 SSE 是**新通道** |
| **v3.13 L5 Cowork** | 4-card view 加 business_key 透出 + 业务流 UI 模式 |
| **v3.14 L5 Ecosystem** | 不变（独立产品） |

v3.15 是**第一个跨层业务流 milestone**——把之前各层独立做的可观测性升级为**纵向业务流绑定**的持续能力。

---

## 8. 历史决策记录

- 2026-08-01: 初稿聚焦 L3 OPA，被用户纠正为"应更技术视角"
- 2026-08-01: 修订为"跨 L0–L5 平台级"，v3.15.0 metrics 底座 SHIPPED [a18a22ba]
- 2026-08-01: 用户再次纠正"应是纵向业务流绑定，不是各层散装"，当前版本增 §3.1 业务流概念 + 重排 v3.15.1-4
