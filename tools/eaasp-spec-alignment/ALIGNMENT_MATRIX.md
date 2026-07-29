# EAASP v2.0 平台骨架对齐矩阵

> 基线：`EAASP-Design-Specification-v2.0.docx`（规范权威）以及 EVOLUTION_PATH / MVP_SCOPE / PHASE_3_DESIGN。状态只描述当前仓库的模拟器级参考实现，不代表生产平台已完成。

## 判定规则

| 状态 | 含义 |
|---|---|
| `aligned` | 当前实现具备规范要求的可执行骨架，允许部署形态简化 |
| `partial` | 有可执行子集，但关键阶段、边界或生产能力缺失 |
| `missing` | 当前实现没有对应平台能力 |
| `deferred_to_v3.11+` | 已确认超出 contract-v1.2.0 / v3.10，登记到 DEFERRED_LEDGER |

## 5 层现状矩阵

| 层 | v2.0 要求 | 当前实现证据 | 状态 | 差距 / owner |
|---|---|---|---|---|
| L0 Protocol | Runtime + Hook 稳定契约 | `proto/eaasp/runtime/v2/`；21 RPC（17 runtime + 4 hook） | aligned | v3.10 禁止扩面；VERIFY 只审计现有 surface |
| L1 Execution | substitutable runtime、T0-T3、Standard/Kernel/Hardware sandbox | `grid-runtime` + 6 comparison runtimes；`grid-engine/src/sandbox/{docker,native,wasm}.rs` | partial | Docker/native/wasm adapter 存在；gVisor/Firecracker/Kata placement 与按 org policy 选 tier 缺失，v3.11+ |
| L2 Assets | Skill、MCP orchestration、Memory、Ontology | `eaasp-skill-registry`、`eaasp-mcp-orchestrator`、`eaasp-l2-memory-engine` | partial | 资产骨架可执行；Ontology、完整 promotion/ACL/analytics、事件共享与 optimistic locking 缺失 |
| L3 Governance | Policy/OPA、五阶段审批、audit、hooks、deterministic verifier | `eaasp-l3-governance/policy_engine.py`、`managed_settings.py`、`audit.py` | partial | in-process allow/deny + request/decision 已有；OPA/Rego 与 Plan→Check→Draft→Approve→Execute 缺失 |
| L4 Orchestration | event engine、session orchestrator、A2A、integration/persistence plane | `eaasp-l4-orchestration/{event_engine,session_orchestrator,l1_client}.py` | partial | 真实 gRPC 与 append-only events 已有；Event 完整状态机、A2A、生产 integration plane 缺失 |
| L5 Cowork | Event Room、四卡、通知、admin/process designer | CLI/SSE 仅作为 Phase 0.5 人工可执行界面 | missing | Cowork UI / Event Room / 四卡均为 Phase 5+ |

## 3 管道现状矩阵

| 管道 | v2.0 要求 | 当前链路 | 状态 | 差距 |
|---|---|---|---|---|
| A Hook | L5 policy → L3 compile/OPA → L1 bridge → L3 audit；14 lifecycle events、4 handler types、deny wins | managed settings + scoped hooks + hook bridge + audit/event interceptor | partial | 无 L5 editor、OPA target、完整 14-event/4-handler 生产链 |
| B Data flow | L5 input → L4 event/context → L3 handshake → L2 assets → L1；上行 chunks/telemetry/memory/events | `create_session` 查询 L2/L3/skill，构造 P1-P5，gRPC Initialize/Send；event stream 持久化 | partial | 无独立 telemetry/memory-write/event-stream 四路生产基础设施；当前为 HTTP/SQLite 模拟器 |
| C Session control | Event Room → Event → Session，crash recovery、reversible compaction、three-way handshake | L4 session row + event stream + L1 lifecycle RPC | partial | Event Room/Event 完整层级、恢复重建、retention/cold archive 缺失 |

## 四元范式 / 四卡

| 卡 | v2.0 数据源 | 当前实现 | 状态 |
|---|---|---|---|
| Event card | L4 event state machine | 基础 Event 模型/聚类，无 Cowork projection | missing |
| Evidence pack | L2 evidence anchors | append-only anchor store 可供未来 projection | partial |
| Action card | L1 plan step tree | 普通 response/tool chunks，无标准 step-tree projection | missing |
| Approval card | L3 approval gate + L5 UI | governance request/decision SSE 与 CLI 同步批准；无 30 秒 card UI | partial |

## 平台边界硬检查

1. **L4 → L1 真 gRPC：通过。** `SessionOrchestrator.create_session()` 调用 `L1RuntimeClient.initialize()`；消息调用 `send()`；关闭调用 `terminate()`；MCP 调用 `connect_mcp()`。没有 stubbed event 代替 RPC。
2. **L2 MCP 经 L4 下发：骨架通过。** Skill dependency → `McpResolver.resolve()` HTTP 调 L2 orchestrator → L4 `ConnectMCP` gRPC 下发。MCP server config 本身在请求体中传输；`McpServerDef.env` 仍允许按 server 声明显式 env map，这不等于用进程环境发现 MCP。L4 基础 URL仍可由 `EAASP_MCP_ORCH_URL` 配置。
3. **L3 OPA / 5-stage：缺口确认。** 当前实现覆盖风险分类、allow/deny/require_approval、append-only request/final decision；没有 OPA sidecar/Rego bundle，也没有 Plan/Check/Draft/Approve/Execute 状态机与 deterministic verifier。
4. **L1 Sandbox Tiers：部分。** Native、Docker（feature gate）、Wasm adapter 存在；规范的 Standard Docker/containerd 只有 adapter-level skeleton，Kernel gVisor 与 Hardware Firecracker/Kata、org-unit placement 未实现。
5. **v3.9 安全兼容：保持。** 本 phase 不改 `grid-server` route catalog、`Role × Action`、Owner-only、`AuthMode::{None,ApiKey,Full}` 或 shared core。

## 单点验证最低标尺

Phase 0.5 人工可执行最低标尺保持为：`make dev-eaasp` 启动服务后，`eaasp-cli` 运行一个真实 Skill，经 L4 查询 L2/L3/Skill Registry，真实 gRPC 调用 L1，流式输出并写入 event/memory/evidence。该标尺证明“骨架可跑”，**不证明** OPA、A2A、Cowork、Marketplace 已完成。

## Spec section cross-index

| Spec section | Status | v3.10 phase | post-v3.10 owner |
|---|---|---|---|
| §2.1 Five-Layer Model | partial | 03.10.0 | Phase 3-6 platform evolution |
| §2.2 Three Vertical Pipelines | partial | 03.10.0/2 | Phase 3-4 |
| §2.3 Collaboration Loop | partial | 03.10.0 | Phase 3-5 |
| §3.1-3.3 Agent Factory flows | missing | audit only | Phase 6 ecosystem |
| §4.1 Event Room | missing | audit only | Phase 5 Cowork |
| §4.2 Four-Card Paradigm | partial | 03.10.0 | Phase 5 Cowork |
| §4.3-4.7 L5 surfaces | missing | audit only | Phase 5 Cowork |
| §5.1 Event Engine | partial | 03.10.2 | Phase 4 |
| §5.2 Session Orchestrator | partial | 03.10.2 | Phase 3-4 |
| §5.3 A2A Router | missing | audit only | Phase 4 A2A |
| §5.4-5.8 L4 planes | partial | audit only | Phase 4 |
| §6.1 Policy Engine | partial | 03.10.2 | Phase 3 OPA |
| §6.2 Approval Gates | partial | 03.10.2 | Phase 3 approval chain |
| §6.3 Audit Service | partial | 03.10.2 | Phase 3 |
| §6.4-6.8 MCP/hooks/security | partial | 03.10.1/2 | Phase 3 |
| §6.9 Approval Control Chain | deferred_to_v3.11+ | 03.10.2 | Phase 3 |
| §6.10 Deterministic Verifier | missing | audit only | Phase 3 |
| §6.11 Evidence Chain | partial | 03.10.1/2 | Phase 3 |
| §7.1-7.6 Assets/Skills | partial | 03.10.1 | Phase 6 ecosystem |
| §7.7 Memory Engine | partial | 03.10.1 | L2 follow-up |
| §7.8 Ontology Service | missing | audit only | Phase 6 ecosystem |
| §7.5-7.8 Phase 6 ecosystem surface (v3.14 cross-index) | aligned | 03.14.0/1/2/3 | `tools/eaasp-ecosystem/{ontology,marketplace,ecosystem,cli}.py` (v3.14.0 + v3.14.1 SHIPPED 2026-07-28 @ `12951d48` + `e2d9c116`) + `sdk/python/src/eaasp/client/ecosystem_client.py` + `sdk/python/src/eaasp/cli/ecosystem_cmd.py` (v3.14.2 SHIPPED 2026-07-30) + `docs/status/PRODUCTION_USABILITY_2026-07-30.md` (v3.14.3 SHIPPED 2026-07-30). v3.14 = final phase of EVOLUTION_PATH §三 8-Phase 路线 (per D-46). **V310-ECOSYSTEM-01 → ✅ CLOSED 2026-07-30**. EVOLUTION_PATH 8-Phase 路线 ALL SHIPPED. |
| §8.1-8.7 L1 abstraction | partial | 03.10.3 | L1 evolution |
| §9.1-9.3 Runtime execution | aligned | 03.10.3 | L1 evolution |
| §9.4 Sandbox Isolation Tiers | partial | 03.10.0 | L1 infrastructure |
| §10.1-10.6 L3/L4 contracts | partial | 03.10.2 | Phase 3 |
| §11.1-11.2 L5/L4 real-time | partial | 03.10.2 | Phase 5 |
| §12.1-12.2 Memory API | aligned | 03.10.1 | L2 evolution |
| §13.1-13.6 L1/L3 hooks | partial | 03.10.2 | Phase 3 |
| §14.1-14.3 A2A | deferred_to_v3.11+ | audit only | Phase 4 A2A |
| §15.1-15.10 Hook architecture | partial | 03.10.2 | Phase 3 |
| §16.1-16.2 Data Flow | partial | 03.10.2 | Phase 3-4 |
| §17.1-17.6 Session Control | partial | 03.10.2 | Phase 4-5 |
| §18.1-18.12 Deployment | deferred_to_v3.11+ | audit only | platform infrastructure |
| §19 Evolution Strategy | aligned | 03.10.0 | roadmap |
| §20 Anti-Patterns | partial | 03.10.3 | continuous audit |
| §21 Decision Trail | aligned | 03.10.0 | ADR governance |
| §22 Team Assignment | not_certified | audit only | organizational planning |

## 审计时间点

本矩阵对应 v3.10 基线 `b0d4502e` + v3.11.3 / v3.12.3 / v3.13.3 / v3.14.3 增量更新 (TRACE-02 跨 phase 维护)。后续 `make v3.10-spec-audit` 以结构化标记验证状态不被静默删除。v3.14.3 增量：§7.5-7.8 状态从 `partial` / `missing` 升级为 `aligned`;V310-ECOSYSTEM-01 ✅ CLOSED 2026-07-30。
