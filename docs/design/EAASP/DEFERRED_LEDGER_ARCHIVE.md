# DEFERRED_LEDGER_ARCHIVE

> 此文件不可再追加, 仅作历史归档。
> 如果一个 DEAD row 之后需要重新激活, 必须以新 NEW-* row 形式在 main LEDGER 中重生, 不在此文件追加。

**Total DEAD rows migrated**: 8
**Migration timestamp**: 2026-05-26
**Migrated from**: `docs/design/EAASP/DEFERRED_LEDGER.md` @ commit `9842dda` (TRIAGE-01 — main-namespace classification pass)
**Migrated by**: Phase 6.2 Plan 01 Task 2 (TRIAGE-02) @ commit `<self-hash>` (this commit; placeholder filled by sed-replace commit 2)
**Bidirectional cross-ref**: this commit hash filled by commit 2 (sed-replace); LEDGER §状态变更日志 cites this commit hash in entry below

**Triage criteria applied** (per Phase 6.2 CONTEXT.md D-02):

- DEAD-(a) octo-leftover: row references `octo_*` / `OctoHookPlugin` / pre-Phase-BA naming removed 2026-04-04
- DEAD-(b) deleted-code: row points at file/module no longer in HEAD
- DEAD-(c) ADR-superseded: row's intent nullified by an Accepted ADR
- DEAD-(d) dormant-by-ADR: row depends on capability ADR explicitly marks dormant

**DEAD distribution by criterion (this archive)**:
- DEAD-(c) ADR-superseded: 5 rows (D27, D35, D40, D66, D88)
- DEAD-(d) dormant-by-ADR: 3 rows (D62, D63, D64)
- DEAD-(a) / DEAD-(b): 0 rows

---

## Archived rows

| ID | 标题 | 处理位置 | 影响 |
|----|------|---------|------|
| **D27** | L4 session_orchestrator `Initialize`/`Send` 占位 | [DEAD-archived] 🔄 superseded by D54 rationale: Row reads '🔄 superseded by D54'; D54 closed Phase 0.5 S1 per ADR-V2-004; DEAD-(c) ADR-superseded | ADR-V2-004 精化 |
| **D35** | L4 无 WebSocket / SSE event streaming | [DEAD-archived] 🔥 P0-active rationale: Row reads '🔥 P0-active' but body says '合并到 D84 S4.T2'; D84 closed Phase 0.5 S4.T2 @ `bd55bc4`; DEAD-(c) ADR-superseded via D84 merge | **合并到 D84 S4.T2** |
| **D40** | L4 `sessions.status` 三态机未实现 | [DEAD-archived] 🔄 superseded by D54 rationale: Row reads '🔄 superseded by D54'; D54 closed Phase 0.5 S1 per ADR-V2-004; DEAD-(c) ADR-superseded | — |
| **D62** | Per-session tool-sandbox container lifecycle | [DEAD-archived] 🔴 phase3-gated rationale: ADR-V2-024 §1 双轴 model — Sandbox Tiers tier-3 never built and grid-platform dormant under 双轴 framework; DEAD-(d) dormant-by-ADR | Sandbox Tiers 未就绪 |
| **D63** | Tool-sandbox 通用基础镜像 + OCI artifact | [DEAD-archived] 🔴 phase3-gated rationale: ADR-V2-024 §1 双轴 model — Sandbox Tiers OCI artifact never built; per D62 dormancy; DEAD-(d) dormant-by-ADR | 与 D62 |
| **D64** | T0/T1 runtime 工具容器化 | [DEAD-archived] 🔴 phase3-gated rationale: ADR-V2-024 §1 双轴 model — T0/T1 runtime containerization never built; per D62 dormancy; DEAD-(d) dormant-by-ADR | 与 D62 |
| **D66** | hermes 内置工具与 MCP monkey-patch | [DEAD-archived] ⏸️ frozen rationale: ADR-V2-017 §hermes 冻结决策 'lang/hermes-runtime-python/ 立即冻结, 不再投入修复 D88 / fork 崩溃' — hermes Frozen, replaced by goose + nanobot; DEAD-(c) ADR-superseded | ADR-V2-017 hermes 冻结 → goose 替代 |
| **D88** 🚨 | hermes-runtime stdio MCP 缺失 | [DEAD-archived] ⏸️ frozen / superseded rationale: ADR-V2-017 §hermes 冻结决策 'lang/hermes-runtime-python/ 立即冻结, 不再投入修复 D88 / fork 崩溃' — D88 explicitly cited as one of the 5 abandoned issues; DEAD-(c) ADR-superseded | ADR-V2-017 → Phase 2.5 goose |

---

*Closed-text archive. New DEAD discoveries must be reborn as NEW-* rows in main LEDGER, not appended here.*
