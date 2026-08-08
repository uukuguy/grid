import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const consoleErrors = [];
const pageErrors = [];

page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => pageErrors.push(err.message + (err.stack ? "\n" + err.stack : "")));

await page.goto("http://127.0.0.1:5180/", { waitUntil: "networkidle" });
// Wait for the tab to be clickable, then click "Chat" tab
await page.waitForTimeout(2000);

const initialTabInfo = await page.evaluate(() => {
  return {
    title: document.title,
    bodyTextLength: document.body.innerText.length,
    visibleText: document.body.innerText.slice(0, 500),
  };
});
console.log("=== INITIAL STATE ===");
console.log(JSON.stringify(initialTabInfo, null, 2));

// Try clicking the Chat tab
const tabButtons = await page.$$("button, [role=tab], a");
const candidates = [];
for (const el of tabButtons) {
  const text = (await el.innerText().catch(() => "")).trim();
  if (text) candidates.push(text);
}
console.log("=== CLICKABLE ELEMENTS (first 30) ===");
console.log(candidates.slice(0, 30));

// Look for Chat specifically
const chatButtons = await page.$$("button:has-text('Chat'), [role=tab]:has-text('Chat'), button[aria-label*='Chat']");
console.log("=== CHAT BUTTONS FOUND: " + chatButtons.length + " ===");

if (chatButtons.length > 0) {
  await chatButtons[0].click();
  await page.waitForTimeout(2000);
}

const afterClick = await page.evaluate(() => ({
  bodyText: document.body.innerText.slice(0, 1500),
}));
console.log("=== AFTER CLICKING CHAT ===");
console.log(afterClick.bodyText);
console.log("=== CONSOLE ERRORS ===");
console.log(consoleErrors.join("\n---\n"));
console.log("=== PAGE ERRORS ===");
console.log(pageErrors.join("\n---\n"));

await browser.close();
