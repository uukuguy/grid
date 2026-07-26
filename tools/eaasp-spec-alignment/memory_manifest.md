# MAT：L2 Memory 与 Skill Manifest 对齐

## Memory Engine（规范 §7.7 / §12）

规范正文明确列出 **6 个** MCP 工具；当前实现有第 7 个 `memory_confirm`，它是文件状态机 `agent_suggested → confirmed` 的显式治理操作。v3.10 将其判为向后兼容扩展，不改名、不删除。

| 规范能力 | 当前实现符号 | 请求 / 返回要点 | 状态 |
|---|---|---|---|
| `memory_search` | `MCP_TOOL_MANIFEST`; `McpToolDispatcher._memory_search` | query 必填；top_k 1..MAX_TOP_K；scope/category；返回 hits；HybridIndex 含 keyword/semantic/time-decay | aligned |
| `memory_read` | `_memory_read` | memory_id 必填；返回 latest MemoryFile；not_found 带可操作提示 | aligned |
| `memory_write_anchor` | `_memory_write_anchor`; `AnchorStore.write` | event/session/type 必填；anchor append-only | aligned |
| `memory_write_file` | `_memory_write_file`; `MemoryFileStore.write` | scope/category/content 必填；可选 memory_id/evidence/status；版本递增 | aligned |
| `memory_list` | `_memory_list` | scope/category/status；limit 1..200；offset ≥0；返回 memories | aligned |
| `memory_archive` | `_memory_archive` | memory_id；状态迁移到 archived | aligned |
| `memory_confirm`（实现扩展） | `_memory_confirm` | memory_id；agent_suggested → confirmed | aligned |

### 已确认差距

- 规范写“6 MCP tools”，Requirements bootstrap 写“7 tools（含 confirm）”；实现以 7 为当前 contract。矩阵保留该版本差异，审计器锁定 7，避免 silent deletion。
- Event 下跨 session 共享、team/org 可见性、optimistic version locking 尚未形成完整平台策略。
- Ontology MCP 三工具不属于 Memory 7-tool catalog，当前缺失。

## Skill Manifest（规范 §7.2-§7.6）

| 规范字段/能力 | 当前实现 | 状态 | 说明 |
|---|---|---|---|
| `name` | `V2Frontmatter.name`; `SkillMeta.name` | aligned | legacy frontmatter 可解析 |
| `version` | `V2Frontmatter.version`; `SkillMeta.version` | aligned | registry 版本化 |
| entrypoints / workflow | `V2Frontmatter.workflow.required_tools` | partial | 有工作流 required_tools，无通用 entrypoints map |
| `required_tools` | `WorkflowMetadata.required_tools: Vec<RequiredTool>` | aligned | 支持 l0/l1/l2 namespace + legacy bare name |
| `mcp_servers` | `V2Frontmatter.dependencies` 中 `mcp:*` | partial | 语义已实现但字段名为 dependencies；L4 经 resolver 下发 |
| permissions | `access_scope` + `risk_level` + hook filters | partial | 无统一 permissions object |
| runtime affinity | `RuntimeAffinity { preferred, compatible }` | aligned | typed structure |
| scoped hooks | `ScopedHooks` / `ScopedHookBody` | aligned | PreToolUse/PostToolUse/Stop |
| promotion lifecycle | `SkillStatus::{Draft,Tested,Reviewed,Production}` | partial | 状态存在；完整自动测试/角色 gate 尚非生产实现 |

## MCP 配置传输边界

`V2Frontmatter.dependencies` → L4 `SessionOrchestrator` 过滤 `mcp:*` → `McpResolver` POST `/v1/mcp/resolve` → L2 `McpManager.resolve_dependencies` → L4 `L1RuntimeClient.connect_mcp` → proto `ConnectMCPRequest`。

- **零 env 发现：满足。** server 选择与配置经 HTTP + gRPC payload，不靠为 L1 设置发现类环境变量。
- `McpServerDef.env` 是 server config 中显式传输的每-server env map（可用于 server credentials/config）；它不是发现机制，也不应被记录到日志。
- `EAASP_MCP_ORCH_URL` 与 L1 endpoint env 是部署地址配置，不携带 skill MCP 清单。

## v3.10 结论

当前 MAT 骨架足以支撑 Phase 0.5 可执行链路。缺口需要 schema / service / authorization 架构扩展，超过 ≤10 LOC 修补界限，登记 deferred，不在 v3.10 伪实现。
