// OBSTACK Phase E.4 — TS mirror of eaasp_common.CollaborationClient.
// Wraps the grid-server /api/v1/collaboration/* surface for the
// React UI (Collaboration.tsx + ProposalList.tsx). Same 1:1
// surface as the Python client; method names, response shapes,
// and HTTP semantics are identical so the two stay in lockstep.
//
// Phase E.4 lesson (security fix commit 1787083e): the Bearer
// header must reach the wire on every transport method — never
// let the auth token fall through ``{}``. TS client mirrors
// the ``getToken`` callback pattern from E.1/E.2/E.3 so token
// refresh / logout propagate without re-creating the client.
import { api } from "./client";
import type {
  CollaborationAgent,
  CollaborationClientOptions,
  CollaborationEvent,
  CollaborationStatus,
  CreateProposalRequest,
  Proposal,
  SharedStateEntry,
  SharedStateResponse,
  Vote,
  VoteRequest,
} from "./collaboration_types";

export type {
  CollaborationAgent,
  CollaborationClientOptions,
  CollaborationEvent,
  CollaborationStatus,
  CreateProposalRequest,
  Proposal,
  SharedStateEntry,
  SharedStateResponse,
  Vote,
  VoteRequest,
};

export class CollaborationClient {
  private baseUrl: string;
  private authToken: string | null;
  private getToken: (() => string | null) | null;

  constructor(options: CollaborationClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.authToken = options.authToken ?? null;
    this.getToken = options.getToken ?? null;
  }

  async get_status(): Promise<CollaborationStatus> {
    return this.fetch<CollaborationStatus>(
      "/api/v1/collaboration/status",
    );
  }

  async list_agents(): Promise<CollaborationAgent[]> {
    // Top-level JSON array (server returns
    // ``Json<Vec<CollaborationAgentResponse>>`` per
    // crates/grid_server::api::collaboration::list_agents).
    return (await this.fetch<unknown>(
      "/api/v1/collaboration/agents",
    )) as CollaborationAgent[];
  }

  async list_events(): Promise<CollaborationEvent[]> {
    return (await this.fetch<unknown>(
      "/api/v1/collaboration/events",
    )) as CollaborationEvent[];
  }

  async list_proposals(): Promise<Proposal[]> {
    return (await this.fetch<unknown>(
      "/api/v1/collaboration/proposals",
    )) as Proposal[];
  }

  async create_proposal(req: CreateProposalRequest): Promise<Proposal> {
    return this.fetch<Proposal>(
      "/api/v1/collaboration/proposals",
      {
        method: "POST",
        body: JSON.stringify({
          from_agent: req.from_agent,
          action: req.action,
          description: req.description,
        }),
      },
    );
  }

  async vote_on_proposal(
    proposal_id: string,
    req: VoteRequest,
  ): Promise<Vote> {
    // E.4 security-fix lesson: ``proposal_id`` is percent-encoded
    // server-side by the Python ``CollaborationClient`` (via
    // ``quote(safe="")``). The TS mirror applies the same
    // encoding so the wire shape stays identical regardless of
    // which client constructed the request.
    const encoded = encodeURIComponent(proposal_id);
    return this.fetch<Vote>(
      `/api/v1/collaboration/proposals/${encoded}/vote`,
      {
        method: "POST",
        body: JSON.stringify({
          agent_id: req.agent_id,
          approve: req.approve,
          reason: req.reason,
        }),
      },
    );
  }

  async get_shared_state(): Promise<SharedStateResponse> {
    return this.fetch<SharedStateResponse>(
      "/api/v1/collaboration/shared-state",
    );
  }

  // ─── Internals ──────────────────────────────────────────
  private async fetch<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(init.headers ?? {});
    // E.4 lesson from commit 1787083e: read the token FRESH
    // per request — module-load snapshots silently dropped
    // the Bearer header on the wire (a HIGH-severity
    // auth-bypass that needed a security fix). The default
    // client wires ``getToken: () => api.getToken()`` so
    // refresh / logout propagate without re-creating the
    // client.
    const token = this.getToken ? this.getToken() : this.authToken;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const resp = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(
        `Collab ${resp.status} ${resp.statusText || ""} from ${path}: ${text}`,
      );
    }
    if (resp.status === 204) return undefined as unknown as T;
    if (resp.headers.get("content-type")?.includes("application/json")) {
      return (await resp.json()) as T;
    }
    return undefined as unknown as T;
  }
}

// Phase E.4 — the default client reuses the existing
// ``api`` singleton for the auth token. The token is
// read fresh per request (via ``getToken`` callback) so
// logout / refresh propagate without re-creating the
// client. Same base URL default as the other clients
// (``http://127.0.0.1:3001``).
export const collaborationClient = new CollaborationClient({
  baseUrl:
    (typeof import.meta !== "undefined" &&
      (import.meta as { env?: Record<string, string> }).env
        ?.VITE_COLLABORATION_BASE_URL) ||
    "http://127.0.0.1:3001",
  getToken: () => api.getToken(),
});
