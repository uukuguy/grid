// OBSTACK Phase E.1 — TS mirror of eaasp_common.SessionsClient.
// Wraps the grid-server /api/v1/sessions/* surface for the React
// UI and (eventually) the eaasp-cli-v2 session subcommands. Same
// 1:1 surface as the Python client; method names, response
// shapes, and HTTP semantics are identical so the two stay in
// lockstep.
import { api } from "./client";
import {
  type ActiveSessionsResponse,
  type ListExecutionsParams,
  type SessionInfo,
  type SessionsClientOptions,
  type StartSessionRequest,
  type StartSessionResponse,
} from "./sessions_types";

export type {
  ActiveSessionsResponse,
  ListExecutionsParams,
  SessionInfo,
  StartSessionRequest,
  StartSessionResponse,
  SessionsClientOptions,
};

export class SessionsClient {
  private baseUrl: string;
  private authToken: string | null;
  private getToken: (() => string | null) | null;

  constructor(options: SessionsClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    // Security fix (MEDIUM auth-token-lifecycle): refresh-aware
    // ``getToken`` callback when supplied; falls back to the
    // constructor-snapshotted ``authToken`` for back-compat.
    this.authToken = options.authToken ?? null;
    this.getToken = options.getToken ?? null;
  }

  async list_active(): Promise<ActiveSessionsResponse> {
    return this.fetch<ActiveSessionsResponse>("/api/v1/sessions/active");
  }

  async get_session(id: string): Promise<SessionInfo> {
    return this.fetch<SessionInfo>(`/api/v1/sessions/${encodeURIComponent(id)}`);
  }

  async list_executions(
    id: string,
    params?: ListExecutionsParams,
  ): Promise<unknown> {
    // OBSTACK Phase E.1 — pass through the wire shape (a top-level
    // JSON array of ToolExecution records) rather than coercing it
    // to ``Record<string, unknown>``. The Python
    // ``SessionsClient.list_executions`` mirror returns ``Any`` for
    // the same reason (see ``sessions_client.py``).
    const search: string[] = [];
    if (params) search.push(`limit=${params.limit}`);
    const qs = search.length > 0 ? `?${search.join("&")}` : "";
    return this.fetch<unknown>(
      `/api/v1/sessions/${encodeURIComponent(id)}/executions${qs}`,
    );
  }

  async start_session(req: StartSessionRequest): Promise<StartSessionResponse> {
    return this.fetch<StartSessionResponse>("/api/v1/sessions/start", {
      method: "POST",
      body: JSON.stringify(req),
    });
  }

  async stop_session(id: string): Promise<void> {
    await this.fetch<void>(
      `/api/v1/sessions/${encodeURIComponent(id)}/stop`,
      { method: "DELETE" },
      { allow204: true },
    );
  }

  async kill_session(id: string): Promise<void> {
    await this.fetch<void>(
      `/api/v1/sessions/${encodeURIComponent(id)}/kill`,
      { method: "POST" },
      { allow204: true },
    );
  }

  async resume_session(id: string): Promise<void> {
    await this.fetch<void>(
      `/api/v1/sessions/${encodeURIComponent(id)}/resume`,
      { method: "POST" },
      { allow204: true },
    );
  }

  // ─── Internals ─────────────────────────────────────
  private async fetch<T>(
    path: string,
    init: RequestInit = {},
    extra: { allow204?: boolean } = {},
  ): Promise<T> {
    const headers = new Headers(init.headers ?? {});
    // Security fix (MEDIUM auth-token-lifecycle): read the
    // token fresh per request via the ``getToken`` callback;
    // falls back to the snapshotted ``authToken``. Logout /
    // refresh now propagates without re-creating the client.
    const token = this.getToken ? this.getToken() : this.authToken;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const resp = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(
        `Sessions ${resp.status} ${resp.statusText || ""} from ${path}: ${text}`,
      );
    }
    if (extra.allow204 || resp.status === 204) return undefined as unknown as T;
    if (resp.headers.get("content-type")?.includes("application/json")) {
      return (await resp.json()) as T;
    }
    return undefined as unknown as T;
  }
}

// Phase E.1 — the default client reuses the existing `api`
// singleton. The token is read fresh per request (via
// ``getToken`` callback) so logout / refresh propagates
// without re-creating the client. Default base URL falls back
// to localhost:3001 (grid-server) until /api/v1/config reports
// a real base URL.
export const sessionsClient = new SessionsClient({
  baseUrl:
    (typeof import.meta !== "undefined" &&
      (import.meta as { env?: Record<string, string> }).env
        ?.VITE_SESSIONS_BASE_URL) ||
    "http://127.0.0.1:3001",
  getToken: () => api.getToken(),
});
