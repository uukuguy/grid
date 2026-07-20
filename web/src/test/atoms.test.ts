import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { createStore } from "jotai";
import { toastsAtom, addToastAtom, removeToastAtom } from "../atoms/ui";
import {
  activeTabAtom,
  sidebarOpenAtom,
  connectionStatusAtom,
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
  it("activeTabAtom defaults to chat", () => {
    const store = createStore();
    expect(store.get(activeTabAtom)).toBe("chat");
  });

  it("sidebarOpenAtom defaults to false", () => {
    const store = createStore();
    expect(store.get(sidebarOpenAtom)).toBe(false);
  });

  it("connectionStatusAtom defaults to disconnected", () => {
    const store = createStore();
    expect(store.get(connectionStatusAtom)).toBe("disconnected");
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