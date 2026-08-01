# EAASP 平台级 Observe / Trace / Evaluate / Optimize 技术栈

**日期**: 2026-08-01
**阶段**: v3.15 候选（跨 L0–L5 平台层）
**主题**: EAASP 仿真环境（L0 协议 / L1 runtime×7 / L2 memory / L3 governance / L4 orchestration / L5 cowork）层级关系复杂，需要**稳定可靠**的生产级四项保证能力
**Status**: Design locked（基于 2026-08-01 session 对 v3.11/v3.12/v3.13/v3.14 跨层审计）
**Author**: Jiangwen Su + Claude
**预计周期**: 5 phases (v3.15.0–v3.15.4)
**预计任务量**: 20-28 REQ-IDs / 6 categories

---

## 1. Context / 背景

### 1.1 为什么是平台级（不是 L3 级）

EAASP 仿真环境当前分层：

```
L0 Protocol       (proto/eaasp/runtime/v2/*.proto, 21 RPC)
L1 Runtime        (7 adapters: grid-runtime + claude-code/goose/nanobot/pydantic-ai/claw-code/ccb)
L2 Memory & Skills (eaasp-l2-memory-engine + eaasp-skill-registry + eaasp-mcp-orchestrator)
L3 Governance     (eaasp-l3-governance + OPA sidecar ADR-V2-034)
L4 Orchestration  (eaasp-l4-orchestration + Event Room + A2A + multi-session)
L5 UI             (eaasp-l5-cowork + eaasp-ecosystem/marketplace)
```

每个层都有**自己的 metrics / logs / 决策 / 副作用**。一次"用户提示词"在 6 个层上产生：

- 1 次 LLM HTTP 调用（L1 → LLM provider）
- 1–N 次 tool_call（L1 → MCP，L2/L3 backend）
- 1–M 次 hook 触发（L1 → L2 anchor / L3 audit）
- 1–K 次 governance 决策（L3 OPA）
- 1–J 次 SSE chunk（L4 → CLI）

如果**没有跨层 trace 串联**，一次故障的根因定位需要人工跨 6 个层拼日志——生产环境不可接受。

### 1.2 当前跨层能力现状（2026-08-01 审计）

| 能力 | L1 Rust | L2 Python | L3 Python | L4 Python | L5 UI | 跨层 |
|------|---------|-----------|-----------|-----------|-------|------|
| **Observe (metrics)** | ⚠️ tracing crate, 无 OTel | ❌ 无 | ⚠️ L3 OPA counter 仅 4 类 | ⚠️ L4 SSE event 类型 5 | ❌ | ❌ 无跨层聚合 |
| **Trace** | ❌ 无 traceparent 注入 | ❌ DB 无 trace 列 | ⚠️ 单 request_id 5 阶段 (v3.11.2) | ⚠️ event_room_events 缺 trace | ❌ | ❌ 跨层无关联 |
| **Evaluate (SLA)** | ❌ 无基线 | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Optimize** | ❌ 无 A/B 路由 | ❌ | ❌ shadow→enforce 手动 | ❌ | ❌ | ❌ |

**结论**：EAASP 平台当前**有日志、无指标；有局部 trace（仅 L3 5 阶段）、无全链路 trace；有功能、无 SLA；有手动切换、无 A/B**。

### 1.3 用户原话

> "EAASP 平台 L3 设计的 OPA 已经是业务视角，所以现在关注的是**技术视角**，因为 EAASP 仿真环境层级关系复杂，需要有**稳定可靠的观察、跟踪、评估、优化能力**。"

→ 这四项能力是**平台级底座工程**（不是 L3 OPA 业务层的事），服务于上层的业务 OPA + 业务审批流 + 业务应用。

---

## 2. Scope Boundaries / 范围边界

### 2.1 In Scope

| Phase | 主题 | 跨层 | 交付物 |
|-------|------|------|--------|
| **v3.15.0 — 平台级 metrics 底座** | 各层 OTel SDK 接入 + 关键指标定义 + 跨层命名规范 | L1/L2/L3/L4 | `crates/grid-runtime/src/observability/` + 4 个 Python `metrics.py` + 命名规范文档 |
| **v3.15.1 — 跨层 trace 关联** | W3C traceparent 注入 + 各层 DB schema 补 trace 列 + trace context 透传 | L0/L1/L2/L3/L4/L5 | 1 个 L1 hook 改动 + 4 个 schema migration + L5 UI trace 视图 |
| **v3.15.2 — 平台级 SLA 基线** | 关键路径延迟/错误率基线 + 回归测试（类似 contract-v1.1 验 7 runtime） | L1/L2/L3/L4 | `tests/platform_sla/` 套件 + 5 个层 × 7 个 runtime 矩阵 |
| **v3.15.3 — 优化闭环** | A/B 路由（runtime 选型）+ 性能告警 + 资源调度建议 | L1/L4 | runtime selector + alert rules + scheduler 建议 |
| **v3.15.4 — Live walkthrough + tag** | 真实跑通 + spec-audit + rbac-audit + tag v3.15 | 全部 | 1 live run + 1 spec-audit + tag |

### 2.2 Out of Scope（v3.16+）

| Deferred | 内容 | 归属 |
|----------|------|------|
| 完整 Grafana dashboard | 可视化 Web 面板 | v3.16，operator 部署时启 |
| 跨 cluster 部署 | 多 L4 实例的 trace 聚合 | v3.16，规模化触发 |
| Auto-scaling | 基于 metrics 自动扩缩 | v3.17+ |
| Cost optimization | LLM token 成本分析 | v3.17+ |
| 业务 KPI 看板 | 业务效果指标（误拒率等） | v3.16+ 业务层 |

### 2.3 关键非 goal

- **不**替换 L3 OPA（v3.11 已 SHIPPED）— 只补 L3 之上的跨层能力
- **不**强加 OTel collector / Jaeger / Prometheus — 默认 stdout exporter，operator 自行配置后端
- **不**改 EAASP L1 contract — 仍 21 RPC，向后兼容；traceparent 在 HTTP/gRPC header 层加
- **不**做业务效果指标 — 这是业务层（v3.16+），平台层只做 SLA

---

## 3. Architecture / 架构

### 3.1 平台级 Observability 栈

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Application Layer (L5 UI + CLI)                                        │
│    ├─ eaasp-l5-cowork: 4-card view + trace_id 透出                      │
│    └─ eaasp-cli-v2: SSE 事件渲染时显示 trace_id                          │
└─────────────────────────────────────────────────────────────────────────┘
                              │ HTTP (X-Trace-Id)
┌─────────────────────────────────────────────────────────────────────────┐
│  Orchestration Layer (L4)                                               │
│    ├─ eaasp-l4-orchestration: OTel tracer + 每 session 1 root span      │
│    └─ Event Room events: payload 增加 trace_id / span_id                 │
└─────────────────────────────────────────────────────────────────────────┘
                              │ gRPC (grpc-trace-bin)
┌─────────────────────────────────────────────────────────────────────────┐
│  Governance Layer (L3)                                                 │
│    ├─ eaasp-l3-governance: OTel tracer + OPA 调用 child span            │
│    ├─ governance_decisions: 加 trace_id / span_id / parent_span_id 列  │
│    └─ OPA sidecar: 自管进程 + 断路器 (v3.15.0 之前的实现已 OK)          │
└─────────────────────────────────────────────────────────────────────────┘
                              │ gRPC (grpc-trace-bin)
┌─────────────────────────────────────────────────────────────────────────┐
│  Runtime Layer (L1) — 7 adapters × EAASP L1 contract                    │
│    ├─ grid-runtime (Rust): tracing-opentelemetry + 每 tool_call 1 span  │
│    ├─ claude-code/goose/nanobot/pydantic-ai/claw-code/ccb: 同等接入      │
│    └─ L1 hook envelope: 注入 W3C traceparent, 转发给 L2/L3              │
└─────────────────────────────────────────────────────────────────────────┘
                              │ stdio JSON-RPC
┌─────────────────────────────────────────────────────────────────────────┐
│  Memory & Skills Layer (L2)                                            │
│    ├─ eaasp-l2-memory-engine: OTel tracer + memory_write/confirm span   │
│    ├─ telemetry_events: 加 trace_id 列                                  │
│    └─ eaasp-skill-registry: 读路径加 span                               │
└─────────────────────────────────────────────────────────────────────────┘
                              │ (跨进程 — 通过 header 传 traceparent)
┌─────────────────────────────────────────────────────────────────────────┐
│  Protocol Layer (L0)                                                   │
│    └─ 21 RPC 全部支持 metadata 透传 (W3C traceparent 在 metadata)        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 v3.15.0 — 平台级 Metrics 底座

**目标**：每层有 OTel SDK 接入 + 暴露**关键 5 类指标**：

| 指标名 | 类型 | 单位 | 必出层 |
|--------|------|------|--------|
| `<layer>.requests.total` | Counter | requests | L1/L2/L3/L4 |
| `<layer>.request.duration` | Histogram | seconds | L1/L2/L3/L4 |
| `<layer>.errors.total` | Counter | errors | L1/L2/L3/L4 |
| `<layer>.in_flight` | UpDownCounter | requests | L1/L2/L3/L4 |
| `<layer>.{domain}.count` | Counter | items | 每层自有 |

**L1 (Rust) 接入**：

- 依赖：`opentelemetry = "0.24"` + `opentelemetry-otlp = "0.17"` + `opentelemetry-stdout = "0.5"`
- `crates/grid-runtime/src/observability/metrics.rs` 暴露全局 MeterProvider
- `crates/grid-engine/src/observability/` 提供 `traced!` 宏，3 行接入
- 启动时按 `GRID_OTEL_EXPORTER` 选 stdout / otlp / none

**L2/L3/L4 (Python) 接入**：

- 依赖：`opentelemetry-api` + `opentelemetry-sdk` + `opentelemetry-exporter-otlp` (可选)
- 每个工具新增 `src/eaasp_*/observability.py` 暴露全局 MeterProvider
- 启动时按 `EAASP_OTEL_EXPORTER` 选 stdout / otlp / none

**统一命名规范**（写进 `docs/design/EAASP/OBSERVABILITY_NAMING.md`）：

- 小写 snake_case
- 三段：`<layer>.<entity>.<measurement>`
- 单位后缀：`duration` (秒) / `total` (count) / `size` (bytes)
- 例子：`l1.runtime.requests.total` / `l3.opa.decision.duration` / `l4.session.sse_chunks.total`

### 3.3 v3.15.1 — 跨层 Trace 关联

**目标**：一次"用户提示词"产生的所有跨层事件能用一个 `trace_id` 串起来。

**实现路径**：

1. **L0 协议层** — tonic / FastAPI 拦截器，从 incoming metadata 提取 `traceparent`，塞进 contextvar / tracing span
2. **L1 hook envelope** — 注入 `traceparent` 到 outbound HTTP（→ L2/L3 backend）和 gRPC metadata（→ L4 后续调用）
3. **L2/L3/L4 schema migration** — `governance_decisions` / `telemetry_events` / `event_room_events` 各加 `trace_id` / `span_id` / `parent_span_id` 3 列
4. **L5 UI** — 4-card view 透出 `trace_id` 链接（点击跳到 L4 Event Room 详情）

**OTel SDK 接入**（轻量）：

- Rust：`tracing-opentelemetry` + `opentelemetry-otlp`
- Python：`opentelemetry-sdk.trace` + `BatchSpanProcessor`
- W3C `traceparent` 格式：`00-{32hex_trace_id}-{16hex_span_id}-01`

**回退方案**（无 OTel collector 时）：

- 写文件：`data/traces/{trace_id}.jsonl`，每行一个 span
- 可用 `make trace-show TRACE=<id>` 还原一次完整调用链

### 3.4 v3.15.2 — 平台级 SLA 基线

**目标**：把"EAASP 平台层是否健康"从**感觉**变成**可测**。

**SLA 关键路径矩阵**（5 层 × 关键路径）：

| 层 | 关键路径 | P50 基线 | P99 基线 | 错误率基线 |
|----|----------|----------|----------|------------|
| L1 grid-runtime | LLM HTTP 调用 | 1.5s | 5.0s | < 1% |
| L1 grid-runtime | tool_call MCP invoke | 0.3s | 1.0s | < 0.5% |
| L2 eaasp-l2-memory | memory_search FTS5 | 0.05s | 0.2s | < 0.1% |
| L2 eaasp-l2-memory | memory_write_anchor | 0.1s | 0.5s | < 1% |
| L3 eaasp-l3-governance | OPA 决策 | 0.05s | 0.2s | < 0.1% (infra_unavail) |
| L3 eaasp-l3-governance | 5 阶段审批链 | 2.0s | 10.0s | < 2% |
| L4 eaasp-l4-orchestration | SessionCreate | 0.5s | 2.0s | < 1% |
| L4 eaasp-l4-orchestration | SSE chunk emit | 0.01s | 0.05s | < 0.5% |

**回归测试套件**（`tests/platform_sla/`）：

- 类似 contract-v1.1 sign-off 的 7-runtime 矩阵
- 这里做 5-layer × 7-runtime × N-requests 的吞吐/延迟/错误率矩阵
- 跑 1000 requests / 路径 / 组合，超阈值即 fail
- `make platform-sla-verify` target 接入 CI

### 3.5 v3.15.3 — 优化闭环

**目标**：基于 metrics / trace / SLA 的自动反馈。

**3 个子能力**：

1. **A/B 路由（runtime 选型）**
   - L4 入口根据 session 元数据（user_id / scope）选 L1 runtime
   - 默认按"过去 1h 错误率"最低选
   - 异常时切到 fallback（grid-runtime 永远可用）
   - 路由结果写入 `session_orchestrator.runtime_selected` 字段

2. **性能告警**
   - 基于 OTel metrics 的 threshold rule
   - 例：`l3.opa.decision.duration.p99 > 0.5s` for 5m → 告警
   - 告警通道：stdout log line + 可选 webhook
   - 告警去重：相同 trace_id 不重复

3. **资源调度建议**
   - 收集各层 CPU/内存/网络（基础 metrics）
   - 报告："L2 memory 在 80% 内存阈值，建议扩容"
   - 不自动扩缩，只给建议

### 3.6 关键技术决策

| 决策点 | 选项 | 选定 | 理由 |
|--------|------|------|------|
| OTel SDK 版本 | 0.24 (Rust) / 1.x (Python) | latest stable | 跟随上游 |
| 默认 exporter | stdout / otlp | stdout (默认) + 配置可切换 | 不强制 operator 部署 collector |
| Trace 列存哪里 | 现有各表 / 新统一表 | 现有各表 + ALTER | 关联查询简单，deferred ledger 不增加新表 |
| SLA 基线 | 跑一次采集定基线 / 写死 | 跑一次采集定基线 + 写死兜底 | 基线是动态的 |
| A/B 路由粒度 | session / request | session | session 内 runtime 切换影响 tool_call 状态 |
| 告警通道 | stdout / webhook | stdout (默认) + 配置文件可加 webhook | 最小依赖 |
| 性能 metrics 采集中 | 1s / 5s / 10s | 5s | 平衡精度与开销 |

---

## 4. Integration Points / 集成点

### 4.1 修改文件清单（预估）

| 文件 | 范围 | 备注 |
|------|------|------|
| `crates/grid-runtime/Cargo.toml` | 加 opentelemetry 依赖 | 必改 |
| `crates/grid-runtime/src/observability/` | **新增** 4 个文件 (metrics / tracing / interceptor / init) | 必加 |
| `crates/grid-runtime/src/harness.rs` | 加 OTel middleware | 必改 |
| `crates/grid-engine/src/observability/` | **新增** 3 个文件 | 必加 |
| `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/observability.py` | **新增** | 必加 |
| `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/db.py` | 加 3 列 ALTER | 必改 |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/observability.py` | **新增** | 必加 |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/db.py` | 加 3 列 ALTER | 必改 |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/opa_backend.py` | 接 tracing | 必改 |
| `tools/eaasp-l3-governance/src/eaasp_l3_governance/opa_sidecar.py` | 接 tracing (v3.15.0 已有) | 必改 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/observability.py` | **新增** | 必加 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/db.py` | 加 3 列 ALTER | 必改 |
| `tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/session_orchestrator.py` | runtime A/B 选型 | v3.15.3 改 |
| `tools/eaasp-l5-cowork/` | trace 视图 | v3.15.1 改 |
| `docs/design/EAASP/OBSERVABILITY_NAMING.md` | **新增** 命名规范 | 必加 |
| `docs/design/EAASP/PLATFORM_SLA_BASELINE.md` | **新增** SLA 基线 | 必加 |
| `tests/platform_sla/` | **新增** 回归测试 | 必加 |
| `Makefile` | 加 4 个 target (otel-init / trace-show / platform-sla-verify / runtime-ab-toggle) | 必改 |
| `tools/eaasp-l3-governance/pyproject.toml` | 加 opentelemetry-* 依赖 | 必改 |

### 4.2 兼容性

- 所有改动**向后兼容**：
  - `L3_OPA_*` / `GRID_OTEL_*` / `EAASP_OTEL_*` 全部可选
  - 缺省 = 不启用 OTel（与现状一致）
  - 启用 = stdout exporter，不强制外部服务
- L1 gRPC contract 21 RPC **不变**；traceparent 走 metadata（gRPC 已有机制）
- L2/L3/L4 schema 加列，**全是 NULL 默认**，不破坏现有数据

### 4.3 ADR 状态

- **不**需要新 ADR — 全部在 ADR-V2-034（OPA 拓扑）+ ADR-V2-024（双轴模型）框架下扩展
- v3.15.4 收口时记 `V315-OBSERVABILITY-01` / `V315-TRACE-01` / `V315-SLA-01` / `V315-OPT-01` 4 个 deferred items

---

## 5. Verification / 验证

### 5.1 单元测试

- `crates/grid-runtime/src/observability/*_test.rs` — Rust metrics 单元 (4 cases)
- `tools/eaasp-l3-governance/tests/test_observability.py` — Python metrics 单元 (3 cases)
- 各层 W3C traceparent 注入/提取测试 (3 cases × 4 层 = 12)

### 5.2 集成测试

- `tests/platform_sla/test_grid_runtime_llm.py` — L1 关键路径 SLA (1 case)
- `tests/platform_sla/test_l2_memory.py` — L2 关键路径 SLA (1 case)
- `tests/platform_sla/test_l3_opa.py` — L3 关键路径 SLA (1 case)
- `tests/platform_sla/test_l4_orchestration.py` — L4 关键路径 SLA (1 case)
- `tests/platform_trace/test_e2e_trace.py` — 一次完整 trace 包含 ≥ 6 个 span (1 case)
- `tests/platform_optimize/test_runtime_ab.py` — A/B 路由在错误率上升时切换 (1 case)

### 5.3 Live walkthrough (v3.15.4)

- 真实跑 `threshold-calibration` skill（v3.14 验证的同一路径）
- 验证 trace_id 在 L1/L2/L3/L4/L5 全部出现
- 验证 metrics 5 类指标在 stdout 输出
- 验证 SLA 回归测试 7 × 5 = 35 组合全 PASS
- 验证 A/B 路由在注入 50% 错误率时切到 fallback
- `make v3.10-spec-audit` + `make rbac-audit` + `make platform-sla-verify` 全 PASS
- Tag `v3.15` force-push

---

## 6. Open Items / 待决策

| # | 内容 | 选项 | 默认 |
|---|------|------|------|
| 1 | OTel SDK 版本锁 | latest vs 固定 | 固定 minor（patch 浮动） |
| 2 | 默认 exporter | stdout / otlp | stdout |
| 3 | Trace 列存表 | 各表 ALTER / 统一新表 | 各表 ALTER |
| 4 | SLA 基线采集时机 | 首次跑时 / 写死 | 首次跑时 + 写死兜底 |
| 5 | A/B 路由粒度 | session / request | session |
| 6 | 告警通道 | stdout / webhook | stdout（默认） + 配置可加 webhook |
| 7 | 性能 metrics 采集间隔 | 1s / 5s / 10s | 5s |

---

## 7. 与 v3.11–v3.14 的关系

| 已有 milestone | v3.15 的处理 |
|----------------|--------------|
| **v3.11 L3 OPA** | ✅ 保留 `opa_backend.py` 不变；新增 `opa_sidecar.py`（v3.15 之前已写）+ `circuit_breaker.py`（v3.15 之前已写） |
| **v3.12 A2A + Event Room** | Event Room events 加 trace_id 列；A2A Router 接 OTel |
| **v3.13 L5 Cowork** | 4-card view 透出 trace_id |
| **v3.14 L5 Ecosystem** | 不变（独立产品） |

v3.15 是**第一个跨层 milestone**——把之前各层独立做的可观测性串成平台级底座。
