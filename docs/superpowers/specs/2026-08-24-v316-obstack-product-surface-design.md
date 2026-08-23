# v3.16 OBSTACK 产品面收口设计

**状态:** Approved for autonomous execution  
**日期:** 2026-08-24  
**替代范围:** `2026-08-09-obstack-v3-15-6-completion.md` 中尚未执行的 6d/6e 骨架

## 目标

在不发明后端契约的前提下，完成现有 OBSTACK 产品面的真实缺口：

1. `web/` 基于 L4 现有六个 business-flow endpoint 提供实时 SSE、统计、告警和优化建议；
2. `eaasp flow` 增加 `list`、`top-failed`、`top-slow`；
3. L4 session 读接口返回已经持久化的 `business_key`，CLI session list/show 展示它；
4. 对没有数据源的 grid-eval、marketplace health、policy decision-rate、memory labels 和 multi-tenant proxy 明确延期；
5. 用正向、负向和双门验证收口。

## 证据校准

旧 D-53/D-54 把三个不同边界混在一起：

- L4 在 `:18084` 拥有 `/v1/business-flows/*`；
- `web/` 已经拥有 OBSTACK list/detail UI，并明确直接访问 L4；
- `web-platform` 只有 Grid 多租户通用页面，`grid-server` 没有 OBSTACK proxy。

因此：

- 不在 `grid-server` RBAC catalog 增加没有真实 handler 的条目，路由基线保持 134；
- 不复制现有 OBSTACK UI 到 `web-platform`；
- 不调用不存在的 `/alerts`、`/stats`、`/optimize` endpoint；
- 不把 `session_id` 假称为 canonical `session|skill|business_object` key；
- 不从 marketplace 生命周期计数伪造业务流健康度。

## 所有权与数据流

```text
L4 /v1/business-flows/{list,timeline,summary,sessions,evaluation,events/stream}
             ├── web/src/api/flows.ts
             │      ├── list/detail JSON
             │      └── authenticated fetch-based SSE parser
             │              └── Flows / FlowsDetail operator views
             └── eaasp_common.ObstackClient
                    └── eaasp flow list/top-failed/top-slow

L4 sessions.business_key (already persisted)
             └── get_session/list_sessions response
                    └── eaasp session list/show
```

`grid-server`、`web-platform`、`grid-eval`、`eaasp-ecosystem` 不在本次数据流上。

## Web 行为

### 现有契约复用

保留 `ObstackClient` 和 `flowsApi` 兼容面。新增 fetch-based SSE 方法，而不是浏览器 `EventSource`，因为 fetch 能携带现有 Bearer token、支持 `AbortSignal`，并能对非 2xx 状态使用与 JSON 调用一致的错误语义。

SSE parser 只接受 `data: <json>` frame；忽略空行和非 data 行；流结束时不把正常 EOF 当错误；取消时不显示错误。解析出的事件追加到当前 timeline，并用 `(ts, layer, component, event_type, stable-json(payload))` identity 去重。

### 派生视图

- Stats 仅由 `/list` 返回值派生：total、failed、active、closed、completion ratio、p95-like slow list（按 `last_duration_ms` 降序展示，不冒充服务端 p95）。
- Alerts 仅由真实 flow row 派生：failed 为 critical，active 且持续时间超过阈值为 warning。
- Optimize 使用 `/evaluation` 的 `hints`，不创建新 endpoint。
- SSE 到达后只刷新当前 detail 的 summary/timeline/evaluation；不会伪造 list aggregate。

## CLI 行为

- `flow list`: 调用 `list_business_flows(FlowListParams)`；支持 `--limit`、`--status`、`--business-object-id`。
- `flow top-failed`: 用服务端最大候选窗 `limit=200,status=failed` 请求 rows，按 `failed_count`、`last_started_at` 降序后截取用户 `--limit`。
- `flow top-slow`: 用服务端最大候选窗 `limit=200` 请求 rows，过滤 `last_duration_ms is not None`，按 duration 降序后截取用户 `--limit`。
- 空集合返回成功并打印明确的 `(no ... flows)`，传输/HTTP 错误保持共享 client 的非零退出行为。
- `session list/show` 只展示 L4 返回的 `business_key`；旧 NULL 行显示为空，不推断。

## L4 session 契约

`sessions.business_key` 已有 schema、migration、create header persistence。本次只把列加入：

- `SessionOrchestrator.get_session()` SELECT 和返回 dict；
- `SessionOrchestrator.list_sessions()` 两个 SELECT 和返回 dict。

兼容规则：历史行返回 JSON `null`。不改 create contract、不改 key 解析、不改数据库 schema。

## 明确延期

下列项目需要新的服务所有权或数据契约，登记到 `DEFERRED_LEDGER.md`，不阻塞本次真实收口：

- `V316-MULTITENANT-OBSTACK-01`: web-platform/grid-server authenticated proxy + real RBAC routes；
- `V316-EVAL-OBSTACK-01`: grid-eval 的 OBSTACK input adapter；
- `V316-ECOSYSTEM-HEALTH-01`: marketplace skill health 与 policy/memory business-key projections。

这些项只有在 producer API 明确、tenant isolation 和鉴权边界确定后才能实施。

## 错误与安全

- malformed business key 继续由 L4 strict parser 返回 400；客户端不改写 key。
- fetch SSE 必须检查 status、处理缺失 body、支持 abort，并不在日志暴露 token。
- 不新增端口、环境变量、shared-core 分支或 customer-specific integration。
- `make rbac-audit` 必须仍为 134 routes；`make v3.10-spec-audit` 必须 PASS。

## 验收矩阵

| 门 | 权重 | 必须通过 |
|---|---:|---|
| Dashboard | 30 | Web contract/derived-view/component tests + build |
| CLI | 25 | 新 flow commands tests |
| BusinessKey | 20 | L4 response + CLI list/show tests |
| Scope integrity | 10 | route ownership/deferral negative audit |
| Final verification | 15 | 聚合脚本、RBAC/spec dual-gates、malformed-key/SSE controls |

总分 100 才满足 climb target；每一门单独判定，不能用其他门的分数替代。

最终脚本必须自己启动或复用可验证的 L4，并硬性检查 malformed-key 400 与至少一个 SSE `data:` frame；不能用会跳过 Playwright 的旧 E2E 结果代替这些门。
