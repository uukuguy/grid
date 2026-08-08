import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

const consoleEvents = [];
const pageErrors = [];
const networkEvents = [];
const wsEvents = [];

page.on("console", (msg) => {
  consoleEvents.push(`[${msg.type()}] ${msg.text()}`);
});
page.on("pageerror", (err) => {
  pageErrors.push(`[pageerror] ${err.message}`);
});
page.on("request", (req) => {
  if (req.url().includes(":3001") || req.url().includes(":18084")) {
    networkEvents.push(`[${req.method()}] ${req.url()}`);
  }
});
page.on("response", (resp) => {
  if (resp.url().includes(":3001") || resp.url().includes(":18084")) {
    networkEvents.push(`[${resp.status()}] ${resp.url()}`);
  }
});
page.on("websocket", (ws) => {
  wsEvents.push(`WS OPEN ${ws.url()}`);
  ws.on("framereceived", (data) => {
    wsEvents.push(`WS RECV ${data.payload().slice(0, 500)}`);
  });
  ws.on("close", () => wsEvents.push(`WS CLOSE ${ws.url()}`));
});

await page.goto("http://127.0.0.1:5180/", { waitUntil: "networkidle" });
await page.waitForTimeout(2000);

// Click Chat tab
const chatBtn = await page.$("button:has-text('Chat'), [role=tab]:has-text('Chat')");
if (chatBtn) {
  await chatBtn.click();
  await page.waitForTimeout(2000);
}

// Inspect page state before sending prompt
const before = await page.evaluate(() => {
  const ta = document.querySelector("textarea");
  return {
    inputPlaceholder: ta?.placeholder,
    inputValue: ta?.value,
    sendButton: !!document.querySelector("button[aria-label*='Send'], button:has-text('Send')"),
    messageListHasContent: document.body.innerText.includes("Start a conversation"),
  };
});
console.log("=== BEFORE SEND ===");
console.log(JSON.stringify(before, null, 2));

// Find the textarea + send button. Use placeholder text.
const textarea = await page.$("textarea");
console.log("=== ATTEMPT TO TYPE ===");
if (textarea) {
  await textarea.fill("Hello, can you hear me?");
  await page.waitForTimeout(500);
} else {
  console.log("NO TEXTAREA FOUND");
}

// Find Send button (try Enter first — it's the usual pattern)
await page.keyboard.press("Enter");
await page.waitForTimeout(8000);

const after = await page.evaluate(() => {
  const messages = Array.from(document.querySelectorAll("[class*='message'], [class*='Message'], [data-testid*='message']"))
    .map((el) => el.innerText)
    .filter((t) => t && t.length > 0);
  return {
    bodyText: document.body.innerText.slice(0, 1500),
    messageCount: messages.length,
    messages: messages.slice(0, 10),
  };
});
console.log("=== AFTER SEND ===");
console.log(JSON.stringify({messageCount: after.messageCount, messages: after.messages.slice(0,3)}, null, 2));
console.log("---bodyText---");
console.log(after.bodyText);

console.log("=== CONSOLE EVENTS ===");
console.log(consoleEvents.join("\n"));
console.log("=== PAGE ERRORS ===");
console.log(pageErrors.join("\n"));
console.log("=== NETWORK EVENTS ===");
console.log(networkEvents.join("\n"));
console.log("=== WS EVENTS ===");
console.log(wsEvents.join("\n"));

await browser.close();
