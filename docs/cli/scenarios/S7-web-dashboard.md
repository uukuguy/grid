# S7: Web dashboard production usability walkthrough

> **Scenario ID:** S7
> **Audience:** Non-developer observer (CTO, lead, evaluator). Goal: open the
> dashboard, observe a running agent, see its tool calls, see its memory
> writes, and stop/resume it — **without devtools**.
> **Acceptance marker (CONTEXT.md D-09, D-07):** Every event surface is visible
> on the dashboard; no browser devtools required.

## Prerequisites

- `grid-server` running on `http://127.0.0.1:3001` (default)
- `grid-cli` available locally (`cargo build -p grid-cli --release`)
- One of `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` exported (any provider grid-server
  accepts)
- A web browser pointing at the dashboard dev server (or built static bundle)

```bash
# Build the web dashboard
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox/web
npm run dev   # Vite dev server on http://127.0.0.1:5180

# In a separate shell, start grid-server
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox
cargo run -p grid-server --release
```

> **Note**: this walkthrough intentionally uses the **dashboard dev server**
> (`npm run dev`) and a **locally-running grid-server** (port 3001). No LLM
> live API key is *required* for the dashboard-only hermetic verification —
> the 3 S7 Playwright specs use route interception (see "Acceptance evidence"
> below).

## Walkthrough steps (non-developer path)

### Step 1 — Open the dashboard

1. Visit `http://127.0.0.1:5180` in your browser.
2. You should see the **Grid dashboard** with the chat tab open.
3. Bottom-right, you should see a **live indicator** (green dot) and a
   **"+ New session"** pill in the top session bar.

### Step 2 — Start an agent

1. Click `+` (New session) in the top session bar. The bar updates with the
   new session id pill.
2. Switch to the **Tasks** tab (left nav rail, second icon).
3. Enter a prompt like `Summarize docs/cli/QUICKSTART.md and store 3 facts
   in memory.`
4. Click **Send task** (action-specific label per UI-SPEC §11.1; previously
   "Submit").
5. The Tasks page should show the new task with status `running`.

### Step 3 — Observe running agent (no devtools)

1. Look at the **bottom-right live indicator**: it should now be **pulsing
   blue** (`bg-primary animate-pulse`). This signals the agent is streaming.
2. **Stop button** appears in the bottom-right corner (replaces the idle
   dot). The label reads `Stop`.
3. Press `Cmd+.` (macOS) or `Ctrl+.` (other). The keyboard shortcut fires
   the same Stop handler.

### Step 4 — See tool calls (in real time)

1. Switch to the **Tools** tab (icon: hammer). Tool calls the agent makes
   appear as rows here in real time.
2. Switch to the **Debug** tab (icon: bug). The **Live Event Stream**
   sub-panel shows the same tool calls in chronological order with full
   input/output payloads.

### Step 5 — See memory writes (new in Phase 3.7.2)

1. Watch the **bottom-right corner**. When the agent writes a memory, a
   cyan **"Memory written"** toast appears for 4 seconds with the message
   `Stored: {first 60 chars of memory content}…`.
2. Switch to the **Memory** tab (icon: brain).
3. In the **Persistent Memory** sub-tab, the newly-added memory appears at
   the top with a cyan-tinted background (`bg-cyan-950/30`) that fades after
   ~4.5 seconds.
4. The page header shows a **Live** badge (green dot + "Live" text) — this
   is proactive disclosure that the page auto-updates.

### Step 6 — Stop the agent

1. Click the **Stop** button in the bottom-right corner (or use `Cmd+.` /
   `Ctrl+.`).
2. Within ~500ms the live indicator stops pulsing and turns red.
3. A **Resume** button appears in place of the Stop button.
4. If Stop fails (network error or 4xx/5xx), an error toast
   `Failed to stop — Try again, or refresh the page.` appears and the prior
   state is restored.

### Step 7 — Resume the agent

1. Click **Resume** in the bottom-right corner.
2. The live indicator resumes pulsing blue.
3. If Resume fails, an error toast `Failed to resume — Try again, or
   refresh the page.` appears.

### Step 8 — Server restart resilience

1. With the dashboard open and the agent streaming, **kill grid-server**
   (e.g. `pkill -f grid-server`).
2. The dashboard's connection status indicator turns red and shows
   "Disconnected".
3. The WebSocket manager retries up to **5 times** with exponential backoff
   (1s, 2s, 4s, 8s, 16s; cap 30s).
4. Every reconnect attempt carries the **same `session_id`** query param.
5. After ~31 seconds total, if the server is still down, the manager gives
   up and shows `Disconnected` permanently.
6. **Restart grid-server**. Within 1-16s of restart, the manager reconnects
   automatically with the same `session_id`.
7. Open the dashboard with `?debug=1` (`http://127.0.0.1:5180/?debug=1`)
   to see sequence-gap logs in the browser console (e.g.
   `WS sequence gap: expected 12, received 14`).

## Expected visible behavior (acceptance checklist)

- [ ] Stop button is visible on every tab (not just chat).
- [ ] Stop button click POSTs `/api/v1/sessions/:id/kill` (visible in
      Network tab — not required for acceptance, just for verification).
- [ ] Within 2 seconds the live indicator transitions from pulsing blue to
      steady red (UI-SPEC §9.1).
- [ ] Memory written toast appears within 1 second of a `memory_added`
      event and is dismissible (UI-SPEC §9.2).
- [ ] Memory page updates in real time without manual refresh; new rows
      have a cyan highlight pulse for ~4.5s.
- [ ] Cmd+. (macOS) / Ctrl+. (other) triggers Stop.
- [ ] Reconnect attempts preserve `session_id` and respect the 5-attempt
      cap (visible only via Network tab or programmatic verification).

## No-devtools acceptance

A non-developer observer can complete the full S7 walkthrough using **only
mouse clicks and the keyboard shortcut Cmd+./Ctrl+.** No browser devtools
intervention is required at any step.

## Acceptance evidence (automated)

The 3 S7 Playwright specs in `web/e2e/` provide hermetic coverage of the
core flows. They use **route interception** (no live grid-server) and
**WebSocket class mocking** (no live WebSocket):

| Spec | Covers | File |
|------|--------|------|
| **E1** | Tasks page Stop + SessionControls global Stop | `web/e2e/S7-stop-resume.spec.ts` |
| **E2** | Memory toast emission + content | `web/e2e/S7-memory-toast.spec.ts` |
| **E3** | WS reconnect preserves `session_id`; `?debug=1` seq logging | `web/e2e/S7-ws-reconnect.spec.ts` |

Run them with:

```bash
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox/web
npx playwright test --config=playwright.config.ts e2e/
```

## Known gaps (out of scope this phase)

- **Multi-tenant (web-platform/)** — still a future milestone.
- **Server-side `memory_added` broadcast** — owned by grid-server team;
  the client (`web/`) is forward-compatible: if the server starts
  broadcasting `memory_added`, the toast + highlight pulse surface
  automatically. If not, the handler is a no-op.
- **Task-level resume** — Tasks page exposes a Resume button only as a
  warning toast ("Tasks cannot be resumed — re-submit if needed."), per
  REQ-WEB-07 which treats `DELETE /api/v1/tasks/:id` as graceful cancel
  rather than true pause/resume.

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI
Co-Authored-By: claude-flow <ruv@ruv.net>