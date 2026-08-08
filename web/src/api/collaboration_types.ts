// OBSTACK Phase E.4 — TS mirror of eaasp_common.CollaborationClient
// models. 1:1 mirror of tools/eaasp-common/.../collaboration_models.py.
// When grid-server changes a wire field, both these files (and
// the Python parent) get updated together.

export interface CollaborationStatus {
  id: string;
  agent_count: number;
  active_agent: string | null;
  pending_proposals: number;
  event_count: number;
  state_keys: string[];
}

export interface CollaborationAgent {
  id: string;
  name: string;
  capabilities: string[];
  session_id: string;
}

/**
 * Server uses ``#[serde(flatten)] event: Value`` so each event
 * carries every field at the top level, NOT nested under
 * ``event``. The TS mirror preserves that — consumers do
 * ``e.event ?? e`` (legacy UI pattern) to handle both shapes.
 */
export interface CollaborationEvent {
  event: Record<string, unknown>;
}

export interface Vote {
  agent_id: string;
  approve: boolean;
  reason: string | null;
}

export interface Proposal {
  id: string;
  from_agent: string;
  action: string;
  description: string;
  status: string;
  votes: Vote[];
}

export interface SharedStateEntry {
  key: string;
  value: unknown;
}

export interface SharedStateResponse {
  entries: SharedStateEntry[];
}

export interface CreateProposalRequest {
  from_agent: string;
  action: string;
  description: string;
}

export interface VoteRequest {
  agent_id: string;
  approve: boolean;
  reason: string | null;
}

export interface CollaborationClientOptions {
  baseUrl: string;
  /** Snapshotted auth token (refresh-invisible). Prefer
   *  ``getToken`` when the caller owns its own auth state. */
  authToken?: string | null;
  /** Per-request token getter — LOGOUT / refresh propagate
   *  without re-creating the client. Wins over ``authToken``
   *  when both are supplied. */
  getToken?: () => string | null;
}
