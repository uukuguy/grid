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
- v3.11.2 5-stage approval state machine + 5 governance.approval.* SSE events 已 SHIPPED，V310-APPROVAL-01 已 CLOSED [c92513ca]。
- v3.11.3 single-point live walkthrough 已 SHIPPED，SSE/OPA/audit 完整证据 PRODUCTION_USABILITY_2026-07-27，tag v3.11 已建立 [c3d1d789]。
- v3.12 milestone bootstrap 已 commit (EAASP Phase 4 A2A Router + Event Room + multi-session) [ba99b851]。
- v3.12.0 audit.py CHECK constraint patch 已 SHIPPED，V311-AUDIT-01 已 CLOSED [c8a5d391]。
- v3.12.1 Event Room + multi-session 已 SHIPPED，5 轮 security review 关闭 9 个问题 [a248d73a]。
- v3.12.2 A2A Router + ReviewSet + 冲突检测已 SHIPPED，3 个 HIGH security fix 关闭，ADR-V2-035 Accepted [815ab12b]。
- v3.12.3 single-point live walkthrough 已 SHIPPED，10+ SSE 事件完整证据，tag v3.12 已建立 [894639dd]。
- v3.13 milestone bootstrap (EAASP Phase 5 L5 Cowork 四卡 + 回溯闭环) on main [ddd83337]。
- v3.13 L5 Cowork 四卡 + retrospective cycle 已 SHIPPED，82/82 tests PASS，V310-COWORK-01 已 CLOSED，tag v3.13 已建立 [d0d83a23]。
- 21:09 v3.14 Phase 6 (Ontology / Marketplace / Skill ecosystem) 已 SHIPPED，66/66 tests PASS，2 轮 security review (3 CRITICAL+1 HIGH) 关闭，V310-ECOSYSTEM-01+V310-MAT-01 已 CLOSED [05074170]；EVOLUTION_PATH 8-Phase 路线全 SHIPPED。
