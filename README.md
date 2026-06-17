# Grid

**Enterprise-grade autonomous agent runtime stack. Built in Rust, delivered as both a runtime engine and a full product suite.**

Grid provides end-to-end autonomous agent capabilities — long-chain reasoning, parallel tool execution, structured multi-tier memory, native MCP tool integration, cron scheduling — with enterprise security boundaries: sandboxed execution (Docker/WASM/subprocess), a security policy engine, audit logging, multi-tenant isolation, and secrets management.

Rust high-performance core. React workbench frontend. 7 runtime comparison adapters validating contract portability.

---

## Architecture

```
grid/
├── crates/
│   ├── grid-types/          Shared type definitions (zero-dep)
│   ├── grid-engine/         Core agent runtime (shared library)
│   │   ├── agent/           AgentRuntime → AgentExecutor → AgentLoop
│   │   ├── sandbox/         Docker · WASM · subprocess adapters
│   │   ├── security/        Policy engine · behavior tracking
│   │   ├── audit/           Audit event storage
│   │   ├── memory/          Working · session · persistent (FTS5 + HNSW) · knowledge graph
│   │   ├── mcp/             MCP client manager (stdio + SSE)
│   │   ├── providers/       Anthropic · OpenAI · retry · provider chain
│   │   ├── scheduler/       Cron scheduling · execution history
│   │   ├── skills/          Skill loading · registry
│   │   └── tools/           Built-in tools (bash, file, search...)
│   │
│   ├── grid-server/         Workbench API server (Axum, port 3001)
│   ├── grid-platform/       Multi-tenant platform (JWT, RBAC, quota)
│   ├── grid-cli/            CLI (16 commands, full TUI)
│   ├── grid-desktop/        Desktop app (Tauri 2, system tray)
│   ├── grid-eval/           Eval framework (10 scorers, 12 suites, 4 benchmarks)
│   ├── grid-runtime/        L1 gRPC runtime adapter
│   ├── grid-sandbox/        Sandbox runtime adapters (shared)
│   └── grid-hook-bridge/    Hook event bridge (shared)
│
├── web/                     Single-user workbench (React, 8 tabs, WS streaming)
├── web-platform/            Multi-tenant UI (React Router, JWT auth)
├── lang/                    6 comparison runtimes (Claude Code, Goose, etc.)
├── tools/                   EAASP L2-L4 shadow implementations
└── proto/                   gRPC contract definitions
```

---

## Quick Start

**Prerequisites:** Rust 1.75+, Node.js 18+, Anthropic or OpenAI API key.

```bash
git clone https://github.com/uukuguy/grid.git
cd grid

cp .env.example .env
# Edit .env with your API key

make setup          # Install frontend deps
make dev            # Backend :3001, Frontend :5180
```

Open [http://localhost:5180](http://localhost:5180).

---

## Product Components

| Component | Type | Description | Status |
|-----------|------|-------------|--------|
| **grid-cli** | CLI | 16 commands, full TUI, streaming, eval bridge | ✅ Active |
| **grid-server** | Backend | Single-user workbench, ~130 endpoints, HMAC/JWT auth | ✅ Active |
| **web/** | Frontend | 8-tab React SPA, WS streaming, Markdown, Jotai state | ✅ Active |
| **grid-platform** | Backend | Multi-tenant platform, JWT tenant isolation, RBAC, quota | ✅ Active |
| **web-platform/** | Frontend | Multi-tenant React UI, login/dashboard/chat/sessions/settings | ✅ Active |
| **grid-eval** | Tooling | 10 scorers, 12 suites, 4 benchmarks (GAIA/SWE-bench/τ-bench), CI | ✅ Active |
| **grid-desktop** | Desktop | Tauri 2 app, system tray, embedded dashboard, 9 IPC commands | ✅ Active |
| **grid-runtime** | Runtime | L1 gRPC adapter for EAASP integration | ✅ Active |

---

## Configuration

Priority (low → high): `config.yaml` < `.env` < CLI args < env vars.

```bash
# LLM provider
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=deepseek-chat

# Server
GRID_HOST=127.0.0.1
GRID_PORT=3001
GRID_DB_PATH=./data/grid.db

# Logging
RUST_LOG=grid_server=info,grid_engine=info
GRID_LOG_FORMAT=pretty
```

Generate the full default config:

```bash
make config-gen
```

---

## Development

```bash
make dev            # Backend + frontend (hot reload)
make server         # Backend only
make web            # Frontend only

make build          # Compile Rust
make check          # Fast cargo check
make test           # Run targeted tests
make test-server    # Server tests only
make fmt            # Format code
make lint           # Clippy + formatter check
make verify         # Static verification: cargo check + tsc + vite build
```

Run the CLI:

```bash
make cli            # Build and run CLI
make cli-ask        # Single prompt
make cli-session    # Interactive session
make studio-tui     # Full TUI dashboard
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent runtime | Rust, Tokio |
| API server | Axum, Tower |
| Database | SQLite (rusqlite, WAL mode), FTS5 full-text search |
| Vector search | HNSW (in-process) |
| MCP | rmcp SDK (stdio + SSE) |
| Sandbox | Docker API, WASM (Wasmtime), native subprocess |
| gRPC | tonic + prost |
| Frontend | React 19, TypeScript, Vite, Jotai, TailwindCSS v4 |
| Desktop | Tauri 2 (Rust + WebView) |
| Eval | GAIA, SWE-bench, τ-bench, custom suites |
| Testing | Rust: cargo test; TypeScript: Vitest; Python: pytest |

---

## License

MIT
