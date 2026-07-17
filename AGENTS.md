# Grid — An Agent Runtime Stack (engine vs data/integration 双轴模型)

> **Note**: ADR-V2-024 (2026-04-28, Accepted) supersedes ADR-V2-023 — Leg A/B 二元框架已替换为双轴模型 (engine vs data/integration). 此文件中"Leg A/B" 历史措辞已统一替换为新框架; 历史 anchor 保留 see-link 至 ADR-V2-024 (see ADR-V2-024 supersedes ADR-V2-023). 详见 ADR-V2-024 Decision 段。
>
> **Brand name:** Grid.
> **Working repo name:** `grid` (renamed from `grid-sandbox` 2026-06-17 per ADR-V2-023 §P6 trigger condition met).
> **Primary strategic reference:** [`docs/design/EAASP/adrs/ADR-V2-024-phase4-product-scope-decision.md`](docs/design/EAASP/adrs/ADR-V2-024-phase4-product-scope-decision.md) (Accepted 2026-04-28). Historical reference: [`ADR-V2-023`](docs/design/EAASP/adrs/ADR-V2-023-grid-two-leg-product-strategy.md) (Superseded 2026-04-28).
>
> **What Grid is:** A Rust-centric agent-runtime stack built around `grid-engine` and the full Grid toolchain (`grid-cli` / `grid-server` / `grid-platform` / `grid-desktop` / `grid-eval` / `grid-hook-bridge` / `grid-sandbox` / `grid-runtime` / `grid-types`). Grid 现按双轴模型 (engine vs data/integration) 切职责, 同时支持两条产品形态:
>
> **engine 接入面** (原 Leg A, see ADR-V2-024 supersedes ADR-V2-023) — 与 EAASP 引擎层 / L1 runtime 生态集成方向。`grid-engine` / `grid-runtime` 是 EAASP 的旗舰 L1 runtime(16-method gRPC contract);`tools/eaasp-*/` 是 **EAASP v2.0 平台尚未完整实现前、按平台契约做的"模拟器"级参考实现**(EVOLUTION_PATH §三 8 Phase 路线已 SHIPPED Phase 0–2.5,待补 Phase 3 审批链 / Phase 4 A2A / Phase 5 L5 Cowork UI / Phase 6 生态扩展)。**不存在"上游 EAASP"独立项目**;EAASP 平台设计文档权威源在 `docs/design/EAASP/`(以 `EAASP-Design-Specification-v2.0.docx` 为规范)。
>
> **Grid 独立产品** (原 Leg B, see ADR-V2-024 supersedes ADR-V2-023) — Grid 独立面向企业的产品套件。`grid-platform` (multi-tenant server) + `grid-server` (single-user workbench) + `grid-desktop` (Tauri app) + `web/` / `web-platform/` frontends + `grid-cli` / `grid-eval` (主客户端 / 主评测)。Grid 独立产品 Activation 8 phases **已 SHIPPED 2026-06-17**(v3.5 milestone 之后),质量分详见 §2 / `.planning/STATE.md` Audit Findings Summary。
>
> **工时 baseline** (per ADR-V2-024 Open Item #2): Grid 全栈 ≈60% / EAASP 引擎 ≈30% / 元工作 ≈10%.
> **优先发力组合** (per ADR-V2-024 Open Item #3): grid-cli + grid-server 优先, 其余组件 dormant 到下个 milestone.
>
> **产品情况同步文档**: [`docs/PROJECT_PRODUCT_OVERVIEW.md`](docs/PROJECT_PRODUCT_OVERVIEW.md) — 项目级 single source of truth,2026-07-17 创建于本次 docs sync。必含:
> - 第 2.2 节:EAASP 全栈(含 8 Phase 进度对照,tools/eaasp-* 模拟器级实现的精确定性)
> - 第六节:Reference Linkage 完整索引(EAASP 设计文档权威源 + 战略 ADR + 项目管理状态)
>
> This file is the **primary project memory for Claude Code**. If anything here goes stale, **update it immediately** — outdated instructions are worse than none.

---

## Product status (canonical facts, 2026-07-17 sync)

The canonical facts below match [`docs/PROJECT_PRODUCT_OVERVIEW.md`](docs/PROJECT_PRODUCT_OVERVIEW.md) and the dated audit snapshot `docs/status/PRODUCT_STATUS_2026-07-17.md`.

- **Grid Activation**: 8 phases (A.0–A.8) **shipped on 2026-06-17**. Post-Activation work continues (`grid-desktop` feature completion, `web-platform/` test coverage).
- **EAASP core engineering**: L0 (protocol) + L1 (runtime contract) + L2 (memory & skills) + L3 (governance) + L4 (orchestration) reference implementation and contract validation are **complete for the current research/reference implementation** in this repository.
- **EAASP platform evolution — explicitly pending**: Phase 3 production OPA approval chain, Phase 4 A2A / Event Room, Phase 5 L5 Cowork UI, Phase 6 ecosystem expansion. These remain future work in the EVOLUTION_PATH 8-Phase roadmap.
- **L1 runtimes**: **7 total** in this repository — 1 production (`grid-runtime`) + 6 comparison runtimes (`claude-code`, `goose`, `nanobot`, `pydantic-ai`, `claw-code`, `ccb`; `hermes` frozen per ADR-V2-017).
- **Contract version**: `contract-v1.2.0` is the **current latest**; `contract-v1.1.0` is the **historical Phase 3 sign-off** (2026-04-18).
- **`tools/eaasp-*` framing**: simulator-level reference implementations of the EAASP v2.0 platform contract, hosted in this same repository. **No separate upstream EAASP project exists**; the EAASP platform design authoritative source is `docs/design/EAASP/` (with `EAASP-Design-Specification-v2.0.docx` as the spec of record).

---

## Product legs at a glance (ADR-V2-024 双轴模型, supersedes ADR-V2-023)

| Dimension | engine 接入面 (原 Leg A, see ADR-V2-024) | Grid 独立产品 (原 Leg B, see ADR-V2-024) |
|-----------|--------------------------|--------------------------|
| Status | **Active (primary focus)** | **Active** (8 phases SHIPPED 2026-06-17;持续 feature 工作) |
| Core | `grid-engine` + `grid-runtime` | `grid-engine` (shared) |
| Toolchain | 与 EAASP L1/L2/L3/L4 引擎层集成,通过 gRPC 接 `tools/eaasp-*/` | `grid-server`, `grid-platform`, `grid-desktop`, `grid-cli`, `grid-eval`, `web/`, `web-platform/` |
| EAASP tools 关系 | 共生于本仓(`tools/eaasp-*/` 是 EAASP v2.0 模拟器级参考实现,本团队自做,不依赖外部 EAASP)| **不直接依赖** `tools/eaasp-*`(Grid 独立产品的客户不需要 EAASP 平台)|
| Phase focus | EVOLUTION_PATH §三 Phase 0–2.5 已 SHIPPED,Phase 3–6 按 8 Phase 路线渐进推进 | A.0–A.8 已 SHIPPED;后续补 grid-desktop feature + web-platform 测试覆盖 |
| Production customer | 部署 EAASP 平台的企业(可一仓跑 EAASP L1–L4 全套);或通过 L1 contract 接 customer 平台 | 想要 Grid 独立产品的企业(可单独部署 grid-server / grid-platform)|

(see ADR-V2-024 supersedes ADR-V2-023 — 表格 column 命名从 Leg A/B 切换为 双轴 framing; substance unchanged for engine/data-integration 职责切, 见 ADR-V2-024 §1)

**Core rule (ADR-V2-023 P1, retained under ADR-V2-024):** changes to shared components (`grid-engine`, `grid-runtime`, `grid-types`, `grid-sandbox`, `grid-hook-bridge`) MUST work for both engine 接入面 and Grid 独立产品. No leg-specific branches in core code (see ADR-V2-024 supersedes ADR-V2-023).

---

## EAASP v2 Architecture (L0–L4) — 同仓共生的引擎层 (见 `docs/design/EAASP/` 权威设计文档)

```
L4 Orchestration       tools/eaasp-l4-orchestration/        session lifecycle + SSE fan-out + governance gates
                                                            (Phase 4 A2A / Event Room ⏸ 未实现 per EVOLUTION_PATH)
L3 Governance          tools/eaasp-l3-governance/           policy DSL + risk classification + shadow/enforce mode
                                                            (Phase 3 OPA 后端 + 完整审批链 ⏸ 未实现)
L2 Memory & Skills     tools/eaasp-l2-memory-engine/        L2 memory (FTS + HNSW + time-decay hybrid, ✅ 全量)
                       tools/eaasp-skill-registry/          skill manifest storage + MCP tool bridge (Cargo)
                       tools/eaasp-mcp-orchestrator/        MCP server lifecycle across sessions (Cargo)
                       tools/eaasp-certifier/               contract certification harness (Cargo)
L1 Runtime (7 adapters) grid-runtime (Rust, 主力) + 6 comparison runtimes (claude-code / goose / nanobot /
                                                            pydantic-ai / claw-code / ccb;hermes frozen)
L0 Protocol            proto/eaasp/runtime/v2/              common.proto / runtime.proto (17 RPC) + hook.proto (4 RPC)
                                                            合计 21 RPC 方法(CLAUDE.md 历史措辞"16 methods"是简化表述)
```

**关键定性 — 2026-07-17 docs sync 修正**:

- `tools/eaasp-*/` **是 EAASP v2.0 平台尚未完整实现前、按平台契约做的"模拟器"级参考实现**(per EVOLUTION_PATH §三 8 Phase 路线:Phase 0–2.5 已 SHIPPED,L3 OPA 后端 / L4 A2A / L5 Cowork UI / Phase 6 生态扩展均⏸待后续 milestone 推进)
- **不存在"上游 EAASP"独立项目** — EAASP 平台设计文档权威源同仓在 `docs/design/EAASP/`,**`EAASP-Design-Specification-v2.0.docx` 是规范权威**
- **CLAUDE.md/AGENTS.md 历史措辞 "high-fidelity local shadows" / "production EAASP lives in separate project" 错误** — 已在 2026-07-17 docs sync PR 改为"模拟器级参考实现";具体修正记录见 `docs/PROJECT_PRODUCT_OVERVIEW.md` §五
- L2–L4 本仓内通过 gRPC `proto/eaasp/runtime/v2/runtime.proto` 调用 L1;L1 substitutable — 每个 adapter 实现同一 contract,7 个 runtime 全部 pass contract-v1.2.0

### EAASP 平台设计文档索引(必读)— `docs/design/EAASP/`

| 文档 | 作用 |
|------|------|
| `EAASP-Design-Specification-v2.0.docx` | **规范权威**(4373KB,导出 markdown `/tmp/eaasp_v2_spec.md` 2944 行)|
| `EAASP_v2_0_EVOLUTION_PATH.md` | 长期 cross-phase 决策登记(5 层 + 3 管道 + 4 元范式 + 7 阶段演化 + 决策登记表)|
| `EAASP_v2_0_MVP_SCOPE.md` | 圈 2 MVP 范围细化 |
| `EAASP_v2_0_Platform_Product_Forms.docx` | 产品形态蓝图 |
| `EAASP_v2_Executive_Overview.docx` + `.html` | 高管摘要 / 对外简版 |
| `PHASE1_EVENT_ENGINE_DESIGN.md` / `PHASE_3_DESIGN.md` | 各 Phase 设计(Phase 3 ⏸ 未实现) |
| `L1_RUNTIME_ADAPTATION_GUIDE.md` | L1 runtime adapter 实现指南 |
| `L1_RUNTIME_STRATEGY.md` + 7 个 R1-R4 eval + `L1_RUNTIME_TIER_SPEC_*` 中英对照 | L1 Runtime 生态策略 + 4 tier 横切 |
| `PROVIDER_CAPABILITY_MATRIX.md` | LLM provider matrix |
| `E2E_VERIFICATION_GUIDE.md` | E2E 验证脚本 living spec |
| `DEFERRED_LEDGER.md` | 跨 phase D-item SSOT(100% ✅ CLOSED)|
| `adrs/ADR-V2-*.md` 23 个 ADR | 战略 + 契约 ADR,ADR-V2-024 + V2-029 为当前双轴 substance |

### L1 Runtime adapters in this repo (1 + 6)

| Name | Crate/Pkg | Language | Role | Notes |
|------|-----------|----------|------|-------|
| **grid-runtime** | `crates/grid-runtime/` | Rust | **Grid's flagship runtime** — full harness | The target engine 接入面 L1 implementation (原 Leg A, see ADR-V2-024) |
| **claude-code-runtime-python** | `lang/claude-code-runtime-python/` | Python | Comparison / sample | Anthropic SDK baseline |
| **goose-runtime** | `crates/eaasp-goose-runtime/` + `crates/eaasp-scoped-hook-mcp/` | Rust | Comparison — Block goose via ACP subprocess | stdio MCP proxy for hook injection |
| **nanobot-runtime-python** | `lang/nanobot-runtime-python/` | Python | Comparison — OpenAI-compat provider | Multi-turn loop, ADR-V2-006 hook envelope |
| **pydantic-ai-runtime-python** | `lang/pydantic-ai-runtime-python/` | Python | Comparison | Phase 3 addition |
| **claw-code-runtime** | `crates/eaasp-claw-code-runtime/` | Rust | Comparison | Phase 3 addition |
| **ccb-runtime-ts** | `lang/ccb-runtime-ts/` | TypeScript (Bun) | Comparison | Phase 3 addition |
| **hermes-runtime-python** | `lang/hermes-runtime-python/` | Python | **Frozen** | ADR-V2-017 — replaced by goose + nanobot |

The 6 comparison runtimes exist in this repo to validate that **the L1 contract is truly portable** — if another team implements `claude-code` / `goose` / `nanobot` / `pydantic-ai` / `claw-code` / `ccb` against the same proto and passes contract v1.1, then `grid-runtime` can't be secretly depending on undocumented behavior. They are **test fixtures for the contract**, not competitors and not products.

Phase 3 sign-off (2026-04-18): all 7 runtimes pass `contract-v1.1.0` (42 PASS / 22 XFAIL each) — `contract-v1.1.0` is the historical Phase 3 sign-off version.

**Current contract: `contract-v1.2.0`** — adopted after Phase 3 sign-off. All 7 runtimes in the repo currently certify against `contract-v1.2.0`.

### Rust crates

Legend: **A** = used by engine 接入面 (原 Leg A, EAASP integration, see ADR-V2-024). **B** = used by Grid 独立产品 (原 Leg B, Grid independent product, see ADR-V2-024). **Shared** = used by both.

| Crate | Leg | Role |
|-------|-----|------|
| `grid-types` | Shared | Shared type definitions (zero-dep) — messages, tools, sessions, sandbox, IDs, errors |
| `grid-sandbox` (crate) | Shared | Sandbox runtime adapters (native subprocess; optional wasm / docker). **Note**: crate name collides with repo name — distinct concept |
| `grid-engine` | Shared | Core engine — agent loop, context, memory (L0/L1/L2), MCP, providers, tools, skills, security, audit, metrics |
| `grid-hook-bridge` | Shared | Hook event bridge between Rust and L2/L3 |
| `grid-runtime` | A (primary) / B (in-process) | L1 runtime adapter wrapping `grid-engine`. engine 接入面 (原 Leg A, see ADR-V2-024) exposes it via gRPC; Grid 独立产品 (原 Leg B) uses it in-process |
| `grid-cli` | A (aux) / B (primary) | CLI binary (`grid` command). engine 接入面 (原 Leg A, see ADR-V2-024) uses EAASP's own CLI; Grid 独立产品 (原 Leg B) uses this as the main client |
| `grid-eval` | A (aux) / B (primary) | Evaluation harness — suites, scorers, benchmarks. engine 接入面 (原 Leg A, see ADR-V2-024) uses EAASP eval; Grid 独立产品 (原 Leg B) uses this |
| `grid-server` | **B** (active, primary) | Single-user workbench HTTP/WS server (Axum) |
| `grid-platform` | **B** (active, primary) | Multi-tenant platform server (Axum + JWT auth + quota) |
| `grid-desktop` | **B** (active, feature-completion) | Tauri desktop app (excluded from default build — `cargo build -p grid-desktop` to build) |
| `eaasp-goose-runtime` | A | L1 adapter for Block goose (Rust) — comparison runtime |
| `eaasp-claw-code-runtime` | A | L1 adapter for claw-code (Rust) — comparison runtime |
| `eaasp-scoped-hook-mcp` | A | stdio MCP proxy that injects Pre/Post-ToolUse hooks per ADR-V2-006 |

**Build order**: `grid-types` → `grid-sandbox` / `grid-engine` (parallel) → everything else. Cargo workspace handles this automatically.

**Grid 独立产品 status (原 Leg B, ADR-V2-023 P2 retained under ADR-V2-024, see ADR-V2-024 supersedes ADR-V2-023,activation SHIPPED 2026-06-17)**: Grid 独立产品 Activation 8 phases (A.0–A.8) **已 SHIPPED**。`grid-server` / `grid-platform` / `web/` / `web-platform` 是 active 的,持续 feature 工作。`grid-desktop` 处于功能补完阶段(IPC 命令齐但 agent/session 交互未实装,详 `docs/PROJECT_PRODUCT_OVERVIEW.md` §4.1)。Activation 已经 past,不再 trigger-gated。

### EAASP Python/TS tools (`tools/`)

| Tool | Role |
|------|------|
| `eaasp-l2-memory-engine` | L2 memory: FTS5 + HNSW + time-decay, 7 MCP tools (search/read/write_file/write_anchor/confirm/list/delete) |
| `eaasp-skill-registry` | Skill manifest storage, MCP tool bridge |
| `eaasp-mcp-orchestrator` | MCP server lifecycle across sessions |
| `eaasp-l3-governance` | Policy DSL + risk classification |
| `eaasp-l4-orchestration` | Session orchestration, SSE streaming, governance gates |
| `eaasp-cli-v2` | End-user CLI (`eaasp session run -s <skill> -r <runtime> "<prompt>"`) |
| `eaasp-certifier` | Contract certification harness (Rust) |
| `mock-scada` | Example external system for verification skills |

### Frontend (Grid 独立产品 only — 原 Leg B, see ADR-V2-024 supersedes ADR-V2-023)

`web/` and `web-platform/` are both **Grid 独立产品 components** (原 Leg B components, ADR-V2-023 P2 retained under ADR-V2-024, see ADR-V2-024). Activation 8 phases **SHIPPED 2026-06-17** — both frontends are active. `web/` is production-quality; `web-platform/` carries quality caveats (test coverage gaps in some flows, see `docs/PROJECT_PRODUCT_OVERVIEW.md` §4.1 / `.planning/STATE.md` Audit Findings Summary).

| Path | Target product | Status |
|------|----------------|--------|
| `web/` | Single-user workbench UI (React + TypeScript + Vite + Jotai + Tailwind) | Active — production-quality post-Activation |
| `web-platform/` | Multi-tenant platform UI | Active — feature-complete with quality caveats |

---

## Tech Stack (current)

| Layer | Technology |
|-------|------------|
| Rust toolchain | rust-version 1.75+, edition 2021, resolver = 2 |
| Async | Tokio 1.42 (full features) |
| HTTP/WS | Axum 0.8 + axum-extra 0.10 |
| MCP SDK | rmcp 1 (client + server + stdio + streamable HTTP) |
| Database | SQLite via `rusqlite` 0.32 + `tokio-rusqlite` 0.6 |
| Vector | HNSW (in-process, ADR-V2-015) |
| LLM providers | Anthropic + OpenAI-compat (OpenRouter, etc.) via `reqwest` |
| Sandbox | native subprocess primary; optional Wasmtime / Bollard (Docker) |
| Crypto | AES-GCM, Argon2, SHA-256, `jsonwebtoken` 9 |
| Proto | tonic-build codegen; `prost-types` + `prost-build` |
| Python runtimes | Python 3.12+, `uv` package manager, `grpcio` + `pydantic` |
| TS runtime | Bun + TypeScript 5 (`lang/ccb-runtime-ts/`) |
| Frontend (planned) | React 19, TypeScript 5.7, Vite 6, Jotai 2.16, Tailwind 4 |

---

## Configuration

Priority (lowest to highest): `config.yaml` < `.env` (gitignored) < CLI args < shell env vars.

**Generate `config.default.yaml` after changing `crates/grid-server/src/config.rs`:**

```bash
make config-gen
```

### Key env vars (prefix `GRID_*`)

```bash
# Required — LLM access
ANTHROPIC_API_KEY=sk-ant-xxxxx
ANTHROPIC_BASE_URL=...       # optional — for OpenRouter or proxies
ANTHROPIC_MODEL_NAME=...     # optional — overrides default model
OPENAI_API_KEY=sk-xxxxx       # when using OpenAI-compat provider
OPENAI_MODEL_NAME=gpt-4o     # OpenAI model (not LLM_MODEL; see MEMORY.md feedback)

# Server
GRID_HOST=127.0.0.1
GRID_PORT=3001
GRID_DB_PATH=./data/grid.db
GRID_GLOBAL_ROOT=~/.grid
GRID_LOG=grid_server=debug,grid_engine=debug
GRID_LOG_FORMAT=pretty       # or json

# Auth / Security
GRID_AUTH_MODE=...
GRID_API_KEY=...
GRID_API_KEY_USER=...
GRID_HMAC_SECRET=...
GRID_CORS_ORIGINS=...
GRID_CORS_STRICT=...

# Hooks / policies
GRID_HOOKS_FILE=...
GRID_POLICIES_FILE=...
GRID_ENABLE_EVENT_BUS=...
GRID_MAX_BODY_SIZE=...

# EAASP
EAASP_PROMPT_EXECUTOR=...    # ADR-V2-XXX prompt execution mode
EAASP_L2_DB_PATH=...
EAASP_TOOL_FILTER=...        # deprecated in favor of skill-declared filter (ADR-V2-020)
EAASP_DEPLOYMENT_MODE=...    # per-session vs shared-multi-session (ADR-V2-019)
```

### Service ports (do NOT hardcode — use config)

| Port | Service | Source |
|------|---------|--------|
| 3001 | Backend (`grid-server`) | `GRID_PORT` / `config.yaml` |
| 5180 | Frontend Vite dev server | `web/vite.config.ts` (planned) |
| 50051 | `grid-runtime` gRPC | runtime config |
| 50052 | `claude-code-runtime-python` | runtime config |
| 50053 | `goose-runtime` | runtime config |
| 50054 | `nanobot-runtime` | runtime config |

---

## Build & Test

`make help` prints all targets. Key ones (Makefile has 130 targets total):

```bash
# Setup
make setup                   # install frontend deps; cp .env.example .env first

# Dev loops
make dev                     # grid-server + web concurrently
make dev-eaasp               # all 4+ EAASP services with log rotation under .logs/latest/
make dev-eaasp-stop          # stop everything dev-eaasp launched
make server                  # backend only
make web                     # frontend only

# Build
make check                   # fast cargo check
make build                   # debug
make release                 # release
make all                     # backend + frontend
make build-eaasp-all         # all EAASP runtimes + tools

# Targeted tests
make test                    # workspace (cargo test) — only use when asked, per behavioral rules
make test-types / test-engine / test-sandbox / test-server
make claude-runtime-test / goose-runtime-* / hermes-runtime-*

# Quality
make fmt / fmt-check / lint
make web-check / web-lint

# Verification
make verify                  # static (cargo check + tsc + vite build)
make verify-runtime          # print manual runtime verification checklist
make verify-dual-runtime     # start both Rust + Python runtimes + certifier

# EAASP contract E2E
make v2-phase2-e2e           # Phase 2 14 @assertions (SKIP_RUNTIMES=true default)
make v2-phase2-e2e-full      # with runtime 6-step
make v2-phase3-e2e           # Phase 3 B1-B8, 112 pytest
make v2-phase3-e2e-rust      # Rust side regression

# CLI
make cli / cli-ask / cli-session / cli-config / cli-doctor
make studio-tui / studio-dashboard / studio

# Config
make config-gen              # regenerate config.default.yaml from grid-server/src/config.rs

# Runtime containers
make claude-runtime-build / claude-runtime-run
make goose-runtime-container-build / goose-runtime-container-run

# Cleanup
make clean / clean-web / clean-all
```

---

## Phase & ADR Workflow

Project development is **phase-driven**. Each phase lives in `docs/plans/YYYY-MM-DD-<topic>.md`, tracked via `dev-phase-manager`. Architecture decisions live in `docs/design/EAASP/adrs/` (ADR-V2-XXX format, enforced by ADR governance plugin).

### Phase state is external to the repo's own memory

- **Active phase stack**: `docs/dev/.phase_stack.json`
- **Current checkpoint**: `docs/plans/.checkpoint.json`
- **Archived checkpoint (previous phase)**: `docs/plans/.checkpoint.archive.json`
- **Work log (prepend-new-on-top)**: `docs/dev/WORK_LOG.md`
- **Recent activity index**: `docs/dev/MEMORY_INDEX.md`
- **Deferred ledger (cross-phase)**: `docs/design/EAASP/DEFERRED_LEDGER.md`

### Skills to use (don't write phase logic by hand)

| Task | Slash command / skill |
|------|----------------------|
| Start a new phase | `/dev-phase-manager:start-phase "<name>"` |
| End / archive a phase | `/dev-phase-manager:end-phase` |
| Checkpoint mid-phase | `/dev-phase-manager:checkpoint-progress` |
| Resume after `/clear` | `/dev-phase-manager:resume-plan` |
| Scan for unresolved `Deferred` items | `/dev-phase-manager:deferred-scan` |
| Execute plan with reviewer loops | `/superpowers:subagent-driven-development` (same session) or `/superpowers:executing-plans` (parallel session) |

**Never create or hand-edit `.phase_stack.json` / `.checkpoint.json` / `docs/dev/NEXT_SESSION_GUIDE.md` directly.** Use the skill. See user-global CLAUDE.md for the "Plugin/Skill State Files — 严禁臆造路径" precedent (the 2026-04-15 incident).

### ADR workflow

Project uses the global ADR governance plugin (`~/.claude/skills/adr-governance/`, meta-ADR: ADR-V2-022).

| Task | Slash command |
|------|---------------|
| Session-start dashboard | `/adr:status` |
| Check which ADRs constrain a file | `/adr:trace <path>` |
| New ADR | `/adr:new --type contract\|strategy\|record` |
| Accept a Proposed ADR (runs F1-F4 lint) | `/adr:accept <id>` |
| Health + staleness review | `/adr:review --health` |
| Full lint gate | `/adr:audit` |

**Hard rules:**
1. Before editing files listed in an Accepted `contract` ADR's `affected_modules`, run `/adr:trace`. PreToolUse hook `adr-guard.sh` also blocks violations automatically.
2. Never write ADR frontmatter by hand — `/adr:new` enforces the schema.
3. New contract ADRs without enforcement (`trace` array + CI / hook) fail F4 lint.

Current ADR audit: `docs/design/EAASP/adrs/AUDIT-2026-04-19.md`. Re-run quarterly.

Vendored plugin scripts live at `.adr-plugin/scripts/` so CI runs without the global plugin. Refresh after upstream update: `/adr:sync-scripts`.

---

## Key Design Docs

Authoritative architecture + design material. If code diverges from these, update the doc as part of the same change.

### EAASP v2 (active)

| Doc | Topic |
|-----|-------|
| **`ADR-V2-023-grid-two-leg-product-strategy.md`** | **Strategic anchor — product legs A/B, dormancy rules, rename deferral (READ FIRST for new contributors)** |
| `docs/design/EAASP/adrs/` | 17 ADRs (V2-001 to V2-023), single source of truth for decisions |
| `docs/design/EAASP/E2E_VERIFICATION_GUIDE.md` | Living spec for `scripts/eaasp-e2e.sh` + Makefile `v2-phase*-e2e` targets |
| `docs/design/EAASP/DEFERRED_LEDGER.md` | Cross-phase Deferred D-items (single SSOT for debt) |
| `docs/design/EAASP/L1_RUNTIME_ADAPTATION_GUIDE.md` | How to build a new L1 runtime adapter (§12 covers TS/Bun) |
| `docs/design/EAASP/L1_RUNTIME_COMPARISON_MATRIX.md` | 7-runtime feature matrix |
| `docs/design/EAASP/L1_RUNTIME_CANDIDATE_ANALYSIS.md` | Research → picks the 7 chosen |

### Grid core (still current)

| Doc | Topic |
|-----|-------|
| `docs/design/Grid/GRID_PRODUCT_DESIGN.md` | Product framing |
| `docs/design/Grid/GRID_CRATE_SPLIT_DESIGN.md` | Why the crate boundary lands where it does |
| `docs/design/Grid/GRID_UI_UX_DESIGN.md` | Target frontend UX (informs future `web/` work) |

### Generic engine (PRE-EAASP-v2 LEGACY — read with skepticism)

`docs/design/` (root level, **excluding** `EAASP/` and `Grid/` subdirs) contains ~60 design docs from 2026-02 to 2026-03 covering agent harness, context engineering, MCP, memory, sandbox, security, provider chain, etc. **These predate the EAASP v2 pivot (2026-04-13)** and are kept for archaeological reference only.

**Authoritative current sources (in priority order):**
1. ADRs at `docs/design/EAASP/adrs/ADR-V2-*.md` — single source of truth for all decisions
2. `docs/design/EAASP/*.md` — current EAASP-v2 design (L1 runtime, contract, deferred ledger)
3. `docs/design/Grid/*.md` — current Grid product framing
4. Code (always trumps stale docs)

**When a root-level `docs/design/*.md` disagrees with any of the above, the ADR/EAASP/Grid doc wins. Do not cite root-level docs as current architecture without first confirming against an ADR.**

---

## Behavioral Rules

**Absolute:**

- Do what has been asked; nothing more, nothing less.
- **Never** create files unless strictly required. Prefer editing over creating.
- **Never** proactively create docs (`*.md`) or READMEs unless asked.
- **Never** save working files, ad-hoc tests, or scratch markdown to the repo root.
- **Never** commit secrets, credentials, or `.env` files.
- **Never** run full test suites (`cargo test --workspace`, `make test`) unsolicited. Run only targeted tests for changed code. If a full run is needed, **ask first**.
- **Always** read a file before editing it (the Edit tool enforces this anyway).
- **Always** verify build succeeds before reporting work as complete.

**Code style:**

- Follow DDD with bounded contexts. Module boundaries already align with EAASP layers.
- Typed interfaces for all public APIs (`pub fn` / `pub struct`).
- Input validation at system boundaries (API, MCP tool invocations, CLI args, deserialization).
- TDD-London (mock-first) preferred for new engine / runtime code.
- Event sourcing for state changes where practical (see `grid-engine/src/event/`).
- File length: aim for <500 LOC; large files (`harness.rs`, `agent_loop.rs`) are accepted when refactoring would break cohesion — prefer extracting modules over arbitrary splits.

**File organization (project-specific, overrides none):**

| Kind | Location |
|------|----------|
| Rust source | `crates/<crate>/src/` |
| Rust tests | `crates/<crate>/tests/` (integration) or inline `#[cfg(test)]` (unit) |
| Python runtime source | `lang/<runtime>/src/<pkg>/` |
| Python runtime tests | `lang/<runtime>/tests/` |
| TS runtime source | `lang/ccb-runtime-ts/src/` |
| EAASP Python tools | `tools/eaasp-*/src/` |
| Proto | `proto/eaasp/runtime/v2/` |
| Design docs (Chinese) | `docs/design/{EAASP,Grid,AgentOS,claude-code-oss}/` |
| ADRs | `docs/design/EAASP/adrs/` (for EAASP) or `docs/adr/` (legacy generic) |
| Phase plans | `docs/plans/YYYY-MM-DD-<topic>.md` |
| Work log | `docs/dev/WORK_LOG.md` |
| Scripts | `scripts/` |
| Examples / fixtures | `examples/` and `tools/*/tests/fixtures/` |

---

## Security Rules

- Never hardcode API keys, credentials, or secrets in source. `.env` only.
- Validate all user input at system boundaries.
- Sanitize file paths (prevent directory traversal) — use `grid-engine/src/security/` helpers.
- Tool execution goes through `SecurityPolicy` + `CommandRiskLevel` + `ActionTracker` (autonomy tiers).
- When touching auth / crypto, check `ADR-003-API_KEY_HMAC.md` and `docs/design/EAASP/adrs/ADR-V2-XXX-*.md` first.

---

## Git Commit Guidelines

- Commit after meaningful work — **not** mechanically before `/clear`.
- **Always** commit after `/dev-phase-manager:end-phase` or `/checkpoint-progress`.
- Message body answers *why*, not *what* (the diff tells you what).
- Subject ≤72 chars; type prefixes: `feat:` `fix:` `chore:` `docs:` `refactor:` `test:` `perf:`.
- **Every commit message ends with**:
  ```
  Generated-By: Claude (claude-<model>) via Claude Code CLI
  Co-Authored-By: claude-flow <ruv@ruv.net>
  ```
- Before destructive operations (major refactor, branch switch), commit first.
- Use a HEREDOC for the message to preserve formatting:
  ```bash
  git commit -m "$(cat <<'EOF'
  subject line
  body
  EOF
  )"
  ```

---

## What Lives Where (global vs project)

Project CLAUDE.md (this file) — Grid-specific: crates, EAASP layers, env vars, Makefile, phase state, design-doc index.

Global `~/.claude/CLAUDE.md` covers everything that's not project-specific:
- Claude Code usage conventions (Context7, extended thinking, MCP priorities, verification tools)
- Language-agnostic behavioral rules
- Multi-agent orchestration guideline (scenario-based RuFlo guidance)
- Memory / feedback management
- General git + commit style
- Plugin/skill state-file discipline

Do **not** duplicate global content here. If you need something project-specific, add it here. If it's general Claude Code behavior, add it to global.

---

## Quick Pointers

- **Where is X?** — `git grep "X"` or Grep tool. `docs/design/EAASP/adrs/` for why.
- **How to run the full EAASP stack?** — `make dev-eaasp` (background services + log rotation under `.logs/latest/`).
- **How to certify a runtime?** — `make verify-dual-runtime` or the L1 adaptation guide §Certification.
- **What ADRs exist?** — `/adr:status` or `/adr:list`.
- **What phase am I in?** — `/dev-phase-manager:resume-plan` or `cat docs/plans/.checkpoint.json | jq '.phase_name, .completed_tasks | length'`.
- **Stale Django README at repo root?** — yes, that's a known cleanup item; ignore it.
