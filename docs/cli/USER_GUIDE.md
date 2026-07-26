---
title: "grid-cli 使用指南手册"
type: user-guide
audience: end-user (developer / SRE / non-developer observer)
version: v3.8.3
date: 2026-07-24
author: Claude (claude-opus-4-8) via Claude Code CLI
status: active
language: mixed (English headings / commands / code; Chinese explanations)
---

# grid-cli 使用指南手册

> **Single end-user reference** for the `grid` command-line tool — the main client for Grid's single-user / single-tenant product surface (leg B per ADR-V2-024). Covers every command, every flag, every env var, and every scenario the tool supports.
>
> 配套文档:
> - [`QUICKSTART.md`](QUICKSTART.md) — 0→first-success 入门
> - [`scenarios/S1-*.md`](scenarios/) — 6 个实战场景的逐步演练
> - [`../../status/PRODUCTION_USABILITY_2026-07-19.md`](../../status/PRODUCTION_USABILITY_2026-07-19.md) — 实战可用性验收记录
> - [`../../PROJECT_PRODUCT_OVERVIEW.md`](../../PROJECT_PRODUCT_OVERVIEW.md) — 项目级产品情况权威源

---

## 目录

1. [快速开始](#1-快速开始)
2. [安装与初始化](#2-安装与初始化)
3. [全局选项](#3-全局选项)
4. [输出格式与错误 UX](#4-输出格式与错误-ux)
5. [命令参考](#5-命令参考)
   - [5.1 `run` — 启动交互式 REPL 会话](#51-run--启动交互式-repl-会话)
   - [5.2 `ask` — 单次查询 (headless)](#52-ask--单次查询-headless)
   - [5.3 `agent` — Agent 生命周期管理](#53-agent--agent-生命周期管理)
   - [5.4 `session` — 会话生命周期管理](#54-session--会话生命周期管理)
   - [5.5 `memory` — 长期记忆](#55-memory--长期记忆)
   - [5.6 `tool` — 工具调用](#56-tool--工具调用)
   - [5.7 `mcp` — MCP 服务器管理](#57-mcp--mcp-服务器管理)
   - [5.8 `config` — 配置管理](#58-config--配置管理)
   - [5.9 `auth` — 凭据管理](#59-auth--凭据管理)
   - [5.10 `skill` — 技能管理](#510-skill--技能管理)
   - [5.11 `root` — GridRoot 路径管理](#511-root--gridroot-路径管理)
   - [5.12 `eval` — 评测管理](#512-eval--评测管理)
   - [5.13 `sandbox` — 沙箱诊断](#513-sandbox--沙箱诊断)
   - [5.14 `init` — 项目初始化](#514-init--项目初始化)
   - [5.15 `doctor` — 健康检查](#515-doctor--健康检查)
   - [5.16 `completions` — Shell 补全](#516-completions--shell-补全)
   - [5.17 `quickstart` — 场景化快速启动](#517-quickstart--场景化快速启动)
   - [5.18 `tui` — 全屏 TUI 工作台](#518-tui--全屏-tui-工作台)
   - [5.19 `dashboard` — 嵌入式 Web Dashboard](#519-dashboard--嵌入式-web-dashboard)
6. [环境变量](#6-环境变量)
7. [实战场景速查](#7-实战场景速查)
8. [故障排查](#8-故障排查)
9. [附录: 数据模型与路径约定](#9-附录-数据模型与路径约定)
10. [Phase 3.7.2 web/ dashboard 实战化](#10-phase-372-web-dashboard-实战化)
11. [Phase 03.8.0+03.8.1+03.8.2+03.8.3 — grid-server 多用户登录 (JWT + RBAC + Tenant)](#11-phase-03800038100038200383--grid-server-多用户登录-jwt--rbac--tenant)

---

## 1. 快速开始

> 0→first-success 路径。完整版见 [`QUICKSTART.md`](QUICKSTART.md)。

```bash
# 1. 编译
cargo build --release --bin grid

# 2. 设置 LLM API key (二选一)
export ANTHROPIC_API_KEY=sk-ant-xxxxx
# 或
export OPENAI_API_KEY=sk-xxxxx
# OpenRouter 用户
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
export OPENAI_MODEL_NAME=anthropic/claude-3.5-sonnet

# 3. 健康检查
grid doctor

# 4. 跑第一个场景 (S1 multi-step tool use)
grid quickstart S1

# 5. 交互式会话
grid run
```

如果遇到任何问题:

```bash
grid doctor --repair       # 自动修复可修复的问题
grid --verbose run         # 详细日志
grid --retry run           # 自动重试 transient 错误
```

---

## 2. 安装与初始化

### 2.1 编译

```bash
# 标准 release 构建 (CLI + TUI + Dashboard, ~25MB)
cargo build --release --bin grid

# Full release (含 sandbox WASM/Docker + file-parsing + dashboard TLS, ~46MB)
cargo build --release --bin grid --features sandbox-wasm,sandbox-docker,file-parsing,dashboard-tls

# 安装到 PATH
cp target/release/grid /usr/local/bin/
```

> 单一 `grid` 二进制提供全部 19 个子命令 (`ask` / `run` / `tui` / `dashboard` / `mcp` / ...)。TUI + Dashboard 默认启用,无需额外 feature flag。`--features full` 仅用于启用 dashboard 的 HTTPS + 自签名证书生成。

### 2.2 初始化新项目

```bash
cd ~/projects/my-agent-app
grid init                  # 生成 .grid/ 目录与基础配置
grid doctor                # 验证环境就绪
```

`grid init` 在当前目录创建:

```
.grid/
├── mcp.json          # MCP 服务器配置 (持久化)
├── hooks.yaml        # Pre/Post-ToolUse 钩子 (可选)
├── policies.yaml     # 风险策略 (可选)
└── sessions/         # 会话历史存储
```

### 2.3 升级既有项目

```bash
cd ~/projects/my-agent-app
git pull
cargo build --release --bin grid
grid doctor               # 检查 API key / 路径 / 钩子是否仍有效
```

---

## 3. 全局选项

所有命令都接受以下全局标志:

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--verbose` | `-v` | `false` | 启用 debug 日志 (`grid_*` crate) |
| `--config <path>` | `-c` | `config.yaml` | 配置文件路径 |
| `--db <path>` | `-d` | 来自 config | SQLite 数据库路径覆盖 |
| `--project <path>` | `-P` | `$PWD` | 目标项目目录 (覆盖 GridRoot 发现) |
| `--output <fmt>` | | `text` | 输出格式: `text` / `json` / `table` |
| `--no-color` | | `false` | 禁用 ANSI 颜色 |
| `--quiet` | `-q` | `false` | 抑制非必要输出 |
| `--retry` | | `false` | 自动重试 transient 错误 (网络 / 配额) |

### 3.1 全局选项示例

```bash
# JSON 输出 (CI / 脚本友好)
grid --output json agent list

# 详细日志
grid --verbose run --agent code-reviewer

# 自动重试 transient 错误
grid --retry ask "summarize the last 10 sessions"

# 组合使用
grid -v --output json --config ./prod-config.yaml run --parallel 3
```

---

## 4. 输出格式与错误 UX

### 4.1 输出格式

每条命令支持三种输出格式:

| 格式 | 适用场景 | 触发方式 |
|------|----------|----------|
| `text` | TTY 终端, 人类阅读 | 默认 / `--output text` |
| `table` | 多列数据展示 (e.g. `agent list`) | `--output table` |
| `json` | CI / 脚本 / 数据处理 | `--output json` 或 stdout 非 TTY |

**TTY 自动检测**: 当 stdout 不是 TTY (例如管道到 `jq` 或重定向到文件), 自动切换到 `json` 输出。

### 4.2 错误 UX (Phase 3.7.1 REQ-AUDIT-05)

错误输出格式:

```
error: <human-readable cause>
fix:   <actionable remediation hint>
```

**错误分类**:

| 类别 | 触发条件 | 推荐动作 |
|------|----------|----------|
| **Retryable** (网络 / 配额 / 临时) | HTTP 5xx, 429, 超时 | `grid --retry ...` 或带 `--retry` 重跑 |
| **Permanent** (配置 / 权限 / 业务规则拒绝) | 4xx (除 429), hook reject, 权限拒绝 | 按 `fix:` 提示修复 (e.g. `grid auth login --provider openai`) |

**示例**:

```bash
$ grid ask "hello"
error: openai API key not configured
fix:   grid auth login --provider openai

$ grid --retry ask "hello"
retrying (attempt 1/3)... [transient: openai 503]
hello! How can I help?

$ grid mcp logs nonexistent
error: MCP server 'nonexistent' not configured
fix:   grid mcp add <name> <command> [...args]    # or check `grid mcp list`
```

**退出码**: 业务错误返回特定退出码 (SessionNotFound=4, AuthFailed=3, ...), 便于脚本区分。`grid error` 子命令可以查看完整退出码表。

---

## 5. 命令参考

### 5.1 `run` — 启动交互式 REPL 会话

启动一个 REPL (read-eval-print loop) 会话, 与 agent 持续对话。

```bash
grid run [OPTIONS]
```

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--continue` | `-C` | `false` | 恢复上次的会话 |
| `--session <ID>` | `-s` | 自动创建 | 恢复指定 session |
| `--agent <ID>` | `-a` | 默认 agent | 指定使用的 agent |
| `--theme <name>` | | `indigo` | 颜色主题 (indigo / solarized / monokai) |
| `--add-dir <path>` | | (空) | 添加额外目录到 context (可重复) |
| `--dual` | | `false` | 启用双 agent 模式 (Plan + Build 并行) |
| `--parallel <N>` | | `1` | 并行启动 N 个 agents (S5 batch 场景) |

**示例**:

```bash
# 启动默认 agent
grid run

# 恢复上次会话 (Ctrl-C 后继续)
grid run --continue

# 恢复指定 session
grid run --session abc123

# 用 code-reviewer agent 启动
grid run --agent code-reviewer

# 启用双 agent (Plan + Build)
grid run --dual

# 并行跑 3 个 agent (S5 场景)
grid run --parallel 3 "implement the OAuth flow"
```

**REPL 快捷键** (在 REPL 内):

| 按键 | 动作 |
|------|------|
| `Ctrl-C` | 中断当前响应 (agent 暂停, session 保留) |
| `Ctrl-D` | 退出 REPL (保存 session) |
| `Ctrl-L` | 清屏 |
| `↑ / ↓` | 命令历史 |
| `Tab` | 命令补全 |

---

### 5.2 `ask` — 单次查询 (headless)

发送单条消息, 不进入交互模式 (适合 CI / 一次性脚本)。

```bash
grid ask [OPTIONS] <MESSAGE>
```

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--session <ID>` | `-s` | 临时 | 使用指定 session |
| `--agent <ID>` | `-a` | 默认 agent | 指定 agent |

**示例**:

```bash
# 一次性查询
grid ask "what's the weather in Tokyo?"

# 在现有 session 中继续
grid ask --session abc123 "and what about tomorrow?"

# 用特定 agent
grid ask --agent sql-expert "explain this query"
```

---

### 5.3 `agent` — Agent 生命周期管理

```bash
grid agent <SUBCOMMAND>
```

#### `grid agent list`

列出所有可用 agent。

```bash
grid agent list
grid agent list --output json    # 机器可读
```

#### `grid agent info <AGENT_ID>`

显示 agent 详情 (role, goal, 配置)。

```bash
grid agent info code-reviewer
```

#### `grid agent create <NAME>`

创建新 agent。

| 标志 | 简写 | 说明 |
|------|------|------|
| `--role <role>` | `-r` | Agent 角色 (e.g. `developer`, `reviewer`) |
| `--goal <goal>` | `-g` | Agent 目标描述 |

```bash
grid agent create sql-expert --role developer --goal "PostgreSQL query optimization"
```

#### `grid agent start|pause|stop <AGENT_ID>`

状态转换:

```bash
grid agent start sql-expert
grid agent pause sql-expert
grid agent stop sql-expert
```

#### `grid agent delete <AGENT_ID>`

删除 agent (软删除, 保留历史):

```bash
grid agent delete sql-expert
```

---

### 5.4 `session` — 会话生命周期管理

```bash
grid session <SUBCOMMAND>
```

#### `grid session list`

列出最近会话。

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--limit <N>` | `-l` | `20` | 最大结果数 |

```bash
grid session list --limit 50
```

#### `grid session create`

创建新 session。

| 标志 | 简写 | 说明 |
|------|------|------|
| `--name <name>` | `-n` | Session 名称 (可选) |

```bash
grid session create --name "OAuth flow investigation"
```

#### `grid session show <SESSION_ID>`

显示 session 详情 (消息历史、token 用量、状态)。

```bash
grid session show abc123
```

#### `grid session resume <SESSION_ID>` (REQ-AUDIT-01)

恢复 session (重放历史 + 继续 streaming)。

```bash
grid session resume abc123
```

#### `grid session delete <SESSION_ID>`

软删除 session。

```bash
grid session delete abc123
```

#### `grid session kill <SESSION_ID>`

强制终止 session。

| 标志 | 简写 | 说明 |
|------|------|------|
| `--purge` | `-p` | 硬删除 (清除 proto sync markers) |

```bash
grid session kill abc123 --purge
```

#### `grid session export <SESSION_ID>`

导出 session。

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--format <fmt>` | `-f` | `json` | 导出格式 (json / markdown) |
| `--output <path>` | `-o` | stdout | 输出文件路径 |

```bash
grid session export abc123 --format markdown --output session.md
```

---

### 5.5 `memory` — 长期记忆

```bash
grid memory <SUBCOMMAND>
```

#### `grid memory search <QUERY>`

语义搜索长期记忆 (FTS + 向量混合检索)。

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--limit <N>` | `-l` | `10` | 最大结果数 |

```bash
grid memory search "OAuth implementation decisions"
```

#### `grid memory list`

列出最近的 memory entries。

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--limit <N>` | `-l` | `20` | 最大结果数 |

#### `grid memory add <CONTENT>`

添加 memory entry。

| 标志 | 简写 | 说明 |
|------|------|------|
| `--tags <tags>` | `-t` | 逗号分隔标签 (e.g. `auth,design`) |

```bash
grid memory add "Decided to use JWT with refresh tokens for OAuth" --tags auth,design
```

#### `grid memory graph [QUERY]`

显示知识图谱实体 (跨 session 持久化的事实)。

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--limit <N>` | `-l` | `20` | 最大结果数 |

```bash
grid memory graph                  # 所有实体
grid memory graph "user:alice"    # 按名字过滤
```

---

### 5.6 `tool` — 工具调用

```bash
grid tool <SUBCOMMAND>
```

#### `grid tool list`

列出所有可用工具 (内置 + MCP bridge)。

#### `grid tool info <TOOL_NAME>`

显示工具详情 (参数 schema, 描述)。

#### `grid tool invoke <TOOL_NAME> [ARGS]`

直接调用工具 (绕过 agent, 适合调试)。

| 参数 | 说明 |
|------|------|
| `TOOL_NAME` | 工具名 |
| `ARGS` | JSON 格式参数 (e.g. `'{"path": "/tmp/x"}'`) |

```bash
grid tool invoke read_file '{"path": "/etc/hostname"}'
```

---

### 5.7 `mcp` — MCP 服务器管理

```bash
grid mcp <SUBCOMMAND>
```

#### `grid mcp list`

列出所有配置的 MCP 服务器。

#### `grid mcp add <NAME> <COMMAND> [...args]`

添加新 MCP 服务器 (持久化到 `.grid/mcp.json`)。

| 标志 | 简写 | 说明 |
|------|------|------|
| `--env <KEY=VALUE>` | `-e` | 环境变量 (可重复) |

```bash
grid mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
grid mcp add github uvx mcp-server-github --env GITHUB_TOKEN=ghp_xxx
```

#### `grid mcp remove <NAME>`

移除 MCP 服务器。

#### `grid mcp status [NAME]`

显示 MCP 服务器状态 (不指定 NAME 则显示全部)。

#### `grid mcp logs <NAME>` (Phase 3.7.1 REQ-AUDIT-04)

查看 MCP 服务器日志。

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--lines <N>` | `-n` | `50` | 显示最近 N 行 (与 `--follow` 互斥) |
| `--follow` | `-f` | `false` | 实时跟踪日志输出 (Ctrl-C 退出) |
| `--level <lvl>` | | (全部) | 按级别过滤: `info` / `warn` / `error` |
| `--output <fmt>` | | TTY 自动 | 输出格式: `text` / `json` |

**示例**:

```bash
# Tail 最近 50 行
grid mcp logs filesystem

# 实时跟踪 + 只看错误
grid mcp logs filesystem --follow --level error

# JSON 输出 (适合管道到 jq)
grid mcp logs filesystem --lines 100 --output json | jq '.message'

# 跟踪所有级别 (Ctrl-C 干净退出)
grid mcp logs filesystem --follow
```

**Level 推断规则** (来自 stderr 行前缀):
- `ERROR` / `[error]` / `ERR ` / `FATAL` → `error`
- `WARN` / `[warn]` / `WARNING` → `warn`
- 其他 → `info`

---

### 5.8 `config` — 配置管理

```bash
grid config <SUBCOMMAND>
```

#### `grid config show`

显示当前生效配置 (合并 config.yaml + 环境变量)。

#### `grid config validate`

验证配置文件 schema, 报告错误。

#### `grid config init`

交互式初始化配置 (生成 `config.yaml`)。

#### `grid config get <KEY>`

获取单个配置值。

```bash
grid config get auth.mode
```

#### `grid config set <KEY> <VALUE>`

设置配置值 (写入 `config.yaml`)。

```bash
grid config set auth.mode ApiKey
grid config set server.port 3001
```

#### `grid config paths`

显示所有配置文件路径 (config.yaml, .grid/, GRID_GLOBAL_ROOT, etc.)。

---

### 5.9 `auth` — 凭据管理

```bash
grid auth <SUBCOMMAND>
```

#### `grid auth login --provider <NAME>`

存储 API key 凭据。

| 标志 | 说明 |
|------|------|
| `--provider <name>` | Provider 名称 (anthropic, openai, openrouter) |
| `--key <value>` | API key 值 (省略则从 stdin 读取) |

```bash
grid auth login --provider openai --key sk-xxxxx
grid auth login --provider anthropic                     # 提示输入
```

凭据存储在 `GRID_GLOBAL_ROOT` 下的加密文件中 (AES-GCM, key 来自 `GRID_HMAC_SECRET`)。

#### `grid auth status`

显示已配置的凭据 (key 被遮蔽)。

```bash
$ grid auth status
✓ anthropic: sk-ant-...xxxxx (added 2026-07-15)
✓ openai:    sk-...xxxxx    (added 2026-07-19)
```

#### `grid auth logout --provider <NAME>`

删除指定 provider 的凭据。

```bash
grid auth logout --provider openai
```

---

### 5.10 `skill` — 技能管理

```bash
grid skill <SUBCOMMAND>
```

#### `grid skill list`

列出所有已加载的技能 (来自 SKILL.md 文件)。

#### `grid skill show <NAME>`

显示技能详情。

#### `grid skill create <NAME>`

生成新技能脚手架 (创建目录 + SKILL.md 模板)。

#### `grid skill validate <PATH>`

验证技能定义是否符合规范。

---

### 5.11 `root` — GridRoot 路径管理

```bash
grid root <SUBCOMMAND>
```

#### `grid root show`

显示所有已解析的路径 (config, .grid/, sessions, logs)。

#### `grid root init`

确保所有目录存在 (创建缺失的子目录)。

---

### 5.12 `eval` — 评测管理

```bash
grid eval <SUBCOMMAND>
```

#### `grid eval list`

列出可用的评测套件。

#### `grid eval config [--path <path>]`

显示 / 验证评测配置 (默认 `./eval.toml`)。

#### `grid eval run --suite <NAME>`

运行评测套件。

| 标志 | 说明 |
|------|------|
| `--suite <name>` | 套件名 |
| `--tag <tag>` | 标记此次运行 |
| `--parallel <N>` | 并行任务数 |

> **注意**: `grid eval run` 当前调用 `grid-eval` 库 (Phase 3.7.1 REQ-AUDIT-03 wired up)。完整功能见 [`grid-eval`](../../crates/grid-eval/) 文档。

---

### 5.13 `sandbox` — 沙箱诊断

```bash
grid sandbox <SUBCOMMAND>
```

#### `grid sandbox status`

显示当前 sandbox profile 和运行模式 (native / docker / wasm)。

#### `grid sandbox dry-run`

显示每个工具类别的路由决策 (调试用, 不实际执行)。

#### `grid sandbox list-backends`

列出已注册的沙箱后端。

#### `grid sandbox build [--tag <tag>] [--dev] [--multi-platform]`

构建 Grid 沙箱 Docker 镜像。

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--tag <tag>` | `-t` | `grid-sandbox:base` | 镜像 tag |
| `--no-cache` | | `false` | 不使用缓存 |
| `--dev` | | `false` | 构建 dev 镜像 (含 Rust toolchain) |
| `--multi-platform` | | `false` | 多平台构建 (linux/amd64, linux/arm64) |

#### `grid sandbox cleanup [--force] [--session <ID>]`

清理沙箱容器。

---

### 5.14 `init` — 项目初始化

```bash
grid init
```

在当前目录创建 `.grid/` 子目录结构, 包含 `mcp.json` / `hooks.yaml` / `policies.yaml` 模板。如已存在, 提示冲突策略。

---

### 5.15 `doctor` — 健康检查 (Phase 3.7.1 REQ-AUDIT-07)

```bash
grid doctor [--repair]
```

运行 12 项健康检查:

| # | 检查项 | 严重度 | `--repair` 可修 |
|---|--------|--------|-----------------|
| 1 | LLM API key 配置 | ERROR | ❌ |
| 2 | 数据库路径可写 | ERROR | ✅ (创建目录) |
| 3 | GridRoot 目录存在 | ERROR | ✅ (创建) |
| 4 | 配置文件有效 | ERROR | ❌ |
| 5 | MCP 服务器配置有效 | WARN | ❌ |
| 6 | Hooks 文件 schema 有效 | WARN | ❌ |
| 7 | Policies 文件 schema 有效 | WARN | ❌ |
| 8 | LLM 模型可达性 | ERROR | ❌ |
| 9 | Memory 引擎健康 | WARN | ❌ |
| 10 | Sandbox profile 可用 | WARN | ❌ |
| 11 | `GRID_HOOKS_FILE` 引用合法 | WARN | ❌ |
| 12 | Eval bridge 状态 (observability) | INFO | ❌ |

**输出示例**:

```bash
$ grid doctor
✓ 12-check health diagnostic
✓ API key (openai): configured
✓ Database path: ./data/grid.db (writable)
✓ GridRoot: ~/.grid (exists)
✓ Config: config.yaml (valid)
⚠ MCP: 0 servers configured (none registered)
✓ Hooks: ./hooks.yaml (skipped, no file)
✓ Policies: ./policies.yaml (skipped, no file)
✓ Model reachability: openai/gpt-4o (200 OK, 142ms)
✓ Memory engine: FTS5 + HNSW (healthy)
⚠ Sandbox: native subprocess (Docker not installed)
✓ Hooks file: valid (skipped, no GRID_HOOKS_FILE)
✓ Eval bridge: stub observability active

9 PASS, 3 WARN, 0 FAIL

$ grid doctor --repair
[repair] Creating missing directory: ~/.grid
[repair] Database directory created: ./data/
✓ 12-check health diagnostic (2 repairs applied)
```

---

### 5.16 `completions` — Shell 补全

```bash
grid completions generate <SHELL>
```

生成 shell 补全脚本。

| Shell | 安装命令 |
|-------|----------|
| `bash` | `grid completions generate bash > ~/.local/share/bash-completion/completions/grid` |
| `zsh` | `grid completions generate zsh > "${fpath[1]}/_grid"` |
| `fish` | `grid completions generate fish > ~/.config/fish/completions/grid.fish` |
| `powershell` | `grid completions generate powershell > grid.ps1` |

---

### 5.17 `quickstart` — 场景化快速启动 (Phase 3.7.1 REQ-AUDIT-06)

```bash
grid quickstart [SCENARIO] [--json]
```

预检 + 跑指定实战场景。

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `SCENARIO` | `S1` | 场景名 (S1-S5) |
| `--json` | `false` | 机器可读 JSON 输出 |

**5 个内置场景**:

| 场景 | 描述 | 详见 |
|------|------|------|
| **S1** | Multi-step tool use | [`scenarios/S1-multi-step-tool-use.md`](scenarios/S1-multi-step-tool-use.md) |
| **S2** | Memory-driven session | [`scenarios/S2-memory-driven-session.md`](scenarios/S2-memory-driven-session.md) |
| **S3** | Hook-driven governance | [`scenarios/S3-hook-driven-governance.md`](scenarios/S3-hook-driven-governance.md) |
| **S4** | Streaming stop/resume | [`scenarios/S4-streaming-stop-resume.md`](scenarios/S4-streaming-stop-resume.md) |
| **S5** | Parallel batch | [`scenarios/S5-parallel-batch.md`](scenarios/S5-parallel-batch.md) |

**预检内容**:
1. `grid doctor` (前 8 项关键检查)
2. `grid init` (若 .grid/ 缺失)
3. LLM API key 验证
4. 至少 1 个可用 agent

**示例**:

```bash
grid quickstart                    # 默认 S1
grid quickstart S4 --json          # S4 流式 stop/resume, JSON 输出
```

---

### 5.18 `tui` — 全屏 TUI 工作台

启动全屏 TUI 模式 (类似 Claude Code / aider),基于 ratatui 0.29。

```bash
grid tui [OPTIONS]
```

| 标志 | 默认值 | 说明 |
|------|--------|------|
| `--theme <name>` | `indigo` | 颜色主题 |

快捷键同 `grid run` REPL, 额外:
- `Ctrl-P` 命令面板
- `Ctrl-H` 历史浏览

TUI 日志路径: 默认 `./logs/tui.log`,可通过 `GRID_TUI_LOG` 覆盖 (per ADR-V2-032)。

```bash
grid tui
GRID_TUI_LOG=/tmp/grid-tui.log grid tui   # 自定义日志路径
```

### 5.19 `dashboard` — 嵌入式 Web Dashboard

启动嵌入式 Web dashboard (Axum HTTP server)。

```bash
grid dashboard [OPTIONS]
```

| 标志 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--port <N>` | `-p` | `8080` | 监听端口 |
| `--host <H>` | | `127.0.0.1` | 绑定主机 |
| `--open` | | `false` | 启动时打开浏览器 |
| `--enable-tls` | | `false` | 启用 HTTPS |
| `--cert-path <path>` | | (空) | TLS 证书 (PEM) |
| `--key-path <path>` | | (空) | TLS 私钥 (PEM) |
| `--require-auth` | | `false` | 强制 API key 鉴权 |
| `--allowed-origins <list>` | | (空) | 允许的 CORS origins (逗号分隔) |
| `--generate-cert` | | `false` | 生成自签名证书 (开发) |

```bash
# 开发环境
grid dashboard --open

# 生产环境 (HTTPS + 鉴权)
grid dashboard --port 443 --host 0.0.0.0 \
  --enable-tls --cert-path /etc/ssl/grid.pem --key-path /etc/ssl/grid.key \
  --require-auth --allowed-origins https://app.example.com
```

---

## 6. 环境变量

### 6.1 优先级链

`config.yaml` < `.env` (gitignored) < **CLI args** < **shell env vars** (highest)

### 6.2 LLM Provider

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API key (claude-code runtime) |
| `ANTHROPIC_BASE_URL` | 自定义 endpoint (OpenRouter 代理) |
| `ANTHROPIC_MODEL_NAME` | 覆盖默认模型 |
| `OPENAI_API_KEY` | OpenAI / OpenAI-compat API key (grid-runtime 默认) |
| `OPENAI_BASE_URL` | OpenAI-compat endpoint (e.g. `https://openrouter.ai/api/v1`) |
| `OPENAI_MODEL_NAME` | 模型名 (e.g. `gpt-4o`, `anthropic/claude-3.5-sonnet`) |
| `OPENAI_NO_PROXY` | macOS Clash 代理兼容 (设为 `1`) |

### 6.3 Server / 数据库

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GRID_HOST` | `127.0.0.1` | 服务绑定主机 |
| `GRID_PORT` | `3001` | 服务监听端口 |
| `GRID_DB_PATH` | `./data/grid.db` | SQLite 数据库路径 |
| `GRID_GLOBAL_ROOT` | `~/.grid` | GridRoot 路径 |
| `GRID_MAX_BODY_SIZE` | `5MB` | HTTP body 上限 |
| `GRID_CORS_ORIGINS` | (空) | CORS 白名单 (逗号分隔) |

### 6.4 日志

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GRID_LOG` | `info` | tracing filter (e.g. `grid_server=debug,grid_engine=debug`) |
| `GRID_LOG_FORMAT` | `pretty` | `pretty` / `json` |
| `GRID_TUI_LOG` | `./logs/tui.log` | TUI 日志路径 |

### 6.5 Auth / Security

| 变量 | 说明 |
|------|------|
| `GRID_AUTH_MODE` | `None` / `ApiKey` / `Full` (HMAC arm in ApiKey) |
| `GRID_API_KEY` | API key (for `ApiKey` mode) |
| `GRID_API_KEY_USER` | API key 关联用户名 |
| `GRID_HMAC_SECRET` | HMAC 签名密钥 (用于加密存储凭据) |

### 6.6 Hooks / Policies

| 变量 | 说明 |
|------|------|
| `GRID_HOOKS_FILE` | Pre/Post-ToolUse 钩子定义 (YAML) |
| `GRID_POLICIES_FILE` | 风险策略 (YAML) |
| `GRID_ENABLE_EVENT_BUS` | 启用 event bus (`true` / `false`) |

### 6.7 EAASP (leg A, 引擎集成)

| 变量 | 说明 |
|------|------|
| `EAASP_PROMPT_EXECUTOR` | prompt 执行模式 |
| `EAASP_L2_DB_PATH` | L2 memory 数据库路径 |
| `EAASP_DEPLOYMENT_MODE` | `per-session` / `shared-multi-session` |

---

## 7. 实战场景速查

| 场景 | 命令 | 关键标志 |
|------|------|----------|
| 跑一个完整任务 | `grid quickstart S1` | — |
| 流式长会话 + 中断恢复 | `grid quickstart S4` 然后 `Ctrl-C` 后 `grid session resume <id>` | `--session <id>` |
| 跨 session 记忆 | `grid quickstart S2` | — |
| Hook 治理演示 | `GRID_HOOKS_FILE=./hooks.yaml grid quickstart S3` | `GRID_HOOKS_FILE` |
| 并行批量 | `grid run --parallel 3 "..."` | `--parallel N` |
| 调试 MCP 服务器 | `grid mcp logs <name> --follow --level error` | `--follow --level` |
| CI 集成 | `grid --output json --quiet run "..."` | `--output json --quiet` |
| 自动修复环境 | `grid doctor --repair` | `--repair` |
| 离线环境数据导出 | `grid session export <id> --format markdown -o session.md` | `--format` |

---

## 8. 故障排查

### 8.1 错误模式速查

| 症状 | 排查命令 | 常见原因 |
|------|----------|----------|
| `error: API key not configured` | `grid auth status` | 凭据未存储 |
| `error: model unreachable` | `grid doctor` (check #8) | 网络 / 代理 / 配额 |
| `error: session not found` | `grid session list` | session_id 拼写错误 |
| MCP 工具不显示 | `grid mcp list` | 未添加 MCP 服务器 |
| Hook 不触发 | `echo $GRID_HOOKS_FILE` | 环境变量未设 |
| `database is locked` | `lsof data/grid.db` | 另一进程持有锁 |
| 退出码 3 (AuthFailed) | `grid auth status` | 凭据失效 |
| 退出码 4 (SessionNotFound) | `grid session list` | session 已删除 |
| `error: unrecognized subcommand 'tui'` 或 `dashboard` | `cargo build --release --bin grid` (默认 features 已包含 TUI/Dashboard) 或 `make tui` | 旧版 grid-studio 二进制已合并,所有命令在统一 grid binary 中 |

### 8.2 重置 / 清理

```bash
# 清理所有 session (保留 config)
grid session kill <id> --purge

# 重建数据库 (⚠️ 删除所有历史)
rm -rf data/grid.db && grid init

# 重建 .grid/ 目录
rm -rf .grid/ && grid init

# 完全重置 (⚠️ 删除 ALL local data)
rm -rf data/ .grid/ && grid init && grid auth login --provider openai
```

### 8.3 启用调试日志

```bash
# 全局 verbose
grid -v run

# 特定模块 debug
GRID_LOG=grid_engine=debug,grid_mcp=trace grid run

# JSON 日志 (适合日志聚合)
GRID_LOG_FORMAT=json grid run 2>&1 | tee grid.log | jq
```

### 8.4 报告问题

提交 issue 时附上:

```bash
grid doctor --output json > doctor.json
grid --version
git -C $(grid root show --output json | jq -r '.grid_cli_path') rev-parse HEAD
```


---

## 12. 路由授权目录审计

`grid-server` 将每个 HTTP method/path 声明为 `Public` 或 `Requires(Action)`。本地提交前运行：

```bash
make rbac-audit
```

成功时输出 `RBAC route audit PASS` 和目录条目数；失败时逐行列出重复路由、未在公开白名单中的 `Public` 路由、缺失的白名单条目，或任何没有角色可执行的 Action，并以非零状态退出。

新增路由时：

1. 在现有 Axum router 中注册 handler。
2. 在 `crates/grid-server/src/rbac/catalog.rs` 增加完全限定 method/path，并选择 `Public` 或最小权限 `Requires(Action)`。
3. 只有 `/api/health`、`/api/health/live`、`/api/v1/auth/login` 可以公开；新增公开面必须同步安全评审和 `PUBLIC_ROUTE_ALLOWLIST`。
4. 如果现有 Action 无法表达语义，在 `grid-engine/src/auth/roles.rs` 同步增加 enum、`Action::parse` 和 `Role::can` 策略，并更新矩阵测试。
5. 运行 `make rbac-audit`、`cargo test -p grid-server --test route_auditor --test route_rbac_enforcement`。

运行语义：`AuthMode::None` 与 `AuthMode::ApiKey` 不携带 JWT claims，保持原行为；`AuthMode::Full` 根据匹配到的 canonical route template 执行完整 Role × Action 检查。目录缺失时 Full mode 默认拒绝。


### 9.1 GridRoot 解析顺序

```
$PWD/.grid/          # 项目级 (优先)
↑ 否则
$GRID_GLOBAL_ROOT    # 全局 (默认 ~/.grid)
```

### 9.2 数据持久化位置

| 数据 | 路径 |
|------|------|
| 配置 | `$GRID_GLOBAL_ROOT/config.yaml` 或 `$PWD/config.yaml` |
| 数据库 | `$GRID_DB_PATH` (默认 `./data/grid.db`) |
| MCP 配置 | `.grid/mcp.json` |
| Hooks | `$GRID_HOOKS_FILE` 指向的文件 |
| Policies | `$GRID_POLICIES_FILE` 指向的文件 |
| Session 历史 | `.grid/sessions/` |
| 加密凭据 | `$GRID_GLOBAL_ROOT/auth/` |
| TUI 日志 | `$GRID_TUI_LOG` (默认 `./logs/tui.log`) |

### 9.3 关键文件 (`.grid/`)

```
.grid/
├── mcp.json           # MCP 服务器注册表
├── hooks.yaml         # Pre/Post-ToolUse 钩子
├── policies.yaml      # 风险分类策略
├── agents/            # 用户创建的 agent 定义
│   └── *.toml
└── sessions/          # 会话历史 (按 session_id 分目录)
    └── <id>/
        ├── messages.jsonl
        ├── events.jsonl
        └── meta.json
```

### 9.4 配置层级

1. **config.yaml** (项目或全局)
2. **.env** (gitignored, 环境特定)
3. **CLI flags** (`grid --config ./prod.yaml run`)
4. **Shell env vars** (最高优先级, 覆盖一切)

### 9.5 错误退出码表

| 退出码 | 含义 |
|--------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 用法错误 (参数无效) |
| 3 | 认证失败 (AuthFailed) |
| 4 | Session 未找到 (SessionNotFound) |
| 5 | Agent 未找到 (AgentNotFound) |
| 6 | 配置无效 (ConfigInvalid) |
| 7 | MCP 服务器未找到 |
| 8 | Tool 调用失败 |
| 9 | Hook 拒绝 (HookRejected) |
| 10+ | 业务特定错误 |

---

## 相关文档

- [`QUICKSTART.md`](QUICKSTART.md) — 0→first-success 入门 (5 分钟)
- [`scenarios/S1-multi-step-tool-use.md`](scenarios/S1-multi-step-tool-use.md) — 实战场景 1-6 演练
- [`../../status/PRODUCTION_USABILITY_2026-07-19.md`](../../status/PRODUCTION_USABILITY_2026-07-19.md) — 实战可用性验收 (REQ-AUDIT 9/9 closed)
- [`../../PROJECT_PRODUCT_OVERVIEW.md`](../../PROJECT_PRODUCT_OVERVIEW.md) — 项目级产品情况
- [`../../design/EAASP/adrs/ADR-V2-024-phase4-product-scope-decision.md`](../../design/EAASP/adrs/ADR-V2-024-phase4-product-scope-decision.md) — 双轴模型 (leg A/B) 战略锚
- [`../../CLAUDE.md`](../../CLAUDE.md) — 项目配置 / build / 架构权威源

---

---

## 10. Phase 3.7.2 web/ dashboard 实战化

> 本节是 **grid-web**(`web/`,Grid 独立产品的单用户 workbench UI)的用户/开发者使用指南。
> Phase 3.7.2 把 web/ 从"Activation 9.0/10(代码质量)"提升到"非开发者可实战使用"——
> 新增全局 SessionControls(Stop/Resume/live indicator)、Memory 实时更新 + cyan toast、
> Tasks 页面 Stop icon、WS 自动重连、sequence 序号 + debug 模式、prefers-reduced-motion。
> 验收:14/14 acceptance criteria 验证或显式文档化,5/5 Playwright + 26/26 vitest + gsd-ui-auditor 8.83/10。

### 10.1 快速启动(3 个 terminal)

```bash
# Terminal A: grid-server (Rust 后端,提供 REST + WS, port 3001)
make server

# Terminal B: web dev server (Vite + HMR, port 5180)
make web-dev
# 或: cd web && npm run dev

# Terminal C: LLM provider
export OPENAI_API_KEY=sk-...      # 或 ANTHROPIC_API_KEY=sk-ant-...
# 健康检查
curl -sf http://localhost:3001/api/health
```

打开 **http://localhost:5180** — 应该看到 8 tabs + 右下角 SessionControls + ConnectionStatus。

### 10.2 Makefile 命令入口(Phase 3.7.2 新增)

| Command | 用途 |
|---|---|
| `make web-dev` | Vite dev server + HMR(port 5180,与 `make web` 等价) |
| `make web-test` | Vitest 单元测试(`web/src/test/*.test.{ts,tsx}`) |
| `make web-test test=session-bar` | 单文件跑(`--run session-bar` 字符串匹配) |
| `make web-e2e` | Playwright E1-E3 hermetic specs(`web/e2e/S7-*.spec.ts`,5 tests) |
| `make web-e2e` + `WEB_BASE_URL=...` | 自定义 baseURL(默认 `http://localhost:5180`) |
| `make web-check` | TypeScript 类型检查(`tsc -b --noEmit`) |
| `make web-lint` | ESLint `web/src/` |
| `make web-build` | Vite 生产构建(产出 `web/dist/`) |
| `make web-install` | `npm install`(first-time 或 `package.json` 变化后) |
| `make web-clean` | 清理 `node_modules/` + `dist/` + `.vite/` + `test-results/` + `playwright-report/` |
| `make quickstart-s7` | S7 walkthrough 指南(3 terminal + 验证步骤,见 §10.4) |
| `make verify-3.7.2` | 一键跑所有 Phase 3.7.2 自动化验收(7 步,见 §10.5) |

### 10.3 关键文件结构(Phase 3.7.2 新增)

```
web/src/components/
├── SessionControls.tsx           ← 旗舰:全局 Stop/Resume + live indicator + Cmd+. 快捷键
├── SessionBar.tsx               ← 缩小(Stop/Resume 移走,只保留 +)
├── Toast.tsx                    ← 扩展 + memory variant(cyan + Database icon)
└── layout/AppLayout.tsx         ← SessionControls + ConnectionStatus global mount

web/src/atoms/
├── session.ts                   ← +sessionStatusAtom / stoppedByUserAtom / recentlyAddedMemoryIdsAtom
└── ui.ts                        ← +pushMemoryEventAtom

web/src/ws/
├── types.ts                     ← +seq?: u64 字段 + memory_added variant
├── events.ts                    ← +memory_added handler + maybeLogSeqGap
└── manager.ts                   ← 5-attempt reconnect with session_id preservation

web/src/test/
├── session-bar.test.tsx         ← NEW (5 tests)
├── ws-reconnect.test.ts         ← NEW (3 tests)
└── memory-toast.test.tsx        ← NEW (2 tests)

web/e2e/
├── S7-stop-resume.spec.ts       ← E1 (Tasks + SessionControls) — 2 tests
├── S7-memory-toast.spec.ts      ← E2 (memory_added event) — 1 test
└── S7-ws-reconnect.spec.ts      ← E3 (reconnect + seq debug) — 2 tests

web/playwright.config.ts         ← NEW (baseURL = http://localhost:5180)
```

### 10.4 非开发者 walkthrough(S7)

**前置**:Terminal A 跑 `make server`,Terminal B 跑 `make web-dev`,Terminal C 设置 `OPENAI_API_KEY`。

```bash
# Terminal C: 启动 S3 hook-governance scenario
cargo build --release -p grid-cli
./target/release/grid quickstart S3
```

**观察清单**:

| 区域 | 期望 |
|---|---|
| 右下角 SessionControls | 显示 Stop button `Stop session <id 前 8 位> (⌘.)` + 脉动绿点 |
| Tasks tab | 任务行有 Stop icon(`aria-label="Stop task <id>"`),点击触发 DELETE `/api/v1/tasks/:id` |
| Memory tab | header 右侧 cyan "Live" badge + pulse;新行出现并临时高亮(cyan background fade) |
| 右下角 toast | cyan "Memory written: Stored: <content>..." (4000ms 自动消失,可手动关闭) |

完整步骤 + 截图要求见 [`docs/cli/scenarios/S7-web-dashboard.md`](../cli/scenarios/S7-web-dashboard.md)。
人类验收 11 项 checklist 见 [`docs/audit/HUMAN_VERIFICATION_3.7.2.md`](../audit/HUMAN_VERIFICATION_3.7.2.md)。

### 10.5 一键验证(`make verify-3.7.2`)

```bash
make verify-3.7.2
```

7 步检查(全部自动化,无需 live backend):

1. `cargo check --workspace` — Rust workspace 编译干净
2. `cd web && npx tsc -b --noEmit` — TypeScript 类型检查
3. `cd web && npm run build` — Vite 生产构建
4. `cd web && npm run test` — Vitest(预期 26/26 PASS)
5. `cd web && npx playwright test` — Playwright E1-E3(预期 5/5 PASS,hermetic)
6. UI-SPEC compliance grep — padding ≥ `px-2 py-1`,buttons `font-normal`,无 new `@theme` color tokens,无 generic CTAs
7. ✅ All 7 checks passed

> **注意**:Step 5 (Playwright) 需要 web dev server 在另一个 terminal 跑(`make web-dev`)。
> 步骤 6 用 `git diff main -- web/src/globals.css` 验证无新 color tokens 加进 `@theme` block。

### 10.6 常见问题

**Q1: 浏览器打开 `http://localhost:5180` 后右下角没看到 SessionControls?**
A: 检查 3 件事:
- `make web-dev` 跑了吗?(`lsof -i :5180`)
- `make server` 跑了吗?(`curl -sf http://localhost:3001/api/health`)
- F12 → Console 有没有红色错误?如果 `Failed to fetch config: 500` 说明 grid-server 没启

**Q2: Playwright E1 找不到 Stop button?**
A: Spec 是 hermetic 不依赖 grid-server。如果 `expect(stopBtn).toBeVisible()` 超时:
- 检查 `web/e2e/S7-stop-resume.spec.ts` 的 `installRoutes()` 是否包含 `/api/v1/config` mock(否则 config.ts:42 init 失败)
- 检查 `playwright.config.ts` baseURL 是 `localhost` 不是 `127.0.0.1`(vite 默认绑 IPv6 `[::1]`)

**Q3: WS 重连不工作?**
A: 浏览器 WS URL 是 `ws://localhost:5180/ws/ws`(double `/ws`)。这是 vite proxy prefix mismatch + wsManager URL 拼接双 prefix。E2E 用 `page.routeWebSocket` 拦截绕过;人验时 grid-server 必须跑在 `:3001` 才能 proxy 成功。

**Q4: self-recorded walkthrough 卡住了?**
A: 需要 live `make server` + `OPENAI_API_KEY`(或 `ANTHROPIC_API_KEY`)。没有 LLM key 就没法 trigger 真实 agent 事件流。详见 `docs/cli/scenarios/S7-web-dashboard.md` 的 prerequisites。

### 10.7 已知 honest gaps

| Gap | 状态 | 原因 |
|---|---|---|
| Self-recorded walkthrough recording | 🟡 BLOCKED | 需要 live grid-server + LLM API key;executor 无法 trigger 真实 agent |
| REQ-WEB-08 (Schedule/Collab/McpWorkbench WS hook) | ⚪ DEFERRED | Secondary pages;SessionControls global + Tasks Stop icons 已覆盖 dominant stop-resume surfaces |
| WS reconnect URL double `/ws` | ⚪ DEFERRED | vite proxy + wsManager URL 拼接问题;E2E bypass;人验 live backend 也工作 |

### 10.8 相关文档

- [`docs/cli/scenarios/S7-web-dashboard.md`](../cli/scenarios/S7-web-dashboard.md) — 非开发者 walkthrough 模板
- [`docs/audit/3.7.2-GAP-AUDIT.md`](../audit/3.7.2-GAP-AUDIT.md) — 480 行 audit doc(8×5 matrix)
- [`docs/audit/HUMAN_VERIFICATION_3.7.2.md`](../audit/HUMAN_VERIFICATION_3.7.2.md) — 11-item 人验 checklist
- [`docs/status/WEB_PRODUCTION_USABILITY_2026-07-20.md`](../status/WEB_PRODUCTION_USABILITY_2026-07-20.md) — 327 行 dated evidence record
- [`docs/design/web-ui-tokens.md`](../design/web-ui-tokens.md) — 261 行 design token SSOT
- [`.planning/phases/03.7.2-web-production/03.7.2-VERIFICATION.md`](../../planning/phases/03.7.2-web-production/03.7.2-VERIFICATION.md) — verification report
- [`.planning/phases/03.7.2-web-production/03.7.2-UI-SPEC.md`](../../planning/phases/03.7.2-web-production/03.7.2-UI-SPEC.md) — UI design contract(APPROVED)

---

## 11. Phase 03.8.0+03.8.1+03.8.2+03.8.3 — grid-server 多用户登录 (JWT + RBAC + Tenant)

> **v3.8 多用户登录模式 (multi-user mode)** — 取代 v3.7 默认的单用户工作台模式。启用后 `grid-server` 通过 JWT 发放会话,所有受保护 endpoint 强制按 `(tenant_id, user_id, role)` 解析 `TenantContext` 并在 route handler 层执行 RBAC。
>
> 配套文档:
> - [§11.6 — Operator env-var reference](#116-operator-环境变量参考)
> - [`../../status/PRODUCTION_USABILITY_2026-07-24.md`](../../status/PRODUCTION_USABILITY_2026-07-24.md) — 5 scenarios UAT walkthrough
> - [`.planning/phases/03.8.0-jwt-primitive/03.8.0-SUMMARY.md`](../../planning/phases/03.8.0-jwt-primitive/03.8.0-SUMMARY.md) — JWT primitive
> - [`.planning/phases/03.8.1-auth-endpoints/03.8.1-SUMMARY.md`](../../planning/phases/03.8.1-auth-endpoints/03.8.1-SUMMARY.md) — login/refresh/logout
> - [`.planning/phases/03.8.2-rbac-tenant/03.8.2-SUMMARY.md`](../../planning/phases/03.8.2-rbac-tenant/03.8.2-SUMMARY.md) — RBAC + tenant isolation

### 11.1 登录流程 (login flow)

`POST /api/v1/auth/login` 是 multi-user 模式的核心入口。客户端提交 `email` + `password`,服务器在 `UserStore` 中验证 Argon2id 哈希(见 `crates/grid-engine/src/auth/user_store.rs`),通过后签发 HS256 JWT。

**请求:**

```bash
curl -X POST http://localhost:3001/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"a@example.com","password":"hunter2"}'
```

**响应 (`200 OK`):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_at": 1753353600
}
```

**错误 (`401 Unauthorized`, AUTH-04):**

```json
{"error":"auth_failed","message":"invalid credentials"}
```

> **AUTH-04 安全保证**:无论错误是 "用户不存在" 还是 "密码错误",响应 body 完全相同 — 服务器不向攻击者泄漏用户是否存在。

随后的请求通过 `Authorization: Bearer <token>` 头传递 JWT:

```bash
curl http://localhost:3001/api/v1/sessions \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

完整请求/响应代码见 `crates/grid-server/src/api/auth.rs::login_handler`。

### 11.2 JWT claims 结构

JWT payload (来自 `crates/grid-engine/src/auth/config.rs::JwtClaims`):

| 字段 | 类型 | 含义 | 来源 |
|------|------|------|------|
| `sub` | string | user_id | `UserRecord.user_id` |
| `email` | string | 用户邮箱 | `UserRecord.email` |
| `role` | string | `viewer`/`user`/`admin`/`owner` | `UserRecord.role` |
| `tenant_id` | string | **v3.8+ REQUIRED** | `UserRecord.tenant_id` |
| `jti` | string (UUIDv4) | **v3.8.1+ REQUIRED** — per-token identifier for logout blacklist | 每次 mint 时新生成 |
| `iat` | i64 | issued-at timestamp (Unix seconds) | 服务端 |
| `exp` | i64 | expiration timestamp (Unix seconds) | `now + GRID_TOKEN_TTL_SECS` |

> **重要历史变更**:
> - v3.8.0 之前签发的 token 没有 `tenant_id` 字段 — `validate_jwt` 会拒绝它们(`multi_user_jwt::token_without_tenant_id_rejected` 覆盖此路径)。
> - v3.8.0 之前签发的 token 没有 `jti` 字段 — v3.8.1 的 logout/blacklist 强制需要 `jti`,因此老 token 在 v3.8.1+ 上完全失效(security review hotfix `7f08ac53`)。
> - 签名算法固定为 HS256(`jsonwebtoken::Algorithm::HS256`);生产环境的 secret 必须 ≥32 字节(RFC 7518 §3.2),否则 `try_from_env()` 在 `mode=full` 下 fail-fast 返回错误(ADR-V2-028 strict-by-default)。

### 11.3 刷新 (refresh)

`POST /api/v1/auth/refresh` 用旧 JWT 换新 JWT。refresh 的关键安全点:**role + tenant_id 从 `UserStore` 重读,不从老 JWT 的 claims 读取** —— 这防止了攻击者通过修改老 token 的 role claim 来实现权限提升(security review hotfix `7f08ac53` 修正的 stale-claim bug)。

```bash
curl -X POST http://localhost:3001/api/v1/auth/refresh \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
# 200 OK + 同样的 { access_token, token_type, expires_at } 响应
```

**v3.8.1 设计选择** (D-04 of 03.8.1 plan):refresh **不轮换 jti**。老 token 仍然有效直到其原 `exp` 时间。这简化了客户端(无须维护 refresh-token 黑名单),代价是被 logout 的老 token 仍可 refresh 一次。完整 jti 轮换是 v3.9+ 范围。

### 11.4 注销 (logout)

`POST /api/v1/auth/logout` 把当前 JWT 的 `jti` 加入 `TokenBlacklist`,直到该 token 的自然 `exp` 时间为止。返回 `204 No Content`:

```bash
curl -X POST http://localhost:3001/api/v1/auth/logout \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
# 204 No Content
```

**Full-mode 中间件**(见 `crates/grid-server/src/middleware/auth.rs`)在每个受保护 endpoint 验证 JWT 后立即检查 blacklist:

```text
validate_jwt(token) → Ok(claims)
    ↓
is_blacklisted(claims.jti) ? → 401 auth_failed
    ↓ (not blacklisted)
handler executes
```

> **Security hotfix `7f08ac53`**:v3.8.1 初版未把 blacklist 接入 AuthMode::Full 中间件,导致 logout 实际上不起作用(后续请求仍然放行)。hotfix 把 `TokenBlacklist` 通过 `AuthConfig::token_blacklist` 字段接入 AppState,每个 Full-mode 请求都强制检查。回归测试 `multi_user_auth_endpoints::logout_blacklists_token_and_subsequent_use_rejected` 覆盖此路径。

> **v3.8.1 单实例限制**:`TokenBlacklist` 是进程内 `Arc<Mutex<HashMap>>`。多实例部署时 logout 仅对收到 logout 请求的那个实例生效。共享 blacklist 后端是 v3.9+ 范围。

### 11.5 RBAC matrix 参考

RBAC 通过 `Role × Action` 矩阵在 handler 层强制执行(`crates/grid-engine/src/auth/roles.rs::Role::can`)。`requires(Action)` middleware 在每个 route 入口读取 `Extension<JwtClaims>` 并检查 `Role::parse(claims.role).can(action)`。`Owner` 总是通过;`Viewer` 只能 `Read`。

| Action ↓ \ Role → | `viewer` | `user` | `admin` | `owner` |
|-------------------|----------|--------|---------|---------|
| `read` | ✅ | ✅ | ✅ | ✅ |
| `create_session` | ❌ | ✅ | ✅ | ✅ |
| `run_agent` | ❌ | ✅ | ✅ | ✅ |
| `manage_mcp` | ❌ | ❌ | ✅ | ✅ |
| `manage_skills` | ❌ | ❌ | ✅ | ✅ |
| `manage_users` | ❌ | ❌ | ❌ | ✅ |
| `manage_config` | ❌ | ❌ | ❌ | ✅ |

**在 v3.8.2 中的实际部署范围**:03.8.2 在三个 representative endpoint 上演示了 `requires(Action)`(`/admin/users`、`/audit`、`/sessions/{id}`)。完整 route catalog wiring 推迟到 v3.9+。当前未标 `requires()` 的 endpoint 仍走 legacy `UserContext::has_permission` 路径 —— v3.8.2 不引入回归。

**跨租户数据访问**(TENANT-03):User A 在 Tenant X 调用 `GET /api/v1/sessions/<id>` 试图读取 Tenant Y 的 session —— 返回 `403 Forbidden` + body `{"error":"tenant_mismatch"}`,底层数据绝不出现在响应中。SessionStore 通过 `get_session_for_tenant(id, tenant_id, user_id) -> TenantSessionResult` 三态枚举强制此隔离(`Ok | TenantMismatch | NotFound`)。

### 11.6 Operator 环境变量参考

v3.8 multi-user 模式需要四个环境变量。严格模式(`mode=full`)下,任何缺失或非法值都会让服务 fail-fast,而不是回退到不安全的默认(ADR-V2-028 strict-by-default)。

#### 11.6.1 `GRID_AUTH_MODE`

覆盖 `config.yaml` 中的 `auth.mode`。可取值(大小写不敏感):

| 值 | 行为 |
|----|------|
| `none` | 无认证。**生产环境禁止** — 服务启动时会打 warn 日志;在 `mode=api_key`/`full` 切换到 `none` 也会 panic 提示设 `GRID_HMAC_SECRET`。 |
| `api_key` (默认) | API Key + HMAC-SHA256 验证。单用户模式 (v3.7 及之前),所有 key 共享 secret。 |
| `full` | JWT + RBAC + 多租户。**本节描述的工作模式**。需要 `GRID_JWT_SECRET` + `GRID_USERS_JSON`。 |

读取位置:`crates/grid-server/src/config.rs:496`。

#### 11.6.2 `GRID_JWT_SECRET`

`mode=full` 下 **REQUIRED**。HS256 签名 secret。最小长度 32 字节(256 bits,匹配 HS256 输出大小,符合 RFC 7518 §3.2)。

```bash
# 生成符合要求的 secret
export GRID_JWT_SECRET=$(openssl rand -base64 32)
```

**失败语义** (ADR-V2-028 D1 — `try_from_env()`):

- 未设置 → `Err("auth.mode = full requires GRID_JWT_SECRET to be set. ...")`。
- 设置但 < 32 字节 → `Err("GRID_JWT_SECRET is too short: N bytes (need >= 32 bytes). ...")`。
- `mode=api_key` 下未设置 → 静默 fallback,生产环境打 warn 日志(单用户模式不强制)。

读取位置:`crates/grid-engine/src/auth/config.rs:159`(`AuthConfig::default`)与 `try_from_env()` (`:198`)。

#### 11.6.3 `GRID_TOKEN_TTL_SECS`

新发 JWT 的生存时间(秒)。默认 `86400` (24 小时)。

```bash
# 短一点(15 min)适合高安全场景
export GRID_TOKEN_TTL_SECS=900
```

读取位置:`crates/grid-server/src/state.rs:157`。在 `AppState::new()` 时一次性读取,后续请求通过 `state.token_ttl_secs` 字段访问(中途中改变量需重启服务)。

#### 11.6.4 `GRID_USERS_JSON`

启动时的 bootstrap 用户凭据(JSON 数组)。每个元素的 wire shape:

```json
[
  {
    "user_id": "alice",
    "tenant_id": "acme",
    "email": "alice@acme.com",
    "password": "hunter2-correct-horse",
    "role": "admin"
  },
  {
    "user_id": "bob",
    "tenant_id": "globex",
    "email": "bob@globex.com",
    "password": "another-strong-password",
    "role": "viewer"
  }
]
```

| 字段 | 含义 | 校验 |
|------|------|------|
| `user_id` | 内部用户 ID (也是 JWT `sub`) | 必须全局唯一,重复则解析失败 |
| `tenant_id` | 用户所属 tenant | 必须非空(用于 TENANT-01/TENANT-03) |
| `email` | 登录标识 (JWT `email`) | 必须全局唯一,重复则解析失败 |
| `password` | 明文密码 | 启动时一次性 Argon2id 哈希;明文不进存储 |
| `role` | `viewer`/`user`/`admin`/`owner` | 必须可被 `Role::parse` 解析,未知值拒绝 |

**错误处理**(读取位置:`crates/grid-server/src/state.rs:135` + `crates/grid-engine/src/auth/user_store.rs:77`):

- 未设置 + `mode=full` → 服务器启动时打 warn 日志,但不 panic(后续 `/auth/login` 返回 401 给所有调用,因为 user store 为空)。
- 设置但 JSON 解析失败 → `mode=full` 下 panic(strict-by-default);`mode=api_key` 下 warn 并使用空 store(login 全面禁用)。
- 任何 email/user_id/role 非法 → 启动失败,返回 operator-actionable 错误消息。

**安全提示**:

- **明文密码**仅出现在 JSON 输入瞬间,Argon2id 哈希(`$argon2id$v=19$m=...$t=...$p=...$salt$hash`)在 `UserStore` 中保存。
- **不建议在 .env 中提交明文密码**;生产部署应使用 secret manager(AWS Secrets Manager / Vault / SOPS)将 JSON 注入到 `GRID_USERS_JSON` 环境变量。
- **timing-side-channel 缓解**:`UserStore::verify_credentials` 在 "未知 email" 分支立即返回 `None`(不执行 Argon2 verify),理论上本地网络上的 timing-attack adversary 可以区分。v3.9+ 配合 login rate-limiting 实际上消除此 concern;constant-time fallback 可在 rate-limiting 落地后补上。

### 11.7 单用户 vs 多用户模式切换

**默认 = 单用户** (`mode=api_key`,无 `GRID_AUTH_MODE` env var)。所有 v3.7 之前部署 **零变更** 继续运行 —— 这是 R-1 回归纪律的硬要求。

切换到 multi-user 模式:

```bash
# 1. 生成 JWT secret
export GRID_JWT_SECRET=$(openssl rand -base64 32)

# 2. 创建 user bootstrap JSON
export GRID_USERS_JSON='[{"user_id":"alice","tenant_id":"acme","email":"alice@acme.com","password":"...","role":"admin"}]'

# 3. (可选)调短 TTL
export GRID_TOKEN_TTL_SECS=3600

# 4. 设置 mode=full
export GRID_AUTH_MODE=full

# 5. 启动 grid-server
cargo run --bin grid-server
```

切换后 **必须** 把现有 v3.7 ApiKey 客户端迁移到 JWT 登录流程。两种 mode 不能在同一进程内共存。

### 11.8 已知 honest gaps

| Gap | 状态 | 原因 |
|-----|------|------|
| Live UAT walkthrough (带真实 LLM key 的端到端) | 🟡 BLOCKED | 需要 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`;hermetic UAT (5/5) 已通过 |
| Refresh-token jti rotation (logout 后老 token 不能 refresh) | ⚪ DEFERRED (v3.9+) | v3.8.1 单 token 滑动过期 (D-04) |
| 共享 TokenBlacklist 后端 (多实例部署 logout 跨实例生效) | ⚪ DEFERRED (v3.9+) | v3.8.1 仅进程内 `Arc<Mutex>` |
| Full route catalog `requires(Action)` 强制覆盖 | ⚪ DEFERRED (v3.9+) | 03.8.2 仅在 3 个 representative endpoint 上演示 |
| Constant-time `verify_credentials` fallback | ⚪ DEFERRED (v3.9+) | 配合 login rate-limiting 落地 |
| DB-backed `users` 表 (取代 `GRID_USERS_JSON`) | ⚪ DEFERRED (v3.9+) | v3.8 接受 "edit env var + restart" 开发循环 |

### 11.9 相关文档

- [`../../status/PRODUCTION_USABILITY_2026-07-24.md`](../../status/PRODUCTION_USABILITY_2026-07-24.md) — 5-scenario UAT walkthrough
- [`.planning/phases/03.8.0-jwt-primitive/03.8.0-SUMMARY.md`](../../planning/phases/03.8.0-jwt-primitive/03.8.0-SUMMARY.md) — JWT mint/verify primitive
- [`.planning/phases/03.8.1-auth-endpoints/03.8.1-SUMMARY.md`](../../planning/phases/03.8.1-auth-endpoints/03.8.1-SUMMARY.md) — login/refresh/logout handlers + audit
- [`.planning/phases/03.8.2-rbac-tenant/03.8.2-SUMMARY.md`](../../planning/phases/03.8.2-rbac-tenant/03.8.2-SUMMARY.md) — RBAC + tenant isolation + AUDIT-02
- [`.planning/REQUIREMENTS.md`](../../planning/REQUIREMENTS.md) v3.8 section — 21 REQ-IDs across 6 categories
- [`.planning/ROADMAP.md`](../../planning/ROADMAP.md) v3.8 ladder
- [`crates/grid-engine/src/auth/`](../../crates/grid-engine/src/auth/) — auth primitives (config, roles, user_store, token_blacklist)
- [`crates/grid-server/src/api/auth.rs`](../../crates/grid-server/src/api/auth.rs) — login/refresh/logout handlers
- [`crates/grid-server/src/middleware/auth.rs`](../../crates/grid-server/src/middleware/auth.rs) — Full-mode middleware + `require_action_middleware`

---

*Version: v3.8.3 (2026-07-24) — Phase 03.8.0+03.8.1+03.8.2+03.8.3 SHIPPED, multi-user login (JWT + RBAC + Tenant) added as §11*
*Status: Active — covers 17 grid-cli commands + web/ Phase 3.7.2 + 9 global flags + 7-step verify-3.7.2 + 6 multi-user scenarios in §11*
*Author: Claude (claude-opus-4-8) via Claude Code CLI*
