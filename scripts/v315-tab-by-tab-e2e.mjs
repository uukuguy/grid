// v315-tab-by-tab-e2e.mjs — Click every tab in order, capture:
//   - console errors per tab
//   - "Connection Lost" toast appearances
//   - WS connection attempts (excluding vite HMR)
//
// Goal: prove whether each non-Chat tab is really WS-disconnected-free
// after the Phase C.0.5 commit-17 fix.

import { chromium } from "/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/web/node_modules/playwright/index.mjs";

const WEB = "http://127.0.0.1:5180";
const TABS = [
  "Chat", "Tasks", "Schedule", "Tools",
  "Memory", "Debug", "MCP", "Collab", "Business Flows",
];
function log(...args) { console.log("[tab-by-tab]", ...args); }

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const allWsAttempts = [];
  page.on("websocket", (ws) => {
    const url = ws.url();
    if (url.includes("/?token=") || url.includes("/hmr")) return;
    allWsAttempts.push({ url, ts: Date.now() });
    log(`WS attempt → ${url}`);
  });

  log(`navigating to ${WEB}`);
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('div[id="root"] > *', { timeout: 5000 });

  const results = [];

  for (const tab of TABS) {
    // Snapshot console + DOM state, then click + collect diff.
    const consoleBefore = [];
    page.on("console", (m) => consoleBefore.push(`[${m.type()}] ${m.text()}`));
    const wsBefore = allWsAttempts.length;

    log(`\n=== clicking "${tab}" tab ===`);
    await page.getByRole("button", { name: tab, exact: true }).click();

    // Wait up to 3s for any reconnect cycle to settle.
    await page.waitForTimeout(3000);

    const bodyText = await page.evaluate(() => document.body.innerText);
    const hasConnectionLost = bodyText.includes("Connection Lost");
    const hasReconnecting = bodyText.includes("Attempting to reconnect");
    const newWs = allWsAttempts.slice(wsBefore);
    const toastCount = await page.evaluate(() =>
      document.querySelectorAll('[role="status"], .toast').length,
    );

    results.push({
      tab,
      newWsAttempts: newWs.length,
      hasConnectionLost,
      hasReconnecting,
      toastCount,
    });

    log(`  new WS attempts: ${newWs.length}`);
    for (const w of newWs) log(`    - ${w.url}`);
    log(`  "Connection Lost" toast present? ${hasConnectionLost}`);
    log(`  "Reconnecting" toast present? ${hasReconnecting}`);
    log(`  total visible toasts: ${toastCount}`);
  }

  // ── Final summary ──────────────────────────────────────────
  log("\n=== FINAL SUMMARY ===");
  log(`total non-HMR WS attempts across all 9 tabs: ${allWsAttempts.length}`);
  for (const r of results) {
    const flag = r.hasConnectionLost || r.hasReconnecting || r.newWsAttempts > 0;
    log(`  ${flag ? "✗" : "✓"} ${r.tab.padEnd(20)} new WS=${r.newWsAttempts} ConnLost=${r.hasConnectionLost} Reconn=${r.hasReconnecting}`);
  }

  await browser.close();
  process.exit(results.some((r) => r.hasConnectionLost || r.hasReconnecting) ? 1 : 0);
}

main().catch((err) => {
  console.error("[tab-by-tab] unexpected error:", err);
  process.exit(1);
});
