// Client → Server
export type ClientMessage =
  | { type: "send_message"; session_id?: string; content: string }
  | { type: "cancel"; session_id: string };

/**
 * Per-message envelope: optional server-assigned sequence number (REQ-WEB-01, D-04).
 * - `seq`: monotonic u64 (represented as JS `number` since JS numbers are safe up
 *   to 2^53). Used by the client to detect gaps during reconnect storms.
 * - Existing event handlers tolerate the absence of `seq` (backward-compatible).
 * - Debug mode (`?debug=1`) logs gaps; normal mode is silent.
 *
 * Implementation note: the union members each carry an optional `seq` field
 * rather than being wrapped in a shared base — TS discriminated unions cannot
 * cleanly intersect with a base, and this additive shape preserves all
 * existing handler logic.
 */
export type ServerMessageBase = { seq?: number };

// Server → Client
export type ServerMessage =
  | ({ type: "session_created"; session_id: string } & ServerMessageBase)
  | ({ type: "text_delta"; session_id: string; text: string } & ServerMessageBase)
  | ({ type: "text_complete"; session_id: string; text: string } & ServerMessageBase)
  | ({ type: "thinking_delta"; session_id: string; text: string } & ServerMessageBase)
  | ({ type: "thinking_complete"; session_id: string; text: string } & ServerMessageBase)
  | ({
      type: "tool_start";
      session_id: string;
      tool_id: string;
      tool_name: string;
      input: Record<string, unknown>;
    } & ServerMessageBase)
  | ({
      type: "tool_result";
      session_id: string;
      tool_id: string;
      output: string;
      success: boolean;
    } & ServerMessageBase)
  | ({ type: "error"; session_id: string; message: string } & ServerMessageBase)
  | ({ type: "done"; session_id: string } & ServerMessageBase)
  | ({
      type: "tool_execution";
      session_id: string;
      execution: {
        id: string;
        session_id: string;
        tool_name: string;
        source: string;
        input: unknown;
        output: unknown | null;
        status: "running" | "success" | "failed" | "timeout";
        started_at: number;
        duration_ms: number | null;
        error: string | null;
      };
    } & ServerMessageBase)
  | ({
      type: "token_budget_update";
      session_id: string;
      budget: {
        total: number;
        system_prompt: number;
        dynamic_context: number;
        history: number;
        free: number;
        usage_percent: number;
        degradation_level: number;
      };
    } & ServerMessageBase)
  | ({
      type: "context_degraded";
      session_id: string;
      level: string;
      usage_pct: number;
    } & ServerMessageBase)
  | ({
      type: "memory_flushed";
      session_id: string;
      facts_count: number;
    } & ServerMessageBase)
  | ({
      type: "memory_added";
      session_id: string;
      memory_id: string;
      content: string;
      category?: string;
    } & ServerMessageBase)
  | ({
      type: "approval_required";
      session_id: string;
      tool_name: string;
      tool_id: string;
      risk_level: string;
    } & ServerMessageBase)
  | ({
      type: "security_blocked";
      session_id: string;
      reason: string;
    } & ServerMessageBase)
  | ({ type: "typing"; session_id: string; state: boolean } & ServerMessageBase);