.PHONY: dev build check test clean fmt lint server web all install setup help \
        tui dashboard cli cli-run cli-ask cli-agent cli-session cli-config \
        cli-doctor cli-mcp-logs verify verify-runtime verify-api verify-api-mcp \
        eval-list eval-run eval-compare eval-benchmark eval-benchmark-mini \
        eval-history eval-report eval-trace eval-diagnose eval-diff \
        eval-progress sandbox-status sandbox-dry-run sandbox-backends \
        sandbox-dev sandbox-staging sandbox-production sandbox-shell \
        skill-registry-build skill-registry-start skill-registry-test \
        mcp-orch-build mcp-orch-start mcp-orch-test runtime-verify \
        check-pyright-prereqs check-ccb-types-ts-sync autofix build-cli \
        build-full clean-all clean-web config-gen fmt-check help-full release \
        runtime-build runtime-build-binary runtime-run test-engine test-sandbox \
        test-server test-types timings web-build web-check web-lint

# Default test project for CLI commands
TEST_PROJECT ?= $(PWD)/examples/demo-project

# ============================================================
# 主要命令
# ============================================================

# Show this help (with grouped, curated targets — full list: `make help-full`)
help:
	@echo "Grid Platform — Make targets"
	@echo ""
	@echo "Development workflow:"
	@echo "  make dev           Start backend + frontend dev servers (concurrent)"
	@echo "  make build         cargo build (workspace, debug)"
	@echo "  make check        cargo check --workspace (fastest, no binaries)"
	@echo "  make test          cargo test --workspace"
	@echo "  make fmt           cargo fmt --all"
	@echo "  make lint          cargo clippy --workspace -- -D warnings"
	@echo "  make clean         cargo clean"
	@echo ""
	@echo "Production / release:"
	@echo "  make release       cargo build --release --features full (all binaries)"
	@echo "  make install       First-time setup (npm install for web/)"
	@echo "  make all           build + web-build"
	@echo ""
	@echo "Grid CLI (single binary — 19 subcommands: ask / run / tui / dashboard / ...):"
	@echo "  make tui           Launch grid tui (alias: grid tui)"
	@echo "  make dashboard     Launch grid dashboard (alias: grid dashboard --open)"
	@echo "  make cli           Show grid --help"
	@echo "  make cli-ask QUERY=\"...\"   Single headless query"
	@echo "  make cli-run       Interactive REPL session"
	@echo "  make cli-agent     List agents"
	@echo "  make cli-session   List sessions"
	@echo "  make cli-config    Show config"
	@echo "  make cli-doctor    Run health diagnostics"
	@echo "  make cli-mcp-logs NAME=<name>   Tail MCP server logs"
	@echo ""
	@echo "Servers:"
	@echo "  make server        Run grid-server (backend, port 3001)"
	@echo "  make web           Run web/ dev server (port 5173)"
	@echo "  make web-build     Build web/ production bundle"
	@echo ""
	@echo "Quickstart / verification:"
	@echo "  make verify        Static checks (cargo check + tsc + vite build)"
	@echo "  make verify-runtime   Print runtime verification checklist"
	@echo ""
	@echo "Full target list:"
	@echo "  make help-full     Show every target with its command"
	@echo "  cat Makefile       Source of truth (~580 lines)"

# Show ALL targets (long output)
help-full:
	@$(MAKE) -p 2>/dev/null | grep -E '^[a-zA-Z_-]+:.*##' | head -50

# 同时启动后端 + 前端开发服务器
dev:
	@echo "Starting backend and frontend..."
	@$(MAKE) -j2 server web

# 完整构建 (后端 + 前端)
all: build web-build

# 首次安装依赖
install: setup

setup:
	cd web && npm install

# 校验 pyrightconfig.json 绑定的 9 个 per-package .venv 全部存在
# 缺 venv 会让 Pyright 回退到根 .venv 产生 500+ 假 unresolved（D155）
check-pyright-prereqs:
	scripts/check-pyright-prereqs.sh

# 校验 proto ChunkType 与 lang/ccb-runtime-ts/src/proto/types.ts 手写 enum 同步
# Option B / D149: proto 新增 variant 必须同步到 TS side，否则 CI 失败
check-ccb-types-ts-sync:
	scripts/check-ccb-types-ts-sync.sh

# ============================================================
# 后端命令
# ============================================================

# 生成默认配置文件 (config.yaml)
config-gen:
	cargo run -p grid-server -- config-gen > config.yaml

# 编译检查 (最快, 不生成二进制)
check:
	cargo check --workspace

autofix:
	cargo fix --workspace --allow-dirty --allow-staged

# 编译构建 (日常开发, 不含 WASM/Docker/PDF)
build:
	cargo build

# 完整构建 (含 WASM/Docker/PDF 等全部功能)
build-full:
	cargo build --features full

# Build the unified `grid` binary (default features: CLI + TUI + Dashboard, ~25MB)
build-cli:
	cargo build -p grid-cli --bin grid

# Release build (full features: CLI + TUI + Dashboard + TLS, ~46MB)
# Note: build-cli-full was removed — `release` is the canonical alias.
release:
	cargo build --release --features full

# 运行后端服务器 (exec ensures Ctrl+C reaches the server directly)
server:
	@exec cargo run -p grid-server

# 运行测试
test:
	cargo test --workspace

# 单个 crate 测试
test-types:
	cargo test -p grid-types

test-engine:
	cargo test -p grid-engine

test-sandbox:
	cargo test -p grid-sandbox

test-server:
	cargo test -p grid-server

# 代码格式化
fmt:
	cargo fmt --all

# 格式化检查 (CI 用)
fmt-check:
	cargo fmt --all -- --check

# Lint
lint:
	cargo clippy --workspace -- -D warnings

# 编译时间分析 (生成 HTML 报告)
timings:
	cargo build --timings

# ============================================================
# 前端命令
# ============================================================

# 前端开发服务器
web:
	cd web && npm run dev

# 前端生产构建
web-build:
	cd web && npm run build

# 前端类型检查
web-check:
	cd web && npx tsc --noEmit

# 前端 lint
web-lint:
	cd web && npx eslint src/

# ============================================================
# 清理命令
# ============================================================

# 清理后端构建产物
clean:
	cargo clean

# 清理前端构建产物
clean-web:
	cd web && rm -rf node_modules dist .vite

# 清理全部
clean-all: clean clean-web

# ============================================================
# Grid CLI 快捷方式 (统一 grid binary, 19 subcommands)
# ============================================================

CLI_ARGS ?=
QUERY    ?=
NAME     ?=

# Show grid --help
cli:
	cargo run -p grid-cli --bin grid -- --help

# Launch full-screen TUI (equivalent to: grid tui)
tui:
	@cargo run --quiet -p grid-cli --bin grid -- tui --project $(TEST_PROJECT) $(CLI_ARGS)

# Launch embedded Web Dashboard (equivalent to: grid dashboard)
dashboard:
	@cargo run --quiet -p grid-cli --bin grid -- dashboard --project $(TEST_PROJECT) $(CLI_ARGS)

# Interactive REPL session (equivalent to: grid run)
cli-run:
	@cargo run --quiet -p grid-cli --bin grid -- --project $(TEST_PROJECT) run $(CLI_ARGS)

# Single headless query
# Usage: make cli-ask QUERY="your question"
cli-ask:
	@if [ -z "$(QUERY)" ]; then echo "Usage: make cli-ask QUERY=\"your question\""; exit 1; fi
	@cargo run --quiet -p grid-cli --bin grid -- --project $(TEST_PROJECT) ask "$(QUERY)" $(CLI_ARGS)

# List agents
cli-agent:
	cargo run -p grid-cli --bin grid -- --project $(TEST_PROJECT) agent list

# List sessions
cli-session:
	cargo run -p grid-cli --bin grid -- --project $(TEST_PROJECT) session list

# Show config
cli-config:
	cargo run -p grid-cli --bin grid -- --project $(TEST_PROJECT) config show

# Run health diagnostics
cli-doctor:
	cargo run -p grid-cli --bin grid -- --project $(TEST_PROJECT) doctor

# Tail MCP server logs
# Usage: make cli-mcp-logs NAME=<server-name>
cli-mcp-logs:
	@if [ -z "$(NAME)" ]; then echo "Usage: make cli-mcp-logs NAME=<server-name>"; exit 1; fi
	@cargo run --quiet -p grid-cli --bin grid -- mcp logs "$(NAME)" --follow --project $(TEST_PROJECT)

# ============================================================
# 评估命令 (grid-eval)
# 注意: 所有命令从 workspace 根目录运行，输出写入 eval_output/
# ============================================================

EVAL_CONFIG     ?= config/eval/benchmark.toml
EVAL_MINI_CONFIG ?= config/eval/benchmark.toml
EVAL_SUITE      ?= tool_call
EVAL_MAX_TASKS  ?= 0
EVAL_FORMAT     ?= both
EVAL_RUN_ID     ?=
EVAL_TASK_ID    ?=

# 列出可用 suite
eval-list:
	cargo run -p grid-eval -- list-suites

# 运行单个 suite（单模型）
# 用法: make eval-run EVAL_SUITE=resilience
eval-run:
	cargo run -p grid-eval -- run --suite $(EVAL_SUITE) \
	  $(if $(filter-out 0,$(EVAL_MAX_TASKS)),--max-tasks $(EVAL_MAX_TASKS),) \
	  --format $(EVAL_FORMAT)

# 多模型对比单个 suite
# 用法: make eval-compare EVAL_SUITE=security EVAL_CONFIG=config/eval/benchmark.toml
eval-compare:
	cargo run -p grid-eval -- compare --suite $(EVAL_SUITE) \
	  --config $(EVAL_CONFIG) \
	  $(if $(filter-out 0,$(EVAL_MAX_TASKS)),--max-tasks $(EVAL_MAX_TASKS),) \
	  --format $(EVAL_FORMAT)

# 完整 benchmark（全部 suite × 全部模型，并发）
# 用法: make eval-benchmark EVAL_CONFIG=config/eval/benchmark.toml
eval-benchmark:
	cargo run -p grid-eval -- benchmark \
	  --config $(EVAL_CONFIG) \
	  $(if $(filter-out 0,$(EVAL_MAX_TASKS)),--max-tasks $(EVAL_MAX_TASKS),) \
	  --format $(EVAL_FORMAT)

# Mini benchmark：每 suite 3 个任务，快速冒烟测试
# 用法: make eval-benchmark-mini
eval-benchmark-mini:
	cargo run -p grid-eval -- benchmark \
	  --config $(EVAL_MINI_CONFIG) \
	  --max-tasks 3 \
	  --format $(EVAL_FORMAT)

# 列出历史运行记录
eval-history:
	cargo run -p grid-eval -- history

# 查看运行报告
# 用法: make eval-report EVAL_RUN_ID=2026-03-16-001
eval-report:
	@if [ -z "$(EVAL_RUN_ID)" ]; then echo "Usage: make eval-report EVAL_RUN_ID=<run_id>"; exit 1; fi
	cargo run -p grid-eval -- report $(EVAL_RUN_ID) --format $(EVAL_FORMAT)

# 查看任务 trace 时间线
# 用法: make eval-trace EVAL_RUN_ID=2026-03-16-001 EVAL_TASK_ID=tc-01
eval-trace:
	@if [ -z "$(EVAL_RUN_ID)" ]; then echo "Usage: make eval-trace EVAL_RUN_ID=<run_id> EVAL_TASK_ID=<task_id>"; exit 1; fi
	@if [ -z "$(EVAL_TASK_ID)" ]; then echo "Usage: make eval-trace EVAL_RUN_ID=<run_id> EVAL_TASK_ID=<task_id>"; exit 1; fi
	cargo run -p grid-eval -- trace $(EVAL_RUN_ID) $(EVAL_TASK_ID)

# 失败原因分类分析
# 用法: make eval-diagnose EVAL_RUN_ID=2026-03-16-001
eval-diagnose:
	@if [ -z "$(EVAL_RUN_ID)" ]; then echo "Usage: make eval-diagnose EVAL_RUN_ID=<run_id>"; exit 1; fi
	cargo run -p grid-eval -- diagnose $(EVAL_RUN_ID)

# 两次运行回归对比
# 用法: make eval-diff EVAL_RUN_A=2026-03-15-001 EVAL_RUN_B=2026-03-16-001
eval-diff:
	@if [ -z "$(EVAL_RUN_A)" ] || [ -z "$(EVAL_RUN_B)" ]; then \
	  echo "Usage: make eval-diff EVAL_RUN_A=<run_a> EVAL_RUN_B=<run_b>"; exit 1; fi
	cargo run -p grid-eval -- diff $(EVAL_RUN_A) $(EVAL_RUN_B)

# 即时进度：查看正在运行的 benchmark 每个 suite/model 的完成情况
# 用法: make eval-progress              (查看 latest 运行)
#       make eval-progress EVAL_RUN_ID=2026-03-16-007
eval-progress:
	@RUN=$$([ -n "$(EVAL_RUN_ID)" ] && echo "eval_output/runs/$(EVAL_RUN_ID)" || readlink -f eval_output/latest 2>/dev/null || echo "eval_output/latest"); \
	echo "=== Benchmark progress: $$RUN ==="; \
	echo ""; \
	echo "--- Suite completion (model_result.json) ---"; \
	for suite in bfcl context gaia resilience security swe_bench tau_bench terminal_bench; do \
	  total=$$(ls "$$RUN/$$suite"/*/model_result.json 2>/dev/null | wc -l | tr -d ' '); \
	  printf "  %-20s %s/4\n" "$$suite" "$$total"; \
	done; \
	echo ""; \
	echo "--- Per-model task progress (tasks_progress.json or traces) ---"; \
	for suite in bfcl context gaia resilience security swe_bench tau_bench terminal_bench; do \
	  for mdir in "$$RUN/$$suite"/*/; do \
	    [ -d "$$mdir" ] || continue; \
	    model=$$(basename "$$mdir"); \
	    if [ -f "$$mdir/model_result.json" ]; then \
	      result=$$(python3 -c "import json; d=json.load(open('$$mdir/model_result.json')); print(f\"{d['total']} tasks done, {d['passed']} passed ({d['pass_rate']*100:.0f}%)\")" 2>/dev/null); \
	      printf "  %-20s %-30s DONE %s\n" "$$suite" "$$model" "$$result"; \
	    elif [ -f "$$mdir/tasks_progress.json" ]; then \
	      result=$$(python3 -c "import json; d=json.load(open('$$mdir/tasks_progress.json')); print(f\"{d['completed']}/{d['total']} tasks, {d['passed']} passed\")" 2>/dev/null); \
	      printf "  %-20s %-30s IN PROGRESS %s\n" "$$suite" "$$model" "$$result"; \
	    else \
	      traces=$$(ls "$$mdir/traces/" 2>/dev/null | wc -l | tr -d ' '); \
	      printf "  %-20s %-30s running (%s traces)\n" "$$suite" "$$model" "$$traces"; \
	    fi; \
	  done; \
	done; \
	echo ""; \
	if [ -f "$$RUN/benchmark.md" ]; then \
	  echo "--- Final benchmark report ---"; \
	  cat "$$RUN/benchmark.md"; \
	fi

# ============================================================
# 手工验证命令 (grid-workbench)
# ============================================================

# 静态验证: 编译检查 + TS 类型 + Vite 生产构建 + hook scripts (无需运行服务)
verify: hook-scripts-test
	@echo "=== [1/3] Rust 编译检查 ==="
	cargo check --workspace
	@echo ""
	@echo "=== [2/3] TypeScript 类型检查 ==="
	cd web && npx tsc --noEmit
	@echo ""
	@echo "=== [3/3] Vite 生产构建 ==="
	cd web && npm run build
	@echo ""
	@echo "✅ 静态验证全部通过"

# 运行时验证指南 (需先 make server + make web 分两个终端)
verify-runtime:
	@echo "=== grid-workbench 运行时验证步骤 ==="
	@echo ""
	@echo "前置条件:"
	@echo "  1. 确认 .env 已配置 ANTHROPIC_API_KEY"
	@echo "  2. 终端A: make server    (后端, 端口 3001)"
	@echo "  3. 终端B: make web       (前端, 端口 5173)"
	@echo ""
	@echo "核心功能验证清单:"
	@echo ""
	@echo "  [Chat Tab]"
	@echo "  □ 发送消息 → 收到流式回复"
	@echo "  □ 发送消息包含文件路径 → Agent 调用 file_read 工具"
	@echo "  □ 发送 'run: echo hello' → Agent 调用 bash 工具"
	@echo "  □ 连续对话 5+ 轮 → 上下文保持正确"
	@echo ""
	@echo "  [Tools Tab (工具执行历史)]"
	@echo "  □ 工具调用后列表出现新条目"
	@echo "  □ 点击条目 → 详情面板展示输入/输出/耗时"
	@echo ""
	@echo "  [Debug Tab]"
	@echo "  □ Token 预算进度条随对话更新"
	@echo "  □ EventBus 事件流显示 (loop_start / tool_call 等)"
	@echo ""
	@echo "  [Memory Explorer]"
	@echo "  □ Working Memory 内容可见"
	@echo "  □ 对话后 Session Memory 有新增记录"
	@echo ""
	@echo "  [MCP Workbench]"
	@echo "  □ 可通过 UI 添加 Stdio MCP Server"
	@echo "  □ 可通过 UI 添加 SSE MCP Server (transport=sse, url 字段)"
	@echo "  □ Server 日志实时显示"
	@echo ""
	@echo "  [API 验证]"
	@echo "  □ make verify-api   (自动检查所有 REST 端点)"
	@echo ""
	@echo "  [Engine Hardening]"
	@echo "  □ 发送 10+ 轮重复消息 → Loop Guard 触发 (日志中可见 circuit_breaker)"
	@echo "  □ 上下文超 60% → 自动降级 (日志可见 context_pruner)"
	@echo ""
	@echo "完成后记录结果到 docs/main/WORK_LOG.md"

# API 端点可用性检查 (需服务器运行在 3001)
# 路由说明 (所有业务端点统一在 /api/v1/ 下):
#   /api/health                         — 健康检查 (readiness, 无版本前缀)
#   /api/health/live                    — 存活探针 (liveness, 无版本前缀)
#   /api/v1/config                      — 前端配置 (统一配置管理)
#   /api/v1/sessions/{id}/executions    — 按 session 查工具执行历史
#   /api/v1/executions/{id}             — 按 execution id 查单条记录
#   /api/v1/mcp/servers/{id}/tools      — 按 server id 查 MCP 工具列表
#   /api/v1/mcp/servers/{id}/logs       — 按 server id 查 MCP 日志
verify-api:
	@echo "=== REST API 端点验证 (需先 make server) ==="
	@echo ""
	@echo "[Health - readiness]"
	curl -sf http://localhost:3001/api/health && echo " ✅ GET /api/health" || echo " ❌ GET /api/health"
	@echo ""
	@echo "[Health - liveness]"
	curl -sf http://localhost:3001/api/health/live && echo " ✅ GET /api/health/live" || echo " ❌ GET /api/health/live"
	@echo ""
	@echo "[Frontend Config]"
	curl -sf http://localhost:3001/api/v1/config && echo " ✅ GET /api/v1/config" || echo " ❌ GET /api/v1/config"
	@echo ""
	@echo "[Sessions - list]"
	curl -sf http://localhost:3001/api/v1/sessions && echo " ✅ GET /api/v1/sessions" || echo " ❌ GET /api/v1/sessions"
	@echo ""
	@echo "[Memories - list all]"
	curl -sf http://localhost:3001/api/v1/memories && echo " ✅ GET /api/v1/memories" || echo " ❌ GET /api/v1/memories"
	@echo ""
	@echo "[Working Memory]"
	curl -sf http://localhost:3001/api/v1/memories/working && echo " ✅ GET /api/v1/memories/working" || echo " ❌ GET /api/v1/memories/working"
	@echo ""
	@echo "[Tool Executions - by session]"
	@FIRST_SID=$$(curl -sf http://localhost:3001/api/v1/sessions | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['session_id'] if d else '')" 2>/dev/null); \
	if [ -n "$$FIRST_SID" ]; then \
	  curl -sf "http://localhost:3001/api/v1/sessions/$$FIRST_SID/executions" && echo " ✅ GET /api/v1/sessions/{id}/executions (session=$$FIRST_SID)" || echo " ❌ GET /api/v1/sessions/{id}/executions"; \
	else \
	  echo " ⚠️  No sessions found — start a conversation first"; \
	fi
	@echo ""
	@echo "[MCP Servers - list]"
	curl -sf http://localhost:3001/api/v1/mcp/servers && echo " ✅ GET /api/v1/mcp/servers" || echo " ❌ GET /api/v1/mcp/servers"
	@echo ""
	@echo "[Built-in Tools - list]"
	curl -sf http://localhost:3001/api/v1/tools && echo " ✅ GET /api/v1/tools" || echo " ❌ GET /api/v1/tools"
	@echo ""
	@echo "[Budget]"
	curl -sf http://localhost:3001/api/v1/budget && echo " ✅ GET /api/v1/budget" || echo " ❌ GET /api/v1/budget"
	@echo ""
	@echo "Note: /api/v1/mcp/servers/{id}/tools and /api/v1/mcp/servers/{id}/logs"
	@echo "      require a server id — use 'make verify-api-mcp ID=<server_id>'"

# MCP server-specific endpoint check (requires server ID)
# Usage: make verify-api-mcp ID=<server_id>
verify-api-mcp:
	@if [ -z "$(ID)" ]; then echo "Usage: make verify-api-mcp ID=<server_id>"; exit 1; fi
	@echo "=== MCP Server $(ID) 端点验证 ==="
	curl -sf "http://localhost:3001/api/v1/mcp/servers/$(ID)" && echo " ✅ GET /api/v1/mcp/servers/$(ID)" || echo " ❌ GET /api/v1/mcp/servers/$(ID)"
	@echo ""
	curl -sf "http://localhost:3001/api/v1/mcp/servers/$(ID)/tools" && echo " ✅ GET /api/v1/mcp/servers/$(ID)/tools" || echo " ❌ GET /api/v1/mcp/servers/$(ID)/tools"
	@echo ""
	curl -sf "http://localhost:3001/api/v1/mcp/servers/$(ID)/logs" && echo " ✅ GET /api/v1/mcp/servers/$(ID)/logs" || echo " ❌ GET /api/v1/mcp/servers/$(ID)/logs"

# ============================================================
# 沙箱环境切换 (sandbox profile / run mode)
# 详细指南: docs/design/SANDBOX_ENVIRONMENT_GUIDE.md
# ============================================================

# 查看当前沙箱状态 (RunMode, Profile, Policy 等)
sandbox-status:
	cargo run -p grid-cli --bin grid -- --project $(TEST_PROJECT) sandbox status

# 预览所有工具类别的路由决策 (不实际执行)
sandbox-dry-run:
	cargo run -p grid-cli --bin grid -- --project $(TEST_PROJECT) sandbox dry-run

# 列出已注册的沙箱后端
sandbox-backends:
	cargo run -p grid-cli --bin grid -- --project $(TEST_PROJECT) sandbox list-backends

# Development 模式运行 CLI (默认, 所有工具本地执行)
sandbox-dev:
	GRID_SANDBOX_PROFILE=dev cargo run --quiet -p grid-cli --bin grid -- --project $(TEST_PROJECT) run $(CLI_ARGS)

# Staging 模式运行 CLI (强制容器, 无后端时报错)
sandbox-staging:
	GRID_SANDBOX_PROFILE=staging cargo run --quiet -p grid-cli --bin grid -- --project $(TEST_PROJECT) run $(CLI_ARGS)

# Production 模式运行 CLI (强制容器隔离)
sandbox-production:
	GRID_SANDBOX_PROFILE=production cargo run --quiet -p grid-cli --bin grid -- --project $(TEST_PROJECT) run $(CLI_ARGS)

# 进入容器内交互式 shell (自动检测为 Sandboxed 模式)
# API keys 从宿主机环境透传 (AD-D5)
sandbox-shell:
	@if ! docker image inspect grid-sandbox:dev >/dev/null 2>&1; then \
		echo "镜像 grid-sandbox:dev 不存在，先构建..."; \
		$(MAKE) container-build-dev; \
	fi
	docker run -it --rm \
		-v $(PWD):/workspace \
		-w /workspace \
		$(if $(ANTHROPIC_API_KEY),-e ANTHROPIC_API_KEY,) \
		$(if $(OPENAI_API_KEY),-e OPENAI_API_KEY,) \
		$(if $(OPENAI_BASE_URL),-e OPENAI_BASE_URL,) \
		grid-sandbox:dev bash

# ============================================================
# grid-runtime container (EAASP L1 Tier 1 Harness)
# ============================================================

# Build grid-runtime release binary
runtime-build-binary:
	@echo "Building grid-runtime binary..."
	cargo build -p grid-runtime

# Build grid-runtime container image
runtime-build:
	@echo "Building grid-runtime container image..."
	docker build -f crates/grid-runtime/Dockerfile -t grid-runtime:latest .

# Start grid-runtime container
runtime-run:
	@echo "Starting grid-runtime container..."
	docker run --rm -p 50051:50051 \
		-e ANTHROPIC_API_KEY=$${ANTHROPIC_API_KEY} \
		grid-runtime:latest

# Verify grid-runtime gRPC contract (requires runtime-run in another terminal)
runtime-verify:
	cargo run -p eaasp-certifier -- verify --endpoint http://localhost:50051

# ============================================================
# L2 Skill Registry
# ============================================================

skill-registry-build:
	cargo build -p eaasp-skill-registry

skill-registry-start:
	cargo run -p eaasp-skill-registry -- --data-dir ./data/skill-registry --port 18081

skill-registry-test:
	cargo test -p eaasp-skill-registry -- --test-threads=1

# ============================================================
# L2 MCP Orchestrator
# ============================================================

mcp-orch-build:
	cargo build -p eaasp-mcp-orchestrator

L2_MCP_ORCH_PORT ?= 18082

mcp-orch-start:
	cargo run -p eaasp-mcp-orchestrator -- --config tools/eaasp-mcp-orchestrator/config/mcp-servers.yaml --port $(L2_MCP_ORCH_PORT)

mcp-orch-test:
	cargo test -p eaasp-mcp-orchestrator -- --test-threads=1

# ============================================================
