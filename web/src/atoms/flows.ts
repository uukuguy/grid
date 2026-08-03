// OBSTACK Phase C.0 — flows atoms (OBSTACK_HANDBOOK.md Ch14).
//
// Lightweight Jotai state for the business-flow dashboard. The atoms
// hold the currently-displayed list of business flows + the active
// selected flow. Real data is fetched via `flowsApi` (see
// `web/src/api/flows.ts`).

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
