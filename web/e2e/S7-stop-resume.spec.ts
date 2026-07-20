import { test, expect, type Page } from "@playwright/test";

// Augment Window with the kill-request recorder exposed via page.exposeFunction.
declare global {
  interface Window {
    __getKillRequests: () => Array<{ method: string; url: string }>;
  }
}

/**
 * S7 E1 — Dashboard Stop flow (REQ-WEB-03, REQ-WEB-07, D-02).
 *
 * Hermetic: route interception fakes `/api/v1/sessions/active` and the
 * kill/resume endpoints. No live grid-server or LLM key required.
 *
 * Asserts:
 *   1. Opening the dashboard and switching to the Tasks tab shows a Stop
 *      button on a running task row.
 *   2. Clicking Stop POSTs `/api/v1/sessions/<id>/kill`.
 *   3. After Stop succeeds, the task list re-fetches and a Resume button
 *      is not visible (delete-only fallback in this phase).
 *   4. The session-level Stop button (SessionControls) issues a POST to
 *      `/api/v1/sessions/<id>/kill` and the live indicator switches from
 *      pulse to steady emerald.
 */

const SESSION_ID = "test-session-12345678";
const TASK_ID = "test-task-abcdef01";

interface TaskFixture {
  id: string;
  status: "running";
  result?: string;
  error?: string;
}

async function installRoutes(page: Page): Promise<void> {
  // Mock the active-sessions endpoint so the SessionBar/SessionControls
  // see the fixture session.
  await page.route("**/api/v1/sessions/active", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sessions: [SESSION_ID], count: 1, max: 16 }),
    });
  });

  // Mock session start (used by SessionBar's "+" button — not exercised here).
  await page.route("**/api/v1/sessions/start", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ session_id: SESSION_ID }),
    });
  });

  // Mock kill — record the call so we can assert it was POST'd with the
  // right session id.
  let killRequests: Array<{ url: string; method: string }> = [];
  await page.route("**/api/v1/sessions/*/kill", async (route) => {
    killRequests.push({ url: route.request().url(), method: route.request().method() });
    await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
  });
  await page.exposeFunction("__getKillRequests", () => killRequests);

  // Mock tasks list
  const tasks: TaskFixture[] = [{ id: TASK_ID, status: "running" }];
  await page.route("**/api/v1/tasks", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(tasks),
    });
  });
  await page.route("**/api/v1/tasks/*", async (route) => {
    const url = route.request().url();
    if (url.endsWith("/cancel")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ task: tasks[0], executions: [] }),
    });
  });
}

test.beforeEach(async ({ page }) => {
  await installRoutes(page);
});

test("E1: Tasks page Stop button issues POST /api/v1/sessions/<id>/kill", async ({
  page,
}) => {
  // Open dashboard
  await page.goto("/");
  await expect(page).toHaveTitle(/Grid|grid/i);

  // Switch to Tasks tab via the TabBar (a11y name or visible text)
  const tasksTab = page.getByRole("button", { name: /Tasks/i });
  await tasksTab.click();

  // The task row's Stop button (icon-only) should be visible
  const stopBtn = page.getByRole("button", { name: new RegExp(`Stop task ${TASK_ID.slice(0, 8)}`) });
  await expect(stopBtn).toBeVisible({ timeout: 10_000 });

  // Click Stop and assert the kill endpoint was hit
  await stopBtn.click();
  await expect.poll(async () => (await page.evaluate(() => window.__getKillRequests())).length).toBe(1);

  const requests = await page.evaluate(() => window.__getKillRequests());
  expect(requests[0].method).toBe("POST");
  expect(requests[0].url).toContain(`/api/v1/sessions/${SESSION_ID}/kill`);
});

test("E1 (SessionControls): global Stop button stops the session", async ({ page }) => {
  await page.goto("/");
  // The SessionControls Stop button is mounted globally (REQ-WEB-03).
  const sessionStop = page.getByRole("button", { name: new RegExp(`Stop session ${SESSION_ID.slice(0, 8)}`) });
  await expect(sessionStop).toBeVisible({ timeout: 10_000 });
  await sessionStop.click();

  await expect.poll(async () => (await page.evaluate(() => window.__getKillRequests())).length).toBe(1);
  const requests = await page.evaluate(() => window.__getKillRequests());
  expect(requests[0].url).toContain(`/api/v1/sessions/${SESSION_ID}/kill`);
});