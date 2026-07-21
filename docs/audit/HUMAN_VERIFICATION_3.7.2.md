# Phase 03.7.2 — 人工验收步骤 (Human Verification Guide)

> 本文档给 Phase 3.7.2 web/ dashboard 实战可用性的人验路径。**所有自动化验证已完成**(vitest 26/26 PASS, Playwright 5/5 PASS, gsd-ui-auditor 8.83/10 ≥ D-09 8.5/10),但 self-recorded walkthrough 需要 live 后端 + LLM API key,无法在 executor 中执行。本文档列出人验命令与期望输出,你可以按步骤复跑。

## TL;DR 状态

| 维度 | 自动化 | 人验 |
|---|---|---|
| 单元测试 (vitest) | ✅ 26/26 PASS | (不需要人验) |
| E2E (Playwright hermetic) | ✅ 5/5 PASS | (不需要人验,后端无关) |
| UI 6-pillar audit | ✅ 8.83/10 PASS | (UI-SPEC §18.1 验证,inline 完成) |
| **Self-recorded walkthrough** | 🟡 BLOCKED | ⬅️ **需要你** |
| **非开发者实操** | 🟡 需要 live 后端 | ⬅️ **需要你** |

---

## 步骤 0 — 前置条件

需要 3 个 terminal:

```bash
# Terminal A: grid-server (Rust 后端,提供 REST + WS)
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox
make server
# 期望: grid-server listening on http://localhost:3001

# Terminal B: web dev server (Vite)
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox/web
npm run dev
# 期望: Vite ready in <300ms; http://localhost:5180

# Terminal C: LLM provider (env var)
export OPENAI_API_KEY=sk-...   # 或 ANTHROPIC_API_KEY=sk-ant-...
# 检查
curl -sf http://localhost:3001/api/health | jq
# 期望: { "status": "ok" }
```

> 如果 `make server` 失败,检查 `.env` 是否有 LLM API key(`cat .env | grep -E 'OPENAI|ANTHROPIC'`)。

## 步骤 1 — 一眼检查 (5 分钟,纯视觉)

打开浏览器到 **http://localhost:5180**。

### 验收清单
- [ ] 页面加载,无 console error (F12 → Console 标签)
- [ ] 顶部 TabBar 显示 8 个 tab:Chat / Tasks / Schedule / Tools / Memory / Debug / MCP / Collab
- [ ] **右下角看到 SessionControls**(fixed bottom-right):小绿点 + "Idle" 文字 + 没有 Stop button(因为没有 active session)
- [ ] **右下角看到 ConnectionStatus**(在 SessionControls 左边):绿色小条
- [ ] **Tabs 颜色一致** — 都是 `bg-secondary` 灰色背景,active tab 高亮
- [ ] **按钮圆角一致** — 圆角 + `px-2 py-1` 内边距,无突兀的大块
- [ ] F12 → Console 应**没有** "Failed to fetch config: 500" 错误(说明 `/api/v1/config` 200 OK)

### 期望
所有项目 ✅。如果 ConnectionStatus 红色 (Connection lost),说明 grid-server 没启或 WS 路径错了 → 回步骤 0。

## 步骤 2 — 触发一个真实 agent(10 分钟)

### 2.1 通过 grid-cli 启动 session

```bash
# Terminal D: 用 grid-cli quickstart 启动 S3 hook-governance scenario
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox
cargo build --release -p grid-cli
./target/release/grid quickstart S3
# 期望: S3 hook governance 场景运行,输出 agent 思考 + tool calls
```

### 2.2 观察 dashboard

回到浏览器,**右下角 SessionControls** 应该:
- 出现 Stop button(visible only when running,per REQ-WEB-03)
- 显示 `Stop session <session-id 前 8 位> (⌘.)` 或 `(Ctrl+.)`
- 旁边有 pulse dot 在闪烁 (live indicator)

### 2.3 验证事件流

点击 **Tasks** tab:
- [ ] 看到 running task 行的 Stop icon 按钮(`aria-label="Stop task <id 前 8 位>"`)
- [ ] 点击 Stop icon → 任务被取消,后端 DELETE `/api/v1/tasks/:id` 调用
- [ ] 任务行消失或 status 变更

点击 **Memory** tab:
- [ ] 页面 header 右侧有 cyan "Live" badge + 小 pulse dot
- [ ] 当 agent 写入 memory 时,新行出现并**临时高亮**(cyan background fade)
- [ ] 同时右下角弹出 cyan toast "Memory written" + "Stored: <content>..." (4000ms 自动消失,可手动关闭)

### 2.4 验证 stop / resume

- [ ] 在 Chat tab 输入一条消息(例如 "列出项目根目录的文件"),发送
- [ ] agent 开始 streaming → 右下角 Stop button 显示
- [ ] 点击 Stop button → 1-2 秒内 UI 切换为 stopped 状态
- [ ] Resume button 显示(替代 Stop)
- [ ] 点击 Resume → 重新 streaming

## 步骤 3 — 验证 WS reconnect(5 分钟)

### 3.1 杀掉 grid-server

回到 Terminal A(grid-server running),按 `Ctrl+C` 杀掉。

### 3.2 观察 UI

- [ ] ConnectionStatus 变红 "Connection lost"
- [ ] SessionControls 显示 "Reconnecting... (N)"(N=1,2,3,4,5)
- [ ] 5 次尝试后,UI 给出 "Disconnected — refresh the page to reconnect" toast

### 3.3 重启 grid-server

```bash
# Terminal A
make server
# 等待 3 秒,UI 应自动重连
```

- [ ] ConnectionStatus 变回绿色
- [ ] SessionControls 回到 idle 状态

## 步骤 4 — 验证 sequence number debug mode(可选,2 分钟)

打开 **http://localhost:5180/?debug=1**

- [ ] F12 → Console 应看到 WS message 序号日志 `seq=N`
- [ ] (高级) 触发 WS frame 失序不会破坏 UI(测试时断 WS server 立刻重连)

## 步骤 5 — 验证 prefers-reduced-motion(可选,2 分钟)

macOS: System Settings → Accessibility → Display → Reduce motion → ON

刷新页面:
- [ ] 工具调用行的 transition 应该静止
- [ ] Live indicator 不再 pulse

关闭 Reduce motion,刷新,确认 pulse 恢复。

## 步骤 6 — 复跑 Playwright 套件(可选,自动化)

```bash
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox/web
npx playwright test --reporter=list
# 期望: 5 passed (E1 Tasks + E1 SessionControls + E2 memory toast + E3 ws reconnect + E3 debug=1)
```

注:本套件是 hermetic(不需要 grid-server),但 dev server 需要在跑。

## 步骤 7 — 复跑 vitest(可选,自动化)

```bash
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox/web
npm run test
# 期望: Test Files 4 passed (4); Tests 26 passed (26)
```

## 验收总结

| # | 检查项 | 结果 |
|---|---|---|
| 1 | 浏览器加载 + 无 console error | ☐ |
| 2 | TabBar 8 tabs + SessionControls + ConnectionStatus 全部在右下角 | ☐ |
| 3 | 启动 grid quickstart S3 后,SessionControls Stop button 显示 | ☐ |
| 4 | Tasks tab Stop icon 工作(DELETE /api/v1/tasks/:id) | ☐ |
| 5 | Memory tab Live badge + 新行高亮 + cyan toast | ☐ |
| 6 | Stop / Resume button 工作 | ☐ |
| 7 | 杀 grid-server → 重连 5 次尝试 → 重启后自动恢复 | ☐ |
| 8 | `?debug=1` 显示 WS seq | ☐ |
| 9 | Reduce motion 关闭 transition | ☐ |
| 10 | Playwright 5/5 PASS | ☐ |
| 11 | vitest 26/26 PASS | ☐ |

**全部 ✅ = Phase 3.7.2 完整收口。**

如果有任何 ❌,把出错截图 + F12 console 日志 + 复跑步骤贴出来,作为 Phase 3.7.2.1 修复 task。

---

## 相关文件

- `docs/audit/3.7.2-GAP-AUDIT.md` — 480 行 audit doc,8×5 matrix
- `docs/cli/scenarios/S7-web-dashboard.md` — non-developer walkthrough 模板
- `docs/status/WEB_PRODUCTION_USABILITY_2026-07-20.md` — dated evidence record(327 行)
- `docs/design/web-ui-tokens.md` — design token SSOT(261 行)
- `web/src/components/SessionControls.tsx` — 旗舰组件(215 行)
- `.planning/phases/03.7.2-web-production/03.7.2-VERIFICATION.md` — verification report(本 phase)

---

*Phase: 03.7.2-web-production*
*Document: HUMAN_VERIFICATION_3.7.2.md*
*Author: Claude (claude-opus-4-8) via Claude Code CLI*

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI
Co-Authored-By: claude-flow <ruv@ruv.net>
EOF