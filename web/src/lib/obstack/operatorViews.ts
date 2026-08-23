import type {
  BusinessFlowSummary,
  FlowAlert,
  FlowStats,
} from "../../api/obstack_types";

export const STALE_ACTIVE_THRESHOLD_SECONDS = 900;

export function deriveFlowStats(flows: BusinessFlowSummary[]): FlowStats {
  const stats: FlowStats = {
    total: flows.length,
    failed: 0,
    active: 0,
    closed: 0,
    completionRate: 0,
  };

  for (const flow of flows) {
    stats[flow.status] += 1;
  }
  stats.completionRate = stats.total === 0 ? 0 : stats.closed / stats.total;
  return stats;
}

export function deriveFlowAlerts(
  flows: BusinessFlowSummary[],
  nowSeconds = Math.floor(Date.now() / 1000),
): FlowAlert[] {
  const alerts: FlowAlert[] = [];
  for (const flow of flows) {
    if (flow.status === "failed") {
      alerts.push({
        businessKey: flow.business_key,
        severity: "critical",
        reason: "failed",
        message: "Business flow failed",
      });
    }
    if (
      flow.status === "active" &&
      flow.last_started_at !== null &&
      nowSeconds - flow.last_started_at >= STALE_ACTIVE_THRESHOLD_SECONDS
    ) {
      alerts.push({
        businessKey: flow.business_key,
        severity: "warning",
        reason: "stale-active",
        message: "Business flow has been active for at least 15 minutes",
      });
    }
  }
  return alerts;
}

export function rankSlowFlows(
  flows: BusinessFlowSummary[],
  limit: number,
): BusinessFlowSummary[] {
  return flows
    .filter((flow) => flow.last_duration_ms !== null)
    .sort((left, right) => right.last_duration_ms! - left.last_duration_ms!)
    .slice(0, Math.max(0, Math.floor(limit)));
}
