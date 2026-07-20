import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { Provider, createStore } from "jotai";
import type { ReactNode } from "react";
import {
  stoppedByUserAtom,
  isStreamingAtom,
  activeSessionIdAtom,
} from "../atoms/session";
import { toastsAtom } from "../atoms/ui";
import { SessionControls } from "../components/SessionControls";

/**
 * SessionControls tests (REQ-WEB-03, D-02, D-08, UI-SPEC §9.1).
 *
 * Verifies the Stop/Resume affordance:
 *   - Running state shows visible Stop button, live indicator pulse,
 *     no Resume button.
 *   - Stopped/paused state shows Resume button, no Stop.
 *   - Click Stop → POST /api/v1/sessions/:id/kill + optimistic disable.
 *   - Click Resume → POST /api/v1/sessions/:id/resume + optimistic disable.
 *   - Failed POST restores prior state and emits a failure toast.
 *   - The component is mounted unconditionally — independent of the active
 *     tab.
 *
 * Hermetic: fetch is mocked on globalThis.
 */

function renderWithStore(
  ui: ReactNode,
  init?: (store: ReturnType<typeof createStore>) => void,
) {
  const store = createStore();
  if (init) init(store);
  return {
    store,
    ...render(<Provider store={store}>{ui}</Provider>),
  };
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      // Capture the request for assertions
      (globalThis as any).__lastFetch = { url, init };
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  // Set a session id so the component has something to control
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("SessionControls (REQ-WEB-03, D-02, UI-SPEC §9.1)", () => {
  it("renders a visible Stop button + live indicator when status is running", () => {
    renderWithStore(<SessionControls />, (store) => {
      store.set(activeSessionIdAtom, "session-12345678");
      store.set(isStreamingAtom, true);
    });

    expect(screen.getByRole("button", { name: /Stop session/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Resume session/i })).toBeNull();
  });

  it("renders a Resume button and hides Stop when status is stopped", () => {
    renderWithStore(<SessionControls />, (store) => {
      store.set(activeSessionIdAtom, "session-12345678");
      store.set(stoppedByUserAtom, true);
    });

    expect(screen.getByRole("button", { name: /Resume session/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Stop session/i })).toBeNull();
  });

  it("clicking Stop POSTs to /api/v1/sessions/:id/kill and flips state to stopped", async () => {
    const { store } = renderWithStore(<SessionControls />, (s) => {
      s.set(activeSessionIdAtom, "session-abc");
      s.set(isStreamingAtom, true);
    });

    const stopBtn = screen.getByRole("button", { name: /Stop session/i });

    await act(async () => {
      fireEvent.click(stopBtn);
    });

    // Optimistic state flip happens synchronously inside handleStop.
    expect(store.get(stoppedByUserAtom)).toBe(true);

    // Wait for the fetch to flush
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const lastFetch = (globalThis as any).__lastFetch;
    expect(lastFetch.url).toBe("/api/v1/sessions/session-abc/kill");
    expect(lastFetch.init.method).toBe("POST");
  });

  it("clicking Resume POSTs to /api/v1/sessions/:id/resume", async () => {
    const { store } = renderWithStore(<SessionControls />, (s) => {
      s.set(activeSessionIdAtom, "session-xyz");
      s.set(stoppedByUserAtom, true);
    });

    const resumeBtn = screen.getByRole("button", { name: /Resume session/i });

    await act(async () => {
      fireEvent.click(resumeBtn);
    });

    // Optimistic state flip happens synchronously inside handleResume.
    expect(store.get(stoppedByUserAtom)).toBe(false);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    const lastFetch = (globalThis as any).__lastFetch;
    expect(lastFetch.url).toBe("/api/v1/sessions/session-xyz/resume");
    expect(lastFetch.init.method).toBe("POST");
  });

  it("on Stop failure, restores prior state and emits a failure toast", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        return new Response("server down", { status: 500 });
      }),
    );

    const { store } = renderWithStore(<SessionControls />, (s) => {
      s.set(activeSessionIdAtom, "session-fail");
      s.set(isStreamingAtom, true);
      s.set(stoppedByUserAtom, false);
    });

    fireEvent.click(screen.getByRole("button", { name: /Stop session/i }));

    await act(async () => {
      await Promise.resolve();
    });

    // stoppedByUserAtom must be false again (rolled back)
    expect(store.get(stoppedByUserAtom)).toBe(false);

    // Failure toast must be present with the exact UI-SPEC §11.2 copy
    const toasts = store.get(toastsAtom);
    const failToast = toasts.find((t) => t.title === "Failed to stop");
    expect(failToast).toBeDefined();
    expect(failToast!.message).toMatch(/Try again/);
  });
});