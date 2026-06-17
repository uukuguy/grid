# Grid

**企业级自主智能体运行时栈。Rust 高性能核心，同时提供运行时引擎和完整产品套件。**

Grid 提供端到端自主智能体能力——长链推理、并行工具执行、结构化多层记忆、MCP 原生工具集成、定时调度——同时内建企业级安全边界：Docker/WASM/subprocess 沙箱隔离执行、安全策略引擎、操作审计、多租户隔离、密钥管理。

---

## 为什么选择 Grid

| 能力 | 说明 |
|---|---|
| **沙箱执行** | Docker 容器、WASM 运行时、原生 subprocess 适配器——不可信代码永远不在宿主机上运行 |
| **安全策略** | 每个 Agent 独立自主等级配置、命令风险分级、路径白名单 |
| **审计日志** | 所有工具调用、Agent 行为、会话事件均持久化记录 |
| **MCP 原生** | 完整 Model Context Protocol 支持——stdio 和 SSE 传输，运行时热插拔无需重启 |
| **多层记忆** | 工作记忆（会话内）、会话记忆、持久记忆（FTS5 全文检索 + HNSW 向量搜索）、知识图谱 |
| **定时调度** | Cron 表达式任务调度，附执行历史记录 |
| **多 LLM 提供商** | Anthropic、OpenAI 及兼容接口（DeepSeek、代理等） |
| **并行工具执行** | Semaphore 限流的并发工具调用，可配置并发上限 |
| **Skills 系统** | 文件系统加载的技能模块，热重载，支持 per-agent 工具过滤 |
| **多租户平台** | JWT 租户隔离、RBAC 权限（admin/member/viewer）、配额管理 |
| **对比验证** | 6 个对比运行时适配器，验证 L1 合同可移植性 |

---

## 架构

```
grid/
├── crates/
│   ├── grid-types/          共享类型定义
│   ├── grid-engine/         核心 Agent 运行时（共享库）
│   │   ├── agent/           AgentRuntime → AgentExecutor → AgentLoop
│   │   ├── sandbox/         Docker · WASM · subprocess 适配器
│   │   ├── security/        策略引擎 · 行为追踪
│   │   ├── audit/           审计事件存储
│   │   ├── memory/          工作记忆 · 会话记忆 · 持久记忆 · 知识图谱
│   │   ├── mcp/             MCP 客户端管理（stdio + SSE）
│   │   ├── providers/       Anthropic · OpenAI · 重试 · 提供商链
│   │   ├── scheduler/       Cron 调度 · 执行历史
│   │   ├── skills/          技能加载 · 注册表
│   │   └── tools/           内置工具（bash、文件、搜索…）
│   │
│   ├── grid-server/         工作台 API 服务器（Axum，端口 3001）
│   ├── grid-platform/       多租户平台（JWT、RBAC、配额）
│   ├── grid-cli/            命令行工具（16 命令、全 TUI）
│   ├── grid-desktop/        桌面应用（Tauri 2、系统托盘）
│   ├── grid-eval/           评测框架（10 评分器、12 套件、4 基准）
│   ├── grid-runtime/        L1 gRPC 运行时适配器
│   ├── grid-sandbox/        沙箱运行时适配器（共享）
│   └── grid-hook-bridge/    钩子事件桥接（共享）
│
├── web/                     单用户工作台（React、8 标签、WS 流式）
├── web-platform/            多租户 UI（React Router、JWT 认证）
├── lang/                    6 个对比运行时（Claude Code、Goose 等）
├── tools/                   EAASP L2-L4 本地影子实现
└── proto/                   gRPC 合同定义
```

**双轴产品模型：**

- **engine 接入面（EAASP 集成）** —— `grid-engine` / `grid-runtime` 作为 L1 运行时被上游 EAASP 平台调用。`lang/*` 和 `tools/eaasp-*` 是本地验证护栏。
- **Grid 独立产品** —— `grid-server` / `grid-cli` / `grid-platform` / `grid-desktop` / `web/` / `web-platform/` / `grid-eval` 构成完整的终端用户产品表面。

---

## 产品组件

| 组件 | 类型 | 说明 | 状态 |
|------|------|------|------|
| **grid-cli** | CLI | 16 命令、全 TUI、流式输出、eval 桥接 | ✅ 活跃 |
| **grid-server** | 后端 | 单用户工作台，~130 端点，HMAC/JWT 认证 | ✅ 活跃 |
| **web/** | 前端 | 8 标签 React SPA，WS 流式，Markdown，Jotai 状态 | ✅ 活跃 |
| **grid-platform** | 后端 | 多租户平台，JWT 租户隔离，RBAC，配额 | ✅ 活跃 |
| **web-platform/** | 前端 | 多租户 React UI，登录/仪表盘/聊天/会话/设置 | ✅ 活跃 |
| **grid-eval** | 工具 | 10 评分器，12 套件，4 基准（GAIA/SWE-bench/τ-bench），CI | ✅ 活跃 |
| **grid-desktop** | 桌面 | Tauri 2 应用，系统托盘，内嵌仪表盘，9 IPC 命令 | ✅ 活跃 |
| **grid-runtime** | 运行时 | L1 gRPC 适配器，EAASP 集成用 | ✅ 活跃 |

---

## 快速开始

**前置条件：** Rust 1.75+、Node.js 18+、Anthropic 或 OpenAI API Key。

```bash
git clone https://github.com/uukuguy/grid.git
cd grid

cp .env.example .env
# 编辑 .env，填写 ANTHROPIC_API_KEY 或 OPENAI_API_KEY

make setup          # 安装前端依赖
make dev            # 后端 :3001，前端 :5180
```

浏览器访问 [http://localhost:5180](http://localhost:5180)。

---

## 配置说明

优先级（低 → 高）：`config.yaml` < `.env` < CLI 参数 < 环境变量。

```bash
# LLM 提供商
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=deepseek-chat

# 服务器
GRID_HOST=127.0.0.1
GRID_PORT=3001
GRID_DB_PATH=./data/grid.db

# 日志
RUST_LOG=grid_server=info,grid_engine=info
GRID_LOG_FORMAT=pretty
```

生成完整注释的配置文件：

```bash
make config-gen
```

---

## 开发命令

```bash
make dev            # 启动后端 + 前端（热重载）
make server         # 仅后端
make web            # 仅前端

make build          # 编译 Rust
make check          # 快速编译检查
make test           # 运行测试
make test-server    # 仅服务器测试
make fmt            # 格式化代码
make lint           # Clippy + 格式化检查
make verify         # 静态验证：cargo check + tsc + vite build
```

运行 CLI：

```bash
make cli            # 构建并运行 CLI
make cli-ask        # 单次提问
make cli-session    # 交互式会话
make studio-tui     # 全 TUI 仪表盘
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| Agent 运行时 | Rust、Tokio |
| API 服务器 | Axum、Tower |
| 数据库 | SQLite（rusqlite，WAL 模式）、FTS5 全文检索 |
| 向量搜索 | HNSW（进程内） |
| MCP | rmcp SDK（stdio + SSE） |
| 沙箱 | Docker API、WASM（Wasmtime）、原生 subprocess |
| gRPC | tonic + prost |
| 前端 | React 19、TypeScript、Vite、Jotai、TailwindCSS v4 |
| 桌面 | Tauri 2（Rust + WebView） |
| 评测 | GAIA、SWE-bench、τ-bench、自定义套件 |
| 测试 | Rust：cargo test；TypeScript：Vitest；Python：pytest |

---

## 开源协议

MIT
