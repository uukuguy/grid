import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const ws = [];
page.on("websocket", (w) => {
  w.on("framereceived", (data) => {
    const payload = typeof data.payload === "function" ? data.payload() : data.payload;
    if (typeof payload === "string") ws.push(payload);
  });
});
await page.goto("http://127.0.0.1:5180/", { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
const chatBtn = await page.$("button:has-text('Chat')");
if (chatBtn) await chatBtn.click();
await page.waitForTimeout(2000);
const ta = await page.$("textarea");
await ta.fill("Reply with the single word: OK");
await page.keyboard.press("Enter");
await page.waitForTimeout(20000);
// Print first 30 frames + their length distribution
console.log(`Total frames: ${ws.length}`);
ws.slice(0, 30).forEach((f, i) => {
  try {
    const obj = JSON.parse(f);
    console.log(`[${i}] type=${obj.type} chunk=${obj.chunk_type} payload=${JSON.stringify(obj.payload).slice(0,200)}`);
  } catch (e) {
    console.log(`[${i}] non-JSON: ${f.slice(0,200)}`);
  }
});
console.log(`\nUnique types: ${[...new Set(ws.map(f => { try { return JSON.parse(f).type } catch { return '?' } }))].join(',')}`);
// Final visible chat text
const txt = await page.evaluate(() => document.body.innerText.slice(0, 1500));
console.log(`\nVISIBLE BODY:\n${txt}`);
await browser.close();
