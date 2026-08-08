import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (err) => errors.push("PAGE_ERROR: " + err.message));
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push("CONSOLE_ERROR: " + msg.text());
});

await page.goto("http://127.0.0.1:5180/", { waitUntil: "networkidle" });
await page.waitForTimeout(2000);

// Click Chat tab
const chatBtn = await page.$("button:has-text('Chat'), [role=tab]:has-text('Chat')");
if (chatBtn) {
  await chatBtn.click();
  await page.waitForTimeout(2500);
}

// Verify Chat UI is rendered (not error overlay)
const result = await page.evaluate(() => ({
  title: document.title,
  errorOverlayPresent: document.body.innerText.includes("Something went wrong"),
  sessionBarVisible: !!document.querySelector("button[aria-label='New session']"),
  sessionPillsRendered: document.querySelectorAll("button[class*='group flex items-center']").length,
  chatInputPresent: !!document.querySelector("textarea"),
  first400chars: document.body.innerText.slice(0, 400),
}));

console.log("=== CHAT TAB STATE ===");
console.log(JSON.stringify(result, null, 2));
console.log("\n=== ERRORS CAPTURED ===");
console.log(errors.length === 0 ? "(no errors — fix successful)" : errors.join("\n"));

// Try a second interaction: click Tasks tab then back to Chat
await page.click("button:has-text('Tasks'), [role=tab]:has-text('Tasks')").catch(() => {});
await page.waitForTimeout(800);
await page.click("button:has-text('Chat'), [role=tab]:has-text('Chat')").catch(() => {});
await page.waitForTimeout(800);

const secondState = await page.evaluate(() => ({
  errorOverlayStillAbsent: !document.body.innerText.includes("Something went wrong"),
  chatInputPresent: !!document.querySelector("textarea"),
}));
console.log("\n=== AFTER CHAT↔TABS NAV ===");
console.log(JSON.stringify(secondState, null, 2));

await browser.close();
process.exit(errors.length > 0 && result.errorOverlayPresent ? 1 : 0);
