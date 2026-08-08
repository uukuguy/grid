import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

const allConsole = [];
page.on("console", (msg) => {
  allConsole.push(`[${msg.type()}] ${msg.text()}`);
});
page.on("pageerror", (err) => allConsole.push(`[pageerror] ${err.message}`));

await page.goto("http://127.0.0.1:5180/", { waitUntil: "networkidle" });
await page.waitForTimeout(2000);

console.log("=== INIT CONSOLE ===");
console.log(allConsole.join("\n"));

// Click Chat if not already there
const chatBtn = await page.$("button:has-text('Chat'), [role=tab]:has-text('Chat')");
if (chatBtn) await chatBtn.click();
await page.waitForTimeout(2000);

console.log("\n=== POST-CHAT CONSOLE ===");
console.log(allConsole.join("\n"));

// Trigger fetch manually + check sessionsAtom
const result = await page.evaluate(async () => {
  // Need to import via a known global path. Try to call fetch directly.
  const r = await fetch("/api/v1/sessions/active");
  const text = await r.text();
  return { status: r.status, body: text };
});
console.log("\n=== /api/v1/sessions/active response ===");
console.log(JSON.stringify(result, null, 2));

await browser.close();
