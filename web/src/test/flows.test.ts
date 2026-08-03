// OBSTACK Phase C.0 — smoke tests for the new flows atoms (commit C.2).
//
// Verifies defaults + that selectedFlowKeyAtom round-trips a string.
// Real integration (HTTP fetch + render) is covered by the e2e
// Playwright suite + the manual walkthrough; these tests just guard
// the atom contracts so refactors don't silently break consumers.

import { describe, it, expect } from "vitest";
import { createStore } from "jotai";
import {
  flowsListAtom,
  flowsTotalAtom,
  selectedFlowKeyAtom,
  selectedFlowSummaryAtom,
} from "../atoms/flows";
import type { BusinessFlowSummary } from "../api/flows";

const SAMPLE: BusinessFlowSummary = {
  business_key: "sess_demo|threshold-calibration|Transformer-X",
  business_object_id: "Transformer-X",
  skill_id: "threshold-calibration",
  session_id: "sess_demo",
  session_count: 3,
  finished_count: 3,
  failed_count: 0,
  last_started_at: 1700000000,
  last_completed_at: 1700000030,
  last_duration_ms: 30000,
  status: "closed",
};

describe("flows atoms (Phase C.0)", () => {
  it("flowsListAtom defaults to []", () => {
    const store = createStore();
    expect(store.get(flowsListAtom)).toEqual([]);
  });

  it("flowsTotalAtom defaults to 0", () => {
    const store = createStore();
    expect(store.get(flowsTotalAtom)).toBe(0);
  });

  it("selectedFlowKeyAtom round-trips a business_key string", () => {
    const store = createStore();
    expect(store.get(selectedFlowKeyAtom)).toBeNull();
    store.set(selectedFlowKeyAtom, SAMPLE.business_key);
    expect(store.get(selectedFlowKeyAtom)).toBe(SAMPLE.business_key);
    store.set(selectedFlowKeyAtom, null);
    expect(store.get(selectedFlowKeyAtom)).toBeNull();
  });

  it("flowsListAtom holds summaries written via setFlows", () => {
    const store = createStore();
    store.set(flowsListAtom, [SAMPLE]);
    expect(store.get(flowsListAtom)).toHaveLength(1);
    expect(store.get(flowsListAtom)[0]?.business_key).toBe(SAMPLE.business_key);
  });

  it("selectedFlowSummaryAtom round-trips the summary shape", () => {
    const store = createStore();
    expect(store.get(selectedFlowSummaryAtom)).toBeNull();
    const summary = {
      status: "succeeded",
      event_count: 14,
      last_duration_ms: 30000,
      layer_counts: { L4: 14 },
    };
    store.set(selectedFlowSummaryAtom, summary);
    expect(store.get(selectedFlowSummaryAtom)).toEqual(summary);
  });
});
