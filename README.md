# Grid

[![Rust](https://img.shields.io/badge/Rust-1.75+-orange)](https://www.rust-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[中文文档](README.zh.md) | [English](README.md)

**An enterprise autonomous agent runtime stack — not a framework, not a wrapper, but a production-grade execution layer that enterprises actually deploy.**

Grid is what sits between your LLM provider and your business logic. It handles everything the agent needs at runtime: context, memory, tools, sandboxes, security policies, audit trails, scheduling, and MCP integration — all in a single Rust binary. No Python GIL. No 500MB Docker images. No "works on my laptop."

It ships as both a **substitutable L1 runtime** (pluggable into any orchestration platform via gRPC contract) and a **complete standalone product suite** (CLI, desktop app, multi-tenant platform, evaluation framework).

---

## What makes Grid different

### 1. It's a runtime, not a framework

Most tools in this space are Python frameworks that wrap LLM APIs with a few nice utilities. Grid is an execution layer — it owns the agent process from start to finish. The engine manages agent state, enforces security policies at every tool call, and records every decision for audit. You don't integrate Grid's API into your code; you run Grid as your agent infrastructure.

### 2. Substitutable by design — contract-portable L1

Grid-runtime implements a 16-method gRPC contract that any compliant runtime can fulfill. This is proven: **6 comparison runtimes** (Claude Code, Goose, Nanobot, Pydantic AI, Claw Code, CCB) independently pass the same `contract-v1.1.0` test suite. If you need to switch agent engines, you swap the implementation, not the integration. No vendor lock-in at the runtime layer.

### 3. Enterprise security, not a checklist

Every tool call goes through a security policy engine with **per-agent autonomy levels**, command risk classification, and path whitelisting. Sandbox execution supports Docker containers, WASM isolation, and native subprocess — untrusted code never touches the host. Audit events are persisted for every tool invocation, memory access, and session boundary. This isn't a feature flag; it's the default execution model.

### 4. Memory that persists across sessions — and across years

Grid's memory is multi-tier: **working memory** (in-session context), **session memory** (conversation history), **persistent memory** (full-text search via SQLite FTS5 + semantic search via in-process HNSW vectors), and a **knowledge graph** for structured relationships. Time-decay hybrid retrieval ensures recall stays relevant without blowing up context windows.

### 5. Full product suite from one codebase

| Component | What it is | Who it's for |
|-----------|-----------|--------------|
| **grid-server** | HTTP/WS workbench, ~130 endpoints, HMAC + JWT auth | Single-user agent workbench |
| **grid-cli** | 16-command CLI, full TUI, streaming output | Terminal-native developers |
| **web/** | 8-tab React SPA, real-time WS streaming, Markdown | Web-based agent interaction |
| **grid-platform** | Multi-tenant server, JWT tenant isolation, RBAC, quota | SaaS/enterprise deployments |
| **web-platform/** | Multi-tenant React UI, sessions/dashboard/chat/settings | Platform administrators |
| **grid-desktop** | Tauri 2 desktop app, system tray, embedded dashboard | Desktop-first users |
| **grid-eval** | 10 scorers, 12 test suites, 4 benchmarks (GAIA, SWE-bench, τ-bench) | Quality engineering |

All components share a single `grid-engine` core. Fix a bug in the engine, all products benefit.

---

## Architecture

```
                    ┌──────────────────────────┐
                    │    Orchestration Layer    │
                    │  (EAASP L2/L3/L4 — 本仓库  │
                    │   tools/eaasp-*,或接你的 │
                    │   编排平台)              │
                    └──────────┬───────────────┘
                               │ gRPC (16 methods, contract-v1.2.0)
                    ┌──────────▼───────────────┐
                    │      grid-runtime        │
                    │  (L1 contract adapter)   │
                    └──────────┬───────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       │                       │                       │
  ┌────▼─────┐          ┌──────▼──────┐         ┌──────▼──────┐
  │ Agent     │          │  Context    │         │  Scheduler  │
  │ Loop      │          │  Engine     │         │  (Cron)     │
  └────┬─────┘          └──────┬──────┘         └──────┬──────┘
       │                       │                       │
  ┌────▼─────┐  ┌───────┐  ┌───▼────┐  ┌───────┐  ┌───▼────┐
  │ Memory   │  │  MCP  │  │ Tools  │  │ Audit │  │Skills  │
  │ (4-tier) │  │ Client│  │ Engine │  │ Logger│  │Registry│
  └────┬─────┘  └───┬───┘  └───┬────┘  └───┬───┘  └───┬────┘
       │            │          │           │           │
  ┌────▼────────────▼──────────▼───────────▼───────────▼────┐
  │                    Security Policy Engine               │
  │         Autonomy Levels · Risk Classification          │
  │              Path Whitelist · RBAC                     │
  └─────────────────────────┬─────────────────────────────┘
                            │
  ┌─────────────────────────▼─────────────────────────────┐
  │                   Sandbox Router                      │
  │          Docker · WASM · Native Subprocess            │
  └───────────────────────────────────────────────────────┘
```

This stack ships as **one repository** — both the agent runtime (Grid) and the EAASP platform layer (`tools/eaasp-*`) live here. Production deployment can either:

1. Run the full EAASP v2.0 stack — `make dev-eaasp` brings up L2/L3/L4 + L1 runtime from this single repo, or
2. Plug `grid-runtime` into your own orchestration platform via the 16-method gRPC contract (proven portable: 6 independent runtimes pass the same `contract-v1.1.0` test suite).

The engine processes every tool call through: **autonomy check → risk classification → policy evaluation → sandbox routing → execution → audit recording**. This is a pure pipeline — no branching, no optional security.

---

## Quick Start

```bash
# Prerequisites: Rust 1.75+, Node.js 18+, an API key
git clone https://github.com/uukuguy/grid.git && cd grid
cp .env.example .env      # Add ANTHROPIC_API_KEY or OPENAI_API_KEY
make setup                # Install frontend dependencies
make dev                  # Backend :3001, Frontend :5180
```

Or go CLI-native:

```bash
make cli                  # Build CLI
make cli-ask              # Single prompt: "What is 2+2?"
make studio-tui           # Full TUI dashboard
```

---

## Memory Architecture

Grid's memory isn't a vector database bolted on as an afterthought. It's a 4-tier system designed for long-running autonomous agents:

| Tier | Storage | Retrieval | Lifespan |
|------|---------|-----------|----------|
| **Working** | In-memory | Direct access | Single agent turn |
| **Session** | In-memory + journal | Session-scoped query | Single session |
| **Persistent** | SQLite FTS5 + HNSW vectors | Full-text + semantic hybrid | Cross-session |
| **Knowledge Graph** | Entity-relation store | Graph traversal | Permanent |

Persistent memory uses **time-decay hybrid retrieval**: recent memories get boosted, relevance is computed as a weighted combination of text match, vector similarity, and recency. No "lost in the middle" — the retrieval layer keeps context windows tight and relevant.

---

## MCP Integration

Full Model Context Protocol support — not just a pass-through wrapper:

- **Dual transport**: stdio (local servers) and SSE (remote servers)
- **Hot-reload**: add/remove MCP servers at runtime without restarting the agent
- **Per-session configuration**: each session can mount a different set of MCP tools
- **Namespace isolation**: tools from different servers are namespaced to avoid collisions

```bash
# Register a new MCP server at runtime
grid mcp add --name filesystem --command "npx -y @modelcontextprotocol/server-filesystem /tmp"
```

---

## Security Model

Every tool call goes through:

1. **Autonomy check** — Is this agent allowed to make this decision?
2. **Risk classification** — What's the blast radius? (LOW / MEDIUM / HIGH / CRITICAL)
3. **Policy evaluation** — Does the security policy allow this? (path whitelist, network rules)
4. **Sandbox routing** — Where does this execute? (Docker container / WASM VM / native process)
5. **Audit recording** — What happened? (tool name, args, result, duration, sandbox used)

The autonomy tier controls what requires human approval:
- **Autonomous**: full auto, no gates
- **Semi-autonomous**: gates on HIGH/CRITICAL risk operations
- **Supervised**: all tool calls require approval

---

## Evaluation Infrastructure

`grid-eval` is a first-class evaluation framework, not a collection of ad-hoc scripts:

```bash
# Run all tool-call accuracy tests (23 tasks, L1-L4 difficulty)
grid eval run --suite tool_call

# Run security policy tests (14 tasks, S1-S4)
grid eval run --suite security

# Run GAIA benchmark (165 tasks, 3 difficulty levels)
grid eval run --benchmark gaia

# Compare two runs
grid eval compare --baseline baseline.json --candidate candidate.json

# Generate Markdown report
grid eval report --input results/ --output report.md
```

10 scoring methods: ExactMatch, ToolCallMatch, BehaviorPattern, AST structural match, LLM-as-Judge, EventSequence (LCS), and more. Regression detection for CI pipelines.

---

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Runtime | Rust + Tokio | Memory safety, zero-cost abstractions, async I/O |
| HTTP/WS | Axum + Tower | Type-safe, composable middleware, ergonomic extractors |
| Database | SQLite (rusqlite, WAL mode) | Zero-config, embedded, FTS5 for full-text search |
| Vector Search | HNSW (in-process) | No external service dependency, 150x faster than brute force |
| MCP | rmcp | Native Rust MCP implementation, stdio + SSE |
| Sandbox | Docker (Bollard), WASM (Wasmtime), subprocess | Defense in depth across isolation levels |
| gRPC | tonic + prost | Contract-first protocol, type-safe codegen |
| Frontend | React 19, TypeScript, Vite, TailwindCSS v4 | Modern, fast, type-safe UI layer |
| Desktop | Tauri 2 | Native desktop with Rust backend + WebView frontend |
| Eval | GAIA, SWE-bench, τ-bench, 12 custom suites | Industry benchmarks + custom test coverage |

---

## Comparison: Grid vs Alternatives

| | Grid | LangChain | CrewAI | AutoGPT |
|---|---|---|---|---|
| **Language** | Rust | Python | Python | Python |
| **Runtime model** | Execution engine | Framework glue | Framework glue | Agent loop |
| **Sandbox** | Docker + WASM + subprocess | None built-in | None built-in | Docker only |
| **Security policy** | Per-agent autonomy + risk classification | None | None | None |
| **Audit** | Every tool call, memory access, session event | Optional callback | None | None |
| **Multi-tenant** | JWT isolation + RBAC + quota | No | No | No |
| **Memory** | 4-tier with time-decay hybrid retrieval | Vector DB wrappers | Basic | Basic |
| **MCP** | Native (stdio + SSE, hot-reload) | Wrapper | Wrapper | No |
| **Contract portability** | 16-method gRPC, 6 comparison runtimes | None | None | None |
| **Desktop app** | Tauri 2 native | No | No | No |
| **Eval framework** | 10 scorers, 12 suites, 4 benchmarks | LangSmith (SaaS) | None | None |
| **Deployment** | Single binary (`grid`) | pip install 20+ deps | pip install | Docker compose |

Grid isn't trying to be "LangChain but in Rust." It's an entirely different category: a runtime platform for autonomous agents in production, not a library for prototyping.

---

## License

MIT — use it, fork it, deploy it, sell it. No restrictions.
