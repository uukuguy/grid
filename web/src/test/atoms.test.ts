import { describe, it, expect } from "vitest";
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
