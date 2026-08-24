import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import type {
  BusinessFlowSummary,
  EvaluationResponse,
  SessionsResponse,
  SummaryResponse,
  TimelineEvent,
  TimelineResponse,
} from "../api/obstack_types";

const apiMocks = vi.hoisted(() => ({
  list: vi.fn(),
  summary: vi.fn(),
  sessions: vi.fn(),
  timeline: vi.fn(),
  evaluation: vi.fn(),
  stream: vi.fn(),
}));

vi.mock("../api/flows", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/flows")>();
  return {
    ...actual,
    flowsApi: apiMocks,
  };
});

import Flows from "../pages/Flows";
import { FlowsDetail } from "../components/dashboard/FlowsDetail";

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

const summaryResponse: SummaryResponse = {
  business_key: "session|skill|object",
  summary: {
    status: "closed",
    started_at: 1_000,
    completed_at: 1_100,
    total_duration_ms: 100,
    event_count: 1,
    layer_counts: { L4: 1 },
    interrupted_layer: null,
  },
};

const sessionsResponse: SessionsResponse = {
  business_key: "session|skill|object",
  session_ids: [],
  count: 0,
};

const timelineResponse: TimelineResponse = {
  business_key: "session|skill|object",
  events: [],
  count: 0,
};

const evaluationResponse: EvaluationResponse = {
  business_key: "session|skill|object",
  report: {
    window_seconds: 3_600,
    total_flows: 1,
    status_counts: { closed: 1 },
    completion_rate: 1,
    interruption_heatmap: {},
    hints: [{
      layer: "L1",
      metric: "latency",
      severity: "warn",
      recommendation: "Reduce prompt size",
      evidence: {},
    }],
  },
};

function configureDetailReads() {
  apiMocks.summary.mockResolvedValue(summaryResponse);
  apiMocks.sessions.mockResolvedValue(sessionsResponse);
  apiMocks.timeline.mockResolvedValue(timelineResponse);
  apiMocks.evaluation.mockResolvedValue(evaluationResponse);
}

beforeEach(() => {
  vi.clearAllMocks();
  configureDetailReads();
  apiMocks.stream.mockResolvedValue(undefined);
});

afterEach(() => vi.restoreAllMocks());

describe("OBSTACK operator dashboard surface", () => {
  it("renders derived stats and alerts from the currently filtered flow rows", async () => {
    apiMocks.list.mockResolvedValue({
      flows: [
        flow({ business_key: "failed", status: "failed" }),
        flow({ business_key: "active", status: "active", last_started_at: 0 }),
        flow({ business_key: "closed", status: "closed" }),
      ],
      total: 3,
    });

    render(<Provider><Flows /></Provider>);

    await screen.findByRole("button", { name: "Business flow failed" });
    const statistics = screen.getByLabelText("Operator flow statistics");
    expect(statistics.tagName).toBe("DL");
    expect(statistics).toHaveTextContent("3 total");
    expect(screen.getByLabelText("Operator flow alerts")).toHaveTextContent("Business flow failed");
    expect(screen.getByLabelText("Operator flow alerts")).toHaveTextContent("at least 15 minutes");

    fireEvent.click(screen.getByLabelText("Filter failed"));

    await waitFor(() => {
      expect(screen.getByLabelText("Operator flow statistics")).toHaveTextContent("2 total");
      expect(screen.getByLabelText("Operator flow alerts")).not.toHaveTextContent("Business flow failed");
    });
  });

  it("labels evaluation hints as optimization guidance", async () => {
    render(<FlowsDetail businessKey="session|skill|object" onClose={vi.fn()} />);

    expect(await screen.findByText("Optimization guidance")).toBeInTheDocument();
    expect(screen.getByText("Reduce prompt size")).toBeInTheDocument();
  });

  it("keeps a stream connecting until an event, then deduplicates and reloads derived detail reads", async () => {
    let onEvent: ((event: TimelineEvent) => void) | undefined;
    apiMocks.stream.mockImplementation((_key: string, callback: (event: TimelineEvent) => void) => {
      onEvent = callback;
      return new Promise<void>(() => undefined);
    });
    const { rerender } = render(<FlowsDetail businessKey="first" onClose={vi.fn()} />);

    await waitFor(() => expect(apiMocks.stream).toHaveBeenCalledTimes(1));
    expect(screen.getByText("Live updates connecting")).toBeInTheDocument();
    expect(onEvent).toBeDefined();

    act(() => {
      onEvent?.({
        ts: 2,
        layer: "L4",
        component: "flow",
        event_type: "completed",
        payload: { z: 1, a: "same" },
        duration_ms: 4,
        error: null,
      });
      onEvent?.({
        ts: 2,
        layer: "L4",
        component: "flow",
        event_type: "completed",
        payload: { a: "same", z: 1 },
        duration_ms: 4,
        error: null,
      });
    });

    expect(screen.getByText("Live updates live")).toBeInTheDocument();

    await waitFor(() => {
      expect(apiMocks.summary).toHaveBeenCalledTimes(2);
      expect(apiMocks.timeline).toHaveBeenCalledTimes(2);
      expect(apiMocks.evaluation).toHaveBeenCalledTimes(2);
    });
    expect(apiMocks.sessions).toHaveBeenCalledTimes(1);

    rerender(<FlowsDetail businessKey="second" onClose={vi.fn()} />);

    await waitFor(() => expect(apiMocks.stream).toHaveBeenCalledTimes(2));
    const firstSignal = apiMocks.stream.mock.calls[0]?.[2] as AbortSignal;
    expect(firstSignal.aborted).toBe(true);
  });

  it("marks a normally completed stream as disconnected", async () => {
    render(<FlowsDetail businessKey="complete" onClose={vi.fn()} />);

    expect(await screen.findByText("Live updates disconnected")).toBeInTheDocument();
  });

  it("aborts the active stream when the detail panel unmounts", async () => {
    apiMocks.stream.mockImplementation(() => new Promise<void>(() => undefined));
    const { unmount } = render(<FlowsDetail businessKey="active" onClose={vi.fn()} />);

    await waitFor(() => expect(apiMocks.stream).toHaveBeenCalledTimes(1));
    const signal = apiMocks.stream.mock.calls[0]?.[2] as AbortSignal;

    unmount();

    expect(signal.aborted).toBe(true);
  });
});
