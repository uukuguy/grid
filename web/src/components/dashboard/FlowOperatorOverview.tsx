import type { BusinessFlowSummary } from "@/api/flows";
import {
  deriveFlowAlerts,
  deriveFlowStats,
  rankSlowFlows,
} from "@/lib/obstack/operatorViews";

interface FlowOperatorOverviewProps {
  flows: BusinessFlowSummary[];
}

function formatDuration(durationMs: number | null): string {
  if (durationMs === null) return "—";
  if (durationMs < 1_000) return `${durationMs}ms`;
  return `${(durationMs / 1_000).toFixed(1)}s`;
}

export function FlowOperatorOverview({ flows }: FlowOperatorOverviewProps) {
  const stats = deriveFlowStats(flows);
  const alerts = deriveFlowAlerts(flows);
  const slowFlows = rankSlowFlows(flows, 3);

  return (
    <section className="grid gap-3 rounded-lg border border-border bg-card/50 p-3 lg:grid-cols-[2fr_3fr]">
      <div aria-label="Operator flow statistics" className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
        <Stat label="Total" value={`${stats.total} total`} />
        <Stat label="Failed" value={stats.failed} />
        <Stat label="Active" value={stats.active} />
        <Stat label="Closed" value={stats.closed} />
        <Stat label="Completion" value={`${(stats.completionRate * 100).toFixed(0)}%`} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div aria-label="Operator flow alerts">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Alerts</h2>
          {alerts.length === 0 ? (
            <p className="mt-1 text-xs text-muted-foreground">No current flow alerts.</p>
          ) : (
            <ul className="mt-1 space-y-1 text-xs">
              {alerts.map((alert) => (
                <li
                  key={`${alert.businessKey}:${alert.reason}`}
                  className={alert.severity === "critical"
                    ? "rounded bg-red-100 px-2 py-1 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                    : "rounded bg-yellow-100 px-2 py-1 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300"}
                >
                  <span className="font-medium">{alert.businessKey}</span>: {alert.message}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div aria-label="Slowest visible business flows">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Slowest visible</h2>
          {slowFlows.length === 0 ? (
            <p className="mt-1 text-xs text-muted-foreground">No duration data.</p>
          ) : (
            <ol className="mt-1 space-y-1 text-xs">
              {slowFlows.map((flow) => (
                <li key={flow.business_key} className="flex justify-between gap-2 rounded bg-secondary/40 px-2 py-1">
                  <span className="truncate font-mono">{flow.business_key}</span>
                  <span className="shrink-0 text-muted-foreground">{formatDuration(flow.last_duration_ms)}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded bg-secondary/40 px-2 py-1">
      <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  );
}
