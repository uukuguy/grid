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

/**
 * Wire-envelope shape (Phase E.3 commit fix — 2026-08-08).
 *
 * grid-server's ``ws_chunk::map_event`` serializes every
 * streamed chunk as a single envelope:
 *   ``{"type": "chunk", "session_id": <sid>,
 *       "chunk_type": <1-9>, "payload": {<inner>}}``
 *
 * Canonical ``chunk_type`` values (per
 * ``crates/grid-server/src/ws_chunk.rs::map_event``):
 *   1 = ``text_delta``       → ``payload.text``
 *   2 = ``thinking_delta``   → ``payload.text``
 *   3 = ``tool_start``       → ``payload.{tool_name, tool_id, input}``
 *   4 = ``tool_result``      → ``payload.{tool_id, output, success}``
 *   5 = ``done``             → ``payload.text`` (rare; primarily ``{type:'done'}``)
 *   6 = ``error``            → ``payload.message``
 *
 * The previous TS handler had this hardcoded as a flat
 * ``ServerMessage.type === "text_delta"`` discriminator — but
 * the wire actually sends ``type: "chunk"`` with embedded
 * ``chunk_type``. The flat discriminator meant the entire
 * switch fell through to default-no-op for every streamed
 * frame, which made the Chat tab show "no response" even
 * though the WS pipeline was working correctly.
 *
 * ``mapWireMessageToServerMessage`` translates the wire
 * envelope into the existing flat ``ServerMessage``
 * discriminator so the rest of the handler chain
 * (``web/src/ws/events.ts``) keeps working unchanged.
 */
export type ChunkEnvelope = {
  type: "chunk";
  session_id: string;
  chunk_type: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
  payload?: Record<string, unknown>;
  seq?: number;
};

export function mapWireMessageToServerMessage(raw: unknown): ServerMessage | null {
  // TS narrowing helper — accepts the union of legacy flat
  // ServerMessage + new chunk envelope. Falls through to
  // null when the shape doesn't match either.
  if (!raw || typeof raw !== "object") return null;
  const m = raw as Record<string, unknown>;
  const type = m["type"];
  // Legacy flat path (preserves backward-compatibility for
  // any future server that decides to drop the chunk
  // envelope).
  switch (type) {
    case "session_created":
    case "text_delta":
    case "text_complete":
    case "thinking_delta":
    case "thinking_complete":
    case "done":
    case "typing":
    case "error":
    case "token_budget_update":
    case "context_degraded":
    case "memory_flushed":
    case "memory_added":
    case "approval_required":
    case "security_blocked":
      return raw as ServerMessage;
    case "tool_execution": // legacy alias for tool_start / tool_result
      // not in the current grid-server output but kept as a
      // safety net for older server versions.
      return raw as ServerMessage;
  }
  // New chunk-envelope path (the default branch that
  // catches ``{"type":"chunk", ...}``).
  if (type === "chunk") {
    const env = raw as ChunkEnvelope;
    // Defensive: drop chunks with a missing/empty
    // session_id rather than synthesize one. A chunk without
    // a session is a wire-protocol bug we don't want to
    // silently paper over (downstream the handler
    // attributes state by session, so a fake id would
    // leak state).
    if (typeof env.session_id !== "string" || env.session_id.length === 0) {
      return null;
    }
    const sid = env.session_id;
    const payload = env.payload ?? {};
    const text = (payload["text"] as string | undefined) ?? "";
    const message = (payload["message"] as string | undefined) ?? "";
    switch (env.chunk_type) {
      case 1:
        // text_delta — most common streaming case.
        return { type: "text_delta", session_id: sid, text };
      case 2:
        // thinking_delta — same shape, different atom.
        return { type: "thinking_delta", session_id: sid, text };
      case 3:
        // tool_start — pass through with the payload
        // fields that the existing handler expects.
        return {
          type: "tool_start",
          session_id: sid,
          tool_name: (payload["tool_name"] as string) ?? "",
          tool_id: (payload["tool_id"] as string) ?? "",
          input: (payload["input"] as Record<string, unknown>) ?? {},
          seq: env.seq,
        };
      case 4:
        return {
          type: "tool_result",
          session_id: sid,
          tool_id: (payload["tool_id"] as string) ?? "",
          output: (payload["output"] as string) ?? "",
          success: (payload["success"] as boolean) ?? true,
          seq: env.seq,
        };
      case 5:
        // done chunk — the canonical close signal for the
        // response. Surface as a ``done`` event so the
        // events.ts handler resets buffers + commits the
        // streamed text to ``messagesAtom`` (the
        // commit-on-``done`` safety net added in this
        // same fix).
        return { type: "done", session_id: sid, seq: env.seq };
      case 6:
        // error chunk — surface as the ``error`` event so
        // the events.ts handler appends a visible chat
        // bubble + toast. Before this fix, ``type: "chunk"``
        // fell through to default in the handler's switch,
        // silently swallowing LLM errors.
        return { type: "error", session_id: sid, message, seq: env.seq };
      default:
        // unknown chunk_type — drop it (forward-compatible).
        return null;
    }
  }
  return null;
}