# PIPE：EAASP v2.0 管道与平台边界对齐

## Data-flow pipeline（规范 §2.2 Pipeline B / §16）

| 阶段 | 当前实现符号 | 状态 |
|---|---|---|
| input | L4 API `_run_create_session` / message endpoints | aligned |
| context | `SessionOrchestrator.create_session`: L2 memory + Skill Registry；`build_session_payload` P1-P5 | aligned |
| governance | `L3Client.validate_session`；policy_context hooks/version | partial |
| dispatch | `L1RuntimeClient.initialize/send/connect_mcp` real gRPC | aligned |
| result | Send server-stream chunks；SSE `chunk` / `done` | aligned |
| audit | `SessionEventStream.append` + L3 `AuditStore` + Event Engine | partial |
| output | L4 REST/SSE + eaasp-cli | aligned（MVP） |

缺口：规范上行要求 ResponseChunks、TelemetryEvents、MemoryWrites、EventStreamEntries 四条独立语义通道；当前参考实现以 gRPC chunks + HTTP/SQLite event/audit 为主，尚非生产级四路基础设施。

## Hook pipeline（规范 §2.2 Pipeline A / §13 / §15）

当前已有 managed settings、skill scoped hooks、L1 hook bridge、hook telemetry/audit，以及 deny/approval 最小治理。缺少 L5 policy editor、OPA/Rego compilation target、完整 14 lifecycle events、command/http/prompt/agent 四类 handler 的生产部署链。

## Session-control pipeline（规范 §2.2 Pipeline C / §17）

- Session：create → active → close，L1 Initialize/Send/Terminate 可执行。
- Event stream：SESSION_CREATED 与 session 同 transaction；后续 append-only；支持 SSE/list。
- 双 Terminate：L1 contract 的 double-Terminate NO-OP 必须保持。L4 `close_session` 对第二次 close 当前抛 `InvalidStateTransition`，这是 API-level drift，v3.10 仅记录；不能为追求字面一致改变 ADR-V2-017 的 L1 contract。
- 缺口：Event Room、Event 完整状态机、多 Session per Event、crash recovery/recreate、retention/cold archive、reversible compaction orchestration。

## L4 → L1 边界

`L1RuntimeClient` 使用生成的 `runtime_pb2_grpc.RuntimeServiceStub`：

- `Initialize(SessionPayload)`
- `Send(SendRequest)` server streaming
- `ConnectMCP(ConnectMCPRequest)`
- `Terminate(Empty)`

因此 **真 gRPC 贯通成立**。Phase 0.5 注释明确替换了 stubbed runtime events。v3.10 不新增旁路。

## L2 MCP 编排经 L4 下发

Skill Registry 返回 dependencies，L4 调 L2 MCP Orchestrator resolve endpoint，再调用 L1 `ConnectMCP`。MCP 清单、transport、command/args/url 与每-server env map 均在 payload 内传输。部署地址可配置 env，但不以 env 变量注入/发现 skill MCP 依赖。

## L3 governance gate

当前可信基线（v3.7.3）保持：

1. 风险缺省 `read`；
2. tool resolution 后、dispatch 前评估；
3. governance request/final decision append-only；
4. L4 SSE 暴露 request/decision；
5. `write_external` 走批准路径。

规范 §6.9 的 Plan → Check → Draft → Approve → Execute、`approval_chain_policy`、deterministic verifier、OPA/Rego sidecar均缺失。v3.10 不把二元/三元 decision enum 宣称为五阶段链。

## SSE / Event shape

| 事件族 | 当前字段 | 结论 |
|---|---|---|
| response `chunk` | chunk_type/content/tool metadata | aligned to L1 streaming skeleton |
| response `done` | session_id/response_text/events | aligned to MVP output |
| governance request | decision_id/hook_id/tool_name/risk_level/action_preview | aligned to current gate |
| governance decision | decision_id/decision/approver | aligned to current gate |
| Event Engine Event | session_id/event_type/payload/event_id/metadata/created_at/cluster_id/seq | partial vs full L4 event object |

## 不在 v3.10 实现

OPA backend、五阶段审批链、A2A/Event Room、L5 Cowork UI、Marketplace/生态扩展。上述均须在 DEFERRED_LEDGER 有 owner 和后续 milestone。
