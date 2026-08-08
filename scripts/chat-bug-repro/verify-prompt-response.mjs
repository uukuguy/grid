import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

const consoleEvents = [];
const wsEvents = [];
const pageErrors = [];

page.on("console", (msg) => consoleEvents.push(`[${msg.type()}] ${msg.text()}`));
page.on("pageerror", (err) => pageErrors.push(`[pageerror] ${err.message}`));
page.on("websocket", (ws) => {
  wsEvents.push(`WS OPEN ${ws.url()}`);
  ws.on("framereceived", (data) => {
    const payload = typeof data.payload === "function" ? data.payload() : data.payload;
    const text = typeof payload === "string" ? payload : String(payload).slice(0, 1000);
    wsEvents.push(`WS RECV ${text}`);
  });
  ws.on("framesent", (data) => {
    const payload = typeof data.payload === "function" ? data.payload() : data.payload;
    const text = typeof payload === "string" ? payload : String(payload).slice(0, 500);
    wsEvents.push(`WS SENT ${text}`);
  });
  ws.on("close", () => wsEvents.push(`WS CLOSE`));
});

await page.goto("http://127.0.0.1:5180/", { waitUntil: "networkidle" });
await page.waitForTimeout(2000);

// Click Chat tab
const chatBtn = await page.$("button:has-text('Chat'), [role=tab]:has-text('Chat')");
if (chatBtn) {
  await chatBtn.click();
  await page.waitForTimeout(2000);
}

// Type prompt + send via Enter
const textarea = await page.$("textarea");
if (!textarea) {
  console.log("FAIL: no textarea on Chat tab");
  process.exit(1);
}
await textarea.fill("Reply with the single word: OK");
await page.keyboard.press("Enter");

// Wait up to 25s for a streamed text response (deepseek takes ~5-15s)
let visibleText = "";
let assistantMessageSeen = false;
for (let i = 0; i < 25; i++) {
  await page.waitForTimeout(1000);
  const state = await page.evaluate(() => {
    // The body innerText reflects what the user sees — a
    // successful chat shows the assistant reply appended after
    // the user's prompt. We scan for any text after the
    // "Type a message..." placeholder that matches the
    // expected keyword.
    const txt = document.body.innerText;
    // Rough heuristic: assistant replies typically render at
    // least the prompt's expected keyword somewhere in the
    // body. Test for the exact keyword we sent.
    return { text: txt };
  });
  visibleText = state.text;
  if (/OK/i.test(visibleText) && (visibleText.match(/OK/g) || []).length >= 2) {
    // We expect at least 2 occurrences: 1 in the textarea (our
    // prompt) + 1 in the rendered assistant chat bubble.
    assistantMessageSeen = true;
    console.log(`✓ assistant message detected after ${i + 1}s`);
    break;
  }
}

console.log("\n=== VISIBLE BODY (last 1500 chars) ===");
console.log(visibleText.slice(-1500) || "(empty)");

console.log("\n=== WS EVENT COUNT ===");
console.log(`Total WS frames: ${wsEvents.length}`);
// Tally distinct message types from the WS frames (parse JSON).
const typeCounts = {};
for (const e of wsEvents) {
  if (!e.startsWith("WS RECV ") && !e.startsWith("WS SENT ")) continue;
  try {
    const payload = e.slice(8);
    const obj = JSON.parse(payload);
    const t = obj.chunk_type ? `chunk_type=${obj.chunk_type}` : obj.type;
    typeCounts[t] = (typeCounts[t] || 0) + 1;
  } catch {}
}
console.log("type counts:", JSON.stringify(typeCounts));

console.log("\n=== PAGE ERRORS ===");
console.log(pageErrors.length === 0 ? "(none)" : pageErrors.join("\n"));

await browser.close();

const verdict = assistantMessageSeen ? "PASS" : "FAIL";
console.log(`\n=== VERDICT: ${verdict} ===`);
process.exit(verdict === "PASS" ? 0 : 1);
