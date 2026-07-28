# EAASP 仿真环境使用指南

> **版本**：v3.14.0（EAASP v2.0 8-Phase 路线全 SHIPPED）
> **本指南适用**：`uukuguy/grid` 仓库 master 分支，HEAD ≥ `982be1e7`
> **权威规范**：`docs/design/EAASP/EAASP-Design-Specification-v2.0.docx`
> **代码定位**：`tools/eaasp-*/`（同仓共生的"模拟器"级参考实现）

---

## 1. 什么是 EAASP 仿真环境

EAASP v2.0 是一个 5 层 + 3 管道 + 4 元范式的企业级 Agent 平台规范。本仓 **`tools/eaasp-*/`** 是 EAASP 平台完整实现前、按平台契约做的**模拟器级参考实现**。它**不**是上游 EAASP 独立项目（按 2026-07-17 docs sync 修正），也不需要外部 EAASP 服务。

仿真环境能在**本机**完整跑通：

- L2 Memory（Evidence Anchor + File-based Memory + Hybrid Retrieval）
- L3 Governance（Policy DSL + Risk Classification + 5-Stage Approval + **production OPA sidecar**）
- L4 Orchestration（Session Lifecycle + SSE Streaming + **Event Room + A2A Router + ReviewSet + 冲突检测**）
- L5 Cowork（**4 卡视图 Event / Evidence / Action / Approval + Retrospective Cycle**）
- Ecosystem（**Ontology 服务 + Skill Marketplace + SDK**）
- Skill Registry + MCP Orchestrator + Certifier
- 7 个 L1 Runtime（grid-runtime + 6 comparison runtimes）

---

## 2. 30 秒快速开始

### 2.1 先决条件

- macOS / Linux
- Rust 1.75+ toolchain
- Python 3.12+ 与 `uv`
- `curl` + `git`
- `.env` 中已配置 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`

### 2.2 一键启动

```bash
# 1. 安装 OPA sidecar（v3.11.0 引入；本地下载官方 release binary，SHA256 校验）
make opa-install

# 2. 启动 EAASP 仿真服务栈（L2 memory + L3 governance + L4 orchestration +
#    L5 cowork + L5 ecosystem + skill-registry + mcp-orchestrator + mock-scada）
#    日志写入 .logs/latest/，PID 在 .logs/latest/pids/
make dev-eaasp

# 3. 在另一个 terminal 跑一个真实 skill
eaasp-cli skill submit skill://threshold-calibration && \
eaasp-cli skill promote threshold-calibration draft && \
eaasp-cli session create --skill threshold-calibration --runtime grid-runtime && \
eaasp-cli session send "校准 Transformer-001 的温度阈值"

# 4. 订阅事件流（包括 5 阶段审批 + A2A 评审 + Cowork 4 卡 + Ecosystem 通知）
eaasp-cli session events --follow <session_id>

# 5. 关闭
make dev-eaasp-stop
```

---

## 3. 工具链组件清单

| Layer | 路径 | 语言 | 职责 |
|---|---|---|---|
| **L0 Protocol** | `proto/eaasp/runtime/v2/` | proto3 | 21 RPC 方法（17 runtime + 4 hook） |
| **L1 Runtime（7 适配器）** | `crates/grid-runtime/`, `lang/{claude-code,nanobot,pydantic-ai,hermes}-runtime-python/`, `crates/eaasp-{goose,claw-code}-runtime/`, `lang/ccb-runtime-ts/` | 多种 | 7 个 T0-T3 runtime 实现同一 contract |
| **L2 Memory Engine** | `tools/eaasp-l2-memory-engine/` | Python | FTS5 + HNSW + time-decay hybrid，7 MCP tools（search/read/write_file/write_anchor/confirm/list/delete） |
| **L2 Skill Registry** | `tools/eaasp-skill-registry/` | Rust | Skill manifest 存储 + 4 阶段 promotion pipeline + MCP tool bridge |
| **L2 MCP Orchestrator** | `tools/eaasp-mcp-orchestrator/` | Rust | MCP server lifecycle across sessions |
| **L3 Governance** | `tools/eaasp-l3-governance/` | Python | Policy DSL + Risk Classification + **OPA sidecar adapter** + **5-Stage Approval State Machine** + append-only decision ledger |
| **L3 Certifier** | `tools/eaasp-certifier/` | Rust | Contract certification harness + `spec-audit` (v3.10 spec-alignment) |
| **L4 Orchestration** | `tools/eaasp-l4-orchestration/` | Python | Session lifecycle + SSE streaming + **Event Room** + **A2A Router** + **ReviewSet aggregation** + **conflict detection** |
| **L5 Cowork** | `tools/eaasp-l5-cowork/` | Python | **4 Card（Event/Evidence/Action/Approval）** + state machine + **Retrospective Cycle** |
| **L5 Ecosystem** | `tools/eaasp-ecosystem/` | Python | **Ontology 服务** + **Skill Marketplace API**（4 阶段 promotion + ACL + analytics）+ **SDK** |
| **L5 CLI** | `tools/eaasp-cli-v2/` | Python | End-user CLI：`eaasp session run -s <skill> -r <runtime> "<prompt>"` |
| **External Example** | `tools/mock-scada/` | Python | 示例外部系统（scada_read_snapshot / scada_set_setpoint） |
| **OPA Sidecar** | `third_party/opac/opa`（gitignored） | Go binary | 生产 OPA 决策后端（v3.11.0+） |

---

## 4. 完整启动流程

### 4.1 一键启动（推荐）

```bash
make dev-eaasp
```

后台启动所有服务，日志写入 `.logs/latest/`，PID 在 `.logs/latest/pids/`。

### 4.2 手动逐步启动（排查用）

按依赖顺序：

```bash
# 1. OPA sidecar
make opa-install                                  # 仅首次
third_party/opac/opa run -s &                    # 默认 :18181

# 2. L2 Memory Engine
cd tools/eaasp-l2-memory-engine && \
  uv run uvicorn eaasp_l2_memory_engine.main:app --port 18091 &

# 3. Skill Registry (Rust)
cd tools/eaasp-skill-registry && cargo run --bin eaasp-skill-registry -- --port 18081 &

# 4. MCP Orchestrator (Rust)
cd tools/eaasp-mcp-orchestrator && cargo run --bin eaasp-mcp-orchestrator -- --port 18082 &

# 5. L3 Governance
cd tools/eaasp-l3-governance && \
  L3_OPA_URL=http://127.0.0.1:18181 \
  L3_L2_DB_PATH=./data/l2.db \
  uv run uvicorn eaasp_l3_governance.api:app --port 18083 &

# 6. L4 Orchestration
cd tools/eaasp-l4-orchestration && \
  L4_L2_URL=http://127.0.0.1:18091 \
  L4_L3_URL=http://127.0.0.1:18083 \
  L4_SKILL_REGISTRY_URL=http://127.0.0.1:18081 \
  uv run uvicorn eaasp_l4_orchestration.api:app --port 18084 &

# 7. L5 Cowork
cd tools/eaasp-l5-cowork && \
  L5_L2_URL=http://127.0.0.1:18091 \
  L5_L3_URL=http://127.0.0.1:18083 \
  L5_L4_URL=http://127.0.0.1:18084 \
  uv run uvicorn eaasp_l5_cowork.main:app --port 18086 &

# 8. L5 Ecosystem
cd tools/eaasp-ecosystem && \
  ECOSYSTEM_L2_DB_PATH=./data/l2.db \
  ECOSYSTEM_L3_DB_PATH=./data/l3.db \
  ECOSYSTEM_L4_DB_PATH=./data/l4.db \
  uv run uvicorn eaasp_ecosystem.main:app --port 18090 &

# 9. Mock-SCADA
cd tools/mock-scada && uv run python main.py --port 18085 &

# 10. CLI
cd tools/eaasp-cli-v2 && \
  EAASP_L4_URL=http://127.0.0.1:18084 \
  EAASP_SKILL_REGISTRY_URL=http://127.0.0.1:18081 \
  uv run eaasp --help
```

### 4.3 健康检查

```bash
# 整体
make v3.10-spec-audit           # v3.10 spec alignment (4 files / 37 rows)
make rbac-audit                  # v3.9 grid-server 134 routes

# 各服务
curl -fsS http://127.0.0.1:18181/health          # OPA
curl -fsS http://127.0.0.1:18091/health          # L2 memory
curl -fsS http://127.0.0.1:18083/health          # L3 governance
curl -fsS http://127.0.0.1:18084/health          # L4 orchestration
curl -fsS http://127.0.0.1:18086/health          # L5 cowork
curl -fsS http://127.0.0.1:18090/health          # L5 ecosystem
curl -fsS http://127.0.0.1:18081/health          # Skill registry
curl -fsS http://127.0.0.1:18082/health          # MCP orchestrator
curl -fsS http://127.0.0.1:18085/health          # Mock-SCADA
```

---

## 5. CLI 速查

```bash
eaasp skill submit <path>              # 提交 skill YAML（自动 parse frontmatter）
eaasp skill promote <name> <stage>     # draft→tested→reviewed→production
eaasp skill list
eaasp skill show <name>

eaasp policy deploy <path.json>        # 部署 managed-settings / hooks
eaasp policy mode <hook_id> <shadow|enforce>

eaasp session create --skill <name> --runtime <name>
eaasp session send <message>           # 向 session 发消息
eaasp session show <id>                # 4 卡（Event/Evidence/Action/Approval）状态
eaasp session events <id>              # 列出所有事件
eaasp session events --follow <id>     # 实时订阅 SSE
eaasp session close <id>

eaasp memory search "transformer 阈值"   # 跨 session 语义检索
eaasp memory read <anchor_id>
eaasp memory list

eaasp cowork cards <session_id>        # 取 4 卡视图
eaasp cowork trace <session_id>        # 取回溯闭环链

eaasp ontology tree [--domain <name>]
eaasp ontology links <node_id>
eaasp marketplace submit <skill_path>
eaasp marketplace promote <name> <stage>
eaasp marketplace analytics <name>

eaasp run -s <skill> -r <runtime> "<prompt>"   # 一键创建 + 发送 + 跟踪
```

---

## 6. 真实场景演示

### 6.1 阈值校准助手（threshold-calibration）

跨 session memory + 5 阶段治理 + A2A 多 reviewer 评审 + Cowork 4 卡的完整演示。

```bash
# 准备 skill
eaasp skill submit skill://threshold-calibration
eaasp skill promote threshold-calibration draft
eaasp skill promote threshold-calibration tested
eaasp skill promote threshold-calibration reviewed   # 触发 A2A multi-reviewer review
eaasp skill promote threshold-calibration production # 触发 5-stage approval

# 启动 reviewer sessions（共享同一个 Event Room）
eaasp session create --skill threshold-calibration --runtime grid-runtime &
eaasp session create --skill threshold-calibration --runtime grid-runtime &

# 启动 initiator session
eaasp session create --skill threshold-calibration --runtime grid-runtime

# 触发高风险 action
eaasp session send "校准 Transformer-001 的温度阈值" --session-id <initiator_id>

# 订阅全部 SSE 事件：5 governance.approval.* + 5 a2a.* + 5 cowork.*
eaasp session events --follow <initiator_id>
```

### 6.2 多 agent 评审与冲突检测

```bash
# A2A review with conflict
# reviewer A: allow
# reviewer B: needs_revision
# reviewer C: deny
# → aggregation engine 检测 conflict，emit a2a.conflict.detected SSE
# → 5-stage approval pause at DECISION_AWAIT_HUMAN
# → 人工决策 → resume
# → event room shared event
```

### 6.3 第三方 publisher 通过 SDK 提交 skill

```python
from eaasp_ecosystem_sdk import EcosystemSDK

sdk = EcosystemSDK(base_url="http://127.0.0.1:18090", api_key="...")

# 1. submit draft
draft = sdk.submit_skill(
    name="my-publisher-skill",
    path="examples/third_party_skill_publisher.py",
)

# 2. promote tested → reviewed
sdk.promote_skill(name="my-publisher-skill", stage="tested")
sdk.promote_skill(name="my-publisher-skill", stage="reviewed")  # 触发 A2A review
# 等待 3 reviewers decision...
sdk.promote_skill(name="my-publisher-skill", stage="production")  # 触发 5-stage approval
```

---

## 7. SSE 事件参考

| 事件源 | 事件名 | 触发时机 |
|---|---|---|
| L4 | `session.created` | session 创建 |
| L4 | `session.event` | session 内部事件 |
| L3 | `governance.request` | risk classification 决策请求 |
| L3 | `governance.decision` | final decision 输出 |
| L3 | `governance.approval.plan` | 5-stage state machine: Plan 阶段 |
| L3 | `governance.approval.check` | 5-stage state machine: Check 阶段 |
| L3 | `governance.approval.draft` | 5-stage state machine: Draft 阶段 |
| L3 | `governance.approval.approve` | 5-stage state machine: Approve 阶段（human-in-the-loop） |
| L3 | `governance.approval.execute` | 5-stage state machine: Execute 阶段 |
| L4 | `a2a.request.sent` | A2A Router 发出 message |
| L4 | `a2a.request.acknowledged` | target session 确认收到 |
| L4 | `a2a.review.submitted` | ReviewSet 收到 reviewer decision |
| L4 | `a2a.review.closed` | ReviewSet aggregation 完成 |
| L4 | `a2a.conflict.detected` | ReviewSet aggregation 检测到 contradict decisions |
| L5 | `cowork.card.created` | 4 卡视图新 card 产生 |
| L5 | `cowork.card.updated` | 4 卡 card 状态变化 |
| L5 | `cowork.card.closed` | 4 卡 card 关闭 |
| L5 | `cowork.workflow.advanced` | workflow 状态推进 |
| L5 | `cowork.workflow.escalated` | workflow 升级 |
| L5 | `ecosystem.*` | Ontology / Marketplace 事件 |
| L5 | `retrospective.trace` | 回溯闭环 trace 完成 |

总计 **20+ SSE 事件类型**，覆盖从 L0 contract 到 L5 Cowork 全部 5 层 + 3 管道 + 4 元范式。

---

## 8. OPA Sidecar 策略

### 8.1 启动与停止

```bash
make opa-install     # 下载官方 release 到 third_party/opac/opa，SHA256 校验
make opa-clean       # 清理
third_party/opac/opa version
```

### 8.2 失败模式（fail-closed）

OPA 不可达 / timeout / 2xx 非 200 / parse-error / 缺字段 → 一律：

- 返回 `deny`
- emit audit row with `infra_unavailable=true` + 失败原因
- 不阻塞治理调用

`L3_OPA_URL` 启动时强制 explicit（per ADR-V2-028 strict-by-default），缺省 fail。

### 8.3 自定义 Rego 策略

```bash
# 编辑
vi tools/eaasp-l3-governance/policies/governance.rego

# bundle 推到 in-repo + atomic user bundle
# L3 启动时 reload
kill -HUP $(cat .logs/latest/pids/l3)
```

---

## 9. 多租户与 RBAC

- **L3 governance_decisions** 表带 `tenant_id` 列 + idempotent migration
- **Event Room** + **A2A Router** + **Cowork** + **Ecosystem** 全部跨租户隔离
- **v3.9 grid-server** 134 routes RBAC catalog（Owner-only 边界）继续生效
- 所有 v3.9-v3.14 hard 约束**保持**：v3.10 spec-audit + v3.9 rbac-audit + shared-core rule + ADR-V2-023 P1 + ADR-V2-028 strict-by-default

---

## 10. 数据持久化与重置

每个工具默认在 `data/` 子目录放 SQLite。完全重置：

```bash
make dev-eaasp-stop
rm -rf tools/eaasp-*/data/*.db tools/eaasp-*/data/*.db-shm tools/eaasp-*/data/*.db-wal
make dev-eaasp
```

单服务重置：

```bash
make dev-eaasp-stop
rm tools/eaasp-l3-governance/data/l3.db*
make dev-eaasp
```

---

## 11. 故障排查

| 症状 | 原因 | 修复 |
|---|---|---|
| `make opa-install` 失败 | 网络受限 | 设置 `OPA_VERSION` env 走已下载 binary |
| OPA 决策 deny 所有请求 | OPA URL 不通 | `curl -fsS $L3_OPA_URL/health` |
| L3 启动 fail | 缺 env var | 设置 `L3_OPA_URL` / `L3_L2_DB_PATH` |
| skill registry 端口冲突 | 旧 PID 未释放 | `lsof -i :18081` → kill |
| SSE 不更新 | 客户端没带 `Last-Event-ID` | 重新 `--follow` |
| Decision 在 5-stage 暂停 | 正常：DECISION_AWAIT_HUMAN | reviewer 通过 SSE 或 `eaasp session send` 推进 |
| Retrospective trace 不返回数据 | session_id 不在 Event Room | 确认 session 加入 room |
| A2A review 一直 open | reviewer 未提交 decision | 检查 reviewer session 是否 alive |

---

## 12. 与 EAASP 真实企业部署的关系

本仿真环境**不是** EAASP 生产平台。**生产部署**要做：

| 仿真环境组件 | 生产对应 | 替换/升级 |
|---|---|---|
| SQLite | Postgres | 已有 `tokio-rusqlite` 抽象层可换 |
| OPA sidecar | Shared OPA cluster | ADR-V2-005 + ADR-V2-034 |
| in-process Python services | 独立微服务 + k8s | 已有 gRPC `proto/eaasp/runtime/v2/` |
| skill-registry local FS | S3 / Git-backed registry | 现有 `eaasp-skill-registry` 已支持 |
| mock-scada | 真实 SCADA / OPC-UA gateway | `--port 18085` 替换为实际工厂集成 |

**仿真环境足以验证**：L1 contract 7-runtime portability、L2 evidence anchor + memory layer、L3 governance gate 完整闭环、L4 SSE streaming + Event Room + A2A 协议、L5 Cowork 4 卡 + retrospective。

**仿真环境不能验证**：高并发（>100 session）、生产 OPA 集群高可用、真实 LLM latency 端到端合规、第三方 marketplace 商业化。

---

## 13. 关键 reference

| 文件 | 用途 |
|---|---|
| `docs/design/EAASP/EAASP-Design-Specification-v2.0.docx` | **规范权威**（4373KB docx；导出 markdown 在 `/tmp/eaasp_v2_spec.md` 2944 行） |
| `docs/design/EAASP/EAASP_v2_0_EVOLUTION_PATH.md` | 8-Phase 演化决策（现全部 SHIPPED） |
| `docs/design/EAASP/L1_RUNTIME_ADAPTATION_GUIDE.md` | 如何新增 L1 runtime adapter |
| `docs/design/EAASP/E2E_VERIFICATION_GUIDE.md` | E2E 测试 living spec |
| `docs/design/EAASP/DEFERRED_LEDGER.md` | 跨 phase D-item SSOT（8 项 V310-* 全部 ✅ CLOSED） |
| `docs/design/EAASP/adrs/ADR-V2-024-...md` | 双轴战略（engine vs data/integration） |
| `docs/design/EAASP/adrs/ADR-V2-029-...md` | 双轴 crate-level 边界 |
| `docs/design/EAASP/adrs/ADR-V2-034-...md` | OPA sidecar topology Accepted |
| `docs/design/EAASP/adrs/ADR-V2-035-...md` | A2A Router conflict detection Accepted |
| `docs/PROJECT_PRODUCT_OVERVIEW.md` | 项目级 single source of truth |
| `docs/status/PRODUCTION_USABILITY_2026-07-{27,28,29}.md` | v3.11 / v3.12 / v3.13 live walkthrough dated evidence |
| `docs/status/PRODUCTION_USABILITY_2026-07-30.md` | v3.14 live walkthrough dated evidence |
| `docs/cli/USER_GUIDE.md` | grid-server / grid-cli 用户手册 |
| `.planning/STATE.md` | 当前 milestone 状态（v3.14 SHIPPED） |

---

## 14. 下一步（roadmap）

EVOLUTION_PATH 8-Phase 路线已**全 SHIPPED**。下一候选（与 EAASP 仿真环境无关）：

- **web-platform** 7.5→9.0（前端 dashboard）
- **grid-desktop** 6.5→9.0（桌面端）
- **grid-platform** route catalog audit
- 把 `v3.10-v3.14` 共 80+ commits 推送（已推送 4 个 v3.14 commit 到 origin/main）

---

**Happy hacking！** 如发现 bug，请按 `docs/design/EAASP/DEFERRED_LEDGER.md` 格式登记 D-item。
