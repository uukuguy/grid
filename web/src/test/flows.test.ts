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
  flowsFilterAtom,
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

  it("flowsFilterAtom defaults to all-statuses + 24h window + empty query", () => {
    const store = createStore();
    const f = store.get(flowsFilterAtom);
    expect(f.business_object_id).toBe("");
    expect(f.statuses).toEqual(["failed", "active", "closed"]);
    expect(f.window).toBe("24h");
  });

  it("flowsFilterAtom — toggling status narrows / widens the list", () => {
    const store = createStore();
    const flows: BusinessFlowSummary[] = [
      { ...SAMPLE, business_key: "k1", status: "failed" },
      { ...SAMPLE, business_key: "k2", status: "active" },
      { ...SAMPLE, business_key: "k3", status: "closed" },
    ];
    store.set(flowsListAtom, flows);
    store.set(flowsTotalAtom, 3);

    // Helper — empty statuses means "no status filter applied".
    const applyStatusFilter = (all: BusinessFlowSummary[], statuses: string[]) =>
      statuses.length === 0
        ? all
        : all.filter((f) => statuses.includes(f.status));

    // Default filter = all 3 statuses → see all 3.
    let visible = applyStatusFilter(flows, store.get(flowsFilterAtom).statuses);
    expect(visible.map((f) => f.business_key).sort()).toEqual(["k1", "k2", "k3"]);

    // Narrow to only "failed" → see 1.
    store.set(flowsFilterAtom, { ...store.get(flowsFilterAtom), statuses: ["failed"] });
    visible = applyStatusFilter(flows, store.get(flowsFilterAtom).statuses);
    expect(visible.map((f) => f.business_key)).toEqual(["k1"]);

    // Empty statuses = show all (caller-side "no filter").
    store.set(flowsFilterAtom, { ...store.get(flowsFilterAtom), statuses: [] });
    visible = applyStatusFilter(flows, store.get(flowsFilterAtom).statuses);
    expect(visible.map((f) => f.business_key).sort()).toEqual(["k1", "k2", "k3"]);
  });

  it("flowsFilterAtom — window=1h filters out older flows", () => {
    const store = createStore();
    const now = Math.floor(Date.now() / 1000);
    const flows: BusinessFlowSummary[] = [
      { ...SAMPLE, business_key: "fresh", last_started_at: now - 60 },         // 1 min ago
      { ...SAMPLE, business_key: "old",   last_started_at: now - 60 * 60 * 3 }, // 3h ago
    ];
    store.set(flowsListAtom, flows);

    // 1h window → only "fresh"
    store.set(flowsFilterAtom, { ...store.get(flowsFilterAtom), window: "1h" });
    const cutoff1h = now - 60 * 60;
    const visible1h = flows.filter(
      (f) => f.last_started_at !== null && f.last_started_at >= cutoff1h,
    );
    expect(visible1h.map((f) => f.business_key)).toEqual(["fresh"]);

    // "all" window → both
    store.set(flowsFilterAtom, { ...store.get(flowsFilterAtom), window: "all" });
    const visibleAll = flows; // no filtering
    expect(visibleAll.map((f) => f.business_key).sort()).toEqual(["fresh", "old"]);
  });

  it("flowsFilterAtom — business_object_id exact match", () => {
    const store = createStore();
    const flows: BusinessFlowSummary[] = [
      { ...SAMPLE, business_key: "k1|threshold-calibration|Transformer-A",
        business_object_id: "Transformer-A" },
      { ...SAMPLE, business_key: "k2|threshold-calibration|Transformer-B",
        business_object_id: "Transformer-B" },
    ];
    store.set(flowsListAtom, flows);

    // Helper — empty query means "no filter applied".
    const applyObjectFilter = (all: BusinessFlowSummary[], q: string) =>
      q === "" ? all : all.filter((f) => f.business_object_id === q);

    // No filter — see both
    let visible = applyObjectFilter(flows, store.get(flowsFilterAtom).business_object_id);
    expect(visible).toHaveLength(2);

    // Exact match on Transformer-A
    store.set(flowsFilterAtom, { ...store.get(flowsFilterAtom), business_object_id: "Transformer-A" });
    visible = applyObjectFilter(flows, store.get(flowsFilterAtom).business_object_id);
    expect(visible.map((f) => f.business_key)).toEqual(["k1|threshold-calibration|Transformer-A"]);
  });
});
