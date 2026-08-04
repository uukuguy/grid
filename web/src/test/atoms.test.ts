import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createStore } from "jotai";
import { toastsAtom, addToastAtom, removeToastAtom } from "../atoms/ui";
import {
  activeTabAtom,
  sidebarOpenAtom,
  connectionStatusAtom,
  TAB_METADATA,
  type TabId,
} from "../atoms/ui";
import {
  sessionsAtom,
  activeSessionIdAtom,
  isStreamingAtom,
  streamingTextAtom,
  toolExecutionsAtom,
  sessionStatusAtom,
  stoppedByUserAtom,
  recentlyAddedMemoryIdsAtom,
  addRecentlyAddedMemoryIdAtom,
} from "../atoms/session";

describe("UI atoms", () => {
  it("activeTabAtom defaults to 'flows' (OBSTACK Phase C.0.3)", () => {
    // Phase C.0.3 changed the default from "chat" to "flows" because
    // chat auto-connects to grid-server /ws which 404s today. Operators
    // should land on the dashboard; chat is opt-in.
    const store = createStore();
    expect(store.get(activeTabAtom)).toBe("flows");
  });

  it("TAB_METADATA declares per-tab resource requirements", () => {
    // Flows tab is the new entry point — must NOT require WS or grid-server.
    expect(TAB_METADATA.flows.requiresWebSocket).toBe(false);
    expect(TAB_METADATA.flows.requiresGridServer).toBe(false);

    // Chat tab needs both WS + grid-server.
    expect(TAB_METADATA.chat.requiresWebSocket).toBe(true);
    expect(TAB_METADATA.chat.requiresGridServer).toBe(true);

    // Verify every TabId has a metadata entry (catches typos at startup).
    const tabIds: TabId[] = [
      "chat", "tasks", "schedule", "tools", "debug",
      "memory", "mcp", "collaboration", "flows",
    ];
    for (const id of tabIds) {
      expect(TAB_METADATA[id]).toBeDefined();
      expect(TAB_METADATA[id].label.length).toBeGreaterThan(0);
    }
  });

  it("sidebarOpenAtom defaults to false", () => {
    const store = createStore();
    expect(store.get(sidebarOpenAtom)).toBe(false);
  });

  it("connectionStatusAtom defaults to 'connecting'", () => {
    // Phase D.1 — the indicator should not start in the "Disconnected"
    // state, otherwise operators see a red dot briefly on every page
    // load even when wsManager is about to connect. "connecting"
    // matches the WS standard (WebSocket.CONNECTING) and is also
    // more accurate (the manager has not yet finished a handshake).
    const store = createStore();
    expect(store.get(connectionStatusAtom)).toBe("connecting");
  });

  it("addToastAtom adds a toast", () => {
    const store = createStore();
    store.set(addToastAtom, { type: "error", message: "test error" });
    const toasts = store.get(toastsAtom);
    expect(toasts).toHaveLength(1);
    expect(toasts[0]?.type).toBe("error");
    expect(toasts[0]?.message).toBe("test error");
  });

  it("removeToastAtom removes a toast by id", () => {
    const store = createStore();
    store.set(addToastAtom, { type: "info", message: "hello" });
    const toastId = store.get(toastsAtom)[0]!.id;
    store.set(removeToastAtom, toastId);
    expect(store.get(toastsAtom)).toHaveLength(0);
  });
});

describe("Session atoms", () => {
  it("sessionsAtom defaults to empty array", () => {
    const store = createStore();
    expect(store.get(sessionsAtom)).toEqual([]);
  });

  it("activeSessionIdAtom defaults to null", () => {
    const store = createStore();
    expect(store.get(activeSessionIdAtom)).toBeNull();
  });

  it("isStreamingAtom defaults to false", () => {
    const store = createStore();
    expect(store.get(isStreamingAtom)).toBe(false);
  });

  it("streamingTextAtom defaults to empty string", () => {
    const store = createStore();
    expect(store.get(streamingTextAtom)).toBe("");
  });
});

describe("Session status atoms (REQ-WEB-03, D-02)", () => {
  it("sessionStatusAtom is 'running' when isStreamingAtom is true", () => {
    const store = createStore();
    store.set(isStreamingAtom, true);
    expect(store.get(sessionStatusAtom)).toBe("running");
  });

  it("sessionStatusAtom is 'running' when a tool execution is running", () => {
    const store = createStore();
    store.set(toolExecutionsAtom, [
      {
        toolId: "t1",
        toolName: "Bash",
        input: {},
        status: "running",
      },
    ]);
    expect(store.get(sessionStatusAtom)).toBe("running");
  });

  it("sessionStatusAtom is 'stopped' when stoppedByUserAtom is true", () => {
    const store = createStore();
    store.set(isStreamingAtom, false);
    store.set(stoppedByUserAtom, true);
    expect(store.get(sessionStatusAtom)).toBe("stopped");
  });

  it("sessionStatusAtom is 'idle' when no streaming and not stopped", () => {
    const store = createStore();
    store.set(isStreamingAtom, false);
    store.set(stoppedByUserAtom, false);
    expect(store.get(sessionStatusAtom)).toBe("idle");
  });

  it("stoppedByUserAtom flips true on Stop, false on Resume", () => {
    const store = createStore();
    expect(store.get(stoppedByUserAtom)).toBe(false);
    store.set(stoppedByUserAtom, true);
    expect(store.get(stoppedByUserAtom)).toBe(true);
    store.set(stoppedByUserAtom, false);
    expect(store.get(stoppedByUserAtom)).toBe(false);
  });
});

describe("recentlyAddedMemoryIdsAtom (REQ-WEB-04)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("adds an id and removes it after 4500ms", () => {
    const store = createStore();
    expect(store.get(recentlyAddedMemoryIdsAtom)).toEqual([]);
    store.set(addRecentlyAddedMemoryIdAtom, "mem-1");
    expect(store.get(recentlyAddedMemoryIdsAtom)).toEqual(["mem-1"]);
    vi.advanceTimersByTime(4500);
    expect(store.get(recentlyAddedMemoryIdsAtom)).toEqual([]);
  });

  it("removes only the expired id when multiple are present", () => {
    const store = createStore();
    store.set(addRecentlyAddedMemoryIdAtom, "mem-1");
    vi.advanceTimersByTime(2000);
    store.set(addRecentlyAddedMemoryIdAtom, "mem-2");
    vi.advanceTimersByTime(2500);
    // After 4500ms total, mem-1 should be gone but mem-2 still present.
    expect(store.get(recentlyAddedMemoryIdsAtom)).toEqual(["mem-2"]);
    vi.advanceTimersByTime(2000);
    expect(store.get(recentlyAddedMemoryIdsAtom)).toEqual([]);
  });
});