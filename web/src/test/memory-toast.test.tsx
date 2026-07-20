import { describe, it, expect } from "vitest";
import { act, render } from "@testing-library/react";
import { useSetAtom } from "jotai";
import { useEffect } from "react";
import { createStore } from "jotai";
import { Provider } from "jotai";
import type { ReactNode } from "react";
import { toastsAtom, pushMemoryEventAtom } from "../atoms/ui";

/**
 * Memory toast emission/render tests (REQ-WEB-02, REQ-WEB-04, D-02).
 *
 * Verifies:
 *   - `pushMemoryEventAtom` produces a toast of type `memory`
 *   - title is exactly "Memory written"
 *   - message content is truncated to 60 chars with ellipsis suffix
 *   - default duration is 4000ms (UI-SPEC §9.2)
 *
 * Hermetic: no network or websocket. We invoke the write atom directly
 * through a render-bound probe so the React commit lifecycle fires.
 */

function TestProbe({
  pushFnRef,
}: {
  pushFnRef: React.MutableRefObject<((input: { content: string }) => void) | null>;
}) {
  const push = useSetAtom(pushMemoryEventAtom);
  // Expose push via ref so the test can call it outside of React lifecycle.
  useEffect(() => {
    pushFnRef.current = push;
    return () => {
      pushFnRef.current = null;
    };
  }, [push, pushFnRef]);
  return null;
}

function makeStoreWrapper(store: ReturnType<typeof createStore>) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <Provider store={store}>{children}</Provider>;
  };
}

describe("pushMemoryEventAtom (REQ-WEB-02, REQ-WEB-04)", () => {
  function setup(store = createStore()) {
    const pushFnRef = { current: null as ((input: { content: string }) => void) | null };
    const Wrapper = makeStoreWrapper(store);
    render(<TestProbe pushFnRef={pushFnRef} />, { wrapper: Wrapper });
    return { store, push: (input: { content: string }) => pushFnRef.current?.(input) };
  }

  it("emits a memory toast with title 'Memory written' and a 'Stored:' message", () => {
    const { store, push } = setup();

    act(() => {
      push({ content: "hello world" });
    });

    const toasts = store.get(toastsAtom);
    expect(toasts).toHaveLength(1);
    expect(toasts[0]!.type).toBe("memory");
    expect(toasts[0]!.title).toBe("Memory written");
    expect(toasts[0]!.message).toMatch(/^Stored:/);
    // 4000ms is the documented default duration for the memory variant.
    expect(toasts[0]!.duration).toBe(4000);
  });

  it("truncates the stored memory content to 60 characters", () => {
    const { store, push } = setup();

    const long = "x".repeat(200);
    act(() => {
      push({ content: long });
    });

    const toasts = store.get(toastsAtom);
    expect(toasts).toHaveLength(1);
    // Message format is "Stored: {first 60 chars}…"
    const body = toasts[0]!.message.slice("Stored: ".length);
    expect(body.endsWith("…")).toBe(true);
    expect(body.length).toBe(61); // 60 chars + "…"
  });
});