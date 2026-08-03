// OBSTACK Phase C.0 — one-row card for the global business-flow list.
//
// Shows summary stats + status pill + drill-in affordance. Clicking
// the card dispatches `selectedFlowKeyAtom` so the FlowsDetail page
// (Phase C.4) can pick it up.

import { Activity, AlertTriangle, CheckCircle2, Clock } from "lucide-react";
import { useSetAtom } from "jotai";
import type { BusinessFlowSummary } from "@/api/flows";
import { selectedFlowKeyAtom, flowsListAtom } from "@/atoms/flows";
import { cn } from "@/lib/utils";

interface BusinessFlowCardProps {
  flow: BusinessFlowSummary;
}

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = s / 60;
  if (m < 60) return `${m.toFixed(1)}m`;
  return `${(m / 60).toFixed(1)}h`;
}

function formatTimestamp(ts: number | null): string {
  if (ts === null) return "—";
  // Server timestamps are epoch seconds; multiply to ms.
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

function StatusPill({ status }: { status: BusinessFlowSummary["status"] }) {
  const cls =
    status === "failed"
      ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
      : status === "active"
        ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
        : "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300";
  const Icon =
    status === "failed" ? AlertTriangle : status === "active" ? Clock : CheckCircle2;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium",
        cls,
      )}
    >
      <Icon className="h-3 w-3" />
      {status}
    </span>
  );
}

export function BusinessFlowCard({ flow }: BusinessFlowCardProps) {
  const setSelectedFlowKey = useSetAtom(selectedFlowKeyAtom);

  return (
    <button
      type="button"
      onClick={() => setSelectedFlowKey(flow.business_key)}
      className={cn(
        "flex w-full items-center gap-4 rounded-lg border border-border bg-card p-4 text-left",
        "transition-colors hover:border-primary/50 hover:bg-card/80",
      )}
      aria-label={`Business flow ${flow.business_key}`}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-secondary text-primary">
        <Activity className="h-5 w-5" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-mono text-sm font-medium">
            {flow.business_object_id || flow.business_key}
          </span>
          <StatusPill status={flow.status} />
        </div>
        <div className="mt-1 truncate font-mono text-xs text-muted-foreground">
          {flow.business_key}
        </div>
      </div>

      <dl className="hidden grid-cols-4 gap-6 text-xs md:grid">
        <div>
          <dt className="text-muted-foreground">Sessions</dt>
          <dd className="font-medium">{flow.session_count}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Finished</dt>
          <dd className="font-medium">{flow.finished_count}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Failed</dt>
          <dd
            className={cn(
              "font-medium",
              flow.failed_count > 0 && "text-red-600 dark:text-red-400",
            )}
          >
            {flow.failed_count}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Last duration</dt>
          <dd className="font-medium">{formatDuration(flow.last_duration_ms)}</dd>
        </div>
      </dl>

      <time
        dateTime={
          flow.last_started_at !== null
            ? new Date(flow.last_started_at * 1000).toISOString()
            : undefined
        }
        className="hidden whitespace-nowrap text-xs text-muted-foreground lg:block"
      >
        {formatTimestamp(flow.last_started_at)}
      </time>
    </button>
  );
}

// Convenience export for the FlowsPage list-render loop.
export function BusinessFlowCardList({
  flows,
}: {
  flows: BusinessFlowSummary[];
}) {
  const setFlowsList = useSetAtom(flowsListAtom);
  // Keep the global atom in sync so FlowsDetail (Phase C.4) can read it.
  setFlowsList(flows);
  return (
    <div className="flex flex-col gap-2">
      {flows.map((flow) => (
        <BusinessFlowCard key={flow.business_key} flow={flow} />
      ))}
    </div>
  );
}
