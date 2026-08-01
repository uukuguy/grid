# EAASP 平台典型应用 — 技术框架 + 数据流转控制

> **创建日期**: 2026-08-01
> **依据**: 2026-07-30 EAASP v3.14 SHIPPED 后,通过 deepseek-v4-pro 真实跑通端到端 `threshold-calibration` skill 验证所得
> **范围**: 平台 v2.0 现状(L0/L1/L2/L3/L4 + L5 Cowork/Ecosystem);以 `grid-runtime` L1 适配 + 真实 mock-scada + L2 内存引擎 + L3 OPA 后端 + L4 orchestration 为典型应用骨架

## 一、典型应用形态

EAASP 平台上的"典型应用"由以下三层组成:

1. **Skill**(技能):Markdown 描述文件 `SKILL.md`,声明 prose(执行规范)、required_tools(必需工具集)、scoped_hooks(执行期内钩子)、access_scope(权限范围)
2. **Session**(会话):单次 LLM 调用上下文;包含 user_id / scope / policy_version / skill_id / memory_refs
3. **Runtime Adapter**(运行时适配):实现 EAASP L1 gRPC contract 的进程,负责把 Skill prose 注入 LLM、把 Tool 调用路由到 MCP、把 Hook 事件发布给 L2/L3

典型应用流程:
```
用户提示词 + Skill ID → CLI (eaasp session run)
  → L4 Orchestration (HTTP SSE)
    → grid-runtime gRPC (SessionCreate)
      → LLM 调用 (deepseek-v4-pro)
      → MCP tool 调用 (mock-scada / eaasp-l2-memory)
      → Hook 事件发布 (L2 anchor + L3 policy)
    → 流式响应回 CLI
  → CLI 显示 thinking + tool_call + tool_result + final
```

## 二、技术框架(分 L0–L4)

### L0 — Protocol 层
- 路径: `proto/eaasp/runtime/v2/{common,runtime,hook}.proto`
- 契约: 21 RPC(17 runtime + 4 hook)
- 规范权威: `docs/design/EAASP/EAASP-Design-Specification-v2.0.docx`
- 当前版本: `contract-v1.2.0`(2026-05-20 升);`contract-v1.1.0` 是 Phase 3 历史 sign-off

### L1 — Runtime 适配层
- 主力: `grid-runtime` (Rust, target/debug/grid-runtime)
- 7 个对比 runtime: claude-code / goose / nanobot / pydantic-ai / claw-code / ccb(hermes frozen per ADR-V2-017)
- 7 个全部 pass contract-v1.2.0
- 关键代码:
  - `crates/grid-runtime/src/harness.rs` — gRPC server + agent loop
  - `crates/grid-engine/src/agent/harness.rs` — agent 主循环 + tool dispatch + D87 continuation
  - `crates/grid-engine/src/providers/{openai,deepseek,ling,anthropic}.rs` — LLM provider adapters
  - `crates/grid-engine/src/providers/capabilities.rs` — `tool_choice` capability 探测
  - `crates/grid-engine/src/providers/retry.rs` — 重试策略(non-retryable 400 立即 fail)

### L2 — Memory & Skills 层
- 路径: `tools/eaasp-l2-memory-engine/`
- 启动: `python -m eaasp_l2_memory_engine.main`(端口 18085)
- 能力: FTS5 + HNSW + time-decay 混合索引;7 MCP tools(`search/read/write_file/write_anchor/confirm/list/delete`)
- 关键 schema: `MemoryFileIn(memory_id, scope, category, content, evidence_refs, status)`
- 状态机: `agent_suggested → confirmed / archived`(归档终态)
- 已知 fix: `evidence_refs=null` Pydantic ValidationError → coerced to `[]`(commit `a0d846f0`)

### L3 — Governance 层
- 路径: `tools/eaasp-l3-governance/`
- 启动: `python -m eaasp_l3_governance.main`(端口 18083)
- 能力: Policy DSL + risk classification + OPA 后端 adapter(v3.11.1 SHIPPED)
- 治理门: 5-stage approval state machine(v3.11.2 SHIPPED)
- 决策权威: `docs/design/EAASP/adrs/ADR-V2-034-opa-backend-deployment-topology.md`

### L4 — Orchestration 层
- 路径: `tools/eaasp-l4-orchestration/`
- 启动: `uvicorn eaasp_l4_orchestration.main`(端口 18084)
- 能力:
  - **Event Room** (v3.12.1) — 事件流聚合
  - **A2A Router** (v3.12.2) — Agent-to-Agent 通信 + ReviewSet + conflict detection(ADR-V2-035)
  - **L5 Cowork** (v3.13.0) — 4-card view(Event/Evidence/Action/Approval)+ retrospective
  - **L5 Ecosystem** (v3.14) — Ontology + Marketplace + SDK

### L5 — UI / Frontend 层
- Cowork UI(Event/Evidence/Action/Approval 4-card)
- Ecosystem UI(skill marketplace)

## 三、数据流转控制(典型应用 `threshold-calibration` 实测)

### 3.1 数据流向总图

```
┌─────────────────────────────────────────────────────────────────┐
│ User / CLI                                                      │
│   eaasp session run --skill threshold-calibration --yes        │
│   "校准 Transformer-001 的温度阈值"                              │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP POST /v1/sessions/run
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ L4 Orchestration (:18084)                                       │
│   - 创建 session 记录 → DB                                       │
│   - Forward X-Session-Scope header → grid-runtime (D8/L3-04 RBAC)│
│   - 解析 Skill metadata (scope, hooks, required_tools)          │
└────────────────────────────┬────────────────────────────────────┘
                             │ gRPC SessionCreate (v2 contract)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ grid-runtime (:50051, EAASP L1 Tier 1 Harness)                  │
│   - load_skill: 注入 prose (4228 chars) + required_tools       │
│   - materialize hooks/ 目录                                       │
│   - connect MCP servers: mock-scada, eaasp-l2-memory             │
│   - agent loop: LLM ↔ tools ↔ hooks                              │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS POST /v1/chat/completions
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ LLM Provider (deepseek-v4-pro via api.deepseek.com)             │
│   - thinking mode 输出 (未压缩 streaming)                       │
│   - tool_calls 返回 (scada_read_snapshot, memory_search, etc.)   │
└────────────────────────────┬────────────────────────────────────┘
                             │ SSE chunks
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ grid-runtime agent loop                                         │
│   - 解析 tool_call → 路由到 MCP server                          │
│   - 工具结果 → 追加到 messages                                   │
│   - D87 续接: 若 tool_choice_supported 且 EndTurn + 工具未全调 │
│     → 发 WorkflowContinuation event,armed tool_choice=Required  │
│   - TokenEscalation: 若 max_tokens 截断 → 升级后重试            │
└────────────────────────────┬────────────────────────────────────┘
                             │ MCP stdio JSON-RPC
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ MCP Subprocess Servers                                          │
│   - mock-scada (.venv/bin/mock-scada)                            │
│     读 SCADA telemetry → 返回 device_id + samples              │
│   - eaasp-l2-memory (.venv/bin/eaasp-l2-memory)                  │
│     search/read/write_file/write_anchor/confirm/list/delete      │
└────────────────────────────┬────────────────────────────────────┘
                             │ Hook events (PostToolUse / Stop)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Hook Subsystem                                                  │
│   - declarative::command_executor (Stop hook require_anchor)     │
│   - builtin::audit_log (tool execution audit)                    │
│   - memory_write_hook (PostToolUse → L2 HTTP :18085)            │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP POST /tools/memory_write_anchor/invoke
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ L2 Memory Engine (:18085)                                       │
│   - 接收 anchor + file writes                                   │
│   - FTS5 + HNSW 双索引                                          │
│   - 状态机校验(agent_suggested → confirmed/archived)            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 控制流(执行期 / 一次性)

1. **会话创建**:CLI → L4 → grid-runtime → SessionCreate(SSE channel established)
2. **Skill 加载**:prose 注入 `initial_history`(作为 assistant context);required_tools 写入 `tool_filter`;hooks materialize 到 runtime-workspace
3. **MCP 连接**:stdio spawn mock-scada + eaasp-l2-memory;每个 server initialize → tools/list → 工具表注册
4. **Agent loop**:
   - turn N: LLM call (stream) → content + (可选) tool_calls
   - 工具分发:每个 tool_call → MCP invoke → tool_result → append to messages
   - Hook 触发:PostToolUse → memory_write_hook → L2 HTTP (anchor + file)
   - 终止检测:
     - StopReason::EndTurn + 无 tool_use + total_tool_calls > 0 → D87 WorkflowContinuation(若 tool_choice_supported)
     - StopReason::MaxTokens + escalation 失败 → 自动续接 prompt 注入
     - 完成:Stop hook `require_anchor` 校验 → 接受 emit / 返回 continue
5. **响应回传**:SSE chunks → CLI → thinking + tool_call/tool_result + final

### 3.3 数据契约关键点

| 数据 | 出处 | 入处 | 校验 |
|------|------|------|------|
| `auth` Bearer token | CLI (from .env) | L4 + grid-runtime | HMAC-signed, AuthMode=ApiKey arm (ADR-V2-003) |
| `X-Session-Scope` header | CLI (EAASP_SESSION_SCOPE) | L4 → L3 /v1/sessions/{id}/validate | fail-closed: missing → 403 missing_scope; mismatch → 403 scope_mismatch (commit `3398d567`) |
| `tool_choice` capability | CapabilityStore cache | runtime.rs:1623 | probe 失败 → Unsupported → D87 gate 关闭 |
| LLM messages | assistant(user) text + tool_use/tool_result | OpenAI request body | `convert_messages` in `crates/grid-engine/src/providers/openai.rs:254-422` |
| `evidence_refs` | runtime memory_write_hook | L2 MemoryFileIn | null → [] coerce (commit `a0d846f0`);非 literal status → 422 invalid_arg |
| Memory status | MemoryFileIn.status | L2 DB | `_ALLOWED_TRANSITIONS` 校验(agent_suggested → confirmed/archived) |

### 3.4 失败恢复 / 重试策略

| 失败类型 | 处理 | 来源 |
|---------|------|------|
| LLM HTTP 400 invalid_request_error | non-retryable,立即 fail | `crates/grid-engine/src/providers/retry.rs` |
| LLM HTTP 429/5xx/network | retryable,指数退避(默认 max_retries=3) | 同上 |
| L2 write anchor HTTP 4xx/5xx | non-fatal warning,继续 session | `crates/grid-runtime/src/memory_write_hook.rs:90` |
| Stop hook exit=2 (continue) | retry: re-prompt with hook reason | `crates/grid-engine/src/hooks/declarative/command_executor.rs` |
| MCP server spawn 失败 | session 失败,require manual restart | runtime log "Failed to add MCP server" |
| 整个 session gRPC DEADLINE_EXCEEDED | outer timeout,fail-fast | tonic |

## 四、当前已知平台层 Bug(2026-08-01 验证发现)

| Bug | 状态 | 提交 |
|-----|------|------|
| eaasp-ecosystem: Pydantic extra="ignore" 让 author_principal spoof 静默吞掉 | ✅ Fixed | `50f8459e` |
| eaasp-ecosystem: 测试 fixture 缺 `skill_registry_url=REGISTRY_URL` | ✅ Fixed | `c3e82c7a` |
| eaasp-l2-memory: `evidence_refs=null` → Pydantic ValidationError → HTTP 500 | ✅ Fixed | `a0d846f0` |
| eaasp-l2-memory: `_memory_write_file` ValidationError 未捕获 → HTTP 500 | ✅ Fixed | `a0d846f0` |

**未修(平台契约外 / 模型层)**:
- LLM 在 thinking 模式 streaming 中暴露 reasoning 文本到 CLI(应折叠)
- LLM 未遵循 skill prose 中的"完成全工作流"指令,反而拒绝任务(模型对齐问题)

## 五、运维速查

### 启动最小栈
```bash
PROJECT_ROOT=/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox

# 1. L2 memory engine
EAASP_L2_PORT=18085 EAASP_L2_DB_PATH="$PROJECT_ROOT/data/dev-l2.db" \
  "$PROJECT_ROOT/tools/eaasp-l2-memory-engine/.venv/bin/python" \
    -m eaasp_l2_memory_engine.main &

# 2. L3 governance (可选,如需 OPA 后端)
EAASP_L3_PORT=18083 EAASP_L3_DB_PATH="$PROJECT_ROOT/data/dev-l3.db" \
  "$PROJECT_ROOT/tools/eaasp-l3-governance/.venv/bin/python" \
    -m eaasp_l3_governance.main &

# 3. grid-runtime (env -i 清空 shell env,显式传 .env 值)
env -i HOME="$HOME" \
  PATH="$PROJECT_ROOT/tools/mock-scada/.venv/bin:$PROJECT_ROOT/tools/eaasp-l2-memory-engine/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
  LLM_PROVIDER=deepseek \
  DEEPSEEK_API_KEY='...' DEEPSEEK_MODEL_NAME='deepseek-v4-pro' \
  EAASP_L2_DB_PATH="$PROJECT_ROOT/data/dev-l2.db" \
  RUST_LOG=grid_runtime=info,grid_engine=info \
  "$PROJECT_ROOT/target/debug/grid-runtime" &
```

### 跑典型 skill
```bash
env -i HOME="$HOME" \
  PATH="$PROJECT_ROOT/tools/eaasp-cli-v2/.venv/bin:/usr/local/bin:/usr/bin:/bin" \
  bash -c '
    set -a; source '"$PROJECT_ROOT"'/.env; set +a
    export EAASP_SESSION_SCOPE="org:eaasp-verify-2026-07-30"
    eaasp session run --skill threshold-calibration --runtime grid-runtime --yes \
      "校准 Transformer-001 的温度阈值"
  '
```

### 端口冲突排查
```bash
lsof -nP -iTCP:50051 -sTCP:LISTEN   # grid-runtime gRPC
lsof -nP -iTCP:18081 -sTCP:LISTEN  # skill-registry
lsof -nP -iTCP:18082 -sTCP:LISTEN  # mcp-orchestrator
lsof -nP -iTCP:18083 -sTCP:LISTEN  # L3 governance
lsof -nP -iTCP:18084 -sTCP:LISTEN  # L4 orchestration
lsof -nP -iTCP:18085 -sTCP:LISTEN  # L2 memory engine
```

## 六、引用文档

- 战略 ADR: `docs/design/EAASP/adrs/ADR-V2-024-phase4-product-scope-decision.md`(双轴模型)
- 双轴边界 ADR: `docs/design/EAASP/adrs/ADR-V2-029-engine-data-integration-boundary.md`
- OPA 拓扑 ADR: `docs/design/EAASP/adrs/ADR-V2-034-opa-backend-deployment-topology.md`
- A2A 冲突 ADR: `docs/design/EAASP/adrs/ADR-V2-035-a2a-router-conflict-detection.md`
- 规范权威: `docs/design/EAASP/EAASP-Design-Specification-v2.0.docx`
- 演化路径: `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md`
- Deferred Ledger: `docs/design/EAASP/DEFERRED_LEDGER.md`(8 × V310-* + V311-AUDIT-01 全部 CLOSED)
- 端到端验证: `docs/design/EAASP/E2E_VERIFICATION_GUIDE.md`
- 项目 SSOT: `docs/PROJECT_PRODUCT_OVERVIEW.md`
- 会话日志(本验证): `docs/status/PRODUCTION_USABILITY_2026-08-01.md`(待补)