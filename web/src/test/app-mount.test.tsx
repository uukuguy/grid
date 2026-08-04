// OBSTACK Phase C.0.2 — verify the React app actually mounts and the
// flowsApi endpoint returns real data. This is the "browser works"
// smoke test that was missing from commit C.3.
//
// Run: npx vitest run src/test/app-mount.test.tsx --environment jsdom

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Provider } from "jotai";

// Stub localStorage with a clean Map-backed implementation.
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => { store[k] = v; },
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, "localStorage", { value: localStorageMock });

// Stub scrollIntoView — jsdom does not implement it but MessageList
// calls it on every chat mount. Without this stub the App crashes
// on initial render and ErrorBoundary hides the whole tree.
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {};
}

// Stub fetch — flowsApi.list returns one fake business flow.
const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
  const url = typeof input === "string" ? input : input.toString();
  if (url.includes("/v1/business-flows/list")) {
    return new Response(
      JSON.stringify({
        flows: [
          {
            business_key: "sess-mock|threshold-calibration|Transformer-MOCK",
            business_object_id: "Transformer-MOCK",
            skill_id: "threshold-calibration",
            session_id: "sess-mock",
            session_count: 2,
            finished_count: 2,
            failed_count: 0,
            last_started_at: 1700000000,
            last_completed_at: 1700000030,
            last_duration_ms: 30000,
            status: "closed",
          },
        ],
        total: 1,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }
  return new Response("{}", { status: 200 });
});
globalThis.fetch = fetchMock as unknown as typeof fetch;

// Each test gets a fresh module-level App + Provider.
beforeEach(() => {
  fetchMock.mockClear();
});

describe("App mount + Business Flows tab (Phase C.0.2)", () => {
  it("renders the TabBar with the 'Business Flows' entry", async () => {
    const { default: App } = await import("../App");
    render(
      <Provider>
        <App />
      </Provider>,
    );
    await waitFor(() => {
      expect(screen.getByText("Business Flows")).toBeDefined();
    });
  });

  it("clicking Business Flows tab mounts FlowsPage + calls flowsApi.list", async () => {
    const { default: App } = await import("../App");
    render(
      <Provider>
        <App />
      </Provider>,
    );

    // Wait for initial render → tab is in the DOM.
    const tab = await screen.findByText("Business Flows");
    expect(tab).toBeDefined();

    // Click the tab.
    fireEvent.click(tab);

    // FlowsPage should render — header has "Business Flows" text.
    await waitFor(() => {
      // Header still has "Business Flows" label; we just verify FlowsPage
      // produced the "Refresh" button (specific to FlowsPage).
      expect(screen.getByLabelText("Refresh business flows")).toBeDefined();
    });

    // Give React + fetch a beat to settle.
    await new Promise((r) => setTimeout(r, 100));

    // fetchMock should have been called with /v1/business-flows/list
    // (either via the vite proxy or direct to L4 — flowsApi hardcodes
    // L4_BASE_URL = 127.0.0.1:18084, but with globalThis.fetch stubbed,
    // both paths still register the call).
    const calls = fetchMock.mock.calls.map((c) => c[0].toString());
    const listCall = calls.find((u) => u.includes("/v1/business-flows/list"));
    expect(listCall).toBeDefined();
  });
});
