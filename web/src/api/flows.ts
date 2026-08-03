// OBSTACK Phase C.0 (V315-OBSTACK-DEMO, OBSTACK_HANDBOOK.md Ch14):
//   flowsApi wraps L4 /v1/business-flows/* endpoints so the web SPA
//   can render the global observability dashboard.
//
// Multi-tenant upgrade path: add a `tenant_id` query parameter here
// (Phase D). Schema stays the same; only this client adds the param.

import { api } from "./client";

// ─── Shared types (mirror L4 flow_api.py response shapes) ────────────────

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
  total: number;
}

export interface TimelineEvent {
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

export interface SummaryResponse {
  business_key: string;
  summary: {
    status: string;
    started_at: number | null;
    completed_at: number | null;
    total_duration_ms: number | null;
    event_count: number;
    layer_counts: Record<string, number>;
    interrupted_layer: string | null;
  };
}

export interface SessionsResponse {
  business_key: string;
  session_ids: Array<{
    session_id: string;
    status: string;
    created_at: number;
  }>;
  count: number;
}

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

// ─── API surface ─────────────────────────────────────────────────────────

function encodeBusinessKey(key: string): string {
  // /v1/business-flows/{key}/... requires the path segment URL-encoded
  // (pipe character `|` is reserved in URL syntax).
  return encodeURIComponent(key);
}

export interface FlowListParams {
  limit?: number;
  business_object_id?: string;
  status?: string;
}

export const flowsApi = {
  async list(params?: FlowListParams): Promise<BusinessFlowListResponse> {
    const search = new URLSearchParams();
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.business_object_id) {
      search.set("business_object_id", params.business_object_id);
    }
    if (params?.status) search.set("status", params.status);
    const qs = search.toString();
    return api.request<BusinessFlowListResponse>(
      `/v1/business-flows/list${qs ? `?${qs}` : ""}`,
      { method: "GET" },
    );
  },

  async timeline(key: string): Promise<TimelineResponse> {
    return api.request<TimelineResponse>(
      `/v1/business-flows/${encodeBusinessKey(key)}/timeline`,
      { method: "GET" },
    );
  },

  async summary(key: string): Promise<SummaryResponse> {
    return api.request<SummaryResponse>(
      `/v1/business-flows/${encodeBusinessKey(key)}/summary`,
      { method: "GET" },
    );
  },

  async sessions(key: string): Promise<SessionsResponse> {
    return api.request<SessionsResponse>(
      `/v1/business-flows/${encodeBusinessKey(key)}/sessions`,
      { method: "GET" },
    );
  },

  async evaluation(key: string): Promise<EvaluationResponse> {
    return api.request<EvaluationResponse>(
      `/v1/business-flows/${encodeBusinessKey(key)}/evaluation`,
      { method: "GET" },
    );
  },
};
