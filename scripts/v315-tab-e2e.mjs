// v315-tab-e2e.mjs — Reproduce the user's "switch tabs still Connection
// Lost" report. Sequence:
//   1. Open dashboard at /flows (default tab)
//   2. Wait, observe console
//   3. Click "Chat" tab
//   4. Wait, observe console — does wsManager.connect() fire?
//   5. Click "Memory" tab
//   6. Wait, observe console
//   7. Report all WS connections + console errors observed
//
// Goal: prove whether ChatTab mount on click triggers the same
// "Connection Lost" loop the user reported.

import { chromium } from "/Users/sujiangwen/sandbox/LLM/speechless.ai/SGAI/grid-sandbox/web/node_modules/playwright/index.mjs";

const WEB = "http://127.0.0.1:5180";
function log(...args) { console.log("[tab-e2e]", ...args); }

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleMsgs = [];
  const wsConnections = [];

  page.on("console", (m) => consoleMsgs.push(`[${m.type()}] ${m.text()}`));
  page.on("pageerror", (e) => consoleMsgs.push(`[pageerror] ${e.message}`));
  page.on("websocket", (ws) => {
    const url = ws.url();
    const isViteHmr = url.includes("/?token=") || url.includes("/hmr");
    if (isViteHmr) {
      log(`(skip HMR) WS → ${url}`);
      return;
    }
    log(`app WS attempt → ${url}`);
    wsConnections.push({ url, ts: Date.now() });
    ws.on("close", () => log(`app WS closed ← ${url}`));
  });

  log(`navigating to ${WEB}`);
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('div[id="root"] > *', { timeout: 5000 });
  log("App mounted");

  // Wait for default tab settle.
  await page.waitForTimeout(2000);

  // ─── Click Chat tab ──────────────────────────────────────────
  log("clicking Chat tab...");
  const chatTab = page.getByRole("button", { name: "Chat", exact: true });
  await chatTab.click();
  // Give the WS handshake + reconnect cycle time.
  await page.waitForTimeout(5000);
  log(`after Chat click: WS connections = ${wsConnections.length}`);
  const hasConnectionLostChat = await page.evaluate(() => document.body.innerText.includes("Connection Lost"));
  log(`after Chat click: "Connection Lost" toast present? ${hasConnectionLostChat}`);

  // ─── Click Memory tab ──────────────────────────────────────────
  log("clicking Memory tab...");
  await page.getByRole("button", { name: "Memory", exact: true }).click();
  await page.waitForTimeout(3000);
  log(`after Memory click: WS connections = ${wsConnections.length}`);
  const hasConnectionLostMem = await page.evaluate(() => document.body.innerText.includes("Connection Lost"));
  log(`after Memory click: "Connection Lost" toast present? ${hasConnectionLostMem}`);

  // ─── Click Business Flows tab ─────────────────────────────────
  log("clicking Business Flows tab...");
  await page.getByRole("button", { name: "Business Flows", exact: true }).click();
  await page.waitForTimeout(3000);

  // ─── Report ──────────────────────────────────────────────────
  log("");
  log("=== summary ===");
  log(`total app-level WS connections: ${wsConnections.length}`);
  for (const c of wsConnections) {
    log(`  - ${new Date(c.ts).toISOString()}  ${c.url}`);
  }
  log("");
  log("console messages (filtered):");
  const relevant = consoleMsgs.filter((m) =>
    !m.includes("/@vite/client") &&
    !m.includes("vite") &&
    !m.includes("[HMR]") &&
    !m.includes("react-refresh"),
  );
  for (const m of relevant.slice(0, 30)) log(`  ${m}`);

  await browser.close();
  process.exit(0);
}

main().catch((err) => {
  console.error("[tab-e2e] unexpected error:", err);
  process.exit(1);
});
