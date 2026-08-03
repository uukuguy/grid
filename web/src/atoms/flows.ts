// OBSTACK Phase C.0 — flows atoms (OBSTACK_HANDBOOK.md Ch14).
//
// Lightweight Jotai state for the business-flow dashboard. The atoms
// hold the currently-displayed list of business flows + the active
// selected flow + the multi-dimensional filter (Phase C.5). Real
// data is fetched via `flowsApi` (see `web/src/api/flows.ts`).

import { atom } from "jotai";
import type { BusinessFlowSummary } from "@/api/flows";

export const flowsListAtom = atom<BusinessFlowSummary[]>([]);
export const flowsTotalAtom = atom<number>(0);

/** Active selected flow business_key (null = none selected). */
export const selectedFlowKeyAtom = atom<string | null>(null);

/** Selected flow's full summary (loaded on detail view). */
export const selectedFlowSummaryAtom = atom<{
  status: string;
  event_count: number;
  last_duration_ms: number | null;
  layer_counts: Record<string, number>;
} | null>(null);

// ─── Phase C.5 — multi-dimensional filter ─────────────────────────────
//
// `business_object_id` and `status` are sent to the L4 server (status
// is OR'd client-side because the server accepts a single status).
// `window` is client-side only — the L4 list endpoint doesn't expose
// a time-window param today. When OBSTACK moves to a server-side
// time window (Phase C.5.1), swap the client filter for a query param.

export type FlowWindow = "1h" | "24h" | "7d" | "all";

export interface FlowsFilter {
  business_object_id: string;
  /** Multi-select — OR'd client-side. */
  statuses: ("failed" | "active" | "closed")[];
  window: FlowWindow;
}

export const flowsFilterAtom = atom<FlowsFilter>({
  business_object_id: "",
  statuses: ["failed", "active", "closed"],
  window: "24h",
});

