# Journal — append-only event log

> One line per commit / verified result / dropped path. Never edit past lines.
> Format: `## YYYY-MM-DD` date headers, then `- HH:MM <fact> [commit hash if any]`

## 2026-07-25
- 现在确认 v3.8.0–v3.8.3 已全部完成，v3.8 已归档；旧 RESUME baton 曾错误指向 v03.8.3。
- 已重建 lightweight-memory 结构快照与索引，后续讨论从下一 milestone 边界开始。

## 2026-07-26
- 启动 v3.10 EAASP v2.0 平台骨架对齐 milestone。
- v3.10 milestone bootstrap 已 fast-forward 集成到 main [b0d4502e]。
- v3.10 EAASP v2.0 平台骨架对齐已 SHIPPED，main 推进到 179a15a1，tag v3.10 已建立；174 targeted tests PASS。
- v3.11.0 OPA sidecar 基础设施已 SHIPPED，ADR-V2-034 Accepted，make opa-install 可用，V310-OPA-01 已 CLOSED [84ca0a11]。
- v3.11.1 L3 OPA backend adapter + Rego templates 已 SHIPPED (OPABackend.evaluate + 5 fail-closed modes; 57/57 tests PASS; ADR-V2-023 P1 unchanged) — [2acbf62a] + ADR/STATE/REQUIREMENTS sync [4fe41955]。
- v3.11.1 security review 3 issues fixed (Issue 1 /v1/evaluate session binding; Issue 2 bidirectional allow↔decision invariant; Issue 3 URL guard + sanitized origin) — [6338d376]。

## 2026-07-28
- v3.14 EAASP Phase 6 — Ontology/Marketplace/SDK bootstrap (EVO final phase) on main [b878e7b2]
