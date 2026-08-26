// OBSTACK Phase D.3 — TypeScript mirror of the shared Python client.
//
// Every field here corresponds 1:1 with a class field in
// tools/eaasp-common/src/eaasp_common/obstack_models.py. Update both
// files when the L4 wire format changes.

// ─── List endpoint ────────────────────────────────────────────────

export interface BusinessFlowSummary {
  business_key: string;
  business_object_id: string;
  skill_id: string;
  session_id: string;
  session_count: number;
  finished_count: number;
  failed_count: number;
  last_started_at: number | null;
  last_completed_at: number | null;
  last_duration_ms: number | null;
  status: "failed" | "closed" | "active";
}

export interface BusinessFlowListResponse {
  flows: BusinessFlowSummary[];
  /** Session instances represented by the returned flow rows. */
  total: number;
}

// ─── Operator-derived views ────────────────────────────────────────

export interface FlowStats {
  total: number;
  failed: number;
  active: number;
  closed: number;
  completionRate: number;
}

export interface FlowAlert {
  businessKey: string;
  severity: "critical" | "warning";
  reason: "failed" | "stale-active";
  message: string;
}

// ─── Timeline endpoint ────────────────────────────────────────────

export interface TimelineEvent {
  /** Unix epoch milliseconds. */
  ts: number;
  layer: string;
  component: string;
  event_type: string;
  payload: Record<string, unknown>;
  duration_ms: number | null;
  error: string | null;
}

export interface TimelineResponse {
  business_key: string;
  events: TimelineEvent[];
  count: number;
}

// ─── Summary endpoint ────────────────────────────────────────────

export interface SummaryBlock {
  status: string;
  started_at: number | null;
  completed_at: number | null;
  total_duration_ms: number | null;
  event_count: number;
  layer_counts: Record<string, number>;
  interrupted_layer: string | null;
}

export interface SummaryResponse {
  business_key: string;
  summary: SummaryBlock;
}

// ─── Sessions endpoint ────────────────────────────────────────────

export interface SessionRef {
  session_id: string;
  status: string;
  created_at: number;
}

export interface SessionsResponse {
  business_key: string;
  session_ids: SessionRef[];
  count: number;
}

// ─── Evaluation endpoint ──────────────────────────────────────────

export interface OptimizationHint {
  layer: string;
  metric: string;
  severity: "info" | "warn" | "critical";
  recommendation: string;
  evidence: Record<string, unknown>;
}

export interface EvaluationReport {
  window_seconds: number;
  total_flows: number;
  status_counts: Record<string, number>;
  completion_rate: number;
  interruption_heatmap: Record<string, number>;
  hints: OptimizationHint[];
}

export interface EvaluationResponse {
  business_key: string;
  report: EvaluationReport;
}

// ─── List endpoint query params (mirrored client-side) ──────────

export interface BusinessFlowListParams {
  limit?: number;
  /** Exact match on the third pipe-segment of business_key. */
  business_object_id?: string;
  /**
   * Single status to push to the server (L4 endpoint accepts one).
   * For multi-status filtering, set this to the FIRST selected status
   * and let the client-side filter handle the rest.
   */
  status?: string;
}

// ─── Client construction options ───────────────────────────────

export interface ObstackClientOptions {
  /** Base URL of the L4 OBSTACK server (e.g. "http://127.0.0.1:18084"). */
  baseUrl: string;
  /**
   * Optional Bearer token. When set, sent as the Authorization
   * header on every request. Reads from localStorage at boot by
   * the default client (see web/src/api/flows.ts).
   */
  authToken?: string;
  /**
   * Optional refresh-aware token supplier. When present, it is read at
   * request/subscription start so login, refresh, and logout do not require
   * rebuilding the client. Falls back to ``authToken`` for compatibility.
   */
  getToken?: () => string | null;
}
