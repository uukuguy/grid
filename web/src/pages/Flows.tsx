// OBSTACK Phase C.0 — global observability dashboard entry point.
//
// Phase C.0 step 1 (commit C.3): list page only. Shows every business
// flow in L4 with summary stats. Clicking a row sets selectedFlowKeyAtom;
// the FlowsDetail page (commit C.4) reads it.
//
// Phase C.5 (commit C.5): multi-dimensional filter — status multi-select
// + business_object_id text search + time window. Server-pushable
// filters go through `flowsApi.list({...})`; time window is client-side
// only (L4 list endpoint doesn't expose a window param today —
// Phase C.5.1 will move it server-side).
//
// Refresh cadence: on tab activation + manual refresh button + when the
// filter changes (debounced via useEffect deps).

import { useEffect, useState, useCallback, useMemo } from "react";
import { useAtomValue, useSetAtom } from "jotai";
import { RefreshCw, Activity, Search, X } from "lucide-react";
import {
  flowsApi,
  type BusinessFlowSummary,
} from "@/api/flows";
import {
  flowsListAtom,
  flowsTotalAtom,
  selectedFlowKeyAtom,
  flowsFilterAtom,
  type FlowWindow,
} from "@/atoms/flows";
import { cn } from "@/lib/utils";
import { BusinessFlowCard } from "@/components/dashboard/BusinessFlowCard";
import { FlowsDetail } from "@/components/dashboard/FlowsDetail";
import { FlowOperatorOverview } from "@/components/dashboard/FlowOperatorOverview";

// ─── Window → seconds ────────────────────────────────────────────────

const WINDOW_SECONDS: Record<FlowWindow, number | null> = {
  "1h": 60 * 60,
  "24h": 24 * 60 * 60,
  "7d": 7 * 24 * 60 * 60,
  all: null,
};

// ─── Component ────────────────────────────────────────────────────────

export default function Flows() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flows, setFlows] = useState<BusinessFlowSummary[]>([]);
  const [total, setTotal] = useState(0);

  const setFlowsList = useSetAtom(flowsListAtom);
  const setFlowsTotal = useSetAtom(flowsTotalAtom);
  const selectedKey = useAtomValue(selectedFlowKeyAtom);
  const setSelectedKey = useSetAtom(selectedFlowKeyAtom);
  const filter = useAtomValue(flowsFilterAtom);
  const setFilter = useSetAtom(flowsFilterAtom);

  // ─── Load (server-pushable filters) ────────────────────────────────
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Status: pick the first selected as the server filter (L4 takes one);
      // the rest get client-side OR'd below.
      const serverStatus = filter.statuses.length === 1 ? filter.statuses[0] : undefined;
      const res = await flowsApi.list({
        limit: 200,
        business_object_id: filter.business_object_id || undefined,
        status: serverStatus,
      });
      setFlows(res.flows);
      setTotal(res.total);
      setFlowsList(res.flows);
      setFlowsTotal(res.total);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load flows";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [
    filter.business_object_id,
    filter.statuses.length,
    filter.statuses[0],
    setFlowsList,
    setFlowsTotal,
  ]);

  useEffect(() => {
    void load();
  }, [load]);

  // ─── Client-side filters: status (multi) + window ─────────────────
  const visibleFlows = useMemo(() => {
    const windowSec = WINDOW_SECONDS[filter.window];
    const nowSec = Math.floor(Date.now() / 1000);
    const cutoff = windowSec === null ? null : nowSec - windowSec;
    return flows.filter((f) => {
      if (filter.statuses.length > 0 && !filter.statuses.includes(f.status)) {
        return false;
      }
      if (cutoff !== null && f.last_started_at !== null && f.last_started_at < cutoff) {
        return false;
      }
      return true;
    });
  }, [flows, filter.statuses, filter.window]);

  const toggleStatus = (s: "failed" | "active" | "closed") => {
    setFilter({
      ...filter,
      statuses: filter.statuses.includes(s)
        ? filter.statuses.filter((x) => x !== s)
        : [...filter.statuses, s],
    });
  };

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-semibold">Business Flows</h1>
          <span className="rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {visibleFlows.length} visible flow{visibleFlows.length === 1 ? "" : "s"}
            {" · "}{total} session{total === 1 ? "" : "s"}
          </span>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className={cn(
            "flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm",
            "hover:bg-secondary disabled:opacity-50",
          )}
          aria-label="Refresh business flows"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          Refresh
        </button>
      </header>

      {/* ─── Phase C.5 filter bar ───────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-card/50 p-2 text-sm">
        {/* business_object_id text search */}
        <label className="flex items-center gap-1">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="business_object_id…"
            value={filter.business_object_id}
            onChange={(e) =>
              setFilter({ ...filter, business_object_id: e.target.value })
            }
            className="w-48 rounded-md border border-border bg-background px-2 py-1 text-xs"
            aria-label="Filter by business object ID"
          />
          {filter.business_object_id && (
            <button
              type="button"
              onClick={() => setFilter({ ...filter, business_object_id: "" })}
              aria-label="Clear business object ID filter"
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </label>

        {/* Status multi-select checkboxes */}
        <div className="flex items-center gap-1 border-l border-border pl-2">
          {(["failed", "active", "closed"] as const).map((s) => (
            <label key={s} className="flex items-center gap-1">
              <input
                type="checkbox"
                checked={filter.statuses.includes(s)}
                onChange={() => toggleStatus(s)}
                className="h-3 w-3"
                aria-label={`Filter ${s}`}
              />
              <span className="capitalize text-xs">{s}</span>
            </label>
          ))}
        </div>

        {/* Window selector */}
        <label className="flex items-center gap-1 border-l border-border pl-2">
          <span className="text-xs text-muted-foreground">Window</span>
          <select
            value={filter.window}
            onChange={(e) =>
              setFilter({ ...filter, window: e.target.value as FlowWindow })
            }
            className="rounded-md border border-border bg-background px-2 py-1 text-xs"
            aria-label="Time window"
          >
            <option value="1h">1h</option>
            <option value="24h">24h</option>
            <option value="7d">7d</option>
            <option value="all">all</option>
          </select>
        </label>

        {/* Reset */}
        <button
          type="button"
          onClick={() =>
            setFilter({
              business_object_id: "",
              statuses: ["failed", "active", "closed"],
              window: "24h",
            })
          }
          className="ml-auto rounded-md border border-border bg-background px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
        >
          Reset
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/40 dark:text-red-300">
          Failed to load flows: {error}
        </div>
      )}

      <FlowOperatorOverview flows={visibleFlows} />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[2fr_3fr]">
        {/* Left: filtered list of business flows */}
        <section
          aria-label="Business flow list"
          className="flex min-h-0 flex-col gap-2 overflow-y-auto pr-2"
        >
          {loading && flows.length === 0 ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : visibleFlows.length === 0 ? (
            <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              {flows.length === 0
                ? "No business flows yet. Run the OBSTACK demo (scripts/v315-obstack-demo.sh) to seed sample flows."
                : "No flows match the current filter."}
            </p>
          ) : (
            visibleFlows.map((flow) => (
              <BusinessFlowCard key={flow.business_key} flow={flow} />
            ))
          )}
        </section>

        {/* Right: detail panel for selected flow */}
        <section
          aria-label="Business flow detail"
          className="min-h-0 overflow-y-auto rounded-lg border border-border bg-card p-4"
        >
          {selectedKey ? (
            <FlowsDetail
              businessKey={selectedKey}
              onClose={() => setSelectedKey(null)}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              Select a business flow from the list to see its timeline, sessions, and evaluation report.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
