// @ts-nocheck — config file, not application code; node types not in web/ scope
import { defineConfig } from "@playwright/test";

/**
 * Playwright config for Phase 3.7.2 S7 dashboard E2E suite (REQ-WEB-06, D-03).
 *
 * The 3 S7 specs are hermetic — they use route interception and a mocked
 * backend, NOT a live grid-server. No LLM API key is required.
 *
 * If `WEB_BASE_URL` is set (e.g. by CI), use it; otherwise fall back to the
 * Vite dev server (http://127.0.0.1:5180 — see web/vite.config.ts).
 *
 * Browser binaries must be installed separately (`npx playwright install`).
 */
export default defineConfig({
  testDir: "./e2e",
  // Generous timeout because each spec intentionally waits for reconnect /
  // toast timing windows documented in the S7 walkthrough.
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  // Single worker — specs mutate global WebSocket / fetch state.
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: process.env.WEB_BASE_URL ?? "http://127.0.0.1:5180",
    trace: "retain-on-failure",
    video: "retain-on-failure",
    // Surface unexpected console errors as test failures (sentinel).
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  // No live backend. Specs use route interception; if the dashboard is
  // unreachable, tests will fail loudly with a clear network error rather
  // than silently skip.
  reporter: [["list"], ["html", { open: "never" }]],
});