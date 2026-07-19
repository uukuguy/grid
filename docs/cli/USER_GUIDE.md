---
title: "grid-cli 使用指南手册"
type: user-guide
audience: end-user (developer / SRE / non-developer observer)
version: v3.7.1
date: 2026-07-20
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
   - [5.18 Studio 命令 (`tui` / `dashboard`)](#18-studio-命令-tui--dashboard)
6. [环境变量](#6-环境变量)
7. [实战场景速查](#7-实战场景速查)
8. [故障排查](#8-故障排查)
9. [附录: 数据模型与路径约定](#9-附录-数据模型与路径约定)

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
# 标准 release 构建
cargo build --release --bin grid

# 含 Studio TUI / Dashboard (--features studio)
cargo build --release --bin grid --features studio

# 安装到 PATH
cp target/release/grid /usr/local/bin/
```

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

### 5.18 Studio 命令 (`tui` / `dashboard`)

需要 `--features studio` 编译。

#### `grid tui --theme <name>`

启动全屏 TUI 模式 (类似 Claude Code / aider)。

| 标志 | 默认值 | 说明 |
|------|--------|------|
| `--theme <name>` | `indigo` | 颜色主题 |

快捷键同 `grid run` REPL, 额外:
- `Ctrl-P` 命令面板
- `Ctrl-H` 历史浏览

#### `grid dashboard [--port N] [--host H] [--open] [--enable-tls]`

启动嵌入式 Web dashboard。

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

## 9. 附录: 数据模型与路径约定

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

*Version: v3.7.1 (2026-07-20) — Phase 3.7.1 grid-cli SHIPPED, REQ-AUDIT 9/9 closed*
*Status: Active — covers 17 top-level commands + 2 Studio (TUI/Dashboard) + 9 global flags*
*Author: Claude (claude-opus-4-8) via Claude Code CLI*
