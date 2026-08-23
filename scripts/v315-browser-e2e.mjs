// v315-browser-e2e.mjs — Real-browser end-to-end test for OBSTACK
// Phase C.0 dashboard. Uses Playwright + Chromium to:
//
//   1. Open http://localhost:5180 with chromium
//   2. Wait for App mount + TabBar render
//   3. Capture console messages (especially "[WS] Disconnected")
//   4. Verify default tab is "flows" (Business Flows), not "chat"
//   5. Verify NO "Connection Lost" toast appears on landing
//   6. Click "Business Flows" tab → verify flowsApi.list fired
//   7. Verify the business-flow cards rendered
//
// Why we need this (vs jsdom test in src/test/app-mount.test.tsx):
//   - jsdom mocks fetch + doesn't run real React effects
//   - Real browsers trigger different code paths (e.g. layout effects
//     in AppLayout that jsdom skips)
//   - The "Connection Lost" toast only renders in real DOM via
//     ToastContainer; jsdom doesn't render <ToastContainer> reliably
//
// Pre-conditions:
//   bash scripts/v315-web-dev.sh   # L4 + grid-server + web dev
//   bash scripts/v315-obstack-demo.sh   # seed sample flows
//
// Run: node scripts/v315-browser-e2e.mjs
// Exits 0 on success, non-zero on failure.

import { createRequire } from "node:module";

// Resolve Playwright from this worktree's web package, so the smoke test
// remains portable when the linked worktree has a different absolute path.
const require = createRequire(new URL("../web/package.json", import.meta.url));
const { chromium } = require("playwright");

const WEB = "http://127.0.0.1:5180";

function log(...args) { console.log("[browser-e2e]", ...args); }
function fail(msg) { console.error("[browser-e2e] ✗ FAIL:", msg); process.exit(1); }

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture every console message + every toast text that appears.
  const consoleMessages = [];
  const wsConnections = [];

  page.on("console", (msg) => {
    consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
  });
  page.on("pageerror", (err) => {
    consoleMessages.push(`[pageerror] ${err.message}`);
  });

  // Track WebSocket connection attempts.
  page.on("websocket", (ws) => {
    const url = ws.url();
    // Vite dev server's HMR uses its own WS endpoint (typically
    // "ws://host:port/?token=..."). That's expected and not our
    // concern — only flag WS to grid-server / our ws/manager.
    const isViteHmr = url.includes("/?token=") || url.includes("/hmr");
    if (isViteHmr) {
      log(`(skip HMR) WS → ${url}`);
      return;
    }
    wsConnections.push({ url, ts: Date.now() });
    log(`WS attempt → ${url}`);
    ws.on("close", () => log(`WS closed ← ${url}`));
  });

  // ─── 1. Open the dashboard ──────────────────────────────────
  log(`navigating to ${WEB}`);
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  // Wait for React to mount.
  await page.waitForSelector('div[id="root"] > *', { timeout: 5000 });
  log("App mounted");

  // Give the app a moment to settle (config fetch, WS attempts, etc).
  await page.waitForTimeout(2000);

  // ─── 2. Verify default tab = flows ───────────────────────────
  const activeTab = await page.evaluate(() => {
    // Find the active tab button in TabBar (it has bg-secondary class).
    const active = document.querySelector('button.bg-secondary');
    return active ? active.textContent : null;
  });
  log(`active tab button text: ${JSON.stringify(activeTab)}`);
  if (!activeTab || !activeTab.includes("Business Flows")) {
    fail(`expected default tab to be "Business Flows", got ${JSON.stringify(activeTab)}`);
  }
  log("✓ default tab is Business Flows");

  // ─── 3. Verify NO "Connection Lost" toast appeared on landing ─
  //     (real WS connection should not have been triggered)
  const landingToasts = await page.evaluate(() => {
    // toast text content lives in elements with the role=status or just
    // .toast class. Scan the DOM for known strings.
    const body = document.body.innerText;
    return {
      hasConnectionLost: body.includes("Connection Lost"),
      hasReconnecting: body.includes("Attempting to reconnect"),
      hasWebSocketDisconnected: body.includes("WebSocket disconnected"),
    };
  });
  if (landingToasts.hasConnectionLost || landingToasts.hasReconnecting || landingToasts.hasWebSocketDisconnected) {
    log("toasts found on landing:");
    log(JSON.stringify(landingToasts, null, 2));
    fail("toast leaked on landing page — default tab is still triggering ChatTab mount");
  }
  log("✓ no Connection Lost toast on landing");

  // ─── 4. Verify NO WS attempts were made ────────────────────
  if (wsConnections.length > 0) {
    log("WS connections attempted:");
    for (const c of wsConnections) log(`  - ${c.url}`);
    fail(`${wsConnections.length} WS connection(s) attempted on landing — should be 0`);
  }
  log("✓ 0 WS connections attempted on landing");

  // ─── 5. Click "Business Flows" tab → flowsApi.list fires ────
  log("clicking Business Flows tab");
  // Use exact: true so the click matches the TabBar button, not the
  // "Refresh business flows" icon button (whose aria-label contains
  // "business flows" as a substring).
  await page.getByRole("button", { name: "Business Flows", exact: true }).click();
  await page.waitForSelector('[aria-label="Refresh business flows"]', { timeout: 3000 });
  log("✓ FlowsPage mounted (Refresh button visible)");

  // Wait for flowsApi.list fetch to complete.
  await page.waitForTimeout(500);

  // Look for at least one business-flow card.
  const flowCards = await page.evaluate(() => {
    // The BusinessFlowCard uses aria-label="Business flow <key>".
    return document.querySelectorAll('[aria-label^="Business flow "]').length;
  });
  log(`business-flow cards rendered: ${flowCards}`);
  if (flowCards === 0) {
    fail("expected at least one business-flow card on FlowsPage — flowsApi.list may have failed");
  }
  log(`✓ ${flowCards} business-flow cards rendered`);

  // ─── 6. Verify derived operator stats are visible ─────────────
  const stats = page.getByLabel("Operator flow statistics");
  await stats.waitFor({ state: "visible", timeout: 3000 });
  const statsText = await stats.textContent();
  if (!statsText || !statsText.includes("total")) {
    fail(`expected operator statistics with a total, got ${JSON.stringify(statsText)}`);
  }
  log("✓ derived operator statistics visible");

  // ─── 7. Click a card → FlowsDetail panel mounts ──────────────
  // Use `button[aria-label^="..."]` to target the card button itself;
  // a bare `[aria-label^="..."]` matches the SECTION container too
  // (because aria-label is set on a descendant button), and clicking
  // the section doesn't fire the button's onClick.
  const card = page.locator('button[aria-label^="Business flow "]').first();
  await card.scrollIntoViewIfNeeded();
  await card.click();
  // Wait for React to re-render. The selectedFlowKeyAtom triggers
  // a re-render where FlowsDetail mounts in the right panel.
  // Poll for the close button up to 5s.
  let detailMounted = false;
  for (let i = 0; i < 50; i++) {
    const has = await page.evaluate(() =>
      !!document.querySelector('[aria-label="Close detail panel"]'),
    );
    if (has) { detailMounted = true; break; }
    await page.waitForTimeout(100);
  }
  if (!detailMounted) {
    // Debug: dump main text to see what happened.
    const debugText = await page.evaluate(() => document.body.innerText.slice(0, 500));
    log(`detail panel never mounted. body text: ${JSON.stringify(debugText)}`);
    fail("clicking a flow card did not mount the FlowsDetail panel");
  }
  log("✓ FlowsDetail panel mounted (Close button visible)");

  const liveIndicator = page.getByText("Live updates connected");
  await liveIndicator.waitFor({ state: "visible", timeout: 3000 });
  log("✓ live-update indicator visible");

  const optimizationGuidance = page.getByText("Optimization guidance");
  await optimizationGuidance.waitFor({ state: "visible", timeout: 5000 });
  log("✓ optimization guidance visible");

  // ─── 8. Sanity-check console (no JS errors) ───────────────────
  const errors = consoleMessages.filter((m) => m.startsWith("[error]") || m.startsWith("[pageerror]"));
  if (errors.length > 0) {
    log("console errors during e2e:");
    for (const e of errors) log(`  ${e}`);
    fail(`${errors.length} JS error(s) during e2e — first: ${errors[0]}`);
  }
  log("✓ 0 JS errors during e2e");

  // ─── Done ──────────────────────────────────────────────────
  log("ALL CHECKS PASSED ✓");

  await browser.close();
  process.exit(0);
}

main().catch((err) => {
  console.error("[browser-e2e] unexpected error:", err);
  process.exit(1);
});
