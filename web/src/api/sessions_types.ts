// OBSTACK Phase E.1 — TypeScript mirror of the shared Python
// sessions_models.py. Update both files when grid-server changes a
// field. Every consumer (React UI, eaasp-cli-v2 subcommands) reads
// from this single types file or its Python equivalent.

export interface SessionInfo {
  id: string;
  created_at: string;
  status: "running" | "stopped" | "completed" | "failed";
}

/**
 * Wire shape (per ``grid-server /api/v1/sessions/active``):
 * ``{"sessions": ["<uuid>", "<uuid>", ...], "count": N, "max": 64}``.
 * Each entry is a UUID **string**, NOT a typed ``SessionInfo``
 * object — grid-server doesn't include ``created_at`` /
 * ``status`` on this endpoint. Callers needing the full shape
 * use ``/api/v1/sessions`` (returns typed objects).
 */
export interface ActiveSessionsResponse {
  sessions: string[];
  count: number;
  max: number;
}

export interface StartSessionRequest {
  agent_id: string;
  input: Record<string, unknown>;
}

export interface StartSessionResponse {
  session_id: string;
}

export interface ListExecutionsParams {
  limit: number;
}

export interface SessionsClientOptions {
  baseUrl: string;
  /** Snapshotted auth token (refresh-invisible). Prefer
   *  ``getToken`` when the caller owns its own auth state. */
  authToken?: string | null;
  /** Per-request token getter — LOGOUT / refresh propagate
   *  without re-creating the client. Wins over ``authToken``
   *  when both are supplied. */
  getToken?: () => string | null;
}
