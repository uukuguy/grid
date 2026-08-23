import { afterEach, describe, expect, it, vi } from "vitest";
import { ObstackClient } from "../api/flows";
import type { BusinessFlowSummary, TimelineEvent } from "../api/obstack_types";
import {
  deriveFlowAlerts,
  deriveFlowStats,
  rankSlowFlows,
} from "../lib/obstack/operatorViews";

const encoder = new TextEncoder();

function streamResponse(chunks: string[], init: ResponseInit = {}): Response {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, ...init });
}

function flow(overrides: Partial<BusinessFlowSummary> = {}): BusinessFlowSummary {
  return {
    business_key: "session|skill|object",
    business_object_id: "object",
    skill_id: "skill",
    session_id: "session",
    session_count: 1,
    finished_count: 1,
    failed_count: 0,
    last_started_at: 1_000,
    last_completed_at: 1_100,
    last_duration_ms: 100,
    status: "closed",
    ...overrides,
  };
}

afterEach(() => vi.restoreAllMocks());

describe("ObstackClient.stream_business_flow", () => {
  it("URL-encodes the key, propagates Bearer auth, and parses split plus multiple frames", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      streamResponse([
        'event: ignored\n\ndata: {"ts":1,"layer":"L4",',
        '"component":"flow","event_type":"started","payload":{},"duration_ms":null,"error":null}\n\n',
        'data: {"ts":2,"layer":"L1","component":"runtime","event_type":"finished","payload":{"ok":true},"duration_ms":8,"error":null}\n\n',
      ]),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onEvent = vi.fn<(event: TimelineEvent) => void>();
    const client = new ObstackClient({ baseUrl: "https://l4.example/", authToken: "secret" });

    await client.stream_business_flow("session/one|skill|object two", onEvent);

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "https://l4.example/v1/business-flows/session%2Fone%7Cskill%7Cobject%20two/events/stream",
    );
    const requestOptions = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(requestOptions.headers).get("Authorization")).toBe("Bearer secret");
    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent.mock.calls.map(([event]) => event.event_type)).toEqual(["started", "finished"]);
  });

  it("passes the AbortSignal and treats an aborted stream as normal completion", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchMock = vi.fn().mockRejectedValue(new DOMException("Aborted", "AbortError"));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ObstackClient({ baseUrl: "https://l4.example" });

    await expect(client.stream_business_flow("key", vi.fn(), controller.signal)).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      "https://l4.example/v1/business-flows/key/events/stream",
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("rejects an SSE response with a non-2xx status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("denied", { status: 403, statusText: "Forbidden" })));
    const client = new ObstackClient({ baseUrl: "https://l4.example" });

    await expect(client.stream_business_flow("key", vi.fn())).rejects.toThrow("OBSTACK 403 Forbidden");
  });
});

describe("operator flow derivations", () => {
  it("aggregates total, status counts, and completion rate from list rows", () => {
    expect(deriveFlowStats([
      flow({ business_key: "failed", status: "failed" }),
      flow({ business_key: "active", status: "active" }),
      flow({ business_key: "closed-1", status: "closed" }),
      flow({ business_key: "closed-2", status: "closed" }),
    ])).toEqual({ total: 4, failed: 1, active: 1, closed: 2, completionRate: 0.5 });
    expect(deriveFlowStats([])).toEqual({ total: 0, failed: 0, active: 0, closed: 0, completionRate: 0 });
  });

  it("derives critical failed alerts and warning stale-active alerts from real rows", () => {
    expect(deriveFlowAlerts([
      flow({ business_key: "failed", status: "failed" }),
      flow({ business_key: "stale", status: "active", last_started_at: 100 }),
      flow({ business_key: "fresh", status: "active", last_started_at: 101 }),
      flow({ business_key: "unknown-age", status: "active", last_started_at: null }),
    ], 1_000)).toEqual([
      {
        businessKey: "failed",
        severity: "critical",
        reason: "failed",
        message: "Business flow failed",
      },
      {
        businessKey: "stale",
        severity: "warning",
        reason: "stale-active",
        message: "Business flow has been active for at least 15 minutes",
      },
    ]);
  });

  it("ranks only flows with a duration in descending duration order and enforces the limit", () => {
    expect(rankSlowFlows([
      flow({ business_key: "fast", last_duration_ms: 10 }),
      flow({ business_key: "unknown", last_duration_ms: null }),
      flow({ business_key: "slow", last_duration_ms: 99 }),
      flow({ business_key: "medium", last_duration_ms: 50 }),
    ], 2).map((item) => item.business_key)).toEqual(["slow", "medium"]);
  });
});
