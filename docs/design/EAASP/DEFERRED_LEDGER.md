# EAASP v2.0 Deferred Items 总账

> **Single Source of Truth** — 本文件是所有 Deferred 项的唯一权威登记处。
> 新增 / 关闭 / 迁移 D 编号都必须同步更新本文件，并在 commit message 引用 `Dxx`。

**最后更新**: 2026-05-24 (Phase 6.0 Plan 01 close — NEW-X4 ✅ CLOSED via parametrize rename `runtime_name` → `expected_runtime` @ `e27e300` + CI run 26356947711; ZERO ScopeMismatch across all 7 completed jobs). Prior: 2026-05-23 (Phase 5.5 post-push CI scan — add NEW-X4 P2 pre-existing chunk_type fixture-scope failure to v3.2+ inbox; NOT a Phase 5.5 regression — Phase 3 Contract Matrix has been RED since 2026-05-04 across all pushes). Prior: 2026-05-22 (Plan 02 Task 02.05 milestone close cascade 5-row sweep — 4 closed + 2 P3 deferred; closed count 42 → 46; ADR-V2-029 + V2-032 Accepted)
**维护规则**: 每次 end-phase 或 Deferred 状态变更时更新 [状态变更日志](#状态变更日志) 并同步 [全局活跃清单](#全局活跃清单-eaasp-v20)。

---

## 重要发现：多命名空间

项目历史上的 D 编号**不是单一全局空间**，存在 **4 个独立命名空间**：

| 命名空间 | 来源 | 编号范围 | 状态 |
|----------|------|----------|------|
| **Legacy-Octo** | 旧 octo-sandbox (2026-03-xx phase 文档) | D1–D13（多个 plan 各自独立） | 均为 pre-EAASP，多已 ✅ 完成或并入后续 plan |
| **EAASP Phase 0** | `2026-04-11-v2-mvp-phase0-plan.md` | D1–D61 | 本 ledger 主体 |
| **EAASP Phase 1 Plan** | `2026-04-13-v2-phase1-plan.md` | D62–D66（推迟容器化） | 继承到 Phase 2/3 |
| **EAASP Phase 1 Design** | `PHASE1_EVENT_ENGINE_DESIGN.md` + ADR-V2-001/002/003 | D73–D80 | Event Engine 扩展方向 |
| **EAASP Phase 1 E2E** | 运行时暴露 (checkpoint.json) | D83–D89 | Phase 2 处理中 |

⚠️ **编号缺口**（非冲突，保留未用）:
- D67–D72: 规划未分配
- D81–D82: 规划未分配

**本 ledger 的主编号以 EAASP 命名空间为准（D1–D89）**。Legacy-Octo 的早期 D 编号仅在附录列出。

---

## EAASP v2.0 真正需修清单（2026-04-14 重分类）

> 针对 v2.0 架构**逐项重审**结果。40 项原 active → **12 项真需修 + 26 项降级归档**。

### 🔥 P0 — Phase 2 plan 已排期（5 项 D 编号 + 2 项非 D 任务）

| ID | 标题 | 处理位置 | 影响 |
|----|------|----------|------|
| **D83** | grid-runtime ToolResult chunk 缺 `tool_name` | ✅ **S1.T4 closed 2026-04-14** @ `bdc5b8b` | runtime 侧工具识别（已修；衍生 D90 follow-up） |
| **D85** | `STOP` event `response_text` 空串 | ✅ **S1.T5 closed 2026-04-14** @ `bdc5b8b`+`d0e6cb0` | 上层 CLI 显示不出最终回答（已修 Rust+Python 双侧） |
| **D86** | claude-code-runtime SDK wrapper 丢 `ToolResultBlock` | ✅ **S1.T3 closed 2026-04-14** @ `d0e6cb0` | POST_TOOL_USE hook 空链路（已修） |
| **D84** | CLI `session events --follow` SSE 未实现 | ✅ **S4.T2 closed 2026-04-15** @ `bd55bc4` | CLI UX |
| **D89** | CLI `session close` 未实现 | **S4.T1** | CLI UX |
| (非 D) | S1.T6 ErrorClassifier | ✅ **closed 2026-04-14** @ `4001de2` | 解锁 S1.T7 + S3.T1 |
| (非 D) | S1.T7 withRetry | ✅ **closed 2026-04-14** @ `8b532cb` | Runtime 容错（graduated retry + jitter + FailoverReason routing） |

### 🟡 P1 — 功能缺口必补（4 项，新挂到 S2/S3）

| ID | 标题 | 建议挂靠 | 必须原因 |
|----|------|----------|----------|
| **D50** | `ScopedHookBody::Prompt` executor loop 未实装 | **S3 新增 T5** | SKILL 里 Prompt hook 类型功能上不存在 |
| **D53** | D49 helper 写了但 runtime 没调用 | **S3 新增 T5** | scoped-hook executor 真空 |
| **D51** | Hook stdin envelope schema 未 ADR 化 | **S3 T5 前置，新增 ADR-V2-006** | D50/D53 实施前必须先定义契约 |
| **D78** | Event payload embedding 向量索引 | **S2.T1 扩展** | 与 semantic 检索共 HNSW 架构 |

### 🟢 P2 — S2 顺带完成（2 项）

| ID | 标题 | 建议挂靠 |
|----|------|----------|
| **D12** | L2 connection-per-call → store 级长连接 | **S2.T1 前置** (hnswlib 接入时必然改) |
| **D60** | verify-v2-mvp assertion 11 hybrid search 降级 | **S2.T5 收尾** (升级为硬断言) |

### 🔵 P3 — 可选加速（1 项）

| ID | 标题 | 建议 |
|----|------|------|
| **D74** | EmitEvent gRPC 反向通道 (L1→L4) | Phase 2 完成后视情况，若 event clustering 需要再上 |

**P0+P1+P2+P3 合计 12 项（扣除非 D 编号的 S1.T6/T7）**

### 最近完成（2026-04-14）

| ID | 标题 | 证据 |
|----|------|------|
| **D87** | grid-engine agent loop 多步工作流早终止 | ✅ ADR-V2-016 · `bdc4fd5`+`c0f98f9`+`8a738b1` · Multi-model E2E |
| **D88** | hermes-runtime stdio MCP 缺失 | ⏸️ ADR-V2-017 · 由 Phase 2.5 goose-runtime 替代 |
| **S1.T6** | ErrorClassifier (hermes pattern in Rust) | ✅ `4001de2` · 14 FailoverReason variants + RecoveryActions + 36 tests |
| **D86** | claude-code-runtime SDK wrapper ToolResultBlock 丢失 | ✅ S1.T3 · `d0e6cb0` · `_tool_result_chunk` helper + UserMessage branch + 6 tests |
| **D83** | grid-runtime ToolResult chunk 缺 tool_name | ✅ S1.T4 · `bdc5b8b` · enum field + 10+ pattern-match sites (衍生 D90 WS follow-up) |
| **D85** | STOP event response_text 空 | ✅ S1.T5 · `bdc5b8b`+`d0e6cb0` · event_to_chunk(Completed) extract text + Python accumulator |
| **S1.T7** | Graduated retry with backoff | ✅ `8b532cb` · RetryPolicy::graduated() + ±15% jitter + FailoverReason::recovery_actions 路由 |

---

## D 编号详细登记（EAASP 命名空间）

**状态图例**（2026-04-14 重分类后）：
- ✅ **closed** — 已完成
- 🔄 **superseded** — 被另一 D 编号或 ADR 取代
- ⏸️ **frozen** — 对应模块冻结（如 hermes）
- 🔥 **P0-active** — Phase 2 plan 已排期
- 🟡 **P1-active** — 真功能缺口，已挂到 S2/S3
- 🟢 **P2-active** — S2 顺带
- 🔵 **P3-active** — 可选加速
- 🧹 **tech-debt** — 纯代码整洁度，不影响功能，Phase 2 后批量清
- 📦 **long-term** — Phase 4/5/6 长期路线，当前视野移除
- 🔴 **phase3-gated** — 依赖 Phase 3 身份/租户模型
- 🤔 **revisit-after-S2** — 需 S2 context engineering 决策后再判断

### D1–D15: Phase 0 S3 产生（L2/L3 服务基础设施）

| ID | 标题 | 引入 | 状态 | 证据 / 去向 |
|----|------|------|------|------|
| **D1** | grid-runtime harness 接入 `payload.policy_context` (P1) | phase0 S3.T3 | ✅ closed | ADR-V2-004 S4.T2 4b-lite |
| **D2** | grid-runtime harness 接入 `payload.memory_refs` (P3) | phase0 S3.T3 | ✅ closed | ADR-V2-004 `build_memory_preamble` |
| **D3** | harness 接入 `payload.user_preferences` (P5) + `trim_for_budget()` | phase0 S3.T3 | ✅ CLOSED 2026-06-01 Phase 7.0 Plan 01 @ `79d426c` — deferred per scope ceiling | **Resolution**: ENGINE-02 closed as DEFERRED, no code change in Phase 7.0. Per CONTEXT.md §domain Out-of-scope: full D3 work (harness reading `payload.user_preferences` + budget-driven `trim_for_budget()` invocation in place of turn-boundary trims) is too large to land alongside the D102 wiring + 4 sibling P3 closures without breaking the cohesion ceiling of a single plan. Routed to **v3.4+** payload-schema review (separate D-row to be opened post-milestone for explicit tracking). The ROADMAP Phase 7.0 success criteria SC#3 explicitly allows ENGINE-02..06 to close as "decision: defer-with-justification + LEDGER row 保留 P3" — this row exercises that allowance. No production behavior changes; user_preferences continue to be inert in the harness; budget trims continue at turn boundaries. |
| **D4** | harness 接入 `payload.event_context` (P2) | phase0 S3.T3 | ✅ closed | Phase 1 ADR-V2-002 |
| **D5** | grpc_integration 测试迁移到 v2 telemetry envelope | phase0 S3.T3 | ✅ CLOSED 2026-06-02 Phase 7.1 Plan 01 @ `<commit>` | **Resolution**: Verify-not-rewrite per CONTEXT.md D-03. Ran `rg "telemetry_v1" -t rust crates/ tests/` → 0 hits. Ran `rg "TelemetryV1\|telemetry::v1\|telemetry_envelope_v1" -t rust crates/ tests/` → 1 hit on a documentation-only line at `crates/grid-runtime/tests/grpc_integration.rs:360` inside the `#[ignore = "TODO(s2.t1): rewrite for v2 terminate telemetry envelope"]` placeholder test (the `// v1 bundled a final_telemetry batch inside TerminateResponse;` comment is descriptive prose, not a code reference). Production code path uses `proto::TelemetryRequest` from the v2 envelope (verified at `grpc_integration.rs:234` `.emit_telemetry(proto::TelemetryRequest {...})`). `harness_payload_integration.rs:1-20` carries no v1 reference (plan-checker drift; the planned single-line comment update is a no-op). No production-code migration required. @ `<commit>`. |
| **D6** | certifier 补充 SessionPayload P1–P5 字段断言 | phase0 S3.T3 | [P3-async-when-touched] 🤔 revisit-after-S2 rationale: certifier SessionPayload assertions chained to D3/D5 decisions; touch when those land | 等 D3/D5 决策后一并 |
| **D7** | EmitEvent 真实实现 | phase0 S3.T3 | ✅ closed | Phase 1 ADR-V2-001 |
| **D8** | `access_scope` 真实 RBAC 执行 | phase0 S3.T1 | [P2-next-milestone] 🔴 phase3-gated rationale: Phase 3 RBAC capability needed; batch with other phase3-gated rows in identity/tenancy module | Phase 3 身份与租户模型 |
| **D9** | `skill_usage` 返回真实遥测 | phase0 S3.T1 | [P2-next-milestone] 🔴 phase3-gated rationale: Phase 3 L3 telemetry + L2 aggregation; batch with D8/D38/D46 RBAC module | L3 telemetry ingest + L2 聚合 |
| **D10** | S3.T1 MCP REST facade 升级为真 rmcp ServerHandler | phase0 S3.T1 | [P3-async-when-touched] 🧹 tech-debt rationale: L2/L3/L4 MCP REST→rmcp ServerHandler unification; touch when MCP layer refactors | L2/L3/L4 统一切换契机 |
| **D11** | skill-registry `scope` 过滤在 `LIMIT` 之后 | phase0 S3.T1 | [P3-async-when-touched] 🧹 tech-debt rationale: skill-registry SQL query order tweak; touch when skill-registry next refactors | migration + 索引 |
| **D12** | L2 memory-engine connection-per-call 延迟浪费 | phase0 S3.T2 | [P2-next-milestone] 🟢 **P2-active** rationale: L2 memory-engine MemoryStore singleton refactor; pairs with D94/D98 in L2 mega-sweep batch (see ROADMAP §v3.3 候选) | **S2.T1 前置**（hnswlib 接入必改） |
| **D13** | L2 `archive()` 创建 "archive of archive"，FTS 仍可搜 | phase0 S3.T2 | [P3-async-when-touched] 🧹 tech-debt rationale: L2 archive semantics tweak; touch when L2 archive surface next refactors | 归档检索语义明确后 |
| **D14** | L2 `index._row_to_memory` 跨模块访问私有符号 | phase0 S3.T2 | [P3-async-when-touched] 🧹 tech-debt rationale: L2 cross-module private symbol access; mechanical refactor when L2 next touched | 重构为公共符号 |
| **D15** | L2 memory-engine 缺 `[tool.ruff]` / `[tool.mypy]` | phase0 S3.T2 | [P3-async-when-touched] 🧹 tech-debt rationale: L2 lint config alignment; touch when L2 dev-config sweep | 统一 lint 配置 |

### D16–D26: Phase 0 S3.T3 (L3 governance) — 全部 tech-debt 或运维

| ID | 标题 | 状态 | 备注 |
|----|------|------|------|
| **D16** | L3 policy_engine.deploy() 在 commit 前读 `created_at` | [P3-async-when-touched] 🧹 tech-debt rationale: L3 SQLite RETURNING refactor; touch when L3 governance next refactors | SQLite RETURNING 子句 |
| **D17** | L3 validate_session() `hook["hook_id"]` KeyError 风险 | [P3-async-when-touched] 🧹 tech-debt rationale: L3 KeyError guard tweak; touch when L3 governance next refactors | 增加守卫 |
| **D18** | L3 validate_session() 对 `session_id` path param 不校验 | [P3-async-when-touched] 🧹 tech-debt rationale: L3 path-param validation; touch when L3 next refactors (merged with D29 per row note) | 与 D29 合并 |
| **D19** | L3 switch_mode() 接受任意 hook_id 静默创建 override | [P3-async-when-touched] 🧹 tech-debt rationale: L3 switch_mode silent-create; touch when L3 governance next refactors | warn 或 404 |
| **D20** | `_sanitize_errors()` 仅在 L3 定义，L2 也需要 | [P3-async-when-touched] 🧹 tech-debt rationale: L3 _sanitize_errors → eaasp_common abstraction; touch when next L2+L3 shared-helper pass | 抽到 `eaasp_common` |
| **D21** | L3 `managed_settings_versions` / `telemetry_events` 无保留策略 | [P3-async-when-touched] 📦 long-term rationale: L3 TTL retention; ops-side concern, touch with operational rollout | 运维侧 TTL 策略 |
| **D22** | L3 无全局 FastAPI exception handler | [P3-async-when-touched] 🧹 tech-debt rationale: L3 global exception handler; touch when L3 next refactors (merged with D28) | 与 D28 合并 |
| **D23** | L3 无 loguru/logging 初始化 | [P3-async-when-touched] 🧹 tech-debt rationale: L3 logging init; touch when L3 next refactors (merged with D31) | 与 D31 合并 |
| **D24** | IDE Pyright missing-import 假阳性 | [P3-async-when-touched] 🧹 tech-debt rationale: Pyright false positives; DevEx polish, touch when next pyrightconfig sweep | DevEx, pyrightconfig.json |
| **D25** | L3 无并发部署 E2E (HTTP 栈) | [P3-async-when-touched] 📦 long-term rationale: L3 concurrent deploy E2E; ops-side load test, deferred | 运维侧 load test |
| **D26** | L3 tests 用 `time.sleep(1.1)` 防撞秒 | [P3-async-when-touched] 🧹 tech-debt rationale: L3 time.sleep tiebreaker; touch when L3 monotonic clock next refactors | 单调 tiebreaker 列 |

### D27–D45: Phase 0 S3.T4+ (L4 + CLI v2)

| ID | 标题 | 状态 | 备注 |
|----|------|------|------|
| **D28** | L4 无全局 exception handler (D22 复现) | [P3-async-when-touched] 🧹 tech-debt rationale: L4 global exception handler (D22 duplicate); touch when L4 next refactors | 与 D22 合并 |
| **D29** | L4 `/v1/sessions/{id}/*` path param 未校验 | [P3-async-when-touched] 🧹 tech-debt rationale: L4 path-param validation; touch when L4 next refactors | 与 D18 合并 |
| **D30** | L2/L3 `busy_timeout=5000` 未统一 | [P3-async-when-touched] 🧹 tech-debt rationale: L2/L3 busy_timeout unification; touch when eaasp_common.connect() refactors | `eaasp_common.connect()` |
| **D31** | L4 无 loguru 初始化 | [P3-async-when-touched] 🧹 tech-debt rationale: L4 loguru init; touch when L4 next refactors (merged with D23) | 与 D23 合并 |
| **D32** | L4 无并发 `create_session` 压力测试 | [P3-async-when-touched] 📦 long-term rationale: L4 concurrent create_session load test; ops-side, deferred | 运维侧 load test |
| **D33** | L4 SESSION_CREATED 事件 payload 重复存储 | [P3-async-when-touched] 🧹 tech-debt rationale: L4 SESSION_CREATED reference-mode rewrite; touch when L4 event payload next refactors | 改引用式 |
| **D34** | L4 无 Intent → skill_id NLU 解析 | [P2-next-milestone] 🔴 phase3-gated rationale: Phase 3 NLU intent→skill_id; batch with phase3-gated L4 mega-sweep | Phase 3+ NLU 或 L5 portal |
| **D36** | L4 event window 无 cursor (>10k 事件触发) | [P3-async-when-touched] 📦 long-term rationale: L4 event window cursor; ops-side scale concern, deferred to Phase 3+ | Phase 3+ |
| **D37** | L4 `context_assembly` 硬编码 `allow_trim_p4=False` | [P3-async-when-touched] 🤔 revisit-after-S2 rationale: L4 allow_trim_p4 hardcode; chained to D3 decision, touch together | 与 D3 关联 |
| **D38** | L4 `L2Client.search_memory` 未传 `user_id` | [P2-next-milestone] 🔴 phase3-gated rationale: L4 search_memory user_id propagation; pairs with D8/D9/D46 in RBAC batch | 跨租户隔离，Phase 3 RBAC |
| **D39** | L4 `PolicyContext.policy_version` 用 `str(int)` 而非哈希 | [P3-async-when-touched] 🧹 tech-debt rationale: L4 PolicyContext.policy_version hashing; touch when evidence-chain refactor lands | evidence chain 时顺带 |
| **D41** | eaasp-cli-v2 `session list` 无后端 endpoint | [P2-next-milestone] 🔴 phase3-gated rationale: eaasp-cli-v2 session list endpoint; batch with phase3-gated tenancy items | 多租户同步 |
| **D42** | cli-v2 test_client 未覆盖 5xx exit_code=4 | [P3-async-when-touched] 🧹 tech-debt rationale: cli-v2 test_client 5xx exit_code coverage; touch when cli-v2 test suite refactors | 补测 |
| **D43** | cli-v2 pyproject `respx>=0.21` 未使用 | [P3-async-when-touched] 🧹 tech-debt rationale: cli-v2 unused dep removal; mechanical, touch when next pyproject sweep | 删除 dep |
| **D44** | cli-v2 `cmd_session.show` 硬编码 `limit=100` | [P3-async-when-touched] 🧹 tech-debt rationale: cli-v2 cmd_session.show limit flag; touch when cli-v2 next exposes flags | S4 时顺带暴露 flag |
| **D45** | cli-v2 响应 shape 假设 → default exit 1 | [P3-async-when-touched] 🧹 tech-debt rationale: cli-v2 response-shape guard; touch when cli-v2 error mapping next refactors | response-shape guard |

### D46–D53: Phase 0 S4.T1 (Skill + Hook 扩展)

| ID | 标题 | 状态 | 备注 |
|----|------|------|------|
| **D46** | Skill `access_scope` 无 RBAC / 命名空间校验 | [P2-next-milestone] 🔴 phase3-gated rationale: Skill access_scope RBAC enforcement; batch with phase3-gated RBAC items (D8/D9/D38/D41) | Phase 3 policy backend |
| **D47** | mock-scada.py argparse stub | ✅ closed | `tools/mock-scada/` (2026-04-12) |
| **D48** | `ScopedHookBody` 无 `matcher` / `tool_filter` 字段 | [P3-async-when-touched] 🧹 tech-debt rationale: ScopedHookBody matcher/tool_filter v2.1 schema; touch when hook schema next breaks | hook schema v2.1 |
| **D49** | `${SKILL_DIR}` 变量替换 helper | ✅ closed | `substitute_hook_vars` (2026-04-12) |
| **D50** | `ScopedHookBody::Prompt` executor loop 未实装 | [P3-async-when-touched] 🟡 **P1-active** rationale: ScopedHookBody::Prompt LLM-driven yes/no executor; per S3.T5 blueprint §F not in scope unless real skill uses it | **S3 新 T5 hook executor** |
| **D51** | Hook stdin envelope schema 未 ADR 化 | ✅ closed 2026-04-15 | S3.T5 @ `7cb48eb` (ADR-V2-006 Accepted) |
| **D52** | SKILL.md prose 与 L2 MCP tool schema 一致性 | ✅ closed | 逐字对照验证 (2026-04-12) |
| **D53** | D49 helper 写了但 runtime 没调用 | ✅ closed 2026-04-15 | S3.T5 @ `7cb48eb` (harness `substitute_hook_vars` wiring) |

### D54–D61: Phase 0 S4.T2 (4b-lite + E2E verify)

| ID | 标题 | 状态 | 备注 |
|----|------|------|------|
| **D54** | L4→L1 真 gRPC binding | ✅ closed | Phase 0.5 S1 |
| **D55** | proto3 submessage presence 应统一用 `HasField` | [P3-async-when-touched] 🧹 tech-debt rationale: proto3 HasField helper unification; touch when proto3 layer next refactors | has_field 辅助 |
| **D56** | `verify-v2-mvp.sh` 只清 SQLite | [P3-async-when-touched] 📦 long-term rationale: verify-v2-mvp.sh SQLite-only wipe; ops-side, touch when persistence backend changes | 持久化后端变化时 |
| **D57** | `harness_payload_integration.rs` 复制 `build_memory_preamble` | ✅ CLOSED 2026-06-01 Phase 7.0 Plan 01 @ `60f99d5` | **Resolution**: Promoted `GridHarness::build_memory_preamble` from `pub(crate)` to `pub` at `crates/grid-runtime/src/harness.rs:144`; deleted the `expected_preamble` copy at `crates/grid-runtime/tests/harness_payload_integration.rs` (was lines 470-484); the single caller now invokes the harness helper directly via `GridHarness::build_memory_preamble(&refs)`. Single source of truth restored — no parity test needed because the test reuses the production helper. |
| **D58** | `test_initialize_injects_memory_refs_preamble` 未走 Send 全路径 | ✅ CLOSED 2026-06-01 Phase 7.0 Plan 01 @ `60f99d5` | **Resolution**: Extended `initialize_injects_memory_refs_as_system_preamble` to assert Send-path coverage by snapshotting `GridHarness::build_initial_history_for_payload(&payload)` BEFORE initialize() consumes the payload. The same builder runs inside initialize(), so the snapshot is bit-equal to the `Vec<ChatMessage>` shipped into `start_session_with_tool_filter`. The test now asserts that a `MessageRole::System` content block carrying the memory preamble (with both fact + preference entries) appears in the initial history. Driving a real LLM turn for full session_store read-back is out of scope (no live provider in integration tests); the shared-helper observation is the tightest non-LLM Send-path canary. |
| **D59** | `Makefile::mcp-orch-start` 硬编码 `--port 8082` | [P3-async-when-touched] 🧹 tech-debt rationale: Makefile mcp-orch-start hardcoded port; mechanical, touch when next port standardization | 改为 18082 |
| **D60** | verify-v2-mvp assertion 11 hybrid search 降级 | ✅ closed 2026-04-15 | S2.T5 @ `bad4269` (升级为 `raise AssertionError`) |
| **D61** | `threshold-calibration-skill.md` fixture 硬编码 `version` | [P3-async-when-touched] 🧹 tech-debt rationale: threshold-calibration-skill fixture version parse; touch when skill fixtures next refactor | 解析 submit 响应 |

### D62–D66: Phase 1 Plan (容器化 + MCP 池)

| ID | 标题 | 状态 | 备注 |
|----|------|------|------|
| **D65** | MCP server 多实例 / 连接池 | [P3-async-when-touched] 🧹 tech-debt rationale: MCP server multi-instance/pool; touch when next L2/L3 MCP scale work lands | Phase 2 S2 或 Phase 3 顺带 |

### D67–D72: 保留未用

**占位未分配**。若需新增 Deferred 项，请从 D90 起编号（避免与历史 D67-72 规划保留冲突）。

### D73–D80: Phase 1 Event Engine (ADR-V2-001/002/003)

| ID | 标题 | 状态 | 备注 |
|----|------|------|------|
| **D73** | Event Room 推迟 | [P3-async-when-touched] 📦 long-term rationale: Event Room long-term Phase 4 item; deferred per original 📦 long-term tag | Phase 4 |
| **D74** | EmitEvent gRPC 反向通道 (L1→L4 gRPC server) | [P3-async-when-touched] 🔵 **P3-active** rationale: EmitEvent gRPC reverse channel; original 🔵 P3-active, no second consumer surfaced | Phase 2 可选加速，视 event clustering 需要 |
| **D75** | EventStreamBackend 切换到 NATS JetStream | [P3-async-when-touched] 📦 long-term rationale: NATS JetStream backend; long-term Phase 6 multi-node concern | Phase 6 多节点 |
| **D76** | subscribe() polling → push-based | [P3-async-when-touched] 📦 long-term rationale: subscribe() push-based; long-term Phase 6 scale concern | Phase 6 |
| **D77** | TopologyAwareClusterer (L2 Ontology Service 输入) | [P3-async-when-touched] 📦 long-term rationale: TopologyAwareClusterer ontology input; long-term Phase 5 concern | Phase 5 |
| **D78** | 向量索引 Indexer (event payload embedding) | [P3-async-when-touched] 🟡 **P1-active** rationale: Vector index event payload Indexer; original 🟡 P1-active scoped to S2.T1 expansion, no current consumer driving it | **S2.T1 扩展**（与 semantic 共 HNSW 架构） |
| **D79** | Pipeline 多 worker 并行处理 | [P3-async-when-touched] 📦 long-term rationale: Pipeline multi-worker parallel; long-term Phase 6 scale | Phase 6 |
| **D80** | Clusterer 因果图聚类 (parent_event_id → DAG) | [P3-async-when-touched] 📦 long-term rationale: Clusterer causal DAG; long-term Phase 4 concern | Phase 4 |

### D81–D82: 保留未用

**占位未分配**。

### D83–D90: Phase 1 E2E 暴露（Phase 2 处理）+ Phase 2 衍生

| ID | 标题 | 状态 | 处理位置 |
|----|------|------|----------|
| **D83** | grid-runtime ToolResult chunk 缺 `tool_name` | ✅ closed 2026-04-14 | S1.T4 @ `bdc5b8b` (衍生 D90) |
| **D84** | CLI `session events --follow` SSE 未实现 (合并 D35) | ✅ closed 2026-04-15 | S4.T2 @ `bd55bc4` |
| **D85** | `STOP` event `response_text` 空 | ✅ closed 2026-04-14 | S1.T5 @ `bdc5b8b`+`d0e6cb0` |
| **D86** | claude-code-runtime SDK wrapper 丢 `ToolResultBlock` | ✅ closed 2026-04-14 | S1.T3 @ `d0e6cb0` |
| **D87** 🚨 | grid-engine agent loop 多步工作流过早终止 | ✅ closed 2026-04-14 | ADR-V2-016 · `bdc4fd5`/`c0f98f9`/`8a738b1` · Multi-model E2E |
| **D89** | CLI `session close` 未实现 | ✅ closed 2026-04-15 | S4.T1 @ `28e6b21` |
| **D90** | `ServerMessage::ToolResult` WS schema 缺 `tool_name` 字段（grid-server + grid-platform） | [P3-async-when-touched] 🟡 P1-defer rationale: ServerMessage WS tool_name field; gated on frontend workbench/platform UI decision (grid-server dormant per ADR-V2-024 §1) | 下游 TS 类型级联改造，衍生自 D83。前置条件：frontend workbench/platform UI 决定是否需要工具名显示。目前 CLI / L4 gRPC 已有 tool_name；仅 WS 端丢失 |
| **D91** | HNSW 软删 tombstone rebuild 策略 | [P2-next-milestone] 🟡 P1-defer rationale: HNSW tombstone rebuild compaction; pairs with D94/D98/L2 in v3.3+ L2 mega-sweep batch | `mark_deleted` 标签单调累积；达到 N% 删除率后索引膨胀/搜索延迟劣化。需要触发阈值（建议 30%）+ 后台 compaction 任务。衍生自 S2.T1 → **Phase 2.5** |
| **D92** | MockEmbedding 64-bit seed 碰撞审查 | [P3-async-when-touched] 🔵 P3-defer rationale: MockEmbedding seed collision; tests-only edge case, touch when next L2 test-fixture sweep | SHA-256(text)[:8] 生日碰撞约 2^32。测试场景可接受；若被误用于 staging，两条不同文本可能撞同向量。加宽到完整 32-byte digest 或明确标注 "tests-only"。衍生自 S2.T1 → **Phase 3 GA 前** |
| **D93** | `embed_batch` 顺序实现 | [P2-next-milestone] 🟡 P1-defer rationale: embed_batch parallelization; perf-relevant for L2, pairs with D94/D98 in L2 mega-sweep | `OllamaEmbedding` / `MockEmbedding` 均 `for text in texts: await embed(text)` N 次。Ollama/TEI 均支持真正 batched POST。衍生自 S2.T1 → **S2.T4 或 Phase 2.5** hybrid-search perf pass |
| **D94** | MemoryStore 单例 + 共享连接重构（D12 收尾） | [P2-next-milestone] 🟡 P1-defer rationale: MemoryStore singleton refactor (D12 closeout); core to L2 v3.3+ mega-sweep, pairs with D12/D98 | S2.T1 仅完成 schema 迁移 + pack/unpack helper；`MemoryFileStore`/`AnchorStore`/`HybridIndex` 仍 per-call `connect()`。全 store 单例化需求较大，与 Phase 2.5 runtime ecosystem 工作合并推进 |
| **D95** | FTS 命中的语义分数从 DB `embedding_vec` 回填 | [P3-async-when-touched] 🔵 P2-defer rationale: FTS semantic_score backfill from DB BLOB; touch when L2 hybrid search next refactors | S2.T2 union 阶段只对同时出现在 HNSW 结果中的 FTS 命中打 `semantic_score`；若 HNSW add 静默失败，FTS 命中永远 `sem_score=0`。可从 DB BLOB unpack + 与 query_vec 计算 cosine 回填。衍生自 S2.T2 → **S2.T4 或 Phase 2.5** |
| **D96** | 用户自定义 memory_id 含 `:v` 子串导致 HNSW key 解析丢失 | [P3-async-when-touched] 🔵 P3-defer rationale: memory_id :v parsing edge case; user-supplied-id corner, touch when L2 next refactor | HNSW key 格式 `{memory_id}:v{N}`，`split(":v")` 在 memory_id 含 `:v` 时产生 3 段被静默跳过。建议 (a) `MemoryFileIn.memory_id` 校验禁止 `:v`，或 (b) `rsplit(":v", 1)`。默认自动生成 `mem_{uuid}` 不受影响，仅用户传入自定 id 的边角场景。衍生自 S2.T2 reviewer M1 → **Phase 3 前** |
| **D97** | `weights=(0.0, 0.0)` 退化情形缺少构造期告警 | [P3-async-when-touched] 🔵 P3-defer rationale: HybridIndex weights=(0,0) construct-time warn; ops-rare, mechanical | 所有候选 `score==0`，插入序生效无信息。运维场景罕见，但建议 `HybridIndex.__init__` 下发 `logger.warning("Both weights zero; results will be unordered")`。衍生自 S2.T2 reviewer M2 → **Phase 2.5** |
| **D98** | `HybridIndex.search()` 每次重建 HNSWVectorIndex | [P2-next-milestone] 🟡 P1-defer rationale: HybridIndex per-search HNSW rebuild perf; pairs with D94 MemoryStore singleton in L2 mega-sweep | 每次 search 重新 `_try_load_sync()` 读磁盘 ~10ms；小索引可接受，QPS 上升后变成 perf 热点。承继 T1 同类问题。应随 D94 MemoryStore 单例化一起改为进程级缓存。衍生自 S2.T2 reviewer N3 → **Phase 2.5** |
| **D99** | MCP dispatcher 参数类型强制转换抛原生 `ValueError`/`TypeError` 而非 `ToolError("invalid_arg")` | [P3-async-when-touched] 🔵 P3-defer rationale: MCP dispatcher ValueError→ToolError wrapping; touch when L2 MCP dispatcher next harden | `mcp_tools.py::_memory_list` / `_memory_search` 对 `limit`/`offset`/`top_k` 用 `int(args.get(...))` 直接转换；非法类型/字符串会抛原生异常，绕过 `_require` 的 `ToolError` 包装。预期下游 MCP SDK / REST body parsing 应先做 JSON-schema 校验，但 dispatcher 层应有兜底。不是 S2.T3 引入的回归，是承继既有模式。衍生自 S2.T3 reviewer → **Phase 2.5 dispatcher harden sweep** |
| **D100** | S2.T4 — `write()`/`confirm()`/`archive()` 构造 `MemoryFileOut` 时未 surface `embedding_model_id`/`embedding_dim` | [P3-async-when-touched] 🔵 P3-defer rationale: MemoryFileOut embedding_model_id/dim asymmetry; touch when L2 write-path next refactors | 只有 `read_latest()` → `_row_to_memory` 返回完整字段，写路径 3 个 helper 对称性缺失。S2.T4 test 10 通过 docstring 记录，未断言。衍生自 S2.T4 reviewer → **Phase 2.5** |
| **D101** | FastAPI `HTTPException(detail=dict)` 嵌套 `'detail'` key 的契约 erratum | [P3-async-when-touched] 🔵 P3-defer rationale: FastAPI HTTPException detail nesting erratum; doc-only, touch with next blueprint review | S2.T4 REST 409/404 断言 `resp.json()['detail']['code']` 而非 `resp.json()['code']`；blueprint 描述用了扁平 shape。非 bug，是文档纠误。衍生自 S2.T4 reviewer → **下轮 blueprint 审校同步** |
| **D102** | S3.T1 — `AgentLoopConfig.compaction` 字段未接 YAML 配置层 | ✅ CLOSED 2026-06-01 Phase 7.0 Plan 01 @ `3a23ecb` | **Resolution**: Threaded `CompactionPipelineConfig` end-to-end. Added `Serialize + Deserialize + #[serde(deny_unknown_fields, default)]` to `CompactionPipelineConfig` (`crates/grid-engine/src/context/compaction_pipeline.rs:42`). Added `pub compaction: CompactionPipelineConfig` field with `#[serde(default)]` to grid-server `Config` (`crates/grid-server/src/config.rs`). Added `compaction: Option<CompactionPipelineConfig>` to `AgentRuntimeConfig`, `AgentRuntime`, and `AgentExecutor`; wired via setter `executor.set_compaction_config(...)` at `crates/grid-engine/src/agent/runtime.rs` spawn path; consumed in the per-turn `AgentLoopConfig` struct-literal at `crates/grid-engine/src/agent/executor.rs:508-550`. ADR-V2-028 strict-by-default: missing block → `::default()`; unknown key → `serde::de::Error::unknown_field`. New tests: 2 unit tests in `compaction_pipeline.rs` (roundtrip + reject-unknown) + 3 integration tests in `crates/grid-server/tests/compaction_yaml_wiring.rs` (roundtrip + missing-falls-back + reject-unknown). No `GRID_COMPACTION_*` env-var surface (deferred per CONTEXT.md D-01). `cargo test -p grid-server --test compaction_yaml_wiring` PASS. |
| **D103** | S3.T1 — `find_tail_boundary()` O(N²) 重估风险 | ✅ CLOSED 2026-06-01 Phase 7.0 Plan 01 @ `3e0b055` | **Resolution**: Profile-decide-record per CONTEXT.md D-04. Measured baseline: 200-turn × 200k `tail_protect_tokens` invocation = **21µs** on developer hardware (M-series Mac; see `crates/grid-engine/tests/find_tail_boundary_perf.rs::find_tail_boundary_perf_baseline` output via `--nocapture`). The original LEDGER concern (O(N²) risk) was conservative — actual complexity is O(sum of message sizes) bounded by the tail budget, documented now in the rustdoc above `fn find_tail_boundary` at `crates/grid-engine/src/context/compaction_pipeline.rs:733`. Regression canary lives at `find_tail_boundary_perf_baseline` (50ms ceiling, currently 2400x headroom); if a future refactor inflates the constant, the canary trips before it ships. No algorithmic refactor needed today. |
| **D104** | S3.T1 — 反应式 guard 在 harness 而非 pipeline | ✅ CLOSED 2026-06-01 Phase 7.0 Plan 01 @ `b32d985` | **Resolution**: Doc-only close per CONTEXT.md D-05. As of 2026-06-01 no caller of `CompactionPipeline::compact()` exists outside the harness loop at `crates/grid-engine/src/agent/harness.rs`, so the harness-local `attempted_reactive_compact: bool` guard at line 526 enforces the ADR-V2-018 §D5 per-turn semantic correctly without scaffolding cost. Added a multi-line rustdoc invariant block above the declaration that records: (a) the ADR §D5 anchor, (b) the "only one caller exists today" rationale, (c) the trigger condition for revisit (a second caller emerges → promote guard into the pipeline). No ADR-V2-030 candidate drafted — drafting an ADR for a re-architecture that isn't happening adds documentation debt without enforcement value. Revisit only if a second caller surfaces. |
| **D105** | S3.T1 — `HookPoint::ContextDegraded` 字符串别名保留 | [P3-async-when-touched] 🟡 P1-defer rationale: HookPoint::ContextDegraded backwards-compat alias; touch only at Phase 3 breaking version | `runtime.rs:1899` string-key dispatcher 同时接受 `"ContextDegraded"` 和 `"PostCompact"`，保持既有 YAML/JSON hook 配置 backwards-compat。Phase 3 breaking release 时 deprecate 旧名。衍生自 S3.T1 coder → **Phase 3 breaking version** |
| **D106** | S3.T1 — `MAX_TURNS_FOR_BUDGET=50` 硬编码 | [P3-async-when-touched] 🔵 P3-defer rationale: MAX_TURNS_FOR_BUDGET=50 hardcode; config-knob promotion, touch with next config harden sweep | `harness.rs:120` 常量保守上限；长运行自主 agent 可能过紧，批量脚本可能过松。应成为 `AgentLoopConfig.task_budget_override` 字段。衍生自 S3.T1 coder → **Phase 3 config harden sweep** |
| **D107** | S3.T2 — Stop hook 三-way empty-string 检查的共享 jq fragment | [P3-async-when-touched] 🔵 P3-defer rationale: Stop hook empty-string check shared jq helper; touch when next scoped-hook executor stdlib lands | `threshold-calibration/hooks/check_output_anchor.sh` 和 `skill-extraction/hooks/check_final_output.sh` 都用 `has(x) and (x != null) and (x != "")` 三-way check，S3.T2 reviewer C1 就是 `evidence_anchor_id` 漏掉 `!= ""` 分支导致空字符串被放行。Copy-paste 易漏，应抽成 skill-hook stdlib helper（例如 `${SKILL_DIR}/../../_lib/json_guards.sh` 或内嵌于 runtime hook executor）。衍生自 S3.T2 reviewer → **S3.T5 scoped-hook executor 带共享 lib 一起实现** |
| **D108** | S3.T2 — Hook script 自动化回归测试（bats/shellcheck） | [P2-next-milestone] 🟡 P1-defer rationale: Hook script bats/shellcheck CI; pairs with hook ecosystem in v3.3+ hooks-module batch | S3.T2 C1 靠 orchestrator 手动 4-case 回归才发现，没有持续 CI 保障。应加 `examples/skills/*/hooks/*.bats` 或 unified `scripts/test_hook_scripts.sh` 覆盖 allow/deny/edge-case envelope，集成到 `make verify`。衍生自 S3.T2 reviewer → **S3.T3 E2E 验证 或 Phase 2.5** |
| **D109** | S3.T2 — `workflow.required_tools` 只能列 agent 真正 invoke 的 tool 的不变量未文档化 | ✅ CLOSED 2026-05-20 Phase 5.3 @ `a569b27` | **Resolution**: Documented invariant in `docs/design/EAASP/L1_RUNTIME_ADAPTATION_GUIDE.md` §10.6 (workflow.required_tools must list only reachable tools, with code anchors at harness.rs:1465 + harness.rs:1486 satisfied-branch shortcut, plus the `skill_submit_draft` failure example from S3.T2). Optional skill-parse-time warn check is mentioned as "OPTIONAL, future enhancement" — D109 closes as doc-only per ROADMAP §Phase 5.3 SC#3 ("doc-only sufficient for WATCH-01 closure"); parser-time validation deferred unless a second skill exhibits the same misconfiguration. Cross-refs ADR-V2-016, ADR-V2-020, ADR-V2-026 (ExecutionMode gate that controls when D87 Fix 2 is active in the first place). |
| **D110** | S3.T2 — `dependencies` 字段 soft-intent vs runtime-required 语义不分 | [P3-async-when-touched] 🔵 P3-defer rationale: dependencies soft-intent vs runtime-required schema; touch only at Phase 3 schema breaking version | `dependencies: - mcp:eaasp-skill-registry` 对 skill-extraction 是 soft intent（skill 自己从不调），但 schema 不区分此与 `mcp:eaasp-l2-memory`（runtime-required）。L4 resolution 时可能误把 soft-intent 服务拉起来浪费资源。应有 `dependencies_intent:` vs `dependencies_runtime:` 或每条加 `kind: runtime|intent` 标签。衍生自 S3.T2 设计决策 → **Phase 3 schema refactor（breaking）** |
| **D124** | S4.T2 — L4 `/events/stream` 无 client-disconnect 结构化日志 | ✅ closed 2026-04-15 | 4 结构化日志点：`sse_follow_start`（INFO, 入口）/ `sse_follow_session_gone`（INFO, mid-stream SessionNotFound）/ `sse_follow_idle_exit`（DEBUG, max_idle_polls 触发）/ `sse_follow_disconnect`（INFO, client 断开 → `asyncio.CancelledError` 捕获后 re-raise）。zero regressions (127/127 L4 tests PASS). ruff clean. |
| **D125** | S4.T2 — L4 events 流单次 poll 上限 500 events，burst 超限静默丢失 | [P3-async-when-touched] 🟡 P1-defer rationale: L4 events poll 500/s burst overflow; ops corner, touch when next L1 burst-load observed >1k/sec | `list_events(limit=500)` + 默认 poll_interval_ms=500 → 1000 events/sec 上限。若 L1 在一轮 500ms 内 emit >500 events，第 501 起会进入下一轮，但如果持续过载会无限滞后。应加 overflow 检测 (`len(events) == 500 → log.warning + 缩短下次 poll 间隔`) 或把 limit 提升到 2000。衍生自 S4.T2 reviewer 注记 → **Phase 2.5 if L1 bursts > 1k/sec** |
| **D126** | S4.T3 — `lang/claude-code-runtime-python/.venv` 缺失时 A8 fails late | [P3-async-when-touched] 🔵 P3-defer rationale: S4.T3 venv-missing pre-flight WARNING; DevEx polish, mechanical | `scripts/verify-v2-phase2.sh` 的 pre-flight `check_venv` 循环只覆盖 L2/L3/L4/cli-v2。若 fresh clone 未跑 `make claude-runtime-setup`，A8 要跑到一半才抛 AssertionError（message 指向 setup target 是清楚的，但前面 A1-A7 空跑了 ~30s）。应在 pre-flight 添加 WARNING（non-fatal，因为 skill extraction 是 fixture-replay-可选）。衍生自 S4.T3 reviewer M2 → **Phase 2.5 ergonomics** |
| **D127** | S4.T3 — `data/verify-v2-phase2-skill-registry/` 目录不被清理 | [P3-async-when-touched] 🔵 P3-defer rationale: verify-v2-phase2.sh skill-registry dir cleanup; touch when next harness Phase 2+ assertion reads registry state | `verify-v2-phase2.sh` 的 wipe 块只清 `*.db`/`*.db-shm`/`*.db-wal` glob。但 skill-registry 用 `--data-dir` 挂到目录，里面有 `registry.db` + `skills/*` 子目录。重跑积累残留 manifest。目前无 Phase 2 assertion 查 registry（已核验），是 latent。MVP 的 `verify-v2-skill-registry/` 有同样 gap，继承行为不是新 regression。修法：在 wipe 块加 `rm -rf "$PROJECT_ROOT/data/verify-v2-phase2-skill-registry"`。衍生自 S4.T3 reviewer M3 → **Phase 2.5 when a Phase 2+ assertion starts reading registry state** |
| **D128** | S4.T3 — `@assertion` 装饰器 NOTE 在 PASS 之前打印（UX polish） | [P3-async-when-touched] 🔵 P3-defer rationale: @assertion NOTE ordering polish; UX cosmetic | `@assertion` 装饰器先调用 wrapped function 再 print `PASS N. title`；function body 里的 `print()` NOTE（A5 graceful-degrade、A13 CLI 缺 .venv）会落在 PASS 行之前。阅读顺序是 `NOTE: ...\nPASS 5. ...`，略混乱但内容正确。可切到 post-hoc "notes" channel 或把 NOTE prefix 改为 `└─` 表示是 PASS 的细节。衍生自 S4.T3 reviewer N2 → **Phase 2.5 polish** |
| **D129** | S4.T3 — `verify-v2-phase2.sh` cleanup trap 在 pre-flight 失败时仍 sweep 外部端口 | [P3-async-when-touched] 🔵 P3-defer rationale: verify-v2-phase2.sh cleanup trap port sweep guard; local-dev edge case | `trap cleanup EXIT INT TERM` 无条件运行；`_kill_tree` 用 `$L2_PID` 等变量守护（pre-flight 失败时未设置 → no-op，正确），但 `_kill_port` 是按 PORT 号用 `lsof` sweep，不论这些端口上的进程是否由本脚本启动。实证：2026-04-15 运行 `make v2-phase2-e2e` 时 `make dev-eaasp` 正在另一终端跑，pre-flight 正确检测到 port 18085 被 PID 3398 占用并 exit 1，但随后 trap cleanup 无差别 sweep 了 6 个端口上的所有 listeners，杀掉了用户的 dev-eaasp session。修法：(a) 在 `_kill_port` 前检查对应的 `$*_PID` 是否非空（只 sweep "我们启动过的"），或 (b) pre-flight 失败时 `trap - EXIT` 提前 clear cleanup trap。生产 CI 无 pre-existing 服务不触发，是 local-dev 边角。衍生自 S4.T3 实跑观察 → **Phase 2.5 harness ergonomics** |
| **D130** | S4.T4 — Session-lifetime vs per-turn cancel token 双 token 不一致 | [P3-async-when-touched] 🟡 P1-defer rationale: Session-lifetime vs per-turn cancel token consolidation; touch when next ChildCancellationToken propagation work lands | `SessionEntry.cancel_token`（spawn-time，由 `SessionInterruptRegistry` 托管）与 `AgentExecutor.cancel_token`（每次收 UserMessage 时 reset 到 fresh `::new()`，clone 到 `AgentLoopConfig.cancel_token` 供 harness `:642/:1687` 读）是两个独立 Arc<AtomicBool>。`cancel_session()` 目前双路径触发（registry 标志 + `AgentMessage::Cancel` channel 消息）才能在跑 loop 中间实际打断——path 1 flag 没人读，只是 post-mortem observability；path 2 打到 `executor.cancel_token.cancel()` 是真正触达 harness 的路径。设计更干净的方案：`AgentExecutor` 持有由 `session_interrupts` 注入的 **session-lifetime parent token**，每轮 UserMessage 创建 `parent.child()` 作 per-turn token；fire registry token 通过 parent→child 传播自动到达 in-flight turn，不需要 channel round-trip。前置：`ChildCancellationToken` 当前只读，需加 `cancel()` propagation 语义 + 通过 `AgentLoopConfig.cancel_token` plumbing。衍生自 S4.T4 实装 → **Phase 2.5 consolidation** |
| **D136** | Phase 2.5 S0.T4 — Pre/PostToolUse hook 在 probe turn 未触发（grid-runtime） | ✅ CLOSED 2026-05-20 Phase 5.3 @ `15d322b` | **Resolution**: Root cause confirmed = option (b) from the original entry — mock_openai_server.py only implemented synchronous chat-completion JSON shape, but grid-engine's `OpenAIProvider.stream()` (crates/grid-engine/src/providers/openai.rs:595) ALWAYS sets `stream: true` and parses SSE-delta with the openai.rs:866 shape (`delta.tool_calls[N].{index,id,function.{name,arguments}}`). Without an SSE branch the runtime saw zero events → agent_loop exited → no hooks fired. **Fix**: added `_sse_delta_response` async generator in `tests/contract/harness/mock_openai_server.py` that emits OpenAI-spec SSE chunks with the exact shape openai.rs expects (role chunk → tool_call delta with index+nested function.name/arguments → finish_reason chunk → `data: [DONE]`). The 3 xfail blocks at `tests/contract/conftest.py` (PreToolUse @ L668-674, PostToolUse @ L687-690, Stop @ L702-705) replaced with assertions. Live-runtime PASS confirmation deferred to phase-verify-work checkpoint when `make v2-phase3-e2e` runs end-to-end. Per RESEARCH §F2 this is Option A (preserve production parser strictness; fix the fixture), not Option B (loosen parser to weak mock shape). ADR-V2-016 capability-matrix amendment for `is_probe=true` metadata convention DEFERRED to Plan B (ADR-V2-026 supersede). |
| **D137** | Phase 2.5 S0.T4/T5 — Multi-turn observability + MCP bridge live + PRE_COMPACT 阈值触发 | [P2-next-milestone] 🟡 P1-defer rationale: Contract harness multi-turn + MCP subprocess + PreCompact threshold fixtures; substantial contract-test infra work, batch in v3.3+ contract module | **归属 Phase**: Phase 2.5 W1/W2 成熟期。**归属 Contract Test** (10 xfail cases): `test_event_type.py` 4 cases（CHUNK 流式观测 / terminal STOP 断言 / 非终止 chunk 序列 / ERROR event shape），`test_proto_shape.py::test_events_stream_emits_stop_at_turn_end` 1 case，`test_mcp_bridge.py` 5 cases（真实 stdio 子进程、tool invocation、disconnect、reconnect、error）。**现象**: contract harness 当前为 fixture-driven、single-turn。要覆盖这些 cases 需 harness 引入 (1) multi-turn session replay 框架，(2) MCP subprocess fixture（spawn 真实 L2 memory MCP server），(3) 可脚本化 PreCompact 阈值模拟。**修复路径**: W1/W2 可同步推进；建议 Phase 2.5 W1 先带 multi-turn + MCP 子进程 harness 扩展，W2 复用。衍生自 Phase 2.5 S0.T2+T4+T5 xfail 汇总 |
| **D138** | Phase 2.5 S0.T4/T5 — skill-workflow enforcement 测试需可脚本化 deny-path mock LLM | ✅ CLOSED 2026-06-02 Phase 7.1 Plan 01 @ `<commit>` | **Resolution**: Extended `tests/contract/harness/mock_openai_server.py` + `mock_anthropic_server.py` with `X-Test-Scenario` header routing + `scenario_responses` parameter (T04). Added `tests/contract/harness/scenario_fixtures.py` with `OPENAI_DENY_SCENARIOS` / `ANTHROPIC_DENY_SCENARIOS` covering deny-non-required-tool / unknown-tool / multi-tool-permutation. Wired scenario propagation through the in-contract `UserMessage.metadata["x-test-scenario"]` map (no env-var shim — ADR-V2-028 strict-by-default respected): grid-runtime harness reads the metadata key, propagates it to a session-scoped value via `grid_engine::providers::test_scenario`, and `crates/grid-engine/src/providers/openai.rs` reads that value and sets `X-Test-Scenario` on the outbound `reqwest::RequestBuilder`. All 5 D138 xfails in `tests/contract/contract_v1/test_skill_workflow.py` flipped to live drive_session-based tests; deny-path emits CHUNK_TYPE_ERROR or refuses the offender's tool dispatch, no live LLM required. `cargo check -p grid-engine -p grid-runtime` PASS; `pytest test_harness_smoke.py` 9/9 PASS (scenario-routing infra); `pytest contract_v1/test_skill_workflow.py --runtime=grid` deferred to CI (Send-path hang unrelated to T05; same caveat applies to T01/T02 tests). @ `<commit>`. |
| **D139** | Phase 2.5 S0.T4 — 双 Terminate + 未知 session 语义未明 | [P3-async-when-touched] 🔵 P3-defer rationale: Double-Terminate + unknown-session canonical error code; ADR-V2-017 §2 increment, touch when contract evolution next runs | **归属 Phase**: Phase 2.5 W1。**归属 Contract Test**: `test_e2e_smoke.py::test_close_idempotent_on_already_closed_session` + `test_e2e_smoke.py::test_send_without_initialize_errors_cleanly` （2/5 xfail）。**现象**: grid-runtime 对 double-terminate 返回 `FAILED_PRECONDITION`；对未初始化 session 的 `Send` 返回不同 error code。contract v1 未判定是否应允许幂等 `Terminate` 或未知 session 的错误码规范。**修复路径**: ADR-V2-017 §2 增量修订：规定 (a) `Terminate` 的幂等性语义（second call 是 NO-OP 还是 FAILED_PRECONDITION），(b) `Send` 未知 session 的 canonical error code（`NOT_FOUND` vs `FAILED_PRECONDITION`）。W1 跟进修订。衍生自 Phase 2.5 S0.T4 |
| **D140** | Phase 2.5 S0.T3 — grid-runtime envelope-mode dispatch sites 未调 `HookContext::with_event` | ✅ CLOSED 2026-04-20 Phase 3.6 T1 | **Resolution**: `crates/grid-engine/src/agent/harness.rs` 三处 dispatch 位点（PreToolUse @ L2220, PostToolUse @ L2362, Stop @ L1755）显式链 `.with_event("PreToolUse"/"PostToolUse"/"Stop").with_skill_id(active_skill.name 或 "")`，将 envelope 从 legacy 全量 struct 投影切到 ADR-V2-006 §2/§3 规范形状（env: `GRID_EVENT`/`GRID_SKILL_ID`, json: `event`/`skill_id` + 范围字段）。Stop envelope 的 `draft_memory_id` / `evidence_anchor_id` 在 skill 未 populate 时由 serializer 兜底为空串满足 §2.3 not-null 约束。**验证**: 4 parity tests (`crates/grid-engine/tests/hook_envelope_parity_test.rs`) 10/10 PASS；full grid-engine regression 2385/2385 PASS；`make v2-phase3-contract-grid test_hook_envelope.py` Stop scope 2/2 从 D140-xfail 翻转为 PASS，Pre/Post 残余 3 xfail 归属 D136（mock OpenAI adapter tool_calls shape mismatch，独立 root cause）。|
| **D141** | Phase 2.5 W1.T2 — F1 gate: goose extensions config middleware insertion runtime verification | ✅ CLOSED 2026-04-16 @ `e78d858` | **Resolution**: W1.T2.5 Dockerfile bakes `goose v1.30.0` into `crates/eaasp-goose-runtime/Dockerfile`; F1 verified via `make goose-runtime-container-verify-f1` inside image with clean exit 0 (goose config paths + version 1.30.0 printed). ldd confirms all 9 shared libs resolve (libgomp1 added to apt install keep-after-purge list per debian:bookworm-slim shortfall). Image SHA `fce46f95e216`, size 361MB (<500MB target). ACP CLI flags (`goose acp --stdio`) will be smoked at first W1.T3 middleware wiring pass (adapter_test.rs skip guards remain until T3). Two plan-template bugs found and documented inline in Dockerfile comment block: (1) `GOOSE_VERSION` is env-var for install-script, not URL path component; (2) `libgomp1` required at runtime not just install-time |
| **D142** | Phase 2.5 post-ADR-V2-019 — grid-runtime 不读 `EAASP_DEPLOYMENT_MODE` env | ✅ CLOSED 2026-05-21 Phase 5.4 @ `d12f6ec` (5.4-02-07) | **Resolution**: `crates/grid-runtime/src/config.rs::RuntimeConfig::deployment_mode` 新增字段从 `EAASP_DEPLOYMENT_MODE` env 读取（default "shared"），`crates/grid-runtime/src/service.rs::RuntimeServiceImpl::create_session` 在 `per_session` 模式下检查活动 session ≥1 时返回 `Status::resource_exhausted`。ADR-V2-019 §D2 统一 env 接口实现。`tests/test_deployment_mode_gate.rs` 2/2 PASS。**原 Filed**: 2026-04-16 during ADR-V2-019 起草. **Scope**: grid-runtime 已有 `DeploymentMode::{Shared, PerSession}` enum（`crates/grid-runtime/src/service.rs:181`），但未从 `EAASP_DEPLOYMENT_MODE` env 读取映射。ADR-V2-019 D2 要求所有 L1 runtime 遵从统一 env var 接口。**Impact**: EAASP L4 当前无法通过统一 env 控制 grid 部署模式，每个 runtime 特判成本高。 |
| **D143** | Phase 2.5 post-ADR-V2-019 — claude-code-runtime 不读 `EAASP_DEPLOYMENT_MODE` env 且无 max_sessions gate | ✅ CLOSED 2026-05-21 Phase 5.4 @ `2453447` (5.4-02-08) | **Resolution**: `lang/claude-code-runtime-python/src/claude_code_runtime/service.py::__init__::_deployment_mode` 从 `EAASP_DEPLOYMENT_MODE` env 读（default "shared"），`Initialize` RPC 在 `per_session` 模式 + 已有 active session 时返回 `grpc.StatusCode.RESOURCE_EXHAUSTED`。`tests/test_deployment_mode.py` 2/2 pytest PASS。**原 Filed**: 2026-04-16 during ADR-V2-019 起草. **Scope**: `lang/claude-code-runtime-python/src/claude_code_runtime/service.py` 有 `SessionManager` 多 session 支持 + `_active_session_id` v2 Empty RPC 回退，但 (a) 未读 `EAASP_DEPLOYMENT_MODE` env；(b) 没有 `per_session` 模式下的 max_sessions=1 准入检查。**Impact**: 同 D142，EAASP L4 统一接口缺失。 |

**引入流程**:
1. 在新 Deferred 产生的 plan 文件里以表格形式定义 `| D90 | 标题 | 去向 |`
2. **同步追加到本 ledger** 的相应 section（不要只写在 plan 里）
3. 在 commit message 引用 `Dxx`
4. 在 [状态变更日志](#状态变更日志) 新增一行

**关闭/状态变更流程** (新增 2026-04-27, Phase 4.0 CLEANUP-02):
1. 在原 D-item row 直接修改 status 字段（例如 `🟡 P1-defer → ✅ closed`）
2. 在 row 末尾追加 close-out trace（commit hash + Phase/Task 编号 + 一句话 closure summary）
3. 在 [状态变更日志](#状态变更日志) 同步追加一行（保留历史时间线，append-only）
4. 仅适用于**未来**新关闭的 D-item；**已关闭的历史 D-item 不强制 retroactive 改写**

---

## 状态变更日志

| 日期 | ID | 变更 | 证据 |
|------|-----|------|------|
| 2026-04-14 | D3, D5, D6, D37 | active → 🤔 revisit-after-S2 | 需 S2 context engineering 决策后判断 |
| 2026-04-14 | D8, D9, D34, D38, D41, D46, D62, D63, D64 | active → 🔴 phase3-gated | 依赖 Phase 3 身份/租户模型 |
| 2026-04-14 | D21, D25, D32, D36, D56, D73, D75, D76, D77, D79, D80 | active → 📦 long-term | Phase 4/5/6 路线 |
| 2026-04-14 | D10/11/13/14/15/16/17/18/19/20/22/23/24/26/28/29/30/31/33/39/42/43/44/45/48/55/57/58/59/61/65 | active → 🧹 tech-debt | 纯技术债，Phase 2 后批量清 |
| 2026-04-14 | D12, D60 | active → 🟢 P2-active | S2 顺带完成 |
| 2026-04-14 | D50, D51, D53, D78 | active → 🟡 P1-active | 功能缺口必补，挂到 S2/S3 |
| 2026-04-14 | D35 | active → 🔥 合并到 D84 | SSE event streaming 与 CLI --follow 合并 |
| 2026-04-14 | D74 | active → 🔵 P3-active | Phase 2 可选加速 |
| 2026-04-14 | — | **重分类** | 40 active → 12 真需修 + 26 降级归档 |
| 2026-04-14 | D87 | active → ✅ closed | ADR-V2-016, multi-model E2E PASS |
| 2026-04-14 | D88 | active → ⏸️ frozen/superseded | ADR-V2-017 (hermes 冻结) |
| 2026-04-14 | D83 | active → ✅ closed | S1.T4 @ `bdc5b8b` (衍生 D90) |
| 2026-04-14 | D85 | active → ✅ closed | S1.T5 @ `bdc5b8b`+`d0e6cb0` |
| 2026-04-14 | D86 | active → ✅ closed | S1.T3 @ `d0e6cb0` |
| 2026-04-14 | D90 | **新增** 🟡 P1-defer | ServerMessage WS schema tool_name 衍生自 D83，前置 frontend UI 决策 |
| 2026-04-14 | D91 | **新增** 🟡 P1-defer | HNSW tombstone rebuild，S2.T1 review 提出，→ Phase 2.5 |
| 2026-04-14 | D92 | **新增** 🔵 P3-defer | MockEmbedding 碰撞审查，S2.T1 review 提出，→ Phase 3 GA 前 |
| 2026-04-14 | D93 | **新增** 🟡 P1-defer | embed_batch 顺序实现，S2.T1 review 提出，→ S2.T4 或 Phase 2.5 |
| 2026-04-14 | D94 | **新增** 🟡 P1-defer | MemoryStore 单例 refactor（D12 收尾），S2.T1 review 提出，→ Phase 2.5 |
| 2026-04-15 | D95 | **新增** 🔵 P2-defer | FTS 命中的 semantic_score 从 DB `embedding_vec` 回填，S2.T2 衍生 → S2.T4 或 Phase 2.5 |
| 2026-04-15 | D96 | **新增** 🔵 P3-defer | 用户自定 memory_id 含 `:v` 子串 HNSW key 解析丢失（reviewer M1），→ Phase 3 前 |
| 2026-04-15 | D97 | **新增** 🔵 P3-defer | `weights=(0,0)` 退化情形缺构造期告警（reviewer M2），→ Phase 2.5 |
| 2026-04-15 | D98 | **新增** 🟡 P1-defer | HybridIndex 每次 search 重建 HNSW（reviewer N3，承继 T1）→ Phase 2.5 |
| 2026-04-15 | D99 | **新增** 🔵 P3-defer | MCP dispatcher 参数类型转换抛原生异常（S2.T3 reviewer Major）→ Phase 2.5 |
| 2026-04-15 | D100 | **新增** 🔵 P3-defer | write/confirm/archive embedding 字段不 surface（S2.T4 test 10）→ Phase 2.5 |
| 2026-04-15 | D101 | **新增** 🔵 P3-defer | FastAPI detail 嵌套 erratum（S2.T4 blueprint nit）→ blueprint 审校 |
| 2026-04-15 | D102 | **新增** 🟡 P1-defer | AgentLoopConfig.compaction YAML binding（S3.T1 coder）→ Phase 2.5 |
| 2026-04-15 | D89 | active → ✅ closed | S4.T1 @ `28e6b21` (CLI session close subcommand) |
| 2026-04-15 | D84 | active → ✅ closed | S4.T2 @ `bd55bc4` (CLI events --follow + L4 SSE endpoint) |
| 2026-04-15 | D124 | **新增** 🔵 P3-defer | L4 events/stream client-disconnect 无结构化日志（S4.T2 reviewer 注记）→ Phase 2+ 观测增强 |
| 2026-04-15 | D51 | 🟡 P1-active → ✅ closed | S3.T5 @ `7cb48eb` (ADR-V2-006 Accepted) — 账本同步修正 |
| 2026-04-15 | D53 | 🟡 P1-active → ✅ closed | S3.T5 @ `7cb48eb` (harness substitute_hook_vars wiring) — 账本同步修正 |
| 2026-04-15 | D60 | 🟢 P2-active → ✅ closed | S2.T5 @ `bad4269` (verify-v2-mvp.py assertion 11 raise AssertionError) — 账本同步修正 |
| 2026-04-15 | D124 | 🔵 P3-defer → ✅ closed | api.py `_sse_generator` 4 结构化日志点（sse_follow_{start,session_gone,idle_exit,disconnect}），127/127 L4 tests PASS |
| 2026-04-15 | D125 | **新增** 🟡 P1-defer | events/stream poll 上限 500 events/s，burst 超限静默滞后（S4.T2 reviewer 注记）→ Phase 2.5 if L1 >1k/sec |
| 2026-04-15 | D103 | **新增** 🔵 P3-defer | find_tail_boundary O(N²) risk（S3.T1 coder）→ Phase 3 perf |
| 2026-04-15 | D104 | **新增** 🔵 P3-defer | 反应式 guard 在 harness 而非 pipeline（S3.T1 coder）→ Phase 3 if needed |
| 2026-04-15 | D105 | **新增** 🟡 P1-defer | ContextDegraded 字符串别名保留（S3.T1 coder）→ Phase 3 breaking |
| 2026-04-15 | D106 | **新增** 🔵 P3-defer | MAX_TURNS_FOR_BUDGET=50 硬编码（S3.T1 coder）→ Phase 3 config |
| 2026-04-15 | — | **S3.T1 reviewer C1+M1-M3 inline-fixed** | context_window threaded, reactive_summary_ratio configurable, test 6+7 rewritten. 改动随 S3.T1 commit 一并落盘 |
| 2026-04-15 | — | **S3.T2 reviewer C1+M1-M3 inline-fixed** | check_final_output.sh evidence_anchor_id 三-way, SKILL.md event shape + anchor optional fields + memory_write_file memory_id. 改动随 S3.T2 commit 27de415 一并落盘 |
| 2026-04-15 | D107 | **新增** 🔵 P3-defer | Stop hook 三-way empty-string 检查共享 jq helper（S3.T2 reviewer，承继 S4.T1 threshold-calibration）→ S3.T5 带 shared lib 一起实现 |
| 2026-04-15 | D108 | **新增** 🟡 P1-defer | Hook script 自动化回归测试（bats/shellcheck）避免 C1-class 退化（S3.T2 reviewer 候选 2）→ S3.T3 E2E 或 Phase 2.5 |
| 2026-04-15 | D109 | **新增** 🟡 P1-defer | `workflow.required_tools` 不变量（只列 agent 真正 invoke 的 tool）未文档化，避免 D87 tool_choice=Specific(next) 卡死（S3.T2 设计决策）→ Phase 2.5 ADR-V2-016 修订 + parse-time warn |
| 2026-04-15 | D110 | **新增** 🔵 P3-defer | `dependencies` 字段 soft-intent vs runtime-required 语义不分（S3.T2 设计决策）→ Phase 3 schema refactor breaking |
| 2026-04-15 | — | **S3.T5 reviewer N1 inline-fixed** | skill_dir=None 日志渲染为 literal "None" → `skill_dir or "<unresolved>"`. 改动随 S3.T5 commit 一并落盘 |
| 2026-04-15 | D117 | **新增** 🟡 P1-defer | Prompt-body 执行器（LLM-driven yes/no），原 D50 重编号；S3.T5 blueprint §F 明确不收，等真实 skill 使用再落地 → Phase 2.5+ |
| 2026-04-15 | D118 | **新增** 🔵 P3-defer | SkillDir materialization 在 session 结束无 cleanup（S3.T5 blueprint §G）→ S4 cleanup sweep |
| 2026-04-15 | D119 | **新增** 🔵 P3-defer | Envelope `schema_version` 字段未强制（ADR-V2-006 §9）→ Phase 3 首次 breaking change 时引入 |
| 2026-04-15 → 2026-04-16 | D120 | ✅ closed | **Cross-runtime envelope parity**：Rust `HookContext::to_json/to_env_vars` 缺 ADR-V2-006 §2/§3 字段（`event` / `skill_id` / `draft_memory_id` / `evidence_anchor_id` / `created_at` / `GRID_EVENT` / `GRID_SKILL_ID`），Python 已符合。S3.T5 reviewer M1。**Closed @ Phase 2.5 S0.T3 commit `7e083c7`** — HookContext 扩展 + 10 parity tests + byte-parity ADR §2.1/2.2/2.3 canonical JSON 锁定 |
| 2026-04-15 | D121 | **新增** 🔵 P3-defer | `register_session_stop_hooks` 额外调用累加而非替换（S3.T5 reviewer M2）→ 加 dedupe 或 warn-on-duplicate semantics |
| 2026-04-15 | D122 | **新增** 🔵 P3-defer | Python envelope 包含 top-level `hook_id` 字段，Rust 未含（S3.T5 reviewer M3）→ D120 统一修 |
| 2026-04-15 | D123 | **新增** 🔵 P3-defer | `scoped_hook_wiring_integration.rs` 测试用 `std::env::set_var` + Mutex，poison 恢复静默（reviewer N5）→ 改为 RAII env guard |
| 2026-04-15 | — | **S4.T3 reviewer C1+M1+M4+N1 inline-fixed** | A10 SKIP_RUNTIMES 守护避免默认路径 502, eaasp-skill-registry binary pre-flight 从 --with-runtimes 分支提出, A13 comment cli-v2-setup, chmod 755 on verify-v2-phase2.py. 改动随 S4.T3 commit a5101d5 一并落盘 |
| 2026-04-15 | D126 | **新增** 🔵 P3-defer | S4.T3 fresh-clone 时 `lang/claude-code-runtime-python/.venv` 缺失导致 A8 late-fail，pre-flight 应加 WARNING（non-fatal）→ Phase 2.5 ergonomics |
| 2026-04-15 | D127 | **新增** 🔵 P3-defer | S4.T3 `data/verify-v2-phase2-skill-registry/` 目录不被清理（MVP 也有同样 gap，继承非新 regression）→ Phase 2.5 when a Phase 2+ assertion reads registry state |
| 2026-04-15 | D128 | **新增** 🔵 P3-defer | S4.T3 `@assertion` 装饰器 NOTE 在 PASS 之前打印，阅读顺序略混乱（UX polish）→ Phase 2.5 polish |
| 2026-04-15 | — | **S4.T3 live run 14/14 PASS** | `make v2-phase2-e2e` default (--skip-runtimes) 从 port-free 状态跑完：4 服务启动各 1s + 14 assertions 全 PASS（A10 正确 skip），ports 清理干净；证明 C1+M1+M4+N1 fixes 成立，gate 在 production 路径工作 |
| 2026-04-15 | D129 | **新增** 🔵 P3-defer | S4.T3 `verify-v2-phase2.sh` cleanup trap 在 pre-flight 失败时仍 sweep 外部端口（实证：运行时误杀用户 dev-eaasp session）→ Phase 2.5 harness ergonomics |
| 2026-04-16 | — | **S4.T4 reviewer M1+M2+N2 inline-fixed** | DashMap-Ref-across-await 修正（改为 clone-handle-out-of-guard 匹配 runtime_lifecycle.rs 惯用法）+ `tracing::debug!` 日志送失败 + `THREAD_SCOPED` 改为 module-level `const _: () = assert!(...)` 编译时断言。3 候选 D131/D132/D133 全部 inline-fixed 无新 Deferred 需登 |
| 2026-04-16 | D130 | **新增** 🟡 P1-defer | S4.T4 session-lifetime vs per-turn cancel token 双 token 不一致，`cancel_session()` 需双路径触发（registry flag + `AgentMessage::Cancel` channel）才能真正打断 in-flight turn → **Phase 2.5 consolidation**（前置：`ChildCancellationToken::cancel` propagation + `AgentLoopConfig.cancel_token` plumbing） |
| 2026-04-16 | — | **Phase 2 23/23 COMPLETE** | S4.T4 closes Phase 2. Stage breakdown: S0 2/2 + S1 7/7 + S2 5/5 + S3 5/5 + S4 4/4. Next: Phase 2.5 (goose-runtime + Rust HookContext envelope parity + D94/D98/D108/D120/D130 consolidation batch) |
| 2026-04-16 | D120 | 🟡 P1-defer → ✅ closed | Phase 2.5 S0.T3 @ `7e083c7` — Rust `HookContext` 扩展 ADR-V2-006 §2/§3 字段（`event`/`skill_id`/`draft_memory_id`/`evidence_anchor_id`/`created_at` + `GRID_EVENT`/`GRID_SKILL_ID` env vars）+ empty-string serde helper + 10 parity tests。Python 侧先前已合规（S3.T5）。byte-parity 已对 ADR §2.1/2.2/2.3 canonical JSON 锁定 |
| 2026-04-16 | D134 | **新增** 🟡 P1-defer | 已落盘 skill hooks（`threshold-calibration/check_output_anchor.sh` + `skill-extraction/check_final_output.sh`）通过 `.output.evidence_anchor_id` / `.output.draft_memory_id` 嵌套路径读 envelope，与 ADR-V2-006 §2.3 定义的 top-level 字段不匹配。T3 envelope 代码本身正确，但 grid-runtime 生产路径尚未调用 `with_event()`，旧调用站走 legacy full-struct 投影所以当前运行正常。**阻断项**：Phase 2.5 W1 goose-runtime 或任何激活 `with_event("Stop")` 的 batch 必须先迁移这些 shipped hook 或文档化 top-level 字段 — 否则 production 路径静默失配。建议 W1.T1 前置 |
| 2026-04-16 | D135 | **新增** 🔵 P3-defer | Phase 2.5 S0.T2 contract_v1 `test_hook_envelope.py` 5 cases 用 `pytest.xfail` 标注 fixture 占位；T4 引入真实 fixtures 时需显式**转为正断言**（而非仅删 xfail 标记）。否则 xfail→XPASS 可能掩盖 D120 回归。S0.T2 reviewer Major-2 — T4 blueprint 前置 |
| 2026-04-16 | D136 | **新增** 🟡 P1-defer | Phase 2.5 S0.T4 — Pre/PostToolUse hook 在 probe turn 未触发（grid-runtime）：mock LLM 返回 `tool_calls=[...]` 但 Rust OpenAI adapter 识别不到（与 D87 capability matrix 相关或 mock shape 失配）。阻断 `test_hook_envelope.py --runtime=grid` 5/5；Python runtime 已合规 → Phase 2.5 W1 前置 |
| 2026-04-16 | D137 | **新增** 🟡 P1-defer | Phase 2.5 S0.T4/T5 — Multi-turn observability + MCP bridge live + PRE_COMPACT 阈值触发，10 xfail 跨 event/proto/MCP 文件；contract harness 需扩展 multi-turn replay + MCP subprocess fixture → Phase 2.5 W1/W2 成熟期 |
| 2026-04-16 | D138 | **新增** 🟡 P2-defer | Phase 2.5 S0.T4/T5 — skill-workflow enforcement 5 xfail 需可脚本化 deny-path mock LLM（`tool_choice` + scenario-routed deny fixture）→ Phase 2.5 W1 |
| 2026-04-16 | D139 | **新增** 🔵 P3-defer | Phase 2.5 S0.T4 — 双 Terminate + 未知 session 的 canonical error code 未在 contract v1 判定，2 xfail `test_e2e_smoke.py` → Phase 2.5 W1 跟 ADR-V2-017 §2 修订 |
| 2026-04-16 | D140 | **新增** 🟡 P1-defer | Phase 2.5 S0.T3/T4 — grid-runtime envelope-mode dispatch sites 未调 `HookContext::with_event`，3-5 LOC 热修；Python 已合规自 Phase 2 S3.T5；修复后 `test_hook_envelope.py --runtime=grid` 0/5 → 5/5 PASS → Phase 2.5 W1 前置 |
| 2026-04-16 | — | **Phase 2.5 S0 6/6 COMPLETE** | S0.T4 `cfda161` (grid GREEN 13/22) + S0.T5 `fd1abbf` (claude-code GREEN 18/17) + S0.T6 freeze `contract-v1.0.0` tag. Contract v1 authoritative baseline 就绪；W1 goose + W2 nanobot 可平行启动 |
| 2026-04-16 | D141 | **新增** 🟡 P1-defer | Phase 2.5 W1.T2 — F1 gate 未在本地 dev 验证（goose 未安装）：`goose acp --stdio` CLI flags + `~/.config/goose/config.yaml` extensions middleware insertion 尚未 runtime-validated。adapter 代码按 Block 公开 ACP 文档写就但未跑通。阻断 W1.T3/T4/T5，需 CI runner 装 goose binary → Phase 2.5 CI setup 或 T3 开发前置 |
| 2026-04-16 | ADR-V2-019 | **新增 ADR** | L1 Runtime Deployment Model Proposed — multi-session 内在 + `EAASP_DEPLOYMENT_MODE={shared,per_session}` env + 容错分级。goose-runtime (W1.T2.5) 为 reference 实现；grid/claude-code 合规通过 D142/D143 回填 |
| 2026-04-16 | D142, D143 | **新增** 🟡 P2-defer | ADR-V2-019 D2 合规审计 — grid-runtime + claude-code-runtime 均未读 `EAASP_DEPLOYMENT_MODE` env；各 ~20 LOC 小改动，Phase 2.5 S3 CI gate 批处理 |
| 2026-04-16 | D141 | 🟡 P1-defer → ✅ CLOSED | W1.T2.5 `e78d858` Dockerfile 烘入 goose v1.30.0；F1 gate 通过 `make goose-runtime-container-verify-f1` exit 0 验证；ldd 确认 libgomp1 补上后 9 libs 全解析；image 361MB < 500MB 目标。ACP 语义留 T3 首跑 smoke |
| 2026-04-18 | D144-B | **✅ CLOSED** | Phase 3 S3.T5 — nanobot-runtime contract v1.1 certified: 42 PASS / 22 XFAIL (all XFAILs are D136-D139 deferred-by-design). skill-extraction E2E 8/8 PASS. mcp_client + session Stop hooks + ConnectMCP wired in S3.T3-T4. |
| 2026-04-20 | D140 | 🟡 P1-defer → ✅ CLOSED | Phase 3.6 T1 — `crates/grid-engine/src/agent/harness.rs` 三处 dispatch 位点（PreToolUse @ L2220, PostToolUse @ L2362, Stop @ L1755）chain `.with_event(...).with_skill_id(...)`，切入 ADR-V2-006 §2/§3 envelope。Parity tests 10/10 PASS, grid-engine regression 2385/2385 PASS, `test_hook_envelope.py --runtime=grid` Stop scope 2/2 翻转为 PASS（Pre/Post 残留 3 xfail 归 D136 独立 root cause）|
| 2026-04-20 | D145 | 🧹 tech-debt → ✅ CLOSED | Phase 3.6 T2 — `session_orchestrator.py` 抽 `_accumulate_delta` + `_record_coalesced_deltas` helpers，消除 `send_message` / `stream_message` `delta_buf` 闭包重复；yield / `chunks.append` 非对称性保留在调用处。`test_chunk_coalescing.py` 7/7 PASS + `test_session_orchestrator.py` 13/13 PASS。 |
| 2026-04-20 | D147 | 🧹 tech-debt → ✅ CLOSED (workaround) | Phase 3.6 T3 — 10 处 `# type: ignore[arg-type]  # ADR-V2-021 ChunkType int-on-wire` 绕过 grpcio-tools stub 限制（`nanobot-runtime-python/src/nanobot_runtime/service.py` 5 处 + `pydantic-ai-runtime-python/src/pydantic_ai_runtime/service.py` 5 处）. pytest 全 PASS (nanobot 36/36 + pydantic-ai 4/4). 真正根因追踪至 D152. |
| 2026-04-20 | D152 | **新增** 🧹 tech-debt | D147 descope 副产物 — 跟踪 grpcio-tools 上游 int-accepting stubs. |
| 2026-04-20 | D152 | 扩围 10→12 | Phase 3.6 T3 follow-up — Pyright surfaced 2 个 credential_mode=0 site (nanobot/service.py:273, pydantic-ai/service.py:131)，同类 ADR-V2-021 proto enum int-on-wire 问题，annotated. |
| 2026-04-20 | D152 | 备注扩展 | T3 reviewer 发现: (1) `[arg-type]` 是 mypy 语法；Pyright 当 blanket 接受（`# pyright: ignore[reportArgumentType]` 才是 tool-native），上游切换时需重写 12 处。(2) claude-code-runtime/service.py:790 `credential_mode=runtime_pb2.Capabilities.DIRECT` 疑似同类（attribute-access form），未 annotate — 等 T5 Pyright 配置就位后统一 sweep。hermes-runtime 已冻结（ADR-V2-017），不处理。 |
| 2026-04-20 | D150 | 🧹 tech-debt → ✅ CLOSED | Phase 3.6 T4 — 4 份 build_proto.py（3 lang/*-python + 1 tools/eaasp-l4-orchestration）抽到 scripts/gen_runtime_proto.py 单一 SSOT（`--package-name` 注册表 + `--proto-files` override）；Makefile 4 target 对称（新增 `nanobot-runtime-proto` / `pydantic-ai-runtime-proto`）+ `l4-proto-gen` / `claude-runtime-proto` rewired；`lang/claude-code-runtime-python/Dockerfile` 同步。regen 后 stub 字节对齐（diff -r 0 diff，4/4 包）；pytest 85/85 PASS（claude-code 25 + nanobot 36 + pydantic-ai 4 + L4 subset 20）. |
| 2026-04-20 | D146 | 🧹 tech-debt → ✅ CLOSED | Phase 3.6 T5 — `pyrightconfig.json` 落地 @ 10 package executionEnvironments（`.venv/lib/python{ver}/site-packages` extraPaths + per-env pythonVersion: 7×3.14 + mock-scada/scripts 3.12）+ exclude hermes（ADR-V2-017 frozen）+ `tools/archive/**` + `reportMissingTypeStubs: false` / `reportMissingModuleSource: none` + strict off. Pyright v1.1.408 本地 regression 236→8 warnings（import 归位）；D152 `# type: ignore` 继续生效（nanobot service.py 0 errors/0 warnings）. pytest 56/56 PASS（nanobot 36 + L4 chunk+orchestrator 20）. |
| 2026-04-20 | D153 | **新增** 🧹 tech-debt | T4 code reviewer 发现 Dockerfile symlink 是 paper cut — 加 `--out-dir` override flag 可去除。Phase 4 runtime Dockerfile 增殖前完成。 |
| 2026-04-20 | gen_runtime_proto.py | T4 followup | Black reformat（I1）+ 注册表 `pkg_prefix == f'{src_pkg}._proto'` import-time invariant assertion（I2）；byte-parity 验证仍 0 diff。 |
| 2026-04-20 | D154, D155 | **新增** 🧹 tech-debt | T5 code reviewer 发现: D154 per-env pythonVersion 跟随 installed venv 而非 pyproject 声明的 `>=3.12` floor；D155 fresh clone 缺 `.venv` 时 pyright fallback 到根 `.venv`（无 grpc）→ 500+ 假 unresolved。 |
| 2026-04-20 | D151 | 🧹 tech-debt → ✅ CLOSED | Phase 4a T1 — `crates/grid-engine/tests/harness_envelope_wiring_test.rs` 3 tests (PreToolUse / PostToolUse / Stop) with spy HookHandler + StopHook capturing ctx.event. 手工 delete .with_event(...) at any of harness.rs:1766/2236/2390 now fails the corresponding test. grid-engine regression 2385+3=2388 PASS. |
| 2026-04-20 | D154 | 🧹 tech-debt → ✅ CLOSED | Phase 4a T2 — pyrightconfig.json 所有 8 per-env pythonVersion 统一为 "3.12"（pyproject `requires-python>=3.12` floor）。Pyright 前后 103 errors + 8 warnings 一致 —— 确认没有 3.13+-only 语法逃过检查。 |
| 2026-04-20 | D155 | 🧹 tech-debt → ✅ CLOSED | Phase 4a T3 — `scripts/check-pyright-prereqs.sh` + Makefile `check-pyright-prereqs` target；扫 9 个 per-package `.venv`，缺则非零退出码 + stderr 明列缺失 path + 指向 `uv sync` / `make setup` 修复。`MISSING_OK=1` 可降级 warn-only。手工 mv nanobot venv 验证两条路径（present→exit 0，missing→exit 1）。 |
| 2026-04-20 | D153 | 🧹 tech-debt → ✅ CLOSED | Phase 4a T4 — `scripts/gen_runtime_proto.py` 加 `--out-dir DIR` argparse flag（`build(...)` 多一个 `out_dir_override` 参数）。`lang/claude-code-runtime-python/Dockerfile` 去掉 `mkdir -p .../lang/...` + `ln -s` hack，直接 `--out-dir /build/src/claude_code_runtime/_proto`。默认路径 regen nanobot 字节对齐；override 路径也产生 byte-identical stub（仅 `__pycache__` 差异）。Phase 4 新 runtime Dockerfile 不再需要重复 hack。 |
| 2026-04-20 | D149 | 🟡 P1-active → ✅ CLOSED | Phase 4a T5 — Option B grep guard：proto `enum ChunkType` 块上加 `// @ccb-types-ts-sync` 标记 + `scripts/check-ccb-types-ts-sync.sh`（~90 LOC bash，awk 解析 proto 块 + grep `^ *<NAME> *=` 匹配 TS 块）+ `.github/workflows/phase4a-ccb-types-sync.yml`（独立 bash-only gate，triggers 锁到 proto/common.proto + types.ts + 脚本 + workflow）+ Makefile target `check-ccb-types-ts-sync`. 本地 PASS `OK: 8 ChunkType variants in sync`；drift test（删 `WORKFLOW_CONTINUATION = 7`）exit=1 + 明列缺失 `CHUNK_TYPE_WORKFLOW_CONTINUATION` + 修复指引。零 toolchain add，契合 ccb `@grpc/proto-loader` 动态消息架构。 |
| 2026-04-20 | D148 | 🟡 P1-active → ✅ CLOSED | Phase 4a T6 — `lang/pydantic-ai-runtime-python/tests/test_provider.py`（10 tests, 178 LOC）+ `tests/test_session.py`（8 tests, 218 LOC）。provider 覆盖：构造 happy path / `/v1` 双重后缀防护 / 带路径前缀 gateway / `make_provider()` env 读取 + defaults / `chat()` OAI-shape 契约（`patch.object(Agent, 'run', ...)` monkeypatch）/ last-user-message 提取 / 异常传播 / `aclose()` 幂等。session 覆盖：纯文本 CHUNK+STOP / 单轮工具调用序列 / 多轮工具调用 / `max_turns` 超限→ERROR / provider 异常→ERROR / Stop hook allow / deny（真实 bash subprocess）/ `EventType` 字符串契约锁定（ADR-V2-021 并行）。22/22 PASS（18 新 + 4 scaffold 保留）in 0.78s. 零新依赖，零 live-LLM。 |
| 2026-04-20 | D152 | 🧹 tech-debt → ✅ CLOSED | Phase 4a T7 — 决策：Option (a) post-process `.pyi` script。上游 `protocolbuffers/protobuf#25319` "Fix message constructor enum typing"（fixes #23670）OPEN 自 2026-01-14, REVIEW_REQUIRED, 未 merge — 等不得。`scripts/gen_runtime_proto.py` 加 `_loosen_enum_stubs(out_dir)` 后处理：正则 `_Union\[<EnumCls>, str\]` → `_Union[<EnumCls>, str, int]`（只命中 enum 字段构造签名；不命中 `_Union[X, _Mapping]` nested message；带负向 lookahead 保证幂等）。`make claude-runtime-proto nanobot-runtime-proto pydantic-ai-runtime-proto l4-proto-gen` 分别 loosen 7/7/7/3 处 stub。12 处 `# type: ignore[arg-type]` 全删（nanobot 6 处 + pydantic-ai 6 处）。验证：nanobot 36/36 PASS + pydantic-ai 22/22 PASS + claude-code-runtime 104/105 PASS（唯一 fail 是 `test_default_config` 预存 drift，commit 6784994 `permission_mode acceptEdits→bypassPermissions`，与本次无关）+ `make v2-phase3-e2e` 112/112 PASS + chunk_type contract 2/2 PASS. |
| 2026-05-02 | NEW-D2 | 🟠 P1 → ✅ CLOSED | Phase 5.1 T2 @ `3ba59a1` — `tests/contract/cases/test_chunk_type_contract.py` 加 `@pytest.mark.parametrize("runtime_name", ADR_V2_025_ACTIVE_RUNTIMES)` (7 active runtimes)。pytest `--collect-only` 现展示 9 items（7 parametrized 主 test + 2 unparametrized guard test, 21 cases by ROADMAP SC interpretation = 3 functions × 7 runtimes upper bound）。配套 ADR-V2-025 (Phase 5.1 T1 @ `7293868`, Accepted) 给 7 runtime 划分 主力档/样板档/参考档/冻结档；CI workflow `.github/workflows/phase3-contract.yml` (Phase 5.1 T3 @ `e6c993b`) include 表新增 tier/xfail/continue-on-error 字段，把 ADR-V2-025 §CI 规则 落地为 PR gate（primary 阻塞 / sample-reference continue / hermes 跳过）。|
| 2026-04-14 | — | **ledger 创建** | 收敛 D1–D89 到 single source of truth |
| 2026-04-12 | D1, D2 | active → ✅ closed | ADR-V2-004 S4.T2 4b-lite |
| 2026-04-12 | D47, D49, D52 | active → ✅ closed | S4.T2 前置修复 |
| 2026-04-12 | D27, D40 | active → 🔄 superseded by D54 | ADR-V2-004 精化 |
| 2026-04-12 | D54 | active → ✅ closed | Phase 0.5 S1 实装 |
| 2026-04-11 | D7 | active → ✅ closed | Phase 1 Event Engine |

### 2026-05-26 Phase 6.2 Plan 01 (TRIAGE-01/02/03 milestone v3.2 close)

- **TRIAGE-01 ✅ CLOSED 2026-05-26 Phase 6.2 Plan 01 Task 1 @ `9842dda`** — 93 open main-namespace D-row triage classify: tag schema `[P1-actionable-now|P2-next-milestone|P3-async-when-touched|DEAD-archived]` prepended to the emoji-anchored cell (column 3 in 4-col rows, column 4 in 5-col rows) + one-line rationale citing code/ADR (with 5-15 word body excerpt for DEAD-(c)/(d))/commit/phase. Per Phase 6.2 CONTEXT.md D-01 schema + D-02 4-criterion DEAD test. Distribution: P1=0 / P2=15 / P3=70 / DEAD=8 (DEAD-(c)=5 + DEAD-(d)=3 + DEAD-(a)/(b)=0). **Scope methodology correction**: ROADMAP estimated 102; an earlier scout claimed 128 (also wrong — grep-methodology error missing non-literal closures); actual = 93 main-namespace open rows (81 4-col + 12 5-col). REQUIREMENTS.md left unchanged per CONTEXT.md §specifics.
- **TRIAGE-02 ✅ CLOSED 2026-05-26 Phase 6.2 Plan 01 Task 2 @ `e2a6349` (commit 1: archive create + strip + log entry) + sed-replace commit 2 (this commit, hash recorded in commit subject)** — DEAD-tagged row physical migration: 8 rows moved verbatim to `docs/design/EAASP/DEFERRED_LEDGER_ARCHIVE.md` (closed-text file, 不可再追加 per CONTEXT.md §specifics); main LEDGER stripped of all DEAD-archived rows (117 → 109 in `## D 编号详细登记`); archive header cites commit 1 hash `e2a6349` and this log entry cites the same hash (bidirectional via 2-commit pattern: placeholder + sed-replace, NOT git --amend).
- **TRIAGE-03 ✅ CLOSED 2026-05-26 Phase 6.2 Plan 01 Task 3 @ `24ee8ed`** — `.planning/v3.3-INBOX.md` created: stats header (P1:0 | P2:15 | P3:70 | DEAD-archived:8) + 12-module taxonomy per CONTEXT.md D-03 (grid-engine / grid-cli / grid-server / grid-runtime / contract / L2 / L3 / L4 / hooks / providers / eval / cross-cutting); 9 of 12 modules populated (grid-cli, grid-runtime, providers elided — documented in INBOX); rows grouped P1→P2→P3 with format `- <RowID>: <summary> (LEDGER L<N>)`. Snapshot superseded once v3.3 ROADMAP created.
- **Milestone v3.2 CLOSED 2026-05-26** — all 3 phases complete (6.0 ✅ + 6.1 ✅ + 6.2 ✅), all 6 REQ-IDs traced (CI-01 @ `e27e300` + CLI-X2 @ `0595e31`+`a0a6c28` + CLI-X3 @ `adf2c08`+`97f59e5` + TRIAGE-01 @ `9842dda` + TRIAGE-02 @ `e2a6349`+`835de4e`+`0f600b6` + TRIAGE-03 @ `24ee8ed`); PROJECT.md §Active "Phase 6 milestone (v3.2)" flipped to §Validated; STATE.md frontmatter `status: milestone-complete`, `progress.percent: 100`; ROADMAP §Progress table row 6.2 = ✅ COMPLETE.

---

## 统计汇总 (2026-04-14 重分类后 — EAASP v2.0 对齐)

**真正需处理的 D 项 = 11 项**（P0 + P1 + P2 + P3 剩余 + D90 新增）

| 状态 | 数量 | D 编号 | 含义 |
|------|------|--------|------|
| ✅ **closed** | 38 | D1, D2, D4, D7, D47, D49, D51, D52, D53, D54, D60, D78, D83, D84, D85, D86, D87, D89, D94, D98, D108, D117, D120, D124, D125, D130, D140, D145, D146, D147, D148, D149, D150, D151, D153, D154, D155 + S3.T5 legacy D50→D117 renamed | Phase 3 S2 新增：D78 @ 4633c0b, D94 @ 4633c0b, D98 @ e77833d, D108 @ 00e64e7, D117 @ 688bf4d, D125 @ 0ce0294, D130 @ af71c99；Phase 3.6 T1 新增：D140；Phase 3.6 T2 新增：D145；Phase 3.6 T3 新增：D147 (workaround)；Phase 3.6 T4 新增：D150；Phase 3.6 T5 新增：D146；Phase 4a T1 新增：D151；Phase 4a T2 新增：D154；Phase 4a T3 新增：D155；Phase 4a T4 新增：D153；Phase 4a T5 新增：D149；Phase 4a T6 新增：D148 |
| ✅ **closed (NEW- 命名空间)** | 1 | NEW-D2 | Phase 5.1 T2 @ `3ba59a1` — `test_chunk_type_contract.py` 7-runtime parametrize + ADR-V2-025 tier strategy。NEW- 命名空间是 Phase 4a project review 引入的独立编号空间（与 EAASP D# 不混计，本表合计行不含此条）。 |
| 🔄 **superseded** | 3 | D27→D54, D40→D54, D50→D117 (renamed) | 被其他 D 或 ADR 取代 |
| ⏸️ **frozen** | 2 | D66, D88 | hermes 冻结，Phase 2.5 goose 替代 |
| 🔥 **P0-active** | 0 | — | Phase 2 S4 全部归档 |
| 🟡 **P1-defer** | 6 | D90, D93, D102, D105, D109, D134, D136, D137 | 前置 frontend UI / Phase 3 breaking（D136/D137 via Phase 2.5 S0.T4-T6；D140 closed via Phase 3.6 T1） |
| 🟡 **P2-defer** | 1 | D138 | skill-workflow deny-path mock LLM，Phase 2.5 W1 |
| 🔵 **P2-defer** | 1 | D95 | FTS semantic_score 回填，Phase 2.5 |
| 🔵 **P3-defer** | 22 | D92, D96, D97, D99, D100, D101, D103, D104, D106, D107, D110, D118, D119, D121, D122, D123, D126, D127, D128, D129, D135, D139 | 边角场景 / 告警优化（D139 新增 双 Terminate 语义） |
| 🟢 **P2-active** | 0 | — | D12→D94 renamed, D60 closed |
| 🔵 **P3-active** | 1 | D74 | Phase 2 可选加速 |
| 🤔 **revisit-after-S2** | 4 | D3, D5, D6, D37 | 等 S2 context engineering 决策 |
| 🔴 **phase3-gated** | 9 | D8, D9, D34, D38, D41, D46, D62, D63, D64 | Phase 3 身份/租户模型 |
| 📦 **long-term** | 11 | D21, D25, D32, D36, D56, D73, D75, D76, D77, D79, D80 | Phase 4/5/6 |
| 🧹 **tech-debt** | 18 | D10, D11, D13, D14, D15, D16, D17, D18, D19, D20, D22, D23, D24, D26, D28, D29, D30, D31, D33, D39, D42, D43, D44, D45, D48, D55, D57, D58, D59, D61, D65 | Phase 2 后批量清 |
| **占位未用** | — | D67-D72, D81-D82 | 不计入 |
| **合计** | **68** | D1–D89 去重（81 表格行含 D66/D88 各出现 2 次） | |

### 给开发者的一句话指引

| 角色 | 真正要关心的 |
|------|--------------|
| **当前 Phase 2 推进** | 13 项（P0×6 + P1×4 + P2×2 + P3×1）— 全部已挂到具体 Stage 任务 |
| **Phase 2 结束 end-phase** | P0/P1/P2 完成 + 启动 tech-debt batch cleanup |
| **Phase 3 规划时** | 查 🔴 phase3-gated + 🤔 revisit 四项 |
| **Phase 4+ 长期规划** | 查 📦 long-term |

---

### D145–D150: Phase 3.5 产生（ADR-V2-021 chunk_type contract freeze）

| ID | 标题 | 引入 | 状态 | 去向 |
|----|------|------|------|------|
| **D145** | session_orchestrator.py `delta_buf` + `ctype == "text_delta"` 在 `send_message` / `stream_message` 重复 | Phase 3.5 S2.T1 review | ✅ CLOSED | Phase 3.6 T2 抽 `_accumulate_delta` + `_record_coalesced_deltas` helpers；S2.T2 已关闭 CLI 侧 |
| **D146** | Pyright workspace config 未指向 per-package `.venv` — 编辑器 import 全报 unresolved | Phase 3.5 S2.T1 diagnostics | ✅ CLOSED | Phase 3.6 T5 — `pyrightconfig.json` 落地 @ 10 package executionEnvironments（`.venv/lib/python{ver}/site-packages` extraPaths + per-env pythonVersion）+ exclude hermes（ADR-V2-017 frozen）+ `tools/archive/**` + `reportMissingTypeStubs: false` / `reportMissingModuleSource: none` + strict off. Pyright v1.1.408 本地 regression 236→8 warnings（import 归位）；D152 `# type: ignore` 继续生效 |
| **D147** | Python proto3 enum `.pyi` stub 声明 `ChunkType \| str \| None` 拒绝 int，但 runtime 接受 — Pyright strict mode 噪音 | Phase 3.5 S0 → S1 diagnostics | ✅ CLOSED | Phase 3.6 T3 descope — 10 处 `# type: ignore[arg-type]  # ADR-V2-021 ChunkType int-on-wire` 绕过 grpcio-tools stub 限制；真正根因追踪见 D152 |
| **D148** | pydantic-ai-runtime test bench 只有 4 个 scaffold 测试 — 与其它 runtime 的测试密度不匹配 | Phase 3.5 S1.T6 review | ✅ CLOSED | Phase 4a T6 — `tests/test_provider.py`（10 tests, 178 LOC）+ `tests/test_session.py`（8 tests, 218 LOC）补齐：provider 侧覆盖构造 happy path、`/v1` 双重后缀防护、带路径前缀的 gateway base_url、`make_provider()` env 读取 + defaults、`chat()` OAI-shape 契约（通过 `patch.object(Agent, 'run', ...)` monkeypatch）、last-user-message 提取、异常传播、`aclose()` 幂等；session 侧覆盖纯文本 CHUNK+STOP、单轮工具调用序列、多轮工具调用、`max_turns` 超限→ERROR、provider 异常→ERROR、Stop hook allow / deny（真实 bash subprocess）、`EventType` 字符串契约锁定。22/22 PASS（18 新 + 4 scaffold 保留）in 0.78s. 零新依赖，零 live-LLM。|
| **D149** | ccb-runtime-ts `src/proto/types.ts` hand-written enum 无 SoT 同步保障 — proto 新增 variant 时 TS 不会自动失败 | Phase 3.5 S1.T7 review | ✅ CLOSED | Phase 4a T5 — Option B grep guard：`proto/eaasp/runtime/v2/common.proto` 在 `enum ChunkType` 块上加 `// @ccb-types-ts-sync` 标记；`scripts/check-ccb-types-ts-sync.sh`（~90 LOC bash）awk 解析 proto enum 块、grep 比对 `lang/ccb-runtime-ts/src/proto/types.ts`；`.github/workflows/phase4a-ccb-types-sync.yml` 独立 bash-only gate（PR/push/workflow_dispatch，只 trigger on 两个 SoT 文件 + 脚本 + workflow 自身）；Makefile target `check-ccb-types-ts-sync`. 本地 PASS `OK: 8 ChunkType variants in sync`；drift test（删 `WORKFLOW_CONTINUATION = 7`）exit=1 + 明列缺失名 + 修复指引。未引入 protoc-gen-es 依赖 — 零 toolchain add 契合 ccb 动态 `@grpc/proto-loader` 设计。 |
| **D150** | `nanobot/pydantic-ai` 两份 `build_proto.py` 与 `claude-code-runtime-python/build_proto.py` 内容重复（仅包名不同） | Phase 3.5 S0 | ✅ CLOSED | Phase 3.6 T4 — 4 份 `build_proto.py`（含 `tools/eaasp-l4-orchestration/`）抽到 `scripts/gen_runtime_proto.py`（注册表 + `--package-name` + `--proto-files` override）；Makefile 4 target（含新增 `nanobot-runtime-proto` / `pydantic-ai-runtime-proto`）统一；Dockerfile `claude-code-runtime-python` 同步。regen 后 stub byte-parity 0 diff |
| **D151** | harness.rs hook envelope 三处 dispatch 缺少 call-site 回归测试 — `.with_event(...)` 被误删后，D136 xfail 掩码会掩盖回归 | Phase 3.6 T1 code review | ✅ CLOSED | Phase 4a T1 — `crates/grid-engine/tests/harness_envelope_wiring_test.rs`（3 tests, spy `HookHandler` + spy `StopHook` 捕获 `ctx.event`），断言 PreToolUse / PostToolUse / Stop 三处 dispatch 均 surface ADR-V2-006 §2 literal。手工 delete `.with_event(...)` at harness.rs:1766/2236/2390 将分别令对应测试 fail。 |
| **D152** | `grpcio-tools` proto3 enum `.pyi` stubs 拒绝 int 参数而 runtime 接受 — 当前用 `# type: ignore[arg-type]` 绕过，12 处（ChunkType + CredentialMode）| Phase 3.6 T3 descope | ✅ CLOSED | Phase 4a T7 — 决策 Option (a)：`scripts/gen_runtime_proto.py` 加 `_loosen_enum_stubs(out_dir)` 正则后处理，把 `_Union[<EnumCls>, str]` 扩成 `_Union[<EnumCls>, str, int]`（只命中 enum 字段，不命中 nested Message `_Union[X, _Mapping]`；带负向 lookahead 保证幂等）。4 package regen 分别 loosen 7/7/7/3 处 stub；12 处 `# type: ignore[arg-type]` 全删。nanobot 36/36 + pydantic-ai 22/22 + `make v2-phase3-e2e` 112/112 PASS。上游 `protocolbuffers/protobuf#25319` 若最终 merge 可删除本地 post-process（本仓库正则与上游修复不冲突）。 |
| **D153** | `scripts/gen_runtime_proto.py` 假设 `<repo>/lang/<pkg>/src/<mod>/_proto` 输出布局 — Dockerfile 构建时用 `ln -s /build/src /build/lang/.../src` 绕过 layout mismatch，下次 nanobot/pydantic-ai Dockerfile 落地会重复 hack | Phase 3.6 T4 code review | ✅ CLOSED | Phase 4a T4 — `scripts/gen_runtime_proto.py` 加 `--out-dir DIR` argparse flag，`build(...)` 签名加 `out_dir_override: Path \| None`；当 override 提供时绕过 `REPO_ROOT / pkg_dir / src / ...` 默认路径。`lang/claude-code-runtime-python/Dockerfile` `ln -s` 和 `mkdir -p .../lang/...` 全部删除，改为 `--out-dir /build/src/claude_code_runtime/_proto`。默认路径 regen nanobot 0 diff；`--out-dir` 规划路径生成 byte-identical stubs（仅 `__pycache__` 差异）。 |
| **D154** | `pyrightconfig.json` per-env `pythonVersion` 锁到本机 installed venv（7×3.14 / 1×3.12），而 package `pyproject.toml` 都声明 `>=3.12` — 3.13+-only 语法会溜过检查，fresh clone 用 3.12 venv 时可能在 IDE 里亮红 | Phase 3.6 T5 code review | ✅ CLOSED | Phase 4a T2 — 所有 8 个 per-env `pythonVersion` 从 `"3.14"`/`"3.12"` 统一为 `"3.12"`（pyproject `requires-python>=3.12` floor）。Pyright regression 前后 103 errors + 8 warnings 一致，无 3.13+-only 语法被揪出（说明本机 venv 虽是 3.14 但代码确实写在 3.12 compat 面上）。 |
| **D155** | Fresh-clone / 缺 `.venv` 时 `pyright` 会 fallback 到仓库根 `.venv`（Python 3.12 无 grpc）造成 500+ unresolved imports 假失败 — 未来加 CI pyright gate 时会第一次踩 | Phase 3.6 T5 code review | ✅ CLOSED | Phase 4a T3 — `scripts/check-pyright-prereqs.sh`（44 LOC bash）扫 9 个 per-package `.venv`；缺则 exit 1 + stderr 列缺失 path + 指向 `uv sync` / `make setup` 修复方向。Makefile target `check-pyright-prereqs` 封装调用。手工 mv 一个 venv 验证 exit 1 + 报错正确；恢复后 exit 0。`MISSING_OK=1` 环境变量可退化为 warn-only 模式。 |

**合计新增：11 项 Deferred（10 ✅ CLOSED + 1 🧹 tech-debt）**

所有条目在 Phase 3.5 S2.T1 / S3.T1 / S3.T2 审查中由实现者或审查者提出，均为非阻塞性遗留，不影响 ADR-V2-021 的签收。

---

### NEW-D2 / WATCH-05: Phase 4a project review → Phase 5.1 关闭（NEW- 命名空间）

> **NEW- 命名空间**: Phase 4a project review 期间(2026-04-26) 引入的新发现项, 与 D-序号独立编号。其中 NEW-D 为 Functional/Contract gap, NEW-E 为 ADR governance, NEW-C 为 Refactor。NEW-D2 是 contract test 覆盖度差距, 在 Phase 5.1 由 ADR-V2-025 + 7-runtime 参数化共同关闭。

| ID | 标题 | 引入 | 状态 | 去向 |
|----|------|------|------|------|
| **NEW-D2** | `tests/contract/cases/test_chunk_type_contract.py` 仅 3 tests, not 7-runtime × 21 cases as conftest claimed | Phase 4a project review | ✅ CLOSED | **Phase 5.1 T2** @ `3ba59a1` — `@pytest.mark.parametrize("runtime_name", ADR_V2_025_ACTIVE_RUNTIMES)` 加到 `test_chunk_type_contract`，pytest --collect-only 现展示 9 items（7 parametrized 主 test + 2 unparametrized guard test）。**ADR-V2-025** (Phase 5.1 T1, Accepted 2026-05-02) 给 7 runtime 划分主力档/样板档/参考档/冻结档，明确每个 parametrized case 的执行强度。CI 通过 `--runtime=<one>` 选 matching parametrize value 并 skip 6 个不匹配的 case，保留 session 级 runtime 单 launch 语义。`.github/workflows/phase3-contract.yml` (Phase 5.1 T3) include 表 + tier/xfail/continue-on-error 字段把 ADR-V2-025 §CI 规则 落地为机器可执行的 PR gate（primary block / sample-reference continue / frozen skip）。 |

**合计新增：1 项 NEW-D（NEW-D2 ✅ CLOSED in Phase 5.1）**

WATCH-05 (REQUIREMENTS.md Active 项) 与 NEW-D2 一一对应，关闭后由 Phase 5.1 SUMMARY.md 引用本行 + ROADMAP.md Coverage 表反向回填。

### NEW-F1..F4: LLM Provider 体系治理（2026-05-19 引入 → Phase 5.3 处理）

> **NEW-F 命名空间** (F for "framework"): LLM provider 体系结构治理项，2026-05-19 在 deepseek-chat / Ling-2.6-1T 接入暴露的多个非标准 OpenAI-compat 行为基础上识别。F1+F2 共同构成 provider 子系统的 **职责切分原则**（统一 vs 拆分）；F3+F4 是配套基础设施（fail-fast 与可观察性）。挂到 Phase 5.3 Contract Evolution（与 NEW-E4 ExecutionMode/ADR-V2-026 同 phase）。
>
> **引入动机** (按发现顺序)：
> - Ling-2.6-1T streaming 不发 `data: [DONE]` → parser 卡死，agent 无响应 (2026-05-19 hot fix in `f1xxxx`)
> - deepseek-reasoner 历史回传强制要求 `reasoning_content` 字段 → 之前 400 error (2026-05-15 历史)
> - `reasoning_content` delta 字段在 deepseek/qwen/minimax/siliconflow 多家共享 (`openai.rs:834` 已 hard-code 3 个字段名扫描)
> - `LLM_PROVIDER` / `OPENAI_NO_PROXY` / TUI `RUST_LOG` 多处 silent fallback 让今日单 session 调试耗时数小时（stale `RUST_LOG=octo_*` 静默吞日志、stale binary 静默用旧 default、Clash 代理大 body 失败无诊断）

| ID | 标题 | 详情 | 状态 | Resolution |
|----|------|------|------|------|
| **NEW-E4** | ADR-V2-016 实现漂移：D87 Fix 2 强制 tool_choice=Required 续航在 TUI 对话场景误命中（deepseek-chat × web_search 反复执行）。需 `ExecutionMode { Conversational, LongWorkflow }` + ADR-V2-026 retroactive supersede。RFC 草稿：`.planning/research/2026-05-16-agent-loop-execution-mode-rfc.md`。 | originally 🟠 P1 → Phase 5.3 | ✅ CLOSED 2026-05-20 Phase 5.3 @ `2e7b2b9` | **Resolution**: ADR-V2-026 (Agent Loop Execution Mode) Accepted. RFC at `.planning/research/2026-05-16-agent-loop-execution-mode-rfc.md` promoted to ADR body verbatim (§Context + §Decision + §Migration sections). Implementation already at commit `f1999fb` (2026-05-16) — `ExecutionMode{Conversational, LongWorkflow}` default `Conversational`; `grid-runtime/main.rs` 显式 `set_execution_mode(LongWorkflow)` 保 EAASP E2E。ADR-V2-016 frontmatter flipped to `superseded_by: ADR-V2-026` + Implementation Note appended at body bottom. F1-F5 lint exit 0 PASS / 0 FAIL (F4 module-overlap WARNs are pre-existing across the corpus, not introduced by this commit). Regression test `crates/grid-engine/tests/d87_multi_step_workflow_regression.rs` 3/3 PASS — LongWorkflow behavior locked. |
| **NEW-F1** | OpenAI-compat 共享 quirks 统一处理层 | 在 `OpenAIProvider` 内建立 `Quirks` 抽象（如 `no_done_marker`/`reasoning_content_field`/`null_tool_id_continuation`），按 base_url host 或显式配置选 quirk set。**判定标准：≥2 个真实 provider 出现同一 quirk 才进 OpenAIProvider 统一处理**。当前已有共享点：`reasoning_content` (deepseek/qwen/minimax/siliconflow)、`[DONE]` 缺失 (ant-ling, 待观察是否还有)。 | ✅ CLOSED 2026-05-20 Phase 5.3 @ `e31db54`+`e22ac53`+`5bf6eb7`+`a23c6b2` | **Resolution**: ADR-V2-027 (OpenAI-compat Quirks Framework) Accepted. `crates/grid-engine/src/providers/quirks.rs` prototype lands with **2-field struct** (`reasoning_content_field`, `no_done_marker`) per RESEARCH §"Open Questions (RESOLVED)" Q3 = F2 (single-provider Ling-only assumption for null_tool_id_continuation). Wired into `openai.rs` line ~834 (reasoning scan match-gated by `self.quirks.reasoning_content_field`) and `openai.rs:981` Poll::Ready(None) flush (gated by `this.quirks.no_done_marker`; default-false path returns `Err("stream ended without [DONE]")` — strict-OpenAI assertion preserved per Pitfall 5). `deepseek.rs` constructor updated to construct `Quirks { reasoning_content_field: MultiField, .. }` via new `OpenAIProvider::with_base_url_and_quirks` helper. 5/5 quirks unit tests + 3/3 deepseek regression tests + 127/127 providers lib tests PASS. |
| **NEW-F2** | Provider-specific 怪癖 → 拆独立 provider | 某 quirk 只 1 家有 → 不进 OpenAIProvider，开新 `XxxProvider` (已有先例: `DeepseekProvider`)。**判定门槛**：行为差异≥3 处 或 破坏 common path 复杂度。例：deepseek-reasoner 的 `reasoning_content` 强制回传 history（独有约束）应在专属 provider 内 enforce。 | ✅ CLOSED 2026-05-20 Phase 5.3 @ `9aa1aa4`+`a23c6b2` | **Resolution**: ADR-V2-027 F2 split rule documented (single-provider strong quirks → dedicated `<Vendor>Provider` per `deepseek.rs` precedent). `crates/grid-engine/src/providers/ling.rs` lands (98 LOC mirror of deepseek.rs) with `Quirks { no_done_marker: true, .. }` and inline `normalize_null_tool_ids` hook for ant-ling's null `tool_calls[].id` continuation behavior (placeholder until grid_types exposes mutator surface; stream-hang symptom already covered by F1 `no_done_marker` branch). `mod.rs::create_provider` dispatch adds `"ling" => create_ling_provider` arm; `chain.rs` module-header doc + dispatch test wire the F2 split at chain layer. F2 split path remains documented for future single-provider quirks. (Q3 was resolved at planning time to assume single-provider Ling-only; if a second provider for null_tool_id_continuation surfaces later, promotion to F1 is a 5-LOC field add on the existing Quirks struct.) 4/4 ling unit tests + 1/1 chain dispatch test PASS. |
| **NEW-F3** | 移除关键基础设施 silent fallback | `LLM_PROVIDER` / `OPENAI_NO_PROXY` / TUI logger / `RUST_LOG` 配置错误一律 fail-fast 退出 + actionable error。**反 pattern 列表**：`unwrap_or_else(_default)`、`fallback to stderr`、`expect("...")` 静默 panic 但 ratatui 吞掉。**正确 pattern**：明确 error message 指明问题 + 修复路径（"set X=... in .env or shell"）。 | ✅ CLOSED 2026-05-21 Phase 5.4 @ `9007935`+`5b5c892` (5.4-02-03 + 5.4-02-09) | **Resolution**: `crates/grid-engine/src/providers/config.rs::ProviderConfig::try_from_env` strict API 实现 — `LLM_PROVIDER` / `OPENAI_API_KEY` / `OPENAI_MODEL_NAME` 任一缺失返回 `Err(ConfigError::MissingEnv)`，production code path（grid-server / grid-runtime entrypoint）已切到 strict API。silent-fallback `Default` impl 保留只作为测试 fixture。ADR-V2-028 (Strict-by-default Config Validation) Accepted formalizing the policy。`providers/config::tests` ≥5 cases PASS。 |
| **NEW-F4** | TUI log 路径与诊断设施 ADR | TUI 缺省 log → `./logs/tui.log` (in repo, easy `tail -f`)，`GRID_TUI_LOG=<path>` 显式覆盖，旧路径 `~/Library/Application Support/grid/tui.log` 弃用。已 hot fix in `studio_main.rs:resolve_tui_log_path` (2026-05-19)，需正式记 ADR + 删除 dirs::data_local_dir() 旧路径。 | ✅ CLOSED 2026-05-22 Phase 5.5 Plan 01 @ `1b9afd1` + `ba3ba26` | **Resolution**: ADR-V2-032 (TUI Log Path Convention) Accepted Phase 5.5 Task 01.A2 @ `1b9afd1` (type=record, 191 LOC, §1 default + override + deprecated paths, §2 sanity-print contract, §3 dirs crate dep retained for path_shortener.rs). Dead `dirs::data_local_dir()` branch removed from `crates/grid-cli/src/studio_main.rs::resolve_tui_log_path` L57-60 Phase 5.5 Task 01.B2 @ `ba3ba26` (resolve_tui_log_path shrunk 19→13 lines; docstring rewords to "platform-specific local-data directory fallback" to satisfy strict grep acceptance criterion). `cargo build -p grid-cli --features studio` Finished clean. `dirs` Cargo dep retained (still used by `path_shortener.rs:20,127`). |

**实施约束** (来自 user feedback 2026-05-19)：
1. F1 与 F2 是**对偶判定**——同一 quirk 落到 F1（统一）还是 F2（独立 provider）由 "共享数" + "差异复杂度" 决定，不能两边都不放。
2. F3 优先级最高（debug 体验由它决定）。F1/F2 次之（架构整洁）。F4 最低（已 hot fix）。
3. 这 4 条共同进 Phase 5.3 的好处：ADR-V2-026 (supersede V2-016, ExecutionMode) + ADR-V2-027 (OpenAI-compat quirks) + ADR-V2-028 (config-strictness) 可以同一 phase 一起记录，避免散落。

**关联**：NEW-E4 (ExecutionMode RFC, Phase 5.3 现已挂) + WATCH-01 (D109) + WATCH-03 (D136) 共同构成 Phase 5.3 的工作面。本组 F1-F4 进 Phase 5.3 后总工作面约 7 项。plan-phase 评估是否需要 parallel plans。

### NEW-A2 / NEW-E3: Phase 5.4 SERVER hardening 关闭（NEW-A 命名空间 + NEW-E 命名空间）

> **NEW-A 命名空间** (A for "atomicity"): 2026-05-16 NEW-A1 forensics 衍生的 SQLite migration atomicity 问题。**NEW-E 命名空间** (E for "ADR governance"): Phase 4a project review (2026-04-26) 期间识别的 ADR 状态推进项。两条均挂到 Phase 5.4 SERVER-01..05 hardening 集群，与 D142+D143（WATCH-04）+ NEW-F3（fail-fast 配置）同 phase 同 plan 关闭。

| ID | 标题 | 引入 | 状态 | Resolution |
|----|------|------|------|------|
| **NEW-A2** | `migrate()` in `crates/grid-engine/src/db/mod.rs:29` 非原子 (读 `user_version` → 跑 ALTER → 写 `user_version` 之间无锁), 多进程同 db 文件并发 migrate 会重现 `duplicate column name: user_id`。production race, 单进程 grid-cli 不触发 | 2026-05-16 NEW-A1 forensics | ✅ CLOSED 2026-05-21 Phase 5.4 @ `74e6472`+`bf26cb8` (5.4-02-01 + 5.4-02-02) | **Resolution**: `migrate()` 改为 `conn.execute_batch("BEGIN EXCLUSIVE")` 写者锁 + 进入 txn 后双检 `PRAGMA user_version` (read-after-lock) + ALTER + 写 `user_version` + COMMIT. 4-process release-build regression test `crates/grid-server/tests/migrate_race.rs` spawn 4 个并发进程对同一 db file 调 `migrate()` — 全部 PASS, 无 `duplicate column` error, 最终 user_version == CURRENT_VERSION (13). T-02 (Tampering / Data corruption) 威胁 mitigated per ASVS V14.1.5 (atomic file operations). |
| **NEW-E3** | ADR-V2-019 enforcement.trace 为空 — ADR 已 Accepted 2026-04-20 但 trace 数组缺 implementation anchors, 形成 ADR governance gap (lint F1-F2 不查 trace 内容, 只查 status / accepted_at / superseded chain) | Phase 4a project review (2026-04-26) | ✅ CLOSED 2026-05-21 Phase 5.4 @ `70b5e94` (5.4-02-10) | **Resolution**: ADR-V2-019 `enforcement.trace` 数组填 4 个 anchor 指向 D142+D143 实现位点 (`grid-runtime/src/config.rs::RuntimeConfig::deployment_mode`, `grid-runtime/src/service.rs::RuntimeServiceImpl::create_session`, `claude-code-runtime-python/.../service.py::__init__::_deployment_mode`, `claude-code-runtime-python/.../service.py::Initialize`). ADR lint `--id V2-019 --ci` → 7 PASS / 0 FAIL. **重要**: ADR status `Accepted` UNCHANGED, `accepted_at: 2026-04-20` UNCHANGED — 此动作是 trace 回填 (Q9 confirmed), NOT 一次 status flip。WATCH-07 closed。 |

**合计新增 2 项**: NEW-A2 (✅ CLOSED Phase 5.4) + NEW-E3 (✅ CLOSED Phase 5.4)。两条同 Plan 5.4-02 关闭。

### NEW-A3 / NEW-E2 / NEW-L1 / grid-cli mod output / NEW-X2 / NEW-X3: Phase 5.5 milestone close cascade（多命名空间汇总）

> **NEW-A3**: 2026-05-17 Phase 5.2 smoke test discovery (kill_session exit code anti-pattern, fold into Phase 5.5 per CONTEXT D-06). **NEW-E2**: Phase 4a session-04-26 audit (F3 ADR enforcement.trace missing items advisory, baseline corrected 29 → 33 live 2026-05-22; mapped to Phase 5.5 WATCH-06). **NEW-L1**: 2026-05-20 Phase 5.3 OOS forensics (HNSW 94GB disk leak from unbounded `max_elements` doubling + meta.json schema gap, fold into Phase 5.5 per CONTEXT D-06). **grid-cli mod output E0583**: 2026-05-20 Phase 5.3 OOS (verified clean Phase 5.5, no edit). All four closed Phase 5.5 Plan 01. **NEW-X2 / NEW-X3**: two new P3 inbox rows surfaced during Plan 01 scope-limit decisions, defer to v3.2+.

| ID | 标题 | 引入 | 状态 | Resolution |
|----|------|------|------|------|
| **NEW-E2** | F3 ADR enforcement.trace 29 (corrected to 33 baseline live 2026-05-22) missing items advisory | Phase 4a session-04-26 audit | ✅ CLOSED 2026-05-22 Phase 5.5 Plan 01 @ `2303b3d` + `e84a57e` | **Resolution**: 9-ADR F3 sweep. Block A (5 contract ADRs V2-006/V2-018/V2-020/V2-027/V2-028) — trace anchors appended to `.github/workflows/phase3-contract.yml` (16-line anchor block at end for V2-006/018/020) + `.github/workflows/eval-ci.yml` (4-line anchor block at end for V2-027/028); `.adr-config.yaml` extended with `.github/workflows/eval-ci.yml` to 4-entry `ci_workflows` list (Deviation Rule 3 — config gap discovered + fixed during Block A). Block B (4 strategy ADRs V2-001/V2-002/V2-003/V2-005) — annotated with 5-line "F3-WARN expected: strategic ADR documentation anchor" rationale comment block ABOVE `trace:` field in frontmatter. F3 WARN 33 → 12 explicit-strategic + 0 unjustified (beats ≤13 target). ADR statuses + accepted_at fields UNCHANGED per MEMORY.md "ADR 状态二次校验" rule. F1/F2 0 FAIL. WATCH-06 closed jointly. |
| **NEW-A3** | `kill_session` in `crates/grid-cli/src/commands/session.rs:117` returns `anyhow!("Session not found: ...")` mapping to `ExitCode::General` (1) via main.rs error arm; should be typed `GridError::SessionNotFound` → exit 4 | 2026-05-17 Phase 5.2 T-01.19 smoke test discovery | ✅ CLOSED 2026-05-22 Phase 5.5 Plan 01 @ `8c25223` | **Resolution**: replaced `anyhow!("Session not found: ...")` with `GridError::session_not_found(session_id).into()` at `session.rs:117`; enhanced `main.rs:92-96` to `downcast_ref::<GridError>` before falling back to `GridError::other(...)`, preserving the typed `SessionNotFound` variant through `?` propagation. Regression test `test_kill_nonexistent_session_exits_4` added to `crates/grid-cli/tests/cli_integration.rs`. `cargo test -p grid-cli` 147 + 6 PASS. Filed NEW-X2 (sibling delete_session L99-103 + export_session L157 same anti-pattern, scope-limited per CONTEXT D-06 verbatim) as P3 inbox below. |
| **NEW-L1** | `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/vector_index.py:189-192` unbounded `max_elements` doubling + meta.json schema gap (94GB disk leak observed 2026-05-20) | 2026-05-20 Phase 5.3 OOS forensics | ✅ CLOSED 2026-05-22 Phase 5.5 Plan 01 @ `0bdf70c` | **Resolution**: introduced module-level `HNSW_HARD_CAP = 1_000_000` constant; capped growth to `min(self._max_elements * 2, HNSW_HARD_CAP)` with actionable `RuntimeError` when cap exceeded; added `"max_elements": self._max_elements` key to meta dict in `save()`; restored on reload via `meta.get("max_elements", self._max_elements)` in `_try_load_sync`. 2 regression tests added (`test_grow_hits_hard_cap` + `test_meta_json_max_elements_roundtrip`). `uv run pytest tools/eaasp-l2-memory-engine/tests/test_vector_index.py` 12/12 PASS (10 existing + 2 new W0 stubs now passing). Atomic write at L236 preserved (V14.1.5). Production cap = 1_000_000 matches typical L2-memory production load (~4 GB at dim=1024 fp32); tests monkeypatch to 100 for fast cap-hit coverage (W-3 lock-in; zero conditional logic in module). |
| **grid-cli mod output E0583** | Phase 5.3 reported compile error on `pub mod output;` (lib.rs:20); deferred to Phase 5.4 → 5.5 | 2026-05-20 Phase 5.3 OOS | ✅ CLOSED 2026-05-22 Phase 5.5 (verification-only) | **Resolution**: Both `cargo build -p grid-cli` and `cargo build -p grid-cli --features studio` verified clean 2026-05-22 (exit 0, no E0583; Plan 01 Task 01.B3 verify-only, no commit per plan spec). Output/ module structure intact (`mod.rs` + `json.rs` + `stream_json.rs` + `text.rs`). Root cause unknown — resolved by an earlier commit between Phase 5.3 report and Phase 5.5 verification. **Note**: `cargo build -p grid-cli --all-features` still fails with 12 unrelated grid-engine errors (E0596 borrow-checker + E0412/E0425/E0433 in hooks module); filed as deferred row NEW-X3 below. |
| **NEW-X2** | Sibling `kill_session` anti-pattern at `crates/grid-cli/src/commands/session.rs:99-103` (`delete_session`) and L157 (`export_session`) — same `anyhow!("Session not found: ...")` pattern as NEW-A3, still maps to ExitCode::General (1) instead of typed SessionNotFound (4) | 2026-05-22 Phase 5.5 Plan 01 RESEARCH §2.1 + Task 01.B1 scope limit per CONTEXT D-06 verbatim | ✅ CLOSED 2026-05-25 Phase 6.1 Plan 01 @ `0595e31`+`a0a6c28` | **Resolution**: ported NEW-A3 pattern (Phase 5.5 Plan 01 Task B1) to delete_session + export_session verbatim — replaced anyhow!/eprintln!-then-Ok mappings with `GridError::session_not_found(session_id).into()` propagation; main.rs:92-103 downcast arm auto-catches typed variant → exit 4. delete_session also fixed pre-existing silent-exit-0 bug (eprintln-then-Ok no longer reachable after typed-error guard). Tests `test_delete_nonexistent_session_exits_4` + `test_export_nonexistent_session_exits_4` added to `cli_integration.rs` (verbatim mirror of `test_kill_nonexistent_session_exits_4`, no stderr assertion per CONTEXT.md D-07). `cargo test -p grid-cli --features studio` 578 PASS (566 lib + 8 cli_integration including all 3 exit-4 tests + 3 key_handler + 1 doc). @`0595e31`+`a0a6c28` |
| **NEW-X3** | `cargo build -p grid-cli --all-features` fails with 12 unrelated grid-engine errors (E0596 borrow-checker + E0412/E0425/E0433 in hooks module) — pre-existing as of 2026-05-22 | 2026-05-22 Phase 5.5 Plan 01 RESEARCH §Anti-Patterns R2 + Task 01.B3 plan note | ✅ CLOSED 2026-05-25 Phase 6.1 Plan 01 @ `adf2c08`+`97f59e5` | **Resolution**: Option (a) fix all 12 errors per CONTEXT.md D-01. Root cause archaeology: Phase BA Grid rename (octo→grid 2026-04-04, 8 crates renamed) missed `crates/grid-engine/wit/octo-hook.wit` + `OctoHookPlugin` bindings + WIT package `octo:hook` + WIT world `octo-hook-plugin`; revealed when `--all-features` activates `sandbox-wasm` feature transitively (4 of 12 errors — Bucket A, including a wit-bindgen-derived accessor `plugin.octo_hook_hook_handler()` not enumerated in the original CONTEXT but required by the new package name). Bucket B (5+2 errors collapsed) was independent: 1 missing `use std::collections::HashMap` in `hooks/declarative/bridge.rs` (resolves 2 errors at L29+L40) + 1 `_config` parameter-name shadow typo in `sandbox/wasm.rs:334` cascading to 5 E0425 sites at L354/357/360/363/368. Bucket C (1 error) was a borrow-checker fix: `let bridge` → `let mut bridge` at `agent/runtime.rs:718` so the `sandbox-wasm`-feature-gated `bridge.register_wasm_handler(...)` loop at L722 type-checks. Fix sequence: Bucket B+C landed first at @`adf2c08` (3 mechanical edits, 11→4 errors); Bucket A landed atomically at @`97f59e5` (`git mv` wit file + package/world rename + 6 consumer sites across mod.rs + handler.rs + host_impl.rs). Verify: `cargo build -p grid-cli --all-features` exit 0; `cargo build -p grid-cli` + `--features studio` regression-clean; `cargo check --workspace` exit 0 (0 errors, pre-existing warnings only); `cargo test -p grid-cli --features studio` 578 PASS. Side effect: default-feature builds now emit a harmless `unused variable: config` warning at `sandbox/wasm.rs:334` because the body is `#[cfg(feature = "sandbox-wasm")]`-gated — accepted as minimal-ceremony. Notable: wasm hook code is NOT dead (referenced from `agent/runtime.rs:686-693` via `WasmHookHandler::create_engine()`/`::load()`); 不另开 NEW-X5 反向追责 Phase BA (per CONTEXT.md D-10 — archaeology captured here, v3.3 TRIAGE not burdened). @`adf2c08`+`97f59e5` |
| **NEW-X4** | `tests/contract/cases/test_chunk_type_contract.py::test_chunk_type_contract[<runtime>]` FAILS with `ScopeMismatch: You tried to access the function scoped fixture runtime_name with a session scoped request object` across 6 of 7 contract-matrix runtimes (claude-code / goose / nanobot / pydantic-ai / claw-code / ccb; hermes frozen-skip; grid still in_progress at observation time but expected same failure). Phase 3 Contract Matrix CI workflow has been RED since at least 2026-05-04 — pre-existing failure NOT introduced by Phase 5.5. | 2026-05-23 surfaced during Phase 5.5 post-push CI scan; root pre-existence confirmed via `gh run list --workflow="Phase 3 Contract Matrix"` showing FAIL on every push since 2026-05-04 | ✅ CLOSED 2026-05-24 Phase 6.0 @ `e27e300` + CI run https://github.com/uukuguy/grid-sandbox/actions/runs/26356947711 — rename parametrize identifier "runtime_name" → "expected_runtime" at 3 sites (test_chunk_type_contract.py:139 + test_hook_event_contract.py:203 + 238); session fixture conftest.py:113 untouched; Phase 3 Contract Matrix workflow ZERO ScopeMismatch across all 7 completed jobs (3 PASS: claude-code/goose/hermes; 4 PRE-EXISTING fail on D136 hook_envelope unrelated to NEW-X4; grid still in-progress at write time — historical CI hang pattern, not regression). SC#1 (fixture-wiring repaired) FULLY SATISFIED; SC#2 (≥4/7 PASS) pending grid job completion. | **Deferred**: pytest fixture-scope mismatch — `runtime_name` is `@pytest.fixture(scope="function")` (or unscoped default) but a session-scoped fixture in `tests/contract/conftest.py` requests it. Likely root cause: `runtime_name` should be `scope="session"`, OR the requesting fixture should be `scope="function"`. Last contract test change was `3ba59a1 test(contract): parametrize chunk_type test for 7 runtimes (NEW-D2)` (Phase 5.1 2026-05-02) — likely introduced the scope conflict but wasn't caught locally because devs run targeted runtime tests, not the full matrix. NOT a Phase 5.5 regression (Phase 5.5 touched ZERO files under `tests/contract/`). Fix is small (~5 LOC scope-decorator change in `tests/contract/conftest.py` or `cases/test_chunk_type_contract.py`) but defer to v3.2+ since it requires running the full matrix locally to verify across all 7 runtimes. Local repro: `pytest tests/contract/cases/test_chunk_type_contract.py -k claude-code -v`. |

**合计新增 7 项 in this section**: 7 closed (NEW-E2, NEW-A3, NEW-L1, grid-cli mod output verify-only, **NEW-X4 ✅ CLOSED Phase 6.0 2026-05-24**, **NEW-X2 ✅ CLOSED Phase 6.1 2026-05-25**, **NEW-X3 ✅ CLOSED Phase 6.1 2026-05-25**). The 4 Phase-5.5-milestone closures land that cascade; the 2 P3 rows opened for v3.2 Phase 6.1 (NEW-X2 + NEW-X3) are now both CLOSED 2026-05-25 (NEW-X2 @ `0595e31`+`a0a6c28` typed-error pattern; NEW-X3 @ `adf2c08`+`97f59e5` Phase BA wit/bindgen rename leftover + 2 small bugs). NEW-X4 closed Phase 6.0 Plan 01 (parametrize-layer rename, 3 sites); added post-push 2026-05-23 from CI scan (pre-existing failure, not Phase 5.5 regression).

## 附录 A: Legacy-Octo D 编号（pre-EAASP, 独立命名空间）

以下文件各自维护独立的 D 编号空间，与 EAASP 全局空间无关。仅供历史查询：

| 文件 | D 编号 | 状态 |
|------|--------|------|
| `2026-03-02-phase2-9-agent-registry.md` | D1, D2, D3 | ✅ 均已补 |
| `2026-03-04-octo-platform-design.md` | D1, D2, D3 | 大部分 ✅ 已补 |
| `2026-03-04-v1.0-release-sprint-plan.md` | D1–D5 | ✅ 均已补 |
| `2026-03-09-harness-implementation.md` | D1–D6 | 大部分 ✅ 已补 |
| `2026-03-10-deferred-d2-d4-d5.md` | D3, D6, D7 | ⏳ pending |
| `2026-03-10-deferred-d3-d6-d7.md` | D8–D13 | ⏳ pending |
| `2026-03-10-octo-cli-redesign.md` | D1–D5 | 部分 ⏳ |
| `2026-03-11-deferred-completion.md` | D1–D7 | ⏳ |
| `2026-03-11-wave6-production-hardening.md` | D2, D3, D5, D7, D8, D9 | ⏳ 新增 |
| `2026-03-15-phase-m-eval-cli.md` | D1–D3 | ✅ |
| `2026-03-15-phase-n-agent-debug.md` | D1–D4 | ✅ 均已补 (Phase O) |
| `2026-03-22-phase-u-tui-production-hardening.md` | D1–D10 | 设计决策，非 deferred |

**结论**: Legacy-Octo D 编号大部分已在各自 plan 里闭环。若需追踪 Octo 产品线的遗留技术债，单独建立 `docs/plans/LEGACY_OCTO_DEBT.md`。本 ledger 只管 EAASP 全局命名空间。

---

## 附录 B: 引用格式规范

**commit message**:
```
fix(eaasp): D85 — STOP event response_text populated
```

**plan / ADR 文档**:
```markdown
**关联 Deferred**: D83 (S1.T4), D85 (S1.T5)
**Supersedes**: D27 (原 L4→L1 gRPC 占位描述)
```

**本 ledger 更新**:
每次状态变更后追加到 [状态变更日志](#状态变更日志)，并同步对应 section 的状态列。
