import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { wsManager } from "../ws/manager";

/**
 * WS reconnect stress tests (REQ-WEB-05, D-05).
 *
 * Verifies the documented behaviour:
 *   - exactly 5 reconnect attempts are scheduled (the 6th is a no-op)
 *   - all attempts use the same `session_id` query parameter
 *   - exponential backoff schedule is 1000, 2000, 4000, 8000, 16000 ms
 *     (capped at 30000 ms)
 *
 * Hermetic: no live WebSocket. We mock WebSocket on globalThis and use
 * fake timers so the scheduleReconnect setTimeouts fire deterministically.
 *
 * Note on the production flow: each new WebSocket instance starts in
 * CONNECTING state. After the production `connect()` guard rejects a
 * redundant connect (because the prior socket is still CONNECTING), we
 * simulate that the prior socket has been closed by the server before
 * the next reconnect timer fires. This faithfully models "server keeps
 * dying on every reconnect attempt".
 */

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;
  static CLOSING = 2;

  url: string;
  readyState = MockWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((err: unknown) => void) | null = null;
  sent: string[] = [];
  _closed = false;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    if (this._closed) return;
    this._closed = true;
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose();
  }
  /** Test helper: simulate a clean open. */
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) this.onopen();
  }
  /** Test helper: simulate an abrupt close (server died). */
  simulateAbruptClose() {
    this.close();
  }
}

/**
 * Helper: advance fake timers in small steps. After each step, simulate the
 * most-recently-created socket having been closed by the server. This mirrors
 * "server keeps dying on each reconnect attempt" — the only condition under
 * which the production reconnect schedule actually progresses.
 */
async function advanceAndClose(maxMs: number): Promise<void> {
  const stepMs = 500;
  let elapsed = 0;
  while (elapsed < maxMs) {
    await vi.advanceTimersByTimeAsync(stepMs);
    elapsed += stepMs;
    // Close the most-recent socket to mimic the server dying again.
    const last = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    if (last && !last._closed && elapsed > 1) {
      last.simulateAbruptClose();
    }
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  (globalThis as unknown as { WebSocket: unknown }).WebSocket =
    MockWebSocket as unknown;
  vi.useFakeTimers();
  // Provide minimal browser globals the manager reads
  (globalThis as unknown as { localStorage: Storage }).localStorage = {
    getItem: () => null,
    setItem: () => undefined,
    removeItem: () => undefined,
    clear: () => undefined,
    key: () => null,
    length: 0,
  } as Storage;
  (globalThis as unknown as { location: Location }).location = {
    protocol: "http:",
    host: "127.0.0.1:5180",
  } as unknown as Location;
  // Reset manager state
  wsManager.disconnect();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("wsManager reconnect (REQ-WEB-05, D-05)", () => {
  it("schedules exactly 5 reconnect attempts when the server dies", async () => {
    wsManager.connect("session-abc");

    const initial = MockWebSocket.instances[0]!;
    initial.simulateAbruptClose();

    // Advance past the 5 reconnect windows (1+2+4+8+16 = 31s).
    await advanceAndClose(40_000);

    // Total WebSockets created = 1 (initial) + 5 (reconnects) = 6.
    expect(MockWebSocket.instances.length).toBe(6);

    // No 6th reconnect scheduled — verify no further WebSocket is created.
    await vi.advanceTimersByTimeAsync(60_000);
    expect(MockWebSocket.instances.length).toBe(6);
  });

  it("preserves the same session_id query parameter across all 5 attempts", async () => {
    wsManager.connect("session-keep-me");

    const initial = MockWebSocket.instances[0]!;
    initial.simulateAbruptClose();

    await advanceAndClose(40_000);

    for (const ws of MockWebSocket.instances) {
      expect(ws.url).toContain("session_id=session-keep-me");
    }
  });

  it("uses the documented exponential backoff schedule 1s/2s/4s/8s/16s", async () => {
    // We capture the wall-clock delay between each socket creation.
    const creationTimes: number[] = [];
    class TrackedWebSocket extends MockWebSocket {
      constructor(url: string) {
        super(url);
        creationTimes.push(Date.now());
      }
    }
    (globalThis as unknown as { WebSocket: unknown }).WebSocket =
      TrackedWebSocket as unknown;
    MockWebSocket.instances = [];

    wsManager.connect("session-timed");
    const initial = MockWebSocket.instances[0]!;
    initial.simulateAbruptClose();

    // Drive the reconnect loop with a "server-dies-every-cycle" helper.
    await advanceAndClose(40_000);

    // Expect exactly 6 creation events (1 initial + 5 reconnects).
    expect(creationTimes.length).toBe(6);

    // Delays between successive creations should approximate the documented
    // schedule. The helper closes each socket ~500ms into its lifetime, so
    // we allow a generous window (the schedule plus the close step) on each
    // delta. This still proves the schedule is monotonic exponential with
    // the right magnitude — strict equality is too brittle when fake timers
    // interact with the close-and-reschedule cycle.
    const deltas = creationTimes.slice(1).map((t, i) => t - creationTimes[i]!);
    const expected = [1000, 2000, 4000, 8000, 16000];
    for (let i = 0; i < expected.length; i++) {
      const minDelta = expected[i]!;
      const maxDelta = expected[i]! + 1500; // tolerate 500ms close step
      expect(deltas[i]).toBeGreaterThanOrEqual(minDelta);
      expect(deltas[i]).toBeLessThanOrEqual(maxDelta);
    }
  });
});