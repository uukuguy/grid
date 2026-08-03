// OBSTACK Phase C.0 — global observability dashboard entry point.
//
// Phase C.0 step 1 (commit C.3): list page only. Shows every business
// flow in L4 with summary stats. Clicking a row sets selectedFlowKeyAtom;
// the FlowsDetail page (commit C.4) reads it.
//
// Refresh cadence: on tab activation + manual refresh button (no
// auto-polling yet — Phase C.0.1 polish).

import { useEffect, useState, useCallback } from "react";
import { useAtomValue, useSetAtom } from "jotai";
import { RefreshCw, Activity } from "lucide-react";
import { flowsApi, type BusinessFlowSummary } from "@/api/flows";
import { flowsListAtom, flowsTotalAtom, selectedFlowKeyAtom } from "@/atoms/flows";
import { cn } from "@/lib/utils";
import { BusinessFlowCard } from "@/components/dashboard/BusinessFlowCard";
import { FlowsDetail } from "@/components/dashboard/FlowsDetail";

export default function Flows() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flows, setFlows] = useState<BusinessFlowSummary[]>([]);
  const [total, setTotal] = useState(0);

  const setFlowsList = useSetAtom(flowsListAtom);
  const setFlowsTotal = useSetAtom(flowsTotalAtom);
  const selectedKey = useAtomValue(selectedFlowKeyAtom);
  const setSelectedKey = useSetAtom(selectedFlowKeyAtom);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await flowsApi.list({ limit: 50 });
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
  }, [setFlowsList, setFlowsTotal]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-semibold">Business Flows</h1>
          <span className="rounded-md bg-secondary px-2 py-0.5 text-xs font-medium text-muted-foreground">
            {total} session{total === 1 ? "" : "s"}
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
          <RefreshCw
            className={cn("h-4 w-4", loading && "animate-spin")}
          />
          Refresh
        </button>
      </header>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/40 dark:text-red-300">
          Failed to load flows: {error}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[2fr_3fr]">
        {/* Left: list of business flows */}
        <section
          aria-label="Business flow list"
          className="flex min-h-0 flex-col gap-2 overflow-y-auto pr-2"
        >
          {loading && flows.length === 0 ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : flows.length === 0 ? (
            <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              No business flows yet. Run the OBSTACK demo
              (<code className="rounded bg-secondary px-1">scripts/v315-obstack-demo.sh</code>)
              to seed sample flows.
            </p>
          ) : (
            flows.map((flow) => (
              <BusinessFlowCard
                key={flow.business_key}
                flow={flow}
              />
            ))
          )}
        </section>

        {/* Right: detail panel for selected flow (Phase C.4) */}
        <section
          aria-label="Business flow detail"
          className="min-h-0 overflow-y-auto rounded-lg border border-border bg-card p-4"
        >
          {selectedKey ? (
            <FlowsDetail businessKey={selectedKey} onClose={() => setSelectedKey(null)} />
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
