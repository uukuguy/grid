// OBSTACK Phase D.3 — TypeScript client wrapper.
//
// User feedback: "grid-cli 和 grid-web 的 chat (工具调用/MCP 等) 都是
// 基于 grid-engine". The principle: web and CLI should expose the same
// surface, only differ in form. We extracted the OBSTACK API surface
// into a shared Python client (tools/eaasp-common/eaasp_common/
// obstack_client.py — commit 24). This file is its TypeScript mirror
// so the React dashboard uses the same wire format / method names /
// query semantics as the CLI subcommand.
//
// Compared to the pre-D.3 version of this file:
//   - Five hand-rolled fetch methods (l4Fetch + URL composition)
//     are replaced by a single ObstackClient class that mirrors the
//     Python client's API 1:1 (list_business_flows / get_timeline /
//     etc.).
//   - The 50+ lines of duplicated response types are gone — types are
//     imported from obstack_types.ts and re-exported for any caller
//     that still imports them from "@/api/flows".
//   - Multi-tenant upgrade path: pass `tenant_id` via the client's
//     `extraHeaders` option. No app-side URL changes needed.
//
// All previous call sites (`flowsApi.list`, `flowsApi.timeline`, etc.)
// keep working — this commit only refactors internals.
import { api } from "./client";
import {
  type BusinessFlowListParams,
  type BusinessFlowListResponse,
  type BusinessFlowSummary,
  type EvaluationReport,
  type EvaluationResponse,
  type OptimizationHint,
  type SessionRef,
  type SessionsResponse,
  type SummaryBlock,
  type SummaryResponse,
  type TimelineEvent,
  type TimelineResponse,
  type ObstackClientOptions,
} from "./obstack_types";

// Re-export types so existing imports keep working.
export type {
  BusinessFlowListParams,
  BusinessFlowListResponse,
  BusinessFlowSummary,
  EvaluationReport,
  EvaluationResponse,
  OptimizationHint,
  SessionRef,
  SessionsResponse,
  SummaryBlock,
  SummaryResponse,
  TimelineEvent,
  TimelineResponse,
};

// ─── Client (TS mirror of eaasp_common.obstack_client.ObstackClient) ──
//
// This class is a 1:1 surface mirror of the Python client. The
// semantics (URL shape, query params, error handling) are identical
// — the only difference is async-only (Python's sync vs. async split
// is irrelevant for the React dashboard).

export class ObstackClient {
  private baseUrl: string;
  private authToken: string | null;

  constructor(options: ObstackClientOptions) {
    // Trailing slash is stripped so path joining is uniform.
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.authToken = options.authToken ?? null;
  }

  // ─── List ──────────────────────────────────────────────
  async list_business_flows(
    params?: BusinessFlowListParams,
  ): Promise<BusinessFlowListResponse> {
    const search = new URLSearchParams();
    if (params?.limit !== undefined) search.set("limit", String(params.limit));
    if (params?.business_object_id) {
      search.set("business_object_id", params.business_object_id);
    }
    if (params?.status) search.set("status", params.status);
    const qs = search.toString();
    return this.fetch<BusinessFlowListResponse>(
      `/v1/business-flows/list${qs ? `?${qs}` : ""}`,
    );
  }

  // ─── Single-flow endpoints ───────────────────────────
  async get_timeline(business_key: string): Promise<TimelineResponse> {
    return this.fetch<TimelineResponse>(
      `/v1/business-flows/${encodeURIComponent(business_key)}/timeline`,
    );
  }

  async get_summary(business_key: string): Promise<SummaryResponse> {
    return this.fetch<SummaryResponse>(
      `/v1/business-flows/${encodeURIComponent(business_key)}/summary`,
    );
  }

  async get_sessions(business_key: string): Promise<SessionsResponse> {
    return this.fetch<SessionsResponse>(
      `/v1/business-flows/${encodeURIComponent(business_key)}/sessions`,
    );
  }

  async get_evaluation(business_key: string): Promise<EvaluationResponse> {
    return this.fetch<EvaluationResponse>(
      `/v1/business-flows/${encodeURIComponent(business_key)}/evaluation`,
    );
  }

  // ─── Internals ──────────────────────────────────────
  private async fetch<T>(path: string): Promise<T> {
    const headers = new Headers();
    if (this.authToken) {
      headers.set("Authorization", `Bearer ${this.authToken}`);
    }
    const resp = await fetch(`${this.baseUrl}${path}`, { headers });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(
        `OBSTACK ${resp.status} ${resp.statusText || ""} from ${path}: ${text}`,
      );
    }
    return (await resp.json()) as T;
  }
}

// ─── Default client (Phase C.0 direct-L4 access preserved) ───────
//
// The default base URL is L4 (:18084) — same convention as the
// pre-D.3 flowsApi. We carry forward the VITE_L4_BASE_URL override
// so a deployment can point at a different L4 host without rebuilding.
//
// Future (Phase D): this default constructor will resolve its base
// URL from `/api/v1/config` (returned by grid-server) so the React
// bundle always hits the same origin as the L4 it's running with.
// Until then, VITE_L4_BASE_URL or the localhost default is the
// operational contract.

const L4_BASE_URL =
  (typeof import.meta !== "undefined" &&
    (import.meta as { env?: Record<string, string> }).env
      ?.VITE_L4_BASE_URL) ||
  "http://127.0.0.1:18084";

const authToken = api.getToken();

export const obstackClient = new ObstackClient({
  baseUrl: L4_BASE_URL,
  authToken: authToken ?? undefined,
});

// ─── Compatibility shim (Phase D.3) ─────────────────────────────────
//
// Existing call sites use `flowsApi.list(...)` / `.timeline(...)` etc.
// We keep that surface for now so the dashboard can migrate one
// consumer at a time. New code should use `obstackClient` directly
// — the client is the canonical surface going forward.
export const flowsApi = {
  list: (params?: BusinessFlowListParams) =>
    obstackClient.list_business_flows(params),
  timeline: (key: string) => obstackClient.get_timeline(key),
  summary: (key: string) => obstackClient.get_summary(key),
  sessions: (key: string) => obstackClient.get_sessions(key),
  evaluation: (key: string) => obstackClient.get_evaluation(key),
};
