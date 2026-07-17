# Grid

[![Rust](https://img.shields.io/badge/Rust-1.75+-orange)](https://www.rust-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[English](README.md) | [中文文档](README.zh.md)

**企业级自主智能体运行时栈 —— 不是框架，不是封装，而是真正可部署的生产级执行层。**

Grid 是 LLM 提供商与你的业务逻辑之间的执行层。它处理 Agent 运行时的一切：上下文管理、多层记忆、工具执行、沙箱隔离、安全策略、审计留痕、定时调度、MCP 集成——全部内聚在单一 Rust 二进制中。没有 Python GIL，没有 500 MB 的 Docker 镜像，没有“我机器上跑得通”。

Grid 同时以两种形态交付：**可替换的 L1 运行时**（通过 gRPC 合同接入任意编排平台）和**完整的独立产品套件**（CLI、桌面应用、多租户平台、评测框架）。

---

## 为什么 Grid 不一样

### 1. 它是运行时，不是框架

市面上多数工具是 Python 框架，在 LLM API 上包一层 sugar。Grid 是执行引擎——它全流程掌控 Agent 的运行状态，每一步工具调用都经过安全策略校验，每一次决策都进入审计日志。你不是把 Grid 的 API 嵌进代码里；你是把 Grid 作为基础设施跑起来。

### 2. 可替换的 L1 运行时 —— 合同即标准

grid-runtime 实现了一套 16 方法的 gRPC 合同，任何合规运行时都可以接替。这一点已被验证：**6 个对比运行时**（Claude Code、Goose、Nanobot、Pydantic AI、Claw Code、CCB）独立通过同一套 `contract-v1.1.0` 测试套件。需要换 Agent 引擎？换实现，不动上层集成。运行时层不存在厂商绑定。

### 3. 企业安全 —— 不是 checklist，是默认执行模型

每次工具调用经过：**自主等级检查 → 风险分级 → 策略评估 → 沙箱路由 → 执行 → 审计记录**。沙箱支持 Docker 容器、WASM 隔离、原生 subprocess——不可信代码绝不触及宿主机。这不是可开关的 feature flag，这是唯一执行路径。

### 4. 记忆系统 —— 跨会话、跨年份

Grid 的记忆是四层架构：

| 层级 | 存储 | 检索 | 生命周期 |
|------|------|------|----------|
| **工作记忆** | 内存 | 直接访问 | 单次 Agent 轮次 |
| **会话记忆** | 内存 + 日志 | 会话内查询 | 单次会话 |
| **持久记忆** | SQLite FTS5 + HNSW 向量 | 全文 + 语义混合检索 | 跨会话 |
| **知识图谱** | 实体关系存储 | 图遍历 | 永久 |

持久记忆使用**时间衰减混合检索**：近期记忆权重提升，相关性由文本匹配、向量相似度和新鲜度加权计算。上下文窗口永远不会被无用信息撑爆。

### 5. 一个代码库，七个产品

| 组件 | 是什么 | 给谁用 |
|------|--------|--------|
| **grid-server** | HTTP/WS 工作台，~130 端点，HMAC + JWT | 单用户 Agent 工作台 |
| **grid-cli** | 16 命令 CLI，全 TUI，流式输出 | 终端用户的 Agent 界面 |
| **web/** | 8 标签 React SPA，实时 WS 流式，Markdown | Web 端 Agent 交互 |
| **grid-platform** | 多租户服务器，JWT 租户隔离，RBAC，配额 | SaaS/企业部署 |
| **web-platform/** | 多租户 React UI，会话/仪表盘/聊天/设置 | 平台管理员 |
| **grid-desktop** | Tauri 2 桌面应用，系统托盘，内嵌仪表盘 | 桌面用户 |
| **grid-eval** | 10 评分器，12 套件，4 基准（GAIA、SWE-bench、τ-bench） | 质量工程团队 |

所有组件共享同一个 `grid-engine` 核心。Engine 修一个 bug，七个产品全部受益。

---

## 架构

```
                    ┌──────────────────────────┐
                    │      编排层              │
                    │  (EAASP L2/L3/L4 — 本仓库 │
                    │   tools/eaasp-*,或接你的  │
                    │   编排平台)              │
                    └──────────┬───────────────┘
                               │ gRPC (16 方法, contract-v1.2.0)
                    ┌──────────▼───────────────┐
                    │      grid-runtime        │
                    │  (L1 合同适配器)         │
                    └──────────┬───────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
  ┌────▼─────┐          ┌──────▼──────┐         ┌──────▼──────┐
  │ Agent     │          │  上下文     │         │  定时调度   │
  │ 主循环    │          │  引擎       │         │  (Cron)     │
  └────┬─────┘          └──────┬──────┘         └──────┬──────┘
       │                       │                       │
  ┌────▼─────┐  ┌───────┐  ┌───▼────┐  ┌───────┐  ┌───▼────┐
  │ 记忆      │  │ MCP  │  │ 工具  │  │ 审计  │  │技能    │
  │ (四层)    │  │ 客户端│  │ 引擎  │  │ 日志  │  │注册表  │
  └────┬─────┘  └───┬───┘  └───┬────┘  └───┬───┘  └───┬────┘
       │            │          │           │           │
  ┌────▼────────────▼──────────▼───────────▼───────────▼────┐
  │                   安全策略引擎                          │
  │         自主等级 · 风险分级 · 路径白名单 · RBAC          │
  └─────────────────────────┬─────────────────────────────┘
                            │
  ┌─────────────────────────▼─────────────────────────────┐
  │                   沙箱路由器                           │
  │             Docker · WASM · 原生子进程                  │
  └───────────────────────────────────────────────────────┘
```

本仓库**一站式交付**——既包含 agent 运行时(Grid),也包含 EAASP 平台层(`tools/eaasp-*`)。生产部署可任选其一:

1. 直接从本仓跑完整 EAASP v2.0 全栈 — `make dev-eaasp` 启动 L2/L3/L4 + L1 runtime
2. 通过 16 方法 gRPC 合同把 `grid-runtime` 接入自有编排平台(可移植性已证明:6 个独立 runtime 通过同一 `contract-v1.1.0` 测试集)

每一次工具调用走完整流水线:**自主检查 → 风险分级 → 策略评估 → 沙箱路由 → 执行 → 审计记录**。纯流水线，不分叉，没有可跳过的”可选安全”。

---

## 产品状态

- Grid 独立产品 Activation 八个阶段（A.0–A.8）已于 2026-06-17 全部交付。
- EAASP 核心 L0/L1/L2/L3/L4 工程实现与运行时合同验证,均已在当前参考实现中完成。
- 仓库共包含 7 个 L1 运行时,其中包括 6 个对比运行时。
- `contract-v1.1.0` 是 Phase 3 历史签字版合同;`contract-v1.2.0` 是当前最新合同。
- `tools/eaasp-*` 是 EAASP v2.0 平台合同的模拟器级参考实现,不存在独立的"上游 EAASP"项目。
- 后续 EAASP 平台演进(Phase 3 生产级 OPA 审批链、Phase 4 A2A / Event Room、Phase 5 L5 Cowork UI、Phase 6 生态扩展)仍待推进。

更详细的产品情况,请参见 [`docs/PROJECT_PRODUCT_OVERVIEW.md`](docs/PROJECT_PRODUCT_OVERVIEW.md)。

---

## 快速开始

```bash
# 前置条件：Rust 1.75+, Node.js 18+, API key
git clone https://github.com/uukuguy/grid.git && cd grid
cp .env.example .env      # 填写 ANTHROPIC_API_KEY 或 OPENAI_API_KEY
make setup                # 安装前端依赖
make dev                  # 后端 :3001, 前端 :5180
```

或者纯 CLI 体验：

```bash
make cli                  # 构建 CLI
make cli-ask              # 单次提问："2+2 等于多少?"
make studio-tui           # 全 TUI 仪表盘
```

---

## 安全模型

每次工具调用经过 5 步：

1. **自主等级检查** — 该 Agent 是否允许自主执行此操作？
2. **风险分级** — 爆炸半径多大？（LOW / MEDIUM / HIGH / CRITICAL）
3. **策略评估** — 安全策略是否放行？（路径白名单、网络规则）
4. **沙箱路由** — 在何处执行？（Docker 容器 / WASM 虚拟机 / 原生进程）
5. **审计记录** — 发生了什么？（工具名、参数、结果、耗时、沙箱类型）

自主等级决定哪些操作需要人审批：
- **Autonomous**：全自动，无门槛
- **Semi-autonomous**：HIGH/CRITICAL 操作需审批
- **Supervised**：所有工具调用需审批

---

## 评测基础设施

`grid-eval` 是一流的评测框架，不是 ad-hoc 脚本堆砌：

```bash
# 运行工具调用准确性测试（23 任务，L1-L4 难度）
grid eval run --suite tool_call

# 运行安全策略测试（14 任务，S1-S4）
grid eval run --suite security

# 运行 GAIA 基准（165 任务，3 难度级别）
grid eval run --benchmark gaia

# 两次运行对比
grid eval compare --baseline baseline.json --candidate candidate.json

# 生成 Markdown 报告
grid eval report --input results/ --output report.md
```

10 种评分方法：ExactMatch、ToolCallMatch、BehaviorPattern、AST 结构化匹配、LLM-as-Judge、EventSequence（最长公共子序列）等。CI 管线内建回归检测。

---

## GitHub Actions CI

Grid 维护了 8 个 CI workflow：

- **eval-ci** — 单元测试 + 集成测试 + mock suite + GAIA/SWE-bench/τ-bench + 回归检测（定时 + PR 触发）
- **desktop-ci** — 桌面应用检查 + 测试（ubuntu/macos/windows 三平台）
- **phase3-contract** — 7 运行时合同矩阵自动化
- **container-build** — Docker 镜像构建
- **release** — 发布流程
- **adr-audit** — 架构决策审计

---

## 横向对比

| | Grid | LangChain | CrewAI | AutoGPT |
|---|---|---|---|---|
| **语言** | Rust | Python | Python | Python |
| **运行时模型** | 执行引擎 | 框架胶水 | 框架胶水 | Agent 循环 |
| **沙箱** | Docker + WASM + subprocess | 无内置 | 无内置 | 仅 Docker |
| **安全策略** | 逐 Agent 自主等级 + 风险分级 | 无 | 无 | 无 |
| **审计** | 每次工具调用、记忆访问、会话事件 | 可选回调 | 无 | 无 |
| **多租户** | JWT 隔离 + RBAC + 配额 | 否 | 否 | 否 |
| **记忆** | 四层 + 时间衰减混合检索 | Vector DB 封装 | 基础 | 基础 |
| **MCP** | 原生（stdio + SSE，热插拔） | 封装 | 封装 | 无 |
| **合同可移植性** | 16 方法 gRPC，6 对比运行时 | 无 | 无 | 无 |
| **桌面应用** | Tauri 2 原生 | 否 | 否 | 否 |
| **评测框架** | 10 评分器，12 套件，4 基准 | LangSmith (SaaS) | 无 | 无 |
| **部署** | 单二进制 (`grid`) | pip 安装 20+ 依赖 | pip 安装 | Docker compose |

Grid 不是“Rust 版的 LangChain”，它是完全不同的品类：生产环境中的自主 Agent 运行时平台，而非原型开发的库。

---

## 技术栈

| 层级 | 技术选型 | 理由 |
|------|----------|------|
| 运行时 | Rust + Tokio | 内存安全，零成本抽象，异步 I/O |
| HTTP/WS | Axum + Tower | 类型安全，可组合中间件，人体工学 |
| 数据库 | SQLite（rusqlite，WAL 模式） | 零配置，嵌入式，FTS5 全文检索 |
| 向量搜索 | HNSW（进程内） | 无外部服务依赖，比暴力检索快 150 倍 |
| MCP | rmcp | 原生 Rust MCP 实现，stdio + SSE |
| 沙箱 | Docker (Bollard)、WASM (Wasmtime)、subprocess | 纵深防御 |
| gRPC | tonic + prost | 合同优先，类型安全代码生成 |
| 前端 | React 19、TypeScript、Vite、TailwindCSS v4 | 现代、快速、类型安全 |
| 桌面 | Tauri 2 | 原生桌面 + WebView 前端 |
| 评测 | GAIA、SWE-bench、τ-bench + 12 自定义套件 | 行业基准 + 自定义测试覆盖 |

---

## 开源协议

MIT —— 随便用，随便改，随便部署，随便卖。无限制。
