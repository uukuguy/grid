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
