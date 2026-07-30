# EAASP 仿真环境验证计划 — 2026-07-30

> **范围**: Live full-stack 验证(`make dev-eaasp` + L5/OPA 手动补齐 + 真 skill + 真 LLM key)。
> **预置 keys**: `OPENAI_API_KEY` + `ANTHROPIC_API_KEY` 均可用。
> **起点**: v3.14.3 SHIPPED 状态(2026-07-30),工作树 clean,HEAD `4bdfc9fb`,tag `v3.14` pushed。

---

## 0. 验证模式分水岭

| 模式 | service 启动 | LLM key | 时长 | CI 适用 |
|---|---|---|---|---|
| **Hermetic**(v3.14.3 walkthrough 模板) | ❌ 全部 in-process ASGITransport | ❌ | 15-30 min | ✅ |
| **Live Subset** | ✅ L2/L3/L4/L5 + OPA | ❌ | 30-50 min | ⚠️ |
| **Live Full**(本次采用) | ✅ 全部 + 真 skill + 真 LLM | ✅ OPENAI + ANTHROPIC | 40-90 min | ❌ 单机 |

⚠️ **关键发现**: `scripts/dev-eaasp.sh` **不启动** L5 Cowork / L5 Ecosystem / OPA sidecar — 这些是 `EAASP_SIMULATION_USER_GUIDE.md` §4.2 的手动步骤。需要手工补齐。

---

## 1. 前置条件(用户必须先确认)

```bash
cd /Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox

git status -sb                    # 必须 clean;ahead origin/main 2 (refresh + journal)
git log --oneline -3              # HEAD = 4bdfc9fb

rustc --version                  # ≥ 1.75
python3 --version                # ≥ 3.12
uv --version                     # ≥ 0.4

grep -E "^(OPENAI_API_KEY|ANTHROPIC_API_KEY)=" .env   # 都不能为空

ls third_party/opac/opa          # 如果不存在,要 make opa-install

lsof -i :18081 -i :18082 -i :18083 -i :18084 -i :18085 -i :18086 -i :18090 \
     -i :18181 -i :50051 -i :50052 -i :50054 -i :50063 2>/dev/null | head
```

**失败标志**: 任一前置条件不满足 → 不进入 Phase 2。

---

## 2. 依赖图(必须按顺序启动)

```
OPA sidecar :18181           ──┐
                                ├──→  L3 Governance  :18083
skill-registry :18081  ────────┤
L2 memory :18085      ────────┤
                                │
                                ├──→  L4 Orchestration :18084
                                │         │
                                │         ├──→ A2A Router + Event Room
                                │         │
MCP Orchestrator :18082 ───────┤         ├──→ L5 Cowork :18086
                                │         │         │
                                │         │         └──→ L5 Ecosystem :18090
                                │         │
                                └──→ grid-runtime :50051 (gRPC)
                                      claude-code-runtime :50052
                                      nanobot-runtime :50054
                                      goose-runtime :50063 (Docker)

L5 Ecosystem 是 v3.14.0 新增, dev-eaasp.sh 没启, 需手动启。
```

---

## 3. 验证场景(按层递进,每场景独立 PASS/FAIL)

### Phase 1: 服务启停 + 健康检查(无 LLM 调用,~10 min)

| # | 场景 | 命令 | 期望 |
|---|---|---|---|
| 1.1 | OPA sidecar alive | `make opa-install && third_party/opac/opa run -s &` 然后 `curl -fsS http://127.0.0.1:18181/health` | 200 OK,OPA version ≥ 0.68.0 |
| 1.2 | `make dev-eaasp` 启 L1-L4 | 后台运行 → 检查所有端口 200 | 9 个核心端口全部 PASS |
| 1.3 | L5 Cowork 手动启 | `cd tools/eaasp-l5-cowork && uv run uvicorn eaasp_l5_cowork.main:app --port 18086 &` 然后 `curl -fsS :18086/health` | 200 OK |
| 1.4 | L5 Ecosystem 手动启 | `cd tools/eaasp-ecosystem && uv run uvicorn eaasp_ecosystem.main:app --port 18090 &` 然后 `curl -fsS :18090/health` | 200 OK |
| 1.5 | L1 runtime gRPC alive | `grpcurl -plaintext 127.0.0.1:50051 list` (如可用) | 列出 `eaasp.runtime.v2.Runtime` 等服务 |
| 1.6 | 日志可读 | `ls .logs/latest/`,每 service 一个文件,error 计数 == 0 | 0 error in L1-L5 logs |

**关闭顺序**(测试结束后必须执行,否则端口泄漏):

```bash
# 1. 停 L5 Ecosystem + L5 Cowork (手动启的)
pkill -f "uvicorn eaasp_l5_cowork" || true
pkill -f "uvicorn eaasp_ecosystem" || true

# 2. 停 make dev-eaasp (Ctrl+C on the foreground terminal, or kill the PID group)
pkill -f "scripts/dev-eaasp.sh" || true

# 3. 停 OPA
pkill -f "third_party/opac/opa" || true

# 4. sweep orphan ports
for port in 18081 18082 18083 18084 18085 18086 18090 18181 50051 50052 50054 50063; do
  lsof -ti :$port | xargs -r kill -9 2>/dev/null || true
done
```

### Phase 2: Static / Audit 门禁(~5 min)

| # | 场景 | 命令 | 期望 |
|---|---|---|---|
| 2.1 | v3.9 RBAC 134 routes | `make rbac-audit` | PASS / 134 routes |
| 2.2 | v3.10 spec-audit | `make v3.10-spec-audit` | PASS / 4 files / 38 rows |
| 2.3 | v3.7 EAASP 测试集 | `cd tools/eaasp-ecosystem && python -m pytest -v` | **75 PASS** |
| 2.4 | v3.14 SDK 测试 | `cd sdk/python && python -m pytest tests/test_ecosystem_client.py tests/test_cli.py::TestEcosystemCmd -v` | **23 PASS** (17 client + 6 CLI) |

### Phase 3: 真 skill + LLM 端到端(~30 min,**需 LLM key**)

| # | 场景 | 命令 | 期望 |
|---|---|---|---|
| 3.1 | 准备 threshold-calibration skill | `eaasp-cli skill submit skill://threshold-calibration && eaasp-cli skill promote threshold-calibration draft` | 200 + 201 |
| 3.2 | 4 阶段 promote 到 reviewed | `eaasp-cli skill promote threshold-calibration tested → reviewed` | 触发 A2A multi-reviewer (3 reviewers) |
| 3.3 | promote 到 production (5-stage approval) | `eaasp-cli skill promote threshold-calibration production` | 进入 `await_human` paused state(L3 OPA 5-stage state machine) |
| 3.4 | 创建 initiator session | `eaasp-cli session create --skill threshold-calibration --runtime grid-runtime` | 200, session_id |
| 3.5 | 创建 2 reviewer sessions | 同上 × 2 | 200 × 2 |
| 3.6 | 触发高风险 action | `eaasp-cli session send "校准 Transformer-001 的温度阈值" --session-id <id>` | LLM 调用真实完成;非 500 |
| 3.7 | 订阅 SSE | `eaasp-cli session events --follow <id>` | 看到 `governance.approval.*` (5 events) + `a2a.*` (5 events) + `cowork.*` (5 events) + `ecosystem.*` (1+) = **16+ SSE events** |
| 3.8 | Cowork 4 卡 | `eaasp-cli cowork cards <session_id>` | EventCard / EvidenceCard / ActionCard / ApprovalCard 都 ≥ 1 row |
| 3.9 | Retrospective trace | `eaasp-cli cowork trace <session_id>` | 完整 trace 链 |
| 3.10 | Ontology 投影 | `eaasp-cli ontology tree` | **≥ 11 nodes across 4 layers** (per ECOSYSTEM-LIFECYCLE-01) |
| 3.11 | Marketplace analytics | `eaasp-cli marketplace analytics threshold-calibration` | 200 + stats payload |

### Phase 4: 跨 SDK 验证(~10 min)

| # | 场景 | 命令 | 期望 |
|---|---|---|---|
| 4.1 | Python SDK 同等流程 | `python -c "from eaasp_sdk import EcosystemSDK; sdk = EcosystemSDK(...); sdk.submit_skill(...)"` | 201, 与 CLI 等价 |
| 4.2 | Bearer auth | 故意用错 key | 401 + `EaaspEcosystemAuthError` |
| 4.3 | 跨 tenant 拒绝 | 错 tenant_id 调 marketplace | 403 + `EaaspEcosystemTenantForbidden` |
| 4.4 | 缺 skill | `marketplace/promote` 一个不存在的 skill | 404 + `EaaspEcosystemPromotionError` |

---

## 4. 不在范围(本次明确跳过)

- ❌ **Full `cargo test --workspace`** — per `feedback_no_full_tests`,跑 v3.8-v3.13 全栈 = 数小时;只在修代码后跑,且 ASK first
- ❌ **wasm-hook-plugin / Docker sandbox path** — v3.7.3 已 covered,本次不重测
- ❌ **市场推广 / 支付 / billing** — D-46 明确 out of v3.14
- ❌ **TS / Go / Java SDK** — v3.14 仅 Python SDK (D-42)
- ❌ **回写任何 .md / .yaml / 配置文件** — 本次纯验证,不改东西

---

## 5. 反馈格式(用户执行后给)

每完成一个 Phase,粘给 Claude:

```text
=== Phase N.X: <scenario name> ===
状态: PASS / FAIL / PARTIAL
命令: <full command run>
输出尾部: <last 10 lines of stdout/stderr>
端口残留: lsof -i :18081..18090,18181,5005x,50063 (any leftover?)
日志路径: .logs/latest/<service>.log:NN (any error lines?)
```

**失败标志**(任一发生立即停止后续 Phase,先排查):

- 任何 service 启动后 `health` 端点非 200
- 任何 LLM 调用 5xx 或 timeout > 60s
- 任何 SSE 事件缺失(16+ 预期, < 12 视为缺事件)
- Phase 2 任一审计 gate FAIL
- 端口残留(Phase 1.1 关闭后,30s 内 `lsof` 还有进程)

---

## 6. 风险 + 预案

| 风险 | 概率 | 预案 |
|---|---|---|
| OPA 缺失 | 中 | Phase 1.1 自动 `make opa-install`(需联网) |
| LLM key 实际无效 | 低 | 用户已确认两个 key 都有;若实测 401,切到 hermetic 模式 |
| 端口冲突 | 低 | `lsof` 前置检查;如冲突改 `EAASP_*_PORT` env |
| `make dev-eaasp` 启动失败 | 中 | 看 `.logs/latest/dev-eaasp-*.log`,优先看 `skill-registry.log` |
| L5 Cowork/Ecosystem 没启 | 高(常见) | Phase 1.3 + 1.4 单独手动启;不要假设 `make dev-eaasp` 含它们 |
| 评审卡死(5-stage approval await_human) | 中 | 切到 `eaasp-cli policy mode <hook_id> shadow` 跳过人工门 |
| SSE 事件少于 16 个 | 中 | 先看 `.logs/latest/L4-orchestration.log` + L5 cowork 日志 |

---

## 7. 不在 plan 内的"自动跑"承诺

按 CLAUDE.md §3 Background Task Execution:

- **不**自动 `make dev-eaasp` 后台跑(必须用户确认)
- **不**自动 `cargo test --workspace`
- **不**自动 dispatch 任何后台进程
- 任何 step 需要 > 20 min,Claude 用 `Bash run_in_background` 但**先问**
- 每个 Phase 完成后**必须停下来等用户反馈**,不连续推

---

## 8. 验证证据回填位

每 Phase 完成后,在本文件下面对应表格里粘 PASS/FAIL + evidence URL / log path。例:

```markdown
### Phase 1 回填

| # | 状态 | 时间 | evidence |
|---|---|---|---|
| 1.1 | PASS | 2026-07-30 14:30 | `third_party/opac/opa version` → v0.68.0 |
| 1.2 | PASS | 2026-07-30 14:35 | `.logs/latest/skill-registry.log` clean |
```

---

## 9. 引用 + 关联

- `docs/EAASP_SIMULATION_USER_GUIDE.md` — 仿真环境官方使用指南(v3.14.0 加)
- `docs/status/PRODUCTION_USABILITY_2026-07-30.md` — v3.14.3 hermetic walkthrough(基线)
- `scripts/dev-eaasp.sh` — 服务栈启动脚本(只含 L1-L4,**不含** L5/OPA)
- `.planning/STATE.md` — v3.14 SHIPPED + 双 gate PASS(38 rows / 134 routes)
- `EAASP_v2_0_EVOLUTION_PATH.md` §三 8-Phase 路线 ALL SHIPPED(D-46)

---

*Plan 创建 2026-07-30 (UTC+8). 起点:v3.14.3 SHIPPED @ `4bdfc9fb`。*
