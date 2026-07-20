---
type: handoff
date: 2026-07-20
author: Claude (claude-opus-4-8) via Claude Code CLI
from_session: 2026-07-19/20 (unified grid CLI + Makefile trim + USER_GUIDE + UI-SPEC)
to_session: next
---

# Session Handoff — 2026-07-20

## TL;DR

本 session 完成了 **3 个 product-decision 工作**,全部 SHIPPED + 10 commits pushed to `main`(未推 origin,本地领先 10 commits)。**所有改动都验证过**(cargo check + 175 grid-cli tests + 51 grid-engine mcp tests + cargo build --release)。

## 本 session 完成的工作

### 1. grid-cli USER_GUIDE.md (1144 行)
- Commit `08ea6510`:综合用户手册,覆盖全部 17 commands + 2 Studio + 9 global flags + 6 env groups
- 后续修订 commit `0d5f2c77`:补充 `grid` vs `grid-studio` 二进制边界说明(在 Phase 3.7.5 合并前)
- 后续 commit `0d5f2c77`:USER_GUIDE 在 Phase 3.7.5 合并后已简化(删 §5.18 警告块)

### 2. Phase 3.7.5 — Unify grid CLI entry point (合并 grid + grid-studio)
- 删除 `crates/grid-cli/src/studio_main.rs`
- `Cargo.toml` 删除 `[[bin]] grid-studio`、删除 `studio` feature、保留 `dashboard-tls`、`full = ["grid-engine/full", "dashboard-tls"]`
- `Commands` enum 加入 `Tui` 和 `Dashboard` variants,统一 `src/main.rs` 处理
- `Makefile` 添加 `make tui` / `make dashboard` aliases
- **用户视角**:`./target/release/grid tui` 直接工作,不再需要 `grid-studio` binary
- Commit:`0f2baa28`(7 files, +197/-136)

### 3. Phase 3.7.6 — Makefile trim (瘦身)
- 5 个 atomic commits,删除 ~635 行 / 61 dead targets
- 删除类别:`studio`/`build-studio` (Phase 3.7.5 合并)、legacy Chinese help block、container-*、docker-* legacy、claude-runtime/goose-runtime/hermes-runtime (EAASP L1 dormant + hermes FROZEN per ADR-V2-017)、certifier + sdk、L3/L4 + Phase 2/3 contract (历史 frozen)、eval-* (被 `grid eval` CLI 替代)、build-cli-full duplicate
- 重新生成 `.PHONY` 声明:137 → 74 有效条目,清理 85 个 broken refs
- 最终:Makefile 1215 → 580 行 (-52%),targets 135 → 74 (-45%)
- Commits:`88fe842b`(checkpoint), `8f8ae929`(batch 1), `7fe009bf`(batch 2), `a0b0645c`(batch 3-10), `00e5c1da`(help text fix), `7336c3a6`(full feature clarification)

### 4. Phase 3.7.2 启动准备 (前置工作)
- `812ffb02`:Phase 3.7.2 CONTEXT.md(D-01..D-08)
- `2cb53820`:D-09/D-10 加 UI 设计质量要求
- `eaac0bd4`:UI-SPEC.md(1197 行,通过 gsd-ui-checker 7/7 维度验证,0 blockers)

## 仓库当前状态

```
Branch: main
Commits ahead of origin/main: 10
Working tree: clean (untracked: 4 planning artifact files from Phase 3.7.1)

Last 5 commits:
7336c3a6 chore(Makefile): clarify 'full' feature composition + flag Phase 3.7.7
00e5c1da chore(Makefile): update help text — accurate advanced target count
a0b0645c chore(Makefile): batch 3-10 — trim 542 lines, 135→74 targets
7fe009bf chore(Makefile): batch 2/9 — remove legacy Chinese help block
8f8ae929 chore(Makefile): batch 1/9 — remove build-cli-full (duplicate of release)
```

**未 push**(用户在 phase 3.7.1 SHIPPED 后未继续 push,累积 138 commits 的旧债未推)。

## 下次 session 的建议优先级

### **优先级 1:Phase 3.7.2 web/ plan + execute (用户最高优先级)**

**入口**:`$gsd-plan-phase 3.7.2 ${GSD_WS}`

**已就绪的工件**(无需重做):
- `.planning/phases/03.7.2-web-production/3.7.2-CONTEXT.md` — D-01..D-10 锁定
- `.planning/phases/03.7.2-web-production/03.7.2-UI-SPEC.md` — 1197 行,通过 UI 检查器
- `.planning/phases/03.7.2-web-production/3.7.2-DISCUSSION-LOG.md`

**Phase 3.7.2 范围**:
- Plan 01 (audit): 8 pages × 5 events matrix → `docs/audit/3.7.2-GAP-AUDIT.md`
- Plan 02 (fix + tests + walkthrough): SessionBar 提升为全局控制器 + memory toast + tool-call ordering + S6 e2e tests
- 验收:`gsd-ui-auditor` ≥ 8.5/10 + self-recorded S3 walkthrough

**预估**:2-4 小时,2-3 plans。

### **优先级 2:Phase 3.7.7 — 移除 `full` feature (清理 Makefile 中已标记的 TODO)**

**触发**:用户在 Makefile trim 后指出 `full` feature 是 Cargo 抽象,不应该硬塞进 Makefile target 命名。已在 commit `7336c3a6` 加 TODO 注释。

**范围**:
- `crates/grid-cli/Cargo.toml`:删除 `full` feature,只保留 `dashboard-tls` 和任何必要的子 features
- `crates/grid-engine/Cargo.toml`:展开 `full` 子 features(如果需要,改成 `wasm` + `docker` + `pdf` 独立 feature)
- Makefile:`build-full` 改名为 `build-tls`(或 `build-sandbox` 等,按实际语义)
- `make release` 改成 `cargo build --release --features tls`(显式声明)

**预估**:30-60 分钟,跨 2-3 个 Cargo.toml 文件 + Makefile。

### **优先级 3:Phase 3.7.2 web/ 完成后,Phase 3.7.3 EAASP simulation**

**预判**:per user priority 2026-07-19 "先把单用户的 grid-cli/grid-web/EAASP仿真做好",EAASP 是第三顺位。

**范围**:Phase 0-2.5 已 SHIPPED,Phase 3-6 是 dormant reference implementation。Phase 3.7.3 需要 wire minimum credible governance gate hooks(per ROADMAP §3.7.3)。

### **优先级 4:CI 重启(目前 Contract CI 6-17 后断)**

**事实**(已审计):
- Evaluation CI 活跃(79 runs,最近 17 天每天跑)
- Phase 3 Contract Matrix 6-17 后断
- Phase 2.5 Contract Matrix 6-17 后断
- Release / Desktop / Container / Phase 4a sync 长期断

**建议 scope**:瘦身后 Makefile 包含核心 target(`make check` / `make build-cli` / `make cli-doctor`)→ 接 CI workflow → 修复 Contract CI 失败。这是个独立 phase,跟产品迭代可以并行。

## Open Question(下次 session 决策)

### Q1: 10 commits 是否 push?
本 session 累积 10 commits 未 push。用户 Phase 3.7.1 SHIPPED 后未继续 push(累积 138 unpushed 历史)。下次 session 启动时建议:
- 一次性 push 所有 10 commits:`git push origin main`
- 或 review 后分批 push

### Q2: Phase 3.7.2 是否值得规划 walkthrough?
per Phase 3.7.1 模式(USER_GUIDE.md + S1-S6 walkthrough docs),Phase 3.7.2 完成后是否要 S7-web-dashboard walkthrough?

### Q3: Makefile 中 `help-full` 是否实际需要?
目前 `help-full` 用 `make -p` grep,实际意义不大。可以删掉或替换为更友好的 listing。

## 关键文件引用 (按访问频率排序)

| 文件 | 用途 | 最近修改 |
|---|---|---|
| `crates/grid-cli/src/main.rs` | 统一 grid 入口,处理 19 个 subcommands | `0f2baa28` |
| `crates/grid-cli/src/lib.rs` | Commands enum + 共享模块导出 | `0f2baa28` |
| `crates/grid-cli/Cargo.toml` | features + bins 配置 | `0f2baa28` |
| `crates/grid-desktop/Cargo.toml` | 移除 `studio` feature 依赖 | `0f2baa28` |
| `Makefile` | 580 行,74 个 active targets | `7336c3a6` |
| `docs/cli/USER_GUIDE.md` | 1144 行综合手册 | `0d5f2c77` (后续会被 Phase 3.7.5 后的内容再修订) |
| `.planning/phases/03.7.2-web-production/03.7.2-UI-SPEC.md` | 1197 行,UI 设计 contract | `eaac0bd4` |
| `.planning/phases/03.7.2-web-production/3.7.2-CONTEXT.md` | D-01..D-10 locked decisions | `2cb53820` |
| `.planning/phases/03.7.1-grid-cli/3.7.1-CONTEXT.md` | Phase 3.7.1 上下文(D-01..D-08 全部 SHIPPED) | (committed) |
| `docs/audit/3.7.1-GAP-AUDIT.md` | Phase 3.7.1 audit,REQ-AUDIT 9/9 closed | (committed) |

## 验证状态(可重现运行)

```bash
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox
cargo check --workspace                           # 0 errors
cargo test -p grid-cli --tests                    # 175/175 PASS
cargo test -p grid-engine --lib mcp              # 51/51 PASS
cargo build --release --bin grid --features full # 46MB binary
./target/release/grid tui --help                  # ✓ works (Phase 3.7.5 unification)
./target/release/grid dashboard --help            # ✓ works
make help                                          # 47-line curated output
```

## Memory 状态

`.planning/memory/` 目录 — 当前 session 写入的 memory 文件:
- 本 handoff 文档(本文件)
- Phase 3.7.1 + 3.7.5 + 3.7.6 完成记录(committed commits)
- Phase 3.7.2 CONTEXT + UI-SPEC(可重用工件)

未写入 cross-session memory 条目:
- 用户的命名简洁偏好(make target 名应自解释,不绑 Cargo feature 名)
- Makefile 文档化习惯(每个 target 上方注释说明 feature 组合)

下次 session 启动时如果希望保留这些用户偏好,可以写入 `~/.claude/projects/.../MEMORY.md`。

---

*Handoff complete. Resume with `$gsd-progress ${GSD_WS}` to see state, or `/gsd-plan-phase 3.7.2 ${GSD_WS}` to start Phase 3.7.2 web/ planning.*
