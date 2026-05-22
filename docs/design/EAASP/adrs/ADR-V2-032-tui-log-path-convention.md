---
id: ADR-V2-032
title: "TUI Log Path Convention (./logs/tui.log + GRID_TUI_LOG override)"
type: record
status: Accepted
date: 2026-05-22
accepted_at: 2026-05-22
phase: "Phase 5.5 — Interface ADR + Milestone Close"
author: "Jiangwen Su"
supersedes: []
superseded_by: null
deprecated_at: null
deprecated_reason: null
enforcement:
  level: strategic
  trace:
    - "crates/grid-cli/src/studio_main.rs::resolve_tui_log_path"
  review_checklist: "docs/design/EAASP/adrs/ADR-V2-032-tui-log-path-convention.md"
affected_modules:
  - "crates/grid-cli/src/studio_main.rs"
related:
  - ADR-V2-028
---

# ADR-V2-032 — TUI Log Path Convention (./logs/tui.log + GRID_TUI_LOG override)

**Status:** Accepted
**Date:** 2026-05-22
**Accepted At:** 2026-05-22
**Phase:** Phase 5.5 — Interface ADR + Milestone Close
**Author:** Jiangwen Su
**Related:** ADR-V2-028 (Strict-by-default Configuration Validation — both touch logging-related env-var convention)

---

## Context / 背景

2026-05-19 NEW-F1..F4 cascade hot-fix 期间, TUI log 路径从原先的
`dirs::data_local_dir()/grid/tui.log` (macOS: `~/Library/Application Support/grid/tui.log`)
**移到 `./logs/tui.log`** (cwd-relative). 原 hot-fix 在 `crates/grid-cli/src/studio_main.rs::resolve_tui_log_path`
保留了 `dirs::data_local_dir()` 作为 fallback (cwd 不可写时回落), 但实际上
**该 fallback 永远不会触发** — 因为前置代码用 `unwrap_or_else(PathBuf::from("."))`
保证了 `cwd_logs` 必然非空, `std::fs::create_dir_all(&cwd_logs).is_ok()` 在 99.99% 场景成立。
fallback 是 dead code。

Phase 5.4 closure 把 NEW-F4 (TUI log path ADR + dead-path delete) 列入 5.5 OOS inbox
(per CONTEXT D-06)。本 ADR 是 NEW-F4 的 ADR 部分; 配套的 dead-path delete 由 Phase 5.5
Plan 01 Task 01.B2 code change 完成 (`refactor(grid-cli): remove dead dirs::data_local_dir fallback`).

为何独立 ADR 而非合并到 V2-028 strict-config:
- V2-028 涵盖 **环境变量缺失 fallback** (no silent default), 是 config-validation 范畴。
- 本 ADR 涵盖 **文件路径 convention** (TUI log 的 SoT), 是 file-system convention 范畴。
两者都触及 logging infrastructure, 但 substance 不同, 各自独立 ADR 便于 future agents
查找 ("TUI 日志在哪" → V2-032; "config 缺失会发生什么" → V2-028)。

---

## Decision / 决策

### §1. TUI 日志路径约定

**Default path** (无 env override 时):

```
./logs/tui.log
```

— cwd-relative, 紧邻仓库根, 便于开发期 `tail -f` / AI agent inspect。
进程启动时 `std::fs::create_dir_all("./logs")` 自动创建目录, 失败也继续 (写入时再决定)。

**Override env**:

```bash
GRID_TUI_LOG=<absolute-path>   # 强制指定 TUI log 文件位置
```

— 一旦设置即覆盖 default, 不再走 cwd-relative 逻辑; 适合生产环境(把日志收到中央位置) /
secured filesystem (把日志写到加密分区) / CI 测试 (把日志写到 tmp_dir 隔离)。

**Deprecated path** (本 ADR 落盘后从代码中移除):

```
~/Library/Application Support/grid/tui.log   # macOS
~/.local/share/grid/tui.log                  # Linux
```

— 原 `dirs::data_local_dir()/grid/tui.log` fallback dead code; Phase 5.5 Plan 01
Task 01.B2 删除该分支, 仅保留 GRID_TUI_LOG override + ./logs/tui.log default。

### §2. Sanity print

`grid-studio --verbose` 在进入 alternate screen 前向 stderr 打印实际选用的路径:

```
[grid-studio] log: <resolved-path>
```

— 这是 V2-028 §D3 logging-filter strict-include 配对的 sanity message, 让 user 即时
确认日志写到哪 (否则进入 TUI 后 stdout/stderr 全部被 screen 接管, 无法 trace)。

### §3. `dirs` crate dep 保留

虽然 `studio_main.rs` 不再 用 `dirs::data_local_dir()`, 但 `crates/grid-cli/Cargo.toml`
的 `dirs` 依赖 **保留** — `crates/grid-cli/src/tui/formatters/path_shortener.rs:20,127`
仍使用 `dirs::home_dir()` 做 path-shortening (例如 `~/foo/bar` 显示替代 `/Users/.../foo/bar`)。
Cargo.toml 不动, 不需要 Cargo.lock 更新。

---

## Consequences / 后果

### Positive

- **开发期 iteration speed**: TUI log 紧邻仓库, AI agent / engineer 直接 `cat ./logs/tui.log`
  trace 问题, 不必绕到 `~/Library/Application Support/grid/tui.log`。
- **生产部署灵活**: `GRID_TUI_LOG` env 允许任意路径, 包括 secured 分区 / 中央 log
  collector / per-session tmp_dir。
- **代码 simpler**: 删 dead branch 后 `resolve_tui_log_path()` 从 19 行降到 13 行,
  没有 fallback fallback fallback 三层。
- **ADR-driven dead-code cleanup**: 本 ADR 配套的 Task 01.B2 code delete 给 future
  agents 一个"先 ADR 后 code delete" 的 pattern 示例 (与 Phase 5.4 ADR-V2-028 落盘 ↔
  code refactor 一致)。

### Negative

- **Stale logs 累积在 cwd**: `./logs/tui.log` 每次启动 append, 不自动 rotate; 长期 dev
  会累积 dozens of MB。Mitigation: `logs/.gitignore` 已覆盖该目录 (本 repo 已有), user 可
  手动 `rm ./logs/tui.log` 或 systemd timer 切割; 不在本 ADR scope。
- **Cwd-sensitive**: 用户在不同目录启动 `grid-studio` 会得到不同 log 路径; 这对 dev workflow
  ok, 但 surprise factor 真实存在。Mitigation: §2 sanity print 缓解 (启动时 stderr 打出实际路径)。
- **Override 是 single env-var, 不支持 rotate / compress**: 复杂 log 需求需用户外部工具
  (logrotate / pipe to compressor); 本 ADR 故意 keep simple。

### Risks

- **Cwd 不可写场景下日志丢失**: 极端场景 (e.g., user 在只读目录 like `/usr/bin/` 启动 grid-studio)
  原来的 `dirs::data_local_dir()` fallback 会救援, 删除后 TUI 仍能启动但 log 写入会
  silently fail。Mitigation: §1 sanity print 让 user 看到路径; user 可设
  `GRID_TUI_LOG=/tmp/grid-tui.log` 显式覆盖。频率 极低 (production 一般 cwd ≠ /usr/bin),
  接受。
- **GRID_TUI_LOG 设错路径会导致 TUI 启动失败**: 比如 `GRID_TUI_LOG=/dev/full` 或路径父
  目录不存在。Mitigation: V2-028 strict-config 原则 — 错配应 fail-fast 不应 silent;
  本 ADR 配套实装在 `init_logging_tui` 里 propagate error 而非 fallback。具体行为不属于
  本 ADR 范畴 (本 ADR 仅 record 路径 convention)。

---

## Affected Modules / 影响范围

| Module | Impact |
|--------|--------|
| `crates/grid-cli/src/studio_main.rs::resolve_tui_log_path` | 文档化 default + override + 弃用 fallback; Task 01.B2 code delete 配套 |

---

## Alternatives Considered / 候选方案

### Option A: `./logs/tui.log` default + `GRID_TUI_LOG` override (本 ADR 采纳)

**Pros**: 开发期 iteration 最快; 生产 deployment 通过 env override 灵活; 与 V2-028
strict-config 原则一致 (env 缺失 → fall back to documented default, 不 silent)。
**Cons**: cwd-sensitive (启动目录不同 log 位置不同); stale logs 累积。
**Verdict**: ✅ Accepted — 配 §2 sanity print 缓解 cwd-sensitive 副作用。

### Option B: 保留 `dirs::data_local_dir()` fallback (rejected)

**Pros**: cwd 不可写时仍能写入。
**Cons**: 99.99% 场景 dead code; 二级 fallback 复杂度污染 `resolve_tui_log_path()`;
违反 V2-028 strict-by-default 原则 (silent fallback)。
**Verdict**: ❌ Rejected — Task 01.B2 删除。

### Option C: `~/.grid/logs/tui.log` 集中化 (per GRID_GLOBAL_ROOT) (rejected)

**Pros**: 全局唯一日志位置, 不 cwd-sensitive; 跨 session 累积分析便利。
**Cons**: 与 GRID_GLOBAL_ROOT 语义耦合 (该路径用于 session/skill state, 不是 log);
开发期 `tail -f ~/.grid/logs/tui.log` 不如 `tail -f ./logs/tui.log` 简洁; 与现 hot-fix
方向 (cwd-relative) 不一致。
**Verdict**: ❌ Rejected — 通过 `GRID_TUI_LOG=$HOME/.grid/logs/tui.log` env override 可达成。

---

## References / 参考

- **ADR-V2-028 §D3 logging-filter strict-include** — 本 ADR §2 sanity print 是该 ADR 的配对实装位; 都是 logging infrastructure 严格化范畴
- **CLAUDE.md §LLM Provider Policy / feedback_no_fallback** — strict-by-default 原则的项目级 SoT, 本 ADR 服从该原则
- **Phase 5.5 Plan 01 Task 01.B2** — 配套 code delete (移除 `dirs::data_local_dir()` dead branch)
- **MEMORY.md "TUI log path"** — feedback 项已经记录 default + override 行为, 本 ADR 把 feedback 升格为 ADR

---

*Phase 5.5 — NEW-F4 closure (ADR portion); pairs with Task 01.B2 dead-path delete.*
