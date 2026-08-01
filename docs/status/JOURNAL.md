# Journal — append-only event log

> One line per commit / verified result / dropped path. Never edit past lines.
> Format: `## YYYY-MM-DD` date headers, then `- HH:MM <fact> [commit hash if any]`

## 2026-07-25
- 现在确认 v3.8.0–v3.8.3 已全部完成，v3.8 已归档；旧 RESUME baton 曾错误指向 v03.8.3。
- 已重建 lightweight-memory 结构快照与索引，后续讨论从下一 milestone 边界开始。

## 2026-07-26
- 启动 v3.10 EAASP v2.0 平台骨架对齐 milestone。
- v3.10 milestone bootstrap 已 fast-forward 集成到 main [b0d4502e]。
- v3.10 EAASP v2.0 平台骨架对齐已 SHIPPED，main 推进到 179a15a1，tag v3.10 已建立；174 targeted tests PASS。
- v3.11.0 OPA sidecar 基础设施已 SHIPPED，ADR-V2-034 Accepted，make opa-install 可用，V310-OPA-01 已 CLOSED [84ca0a11]。
- v3.11.1 L3 OPA backend adapter + Rego templates 已 SHIPPED (OPABackend.evaluate + 5 fail-closed modes; 57/57 tests PASS; ADR-V2-023 P1 unchanged) — [2acbf62a] + ADR/STATE/REQUIREMENTS sync [4fe41955]。
- v3.11.1 security review 3 issues fixed (Issue 1 /v1/evaluate session binding; Issue 2 bidirectional allow↔decision invariant; Issue 3 URL guard + sanitized origin) — [6338d376]。

## 2026-07-28
- v3.14 EAASP Phase 6 — Ontology/Marketplace/SDK bootstrap (EVO final phase) on main [b878e7b2]
- v3.11.2 5-stage approval state machine + 5 governance.approval.* SSE events 已 SHIPPED，V310-APPROVAL-01 已 CLOSED [c92513ca]。

## 2026-08-01
- v3.15 platform observability 设计文档 + L3 OPA sidecar/circuit-breaker 底座已提交 [e08d9bd9]。原 PHASE_3_5_DESIGN.md 范围过窄(L3 OPA)被替换为 OBSTACK_DESIGN.md(跨 L0–L5 平台级 observe/trace/evaluate/optimize)。v3.15.0–v3.15.4 phases 已 scope 但未实现。
- v3.15.0 L3 OTel metrics baseline 已 SHIPPED: observability.py (no-op 默认 + stdout/otlp 可选) + 8 tests PASS [a18a22ba]。L1/L2/L4 同模式接入待补。
- v3.15.1 BusinessFlow 核心已 SHIPPED: eaasp_common.business_flow (BusinessKey + 序列化/反序列化 + contextvar 传播) + 24/24 tests PASS [87496d65]。设计文档重排为业务流为主线, v3.15.1-4 重排, 业务流 vertical cross-layer binding 是核心。
- v3.15.2 业务流时间线聚合已 SHIPPED: flow_timeline.py (BusinessFlowEvent + Summary + LayerReader + status 推断) + 23/23 tests PASS [61213433]。L4 REST 路由 + L2/L3 reader 接线为 v3.15.3。
- v3.15.3a L3 business_key migration + L4 FlowEventBus 已 SHIPPED: L3 governance_decisions/telemetry_events 加 business_key 列 (idempotent ALTER), L4 flow_sse.py (跨层 pub/sub) + 9/9 tests PASS [d2667707]。L2 migration + api.py SSE 路由 + 评估器为下批。
- v3.15.3c 业务流评估器已 SHIPPED: flow_evaluator.py (达成率 + 中断点热力 + 跨层优化建议) + 15/15 tests PASS [098fb1f1]。L4 business flow 模块 47/47 tests (timeline 23 + sse 9 + evaluator 15)。L2 migration + api.py SSE 路由 + live walkthrough 为下批。
- v3.15.4a L2 memory_engine business_key migration 已 SHIPPED: memory_files + anchors 加 business_key 列 (idempotent ALTER) [2b3f2680]。端到端验证 init_db OK + 两张表 business_key 列均存在。L2/L3/L4 schema 现已就位, timeline aggregator 可读三源数据。
- v3.15.4b L4 业务流 REST + SSE 路由已 SHIPPED: flow_api.py (timeline / summary / events/stream / evaluation 4 个 endpoint) + 8/8 tests PASS [a80f8cc9]。L4 business flow 模块累计 55/55 tests。L2/L3 reader 接线 + live walkthrough + tag v3.15 为下批。
- v3.15.4d eaasp flow CLI 子命令已 SHIPPED: cmd_flow.py (timeline / summary / watch / evaluate) + 8/8 tests PASS [05e3577f]。v3.15 累计 101 tests PASS。L4 服务端 L2/L3 reader 注入 + live walkthrough + tag v3.15 为下批。
- v3.11.3 single-point live walkthrough 已 SHIPPED，SSE/OPA/audit 完整证据 PRODUCTION_USABILITY_2026-07-27，tag v3.11 已建立 [c3d1d789]。
- v3.12 milestone bootstrap 已 commit (EAASP Phase 4 A2A Router + Event Room + multi-session) [ba99b851]。
- v3.12.0 audit.py CHECK constraint patch 已 SHIPPED，V311-AUDIT-01 已 CLOSED [c8a5d391]。
- v3.12.1 Event Room + multi-session 已 SHIPPED，5 轮 security review 关闭 9 个问题 [a248d73a]。
- v3.12.2 A2A Router + ReviewSet + 冲突检测已 SHIPPED，3 个 HIGH security fix 关闭，ADR-V2-035 Accepted [815ab12b]。
- v3.12.3 single-point live walkthrough 已 SHIPPED，10+ SSE 事件完整证据，tag v3.12 已建立 [894639dd]。
- v3.13 milestone bootstrap (EAASP Phase 5 L5 Cowork 四卡 + 回溯闭环) on main [ddd83337]。
- v3.13 L5 Cowork 四卡 + retrospective cycle 已 SHIPPED，82/82 tests PASS，V310-COWORK-01 已 CLOSED，tag v3.13 已建立 [d0d83a23]。
- 21:09 v3.14 Phase 6 (Ontology / Marketplace / Skill ecosystem) 已 SHIPPED，66/66 tests PASS，2 轮 security review (3 CRITICAL+1 HIGH) 关闭，V310-ECOSYSTEM-01+V310-MAT-01 已 CLOSED [05074170]；EVOLUTION_PATH 8-Phase 路线全 SHIPPED。

## 2026-07-29
- 推送 6 commit 到 origin/main（v3.14 EAASP Phase 6 + journal restore + EAASP 仿真环境使用指南 + handoff checkpoint）。
- tag v3.14 annotated 已 push。
- 清理 8 个 SGAI sub-worktree（soft cap 4 已合规）。
- handoff checkpoint: docs/status/RESUME-NEXT-SESSION.md 已落地；EVOLUTION_PATH 8-Phase 路线全 SHIPPED + 8 项 V310-* deferred 全部 ✅ CLOSED [ef10222d]。

## 2026-07-30
- 03.14.2-C1 SDK thin client 落地: `EaaspEcosystemClient` (sync + async) 包装 10 个 L4 /v1/ecosystem/* endpoint; 4 typed exception (AuthError / ACLDenied / TenantForbidden / PromotionError); 17 respx-mocked tests PASS; 实现 SDK-01 + SDK-03 [9c845e29]。
- 03.14.2-C2 MARKETPLACE-03 CLI 落地: `eaasp-ecosystem marketplace {submit,promote,list,stats,audit}` 5 subcommand 全 HTTP httpx.Client(trust_env=False); fix latent os.environ.get NameError bug; 9 respx tests + 75 总数 PASS [ced94f33]。
- 03.14.2-C3 SDK Click CLI 落地: `eaasp ecosystem {schema,ontology,marketplace}` Click group thin wrap EaaspEcosystemClient; 6 respx + CliRunner tests PASS; 实现 SDK-02 [de70d199]。03.14.2 全部 3 个 atomic commit 完成,32 新增 tests 0 regression。
- 03.14.3 single-point live walkthrough 落地: `docs/status/PRODUCTION_USABILITY_2026-07-30.md` 5 步骤 + dual-gate PASS + 7-row boundary invariants; 11 nodes across 4 layers (4 l2_type + 2 l3_risk + 2 l4_event + 2 l5_card + 1 root) + 9-type JSON-schema + 32 新 SDK tests 0 regression [31c804eb]。
- V310-ECOSYSTEM-01 ✅ CLOSED 2026-07-30 (v3.14 SHIP 4-phase ladder); EVOLUTION_PATH §三 8-Phase 路线 ALL SHIPPED; V310-MAT-01 保持 `📦 long-term` (per REQUIREMENTS.md:56 + D-44/D-46 carry-over — out of v3.14 scope)。prior RESUME-NEXT-SESSION.md:44-45 + JOURNAL.md:29 "V310-MAT-01 ✅ CLOSED" 误标已 reconcile 修正。tag `v3.14 -fa` force-push。STATE.md / PROJECT.md / ROADMAP.md / REQUIREMENTS.md / DEFERRED_LEDGER.md / ALIGNMENT_MATRIX.md 全部同步收口 [this commit]。
- GSD state machine 同步: `.planning/phases/03.14.{0,1,2,3}-*/` 4 phase dirs 落地; 4 SUMMARY.md (recap of 03.14.0/1/2/3) + 2 PLAN.md (03.14.2 + 03.14.3); total 6 files / 889 insertions [dbd2a9b9]。v3.14 闭环完整收口。

## 2026-07-30
- v3.14.3 close-out docs text-sync: spec-audit row count 37 → 38 across REPORT.md + PRODUCTION_USABILITY_2026-07-30.md (3 occurrences) + RESUME-NEXT-SESSION.md + DEFERRED_LEDGER.md + EAASP_SIMULATION_USER_GUIDE.md; ADR-V2-034/V2-035 bodies 保留 37 (Acceptance-time historical snapshot per ADR governance immutable-Accepted-body rule); PRODUCTION_USABILITY 添加 snapshot rationale note; certifier + alignment-matrix 2/2 tests PASS [690ca810]。v3.14 闭环 post-merge text-sync gap 已收口。
- Final handoff refresh: docs/status/CURRENT-STATE.md (重写 v3.8-era baseline → v3.14 SHIPPED state) + docs/status/RESUME-NEXT-SESSION.md (重写 9e712833 → 349f769b; HEAD 38-row dual-gate; 8 × V310-* + V311-AUDIT-01 = 9 ✅ CLOSED; 5 v3.15 候选 + ADR-V2-024 Open Item #3 priority axis = grid-cli + grid-server); task list extend 到 #115/#116; 2 files / +217 / -121 [df2922f7]。v3.14 milestone handoff complete — next session reads `df2922f7` + JOURNAL latest entry 即接力。
- .planning/ handoff template pointer refresh: `.planning/.continue-here.md` + `HANDOFF.json` + `RESUME-NEXT-SESSION.md` 三文件从 v3.8-era 内容改写为指向 `docs/status/` canonical baton 的 pointer (避免重复;archived v3.8 内容保留在 git history `0a438e7e`);3 files / +97 / -166 [351b1cc4]。
- EAASP 仿真环境 verification plan 入仓:`docs/status/VERIFICATION_PLAN_2026-07-30.md` 223 行 live full-stack 验证方案(4 phases:服务启停 / static audit gate / 真 skill+LLM 端到端 / 跨 SDK 验证);记录关键发现 dev-eaasp.sh 不含 L5/OPA 需手动启;per CLAUDE.md §3 不自动跑 background / per feedback_no_full_tests 不自动 cargo test --workspace [eb0c553c]。
- skill-registry 旧 schema migration bug fix:`tools/eaasp-skill-registry/src/store.rs` CREATE INDEX 从 CREATE TABLE 块内移出(migrate_add_access_scope() 在 ALTER 后幂等建索引);regression test `store_open_migrates_legacy_schema_without_access_scope_column` 加在 tests/store_test.rs;36 个 tests 全 PASS;自动跑 Phase 1+2 期间发现 [8e3594e2]。
- L4+CLI X-Session-Scope header 转发 fix(D8/L3-04 RBAC):L4 api.py 提取 header + wildcard fallback warning;L4 handshake.py L3Client validate_session 转发;L4 session_orchestrator 贯穿 session_scope;CLI client.call 加 headers kwarg;CLI session create 读 `EAASP_SESSION_SCOPE` env;`examples/skills/threshold-calibration/SKILL.md` access_scope 改 `org:eaasp-verify-2026-07-30` 避免 D11 namespace 冲突;真跑 Phase 3 §6.2-§6.3 + §7 期间发现并修 [a6d75300]。
- L4 fail-CLOSED X-Session-Scope binding(security review follow-up):删 wildcard fallback;加 `_resolve_skill_bound_scope` 严格按 skill 注册的 access_scope 校验 header(防止 free-form scope 冒充);CLI `EAASP_SESSION_SCOPE` 强制必填;3 个 regression tests + 283/284 tests 全 PASS(1 pre-existing 失败 unrelated);[3398d567]。
- L4 round-2 fail-closed(security review round-2):删 skill_registry=None + read_skill 失败 + access_scope 未声明 三处 fail-open fallback;加 `EAASP_DEV_DISABLE_SCOPE_BINDING=1` 显式 dev passthrough;285/286 tests PASS(1 pre-existing);[bbc5d7df]。
- EAASP 仿真环境验证 session 收口:CURRENT-STATE.md 加 Session 2026-07-30 段(14 services + 双 gate PASS + 4 bug fixes);RESUME-NEXT-SESSION.md 头部刷新 HEAD=5cf10bee / ahead origin/main 11 + next session's first 3 actions;服务栈全部 teardown(0 process);[5cf10bee]。
- CLI session.run 转发 X-Session-Scope(原 round-1 漏了 run 路径,只在 create 上):service_client.stream_sse 加 headers kwarg + 转发;§6.3 真跑 session.run 返回 200 + 真 LLM streaming + 阈值校准结果(60°C/65°C/80°C);[d5a4963b]。
- EAASP round-2 verification replay 完整 PASS:重跑 Phase 1(14 services) + Phase 2(audit gates) + Phase 3(§6.2 submit+4 promote / §6.3 真 LLM session.run 返回结构化阈值校准 / §6.4 SSE events / §6.5 schema dump 9 properties + 5 $defs) + Phase 4(§7.1 401 EaaspEcosystemAuthError / §7.2 403 EaaspEcosystemACLDenied / §7.3 404 EaaspEcosystemPromotionError 全 PASS);修复 CLI session.run 漏 X-Session-Scope + L5 ecosystem Pydantic 2.13 ForwardRef 模块化(_marketplace_models.py)+ Body() 注解;MANUAL.md v2 写完反映真实可执行命令 + EAASP_ECOSYSTEM_DEFAULT_TENANT 双模式(§7.2 vs §7.3);服务栈 teardown(0 process);[51cdca76]。
- Session handoff 收口:`1f70d3a3` 后确认状态 — HEAD ahead origin/main 3,工作树 clean(untracked jcode/ 是 IDE 外部目录),服务栈 0 process,ports clean;`.grid/verify-2026-07-30/` 含 MANUAL.md v2 + evidence-phase-1-2.md + evidence-phase-3-4.md + 完整 logs;下一 session 读 MANUAL.md v2 即可按部就班跑;v3.15 scope 仍未选(5 候选在 RESUME-NEXT-SESSION.md §下一候选)。[1f70d3a3]。

## 2026-08-01
- `/goal` "用 .env 跑通 EAASP 仿真环境 + 诊断修复所有平台流程节点上的 bug + 出技术框架文档" 闭环,4 个 sub-goal 全 met。
- eaasp-ecosystem unit test 修复 (从 v3.14 verification 留下的 failing test):`SubmitSkillRequest` 加 `ConfigDict(extra="forbid")` 防 round-2 spoofed `author_principal` 被 Pydantic v2 default `extra="ignore"` 静默吞掉(返回 200 OK 写 server-derived principal,违反 fail-closed 契约)+ `test_round2_spoofed_author_principal_rejected_at_api_layer` 补 `skill_registry_url=REGISTRY_URL` 进 `EcosystemConfig`(FastAPI 内部 `SkillMarketplace` 默认 `http://127.0.0.1:18081` 绕过了 respx mock);75/75 tests PASS [50f8459e + c3e82c7a]。
- eaasp-l2-memory 2 个 server-side bug fix:`MemoryFileIn.evidence_refs` 加 `field_validator(mode="before")` 把 JSON `null` coerce 为 `[]`(否则 Pydantic ValidationError → uncaught → HTTP 500);`_memory_write_file` 包 try/except `ValidationError` → `ToolError("invalid_arg", ...)` 走 422 invalid_arg contract(其他 dispatcher 都已遵循这个 pattern)。Runtime 的 `memory_write_hook` PostToolUse hook 之前每次工具执行都打 "Internal Server Error" warning [a0d846f0]。
- End-to-end 验证 deepseek-v4-pro:.env 切到 `LLM_PROVIDER=deepseek DEEPSEEK_MODEL_NAME=deepseek-v4-pro` (上一 session `inclusionai/ling-3.0-flash:free` 经 OpenRouter 路由到 Novita,probe 通过但真 call 400)。deepseek probe 收 400("Thinking mode does not support this tool_choice")→ `tool_choice=Unsupported` → D87 gate 关;session.run 端到端 19 events / 2236 chars 无 fatal error;`memory_write_hook` 修后无 500 warning;Stop hook `require_anchor` 正确返回 `continue`(LLM 没 write anchor)。注:`dotenvy::dotenv()` 不覆盖现有 shell env vars,所以每次启动用 `env -i HOME=... PATH=... LLM_PROVIDER=...` 显式传 .env 值(MEMORY.md known pitfall)。
- 技术框架文档:`docs/design/EAASP/EAASP_TYPICAL_APP_FRAMEWORK_DATA_FLOW.md` 创建(Skill/Session/Runtime Adapter 三层 + L0-L4 + L5 框架 + 数据流转总图 + 控制流时序 + 数据契约关键点 + 失败恢复策略 + 当前已知平台层 bug 表 + 运维速查);254 insertions [7266557a]。
- Handoff 收口:`docs/status/RESUME-NEXT-SESSION.md` 头部更新(HEAD `7266557a` synced)+ 追加 Session 2026-08-01 段(4 commits 列表 / e2e 验证结果 / 已知 outstanding limitations / next session first 3 actions)。服务栈 teardown(0 process, ports clean)。working tree clean(untracked `jcode/` predates this session)。[this entry]

## 2026-08-01 (OBSTACK 重构 — 1/5)
- 19:35 OBSTACK-1 commit: `git mv` PLATFORM_OBSERVABILITY_DESIGN.md → OBSTACK_DESIGN.md,12 处字符串引用同步替换(8 Python 文件 + 2 status doc);rename detection 100%,`grep PLATFORM_OBSERVABILITY_DESIGN` 0 残留,`grep OBSTACK_DESIGN` 13 hits(1 file + 12 refs);12 files / 13 ins 13 del;不动 §1–§8 内容也不动代码 logic,纯 rename + propagation,为 OBSTACK-2/3/4/5 提供稳定基线[af0f21f6]。

## 2026-08-01 (OBSTACK 重构 — 2/5)
- 19:51 OBSTACK-2 commit: OBSTACK_DESIGN.md 追加 3 章 —— §0 Goal 实现 Status(4 维度 × 子项状态表 + 闭环判据 + v3.15.5 close gate 6 件事)、§4.4 Component Inventory(file-level 视角)、§9 Changelog(文档自身修订记录);1 file / +123 lines;不动 §1–§8 / §5 编号完整保留(grep heading 验证连续),不动 code/tests;权威文档从此自带"实现状态"维度,不必重读 git log + task list 就能查 OBSTACK 进度[b5a1246a]。
