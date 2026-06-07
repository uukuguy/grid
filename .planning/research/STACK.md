# Stack Research

**Project:** Grid v3.4 — Full INBOX Drain (Debt Sweep II)
**Domain:** Agent Runtime Stack + EAASP Platform (Python tools) — incremental debt fixes
**Researched:** 2026-06-07
**Confidence:** HIGH

## Recommended Stack — v3.4 Additions

This document covers **only** stack additions/changes needed for v3.4 new features (~85 P2/P3 debt rows across L2/L3/L4/hooks/contract/eval). The existing validated baseline stack (Rust 1.75+ Tokio/Axum/rmcp, Python 3.12+ FastAPI/grpcio, SQLite+HNSW, Protobuf 3) is detailed in `.planning/PROJECT.md` §Constraints and `CLAUDE.md` §Tech Stack — not repeated here.

### New Python Dependencies — L4 Orchestration

| Library | Version | D-Item | Purpose | Why This Choice |
|---------|---------|--------|---------|-----------------|
| **loguru** | ≥0.7.3 | D31 | Structured logging (replaces stdlib `logging`) | Already used in L3 at same version; standardized across EAASP tools. No learning curve. |
| **rapidfuzz** | ≥3.9 | D34 | NLU Intent→skill_id fuzzy matching | Fast (C++ backend), well-maintained, ideal for P2-level NLU: match user intent text against skill names/descriptions. `process.extractOne()` with `score_cutoff=70` gives good accuracy with zero ML overhead. **Alternative:** Python stdlib `difflib.get_close_matches()` if zero-dependency requirement overrides matching quality. |

### New Python Dependencies — L3 Governance

| Library | Version | D-Item | Purpose | Why This Choice |
|---------|---------|--------|---------|-----------------|
| **mcp** (Python SDK) | ≥1.27 | D10 | MCP Server — upgrade REST facade to proper MCP ServerHandler | L2 already uses `mcp>=1.2` at runtime; L3 needs the same SDK for its own MCP server. Current L3 REST facade is a stopgap — upgrading to real MCP ServerHandler enables tool introspection, typed errors (D99), and protocol compliance. Note: L3 pyproject.toml currently has **no** `mcp` dependency. |

### New Python Dependencies — L2 Memory Engine

| Library | Version | D-Item | Purpose | Why This Choice |
|---------|---------|--------|---------|-----------------|
| **mypy** | ≥2.1 | D15 | Static type checking (dev-only) | L2 has no mypy config. L3 has `ruff>=0.6` in dev deps only — L2 needs the same. mypy is the standard Python type checker; version pinned to match L3 parity. Ruff `[tool.ruff]` section also needed in L2 pyproject.toml (ruff already in L2 dev deps, just missing config). |

### New System Tools — Hooks Testing

| Tool | Version | D-Item | Purpose | Installation |
|------|---------|--------|---------|-------------|
| **shellcheck** | ≥0.11.0 | D108 | Static analysis for hook shell scripts | `brew install shellcheck` (macOS). Already referenced in Makefile `hook-scripts-test` target. Not installed yet on this machine. |
| **bats-core** | 1.13.0 (already installed) | D108 | Bash Automated Testing System | `brew install bats-core` (macOS). Already installed (`/opt/homebrew/bin/bats`). Makefile target exists at L1165. |

### Conditional / Deferrable — Evaluate Per-Phase

These libraries are needed only if specific P3 items are tackled this milestone. Several are marked `📦 long-term` in the LEDGER (Phase 4/5/6 originally) — the v3.4 sweep may defer them:

| Library | Version | D-Item | When to Add | Rationale |
|---------|---------|--------|-------------|-----------|
| **nats-py** | ≥2.15 | D75 | Only if EventStreamBackend NATS JetStream migration is selected for v3.4 | LEDGER marks this `📦 long-term Phase 6`. Adds significant infra (NATS server deployment, migration from SQLite event backend). Includes JetStreamContext for push consumers (D76). **Recommendation: DEFER to v3.5+** — disproportionate for debt sweep. |
| **networkx** | ≥3.6 | D80 | Only if Clusterer causal DAG needs graph algorithms beyond simple dict/set | LEDGER marks this `📦 long-term Phase 4`. For P3 scope, a causal DAG from `parent_event_id` chains can often be implemented with `dict[str, set[str]]` + topological sort without networkx. Only add if clustering algorithm requires graph analytics (centrality, community detection). |

### Rust Stack — No New Dependencies

All v3.4 Rust-side items require **zero new Cargo dependencies**:

| D-Item | Crate | What Changes | Why No New Dep |
|--------|-------|-------------|----------------|
| D74 EmitEvent gRPC reverse channel | grid-runtime | Start `tonic::transport::Server` for L1→L4 event push | `tonic = "0.12"` default features include `transport` with both client (`Channel`) and server (`Server`). No feature flag change needed. |
| D105 HookPoint string alias | grid-engine | Rename/alias enum variant | Pure Rust, no deps |
| D106 MAX_TURNS hardcode | grid-engine | Move const to config | Pure Rust |
| D130 cancel token dual-token | grid-engine | Refactor `CancellationToken` usage | `tokio` already provides `CancellationToken` |
| D90 WS schema tool_name | grid-server | Add field to WS message struct | `axum` + `serde` already in deps |
| D139 双 Terminate 语义 | grid-runtime | Proto definition update | `prost` + `tonic` already in deps |

### No New Dependencies — Python Logic/SQL Fixes

The following D-items need only code changes within the existing dependency set:

| Module | D-Items | Existing Dependencies Sufficient |
|--------|---------|----------------------------------|
| L4 | D28, D29, D32, D33, D36, D37, D39, D41, D42-D45 | FastAPI, aiosqlite, httpx, pytest-asyncio |
| L2 | D14, D59, D65, D77, D78, D79, D92-D101 | FastAPI, aiosqlite, hnswlib, numpy, mcp |
| L3 | D16, D17, D18, D19, D20, D21, D25 | FastAPI, aiosqlite, loguru, pytest-asyncio |
| hooks | D48, D50, D107 | Rust (grid-engine types) + jq (system tool, already available) |
| eval | D56, D126-D129 | Shell, Python stdlib |
| cross-cutting | D24, D73 | pyright config, no code changes |

## Installation

### L4 Orchestration
```bash
cd tools/eaasp-l4-orchestration
uv add loguru>=0.7.3 rapidfuzz>=3.9
```

### L3 Governance
```bash
cd tools/eaasp-l3-governance
uv add mcp>=1.27
# mypy is dev-only, L3 already has ruff in dev; add:
uv add --dev mypy>=2.1
```

### L2 Memory Engine
```bash
cd tools/eaasp-l2-memory-engine
# ruff already in dev deps (≥0.6); add mypy + ruff config
uv add --dev mypy>=2.1
```

### Hooks (System)
```bash
# Already installed: bats-core 1.13.0
brew install shellcheck   # not yet installed
```

### Updated L4 pyproject.toml (target state)
```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "aiosqlite>=0.20",
    "httpx>=0.27",
    "pydantic>=2.8",
    "grpcio>=1.62",
    "protobuf>=5.26",
    "loguru>=0.7.3",       # NEW — D31
    "rapidfuzz>=3.9",       # NEW — D34
]
```

### Updated L3 pyproject.toml (target state)
```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "aiosqlite>=0.20",
    "pydantic>=2.8",
    "httpx>=0.27",
    "loguru>=0.7",
    "mcp>=1.27",            # NEW — D10
]
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **rapidfuzz ≥3.9** (D34 NLU) | `difflib` (stdlib) | If zero new deps is required for L4. `difflib.get_close_matches()` works but is slower and less accurate for multi-word intent matching. |
| **mcp ≥1.27** (D10 L3 MCP) | Keep REST facade | If L3 MCP upgrade is deferred. Current REST facade works but lacks MCP protocol compliance (tool introspection, typed errors). D10 is P3, could defer. |
| **nats-py ≥2.15** (D75 NATS) | Keep SQLite event backend | LEDGER marks D75 `📦 long-term Phase 6`. SQLite backend works for single-node. Only add NATS when multi-node event streaming is needed. **RECOMMENDED: defer to v3.5+** |
| **networkx ≥3.6** (D80 DAG) | `dict`/`set` + custom topo sort | For simple parent→child DAG without community detection or centrality, stdlib structures suffice. Only add networkx when graph analytics (PageRank, Louvain clustering) are needed. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **spaCy / transformers / sentence-transformers** (D34 NLU) | Massively overkill for P2 intent→skill fuzzy matching. Adds GPU dependency, model download, 100MB+ footprint. | `rapidfuzz` (lightweight fuzzy matching) or `difflib` (stdlib zero-dep). |
| **new gRPC library** (D74 EmitEvent) | `tonic 0.12` default features already provide `Server` transport. No additional crate needed. | Use existing `tonic = "0.12"` — just add `tonic::transport::Server` code. |
| **locust / artillery** (D32 concurrency tests) | Overkill for P3 stress tests. Adds external test framework dependency. | `pytest-asyncio` + `httpx.AsyncClient` + `asyncio.gather()` for concurrent request simulation. |
| **kafka-python / redis** (D75 event streaming) | D75 specifically calls for NATS JetStream. Kafka/Redis are different architectures. | `nats-py` if adopted this milestone; otherwise defer entire D75 to v3.5+. |
| **celery / dramatiq** (D79 pipeline multi-worker) | Heavy task queue frameworks overkill for in-process async pipeline. | Python `asyncio` with `asyncio.Queue` + multiple worker coroutines. |

## Stack Patterns by Variant

### D34 NLU: Simple vs. Advanced
**If rapidfuzz is chosen (recommended):**
- Use `process.extractOne(intent_text, [skill["meta"]["name"] for skill in skills], scorer=fuzz.partial_ratio, score_cutoff=70)`
- Fall back to exact `skill_id` match if user provides it explicitly

**If difflib (zero-dep):**
- Use `difflib.get_close_matches(intent_text, skill_names, n=1, cutoff=0.6)`
- Lower accuracy for multi-word intents, higher false positives on short inputs

### D75 EventStreamBackend: SQLite vs NATS
**If keeping SQLite (deferred):**
- Continue with `SqliteWalBackend` — already working, passes Phase 3 E2E
- Add event window cursor (D36) on SQLite with `LIMIT/OFFSET` pagination

**If adopting NATS JetStream (if D75 selected):**
- Replace `event_backend_sqlite.py` with `event_backend_nats.py`
- Requires `nats-server` running (binary or Docker)
- Enables push-based `subscribe()` (D76) as a direct benefit
- Note: adds deployment complexity (NATS server) disproportionate to P3 priority

### L3 MCP Upgrade Path (D10)
**Phase 1 — Add mcp dependency, keep REST facade as fallback:**
- Add `mcp>=1.27` to L3 dependencies
- Implement `Server` class with tool registration
- Keep REST facade for backward compatibility during transition

**Phase 2 — Remove REST facade:**
- Once MCP ServerHandler is live and tested (D25 concurrency E2E), remove REST facade code
- All L3 tool calls go through MCP protocol

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| loguru 0.7.3 | Python ≥3.12 | L3 already uses 0.7.x; L4 Python 3.12+ compatible |
| rapidfuzz 3.9+ | Python ≥3.9 | Pure Python wheel with optional C++ speedup, no external deps |
| mcp 1.27+ | Python ≥3.12, pydantic ≥2.0 | L2 already at mcp 1.27.0; L3 should pin same minimum |
| mypy 2.1 | Python ≥3.9 | Dev-only; no runtime impact |
| shellcheck 0.11.0 | Any shell scripts | System tool, not a Python/Rust dependency |
| nats-py 2.15 | Python ≥3.9 | Only if D75 adopted; requires nats-server binary |

## Rust Tonic 0.12 Server Feature Verification

**Confirmed:** `tonic = "0.12"` default features (`codegen` + `transport`) include both:
- Client: `tonic::transport::Channel`, `tonic::transport::Endpoint`
- Server: `tonic::transport::Server`, `tonic::transport::server::Router`

grid-runtime already depends on `tonic = "0.12"` with no feature restrictions. Starting a gRPC server for D74 EmitEvent reverse channel requires **no Cargo.toml changes** — only code changes to:
1. Define the EmitEvent service proto (or reuse existing)
2. Implement the service trait
3. Start `Server::builder().add_service(...).serve(addr).await`

**No tonic version bump needed** — 0.12 is current, all 4 crates (grid-runtime, grid-hook-bridge, eaasp-goose-runtime, eaasp-claw-code-runtime) pin the same version.

## Summary

| Category | Additions | Deferrals |
|----------|-----------|-----------|
| **L4 Python** | `loguru>=0.7.3` (D31), `rapidfuzz>=3.9` (D34) | — |
| **L3 Python** | `mcp>=1.27` (D10), `mypy>=2.1` dev (D15) | — |
| **L2 Python** | `mypy>=2.1` dev (D15), `[tool.ruff]` config (D15) | `nats-py` (D75), `networkx` (D80) |
| **Hooks System** | `shellcheck>=0.11.0` (D108) | — |
| **Rust** | None — tonic 0.12 covers D74 server | — |
| **Infra** | — | NATS server (D75), any new databases |

**Total new Python dependencies: 4** (loguru, rapidfuzz, mcp, mypy). **Total new system tools: 1** (shellcheck). **Zero new Rust dependencies.** nats-py and networkx deferred to v3.5+ evaluation.

## Sources

- `.planning/v3.3-INBOX.md` — Full 85-row debt catalog, 12-module taxonomy
- `.planning/PROJECT.md` — Current milestone scope, existing stack constraints
- `docs/design/EAASP/DEFERRED_LEDGER.md` — Original D-item classifications (phase3-gated, long-term, tech-debt)
- `tools/eaasp-l4-orchestration/pyproject.toml` — Current L4 dependencies (verified: no loguru, no NLU library)
- `tools/eaasp-l3-governance/pyproject.toml` — Current L3 dependencies (verified: no mcp, loguru present)
- `tools/eaasp-l2-memory-engine/pyproject.toml` — Current L2 dependencies (verified: mcp≥1.2 present, no mypy/ruff config)
- `crates/grid-runtime/Cargo.toml` — Current Rust gRPC setup (tonic 0.12, no features restriction)
- PyPI latest versions: nats-py 2.15.0, rapidfuzz 3.14.5, networkx 3.6.1, mypy 2.1.0, mcp 1.27.2, loguru 0.7.3, ruff 0.15.16
- Homebrew: bats-core 1.13.0 (installed), shellcheck 0.11.0 (not installed)
- L2 `.venv`: mcp 1.27.0 (installed), confirms version compatibility

---

*Stack research for: Grid v3.4 Full INBOX Drain*
*Researched: 2026-06-07*
*Confidence: HIGH — all additions verified against current pyproject.toml files and PyPI latest versions*
