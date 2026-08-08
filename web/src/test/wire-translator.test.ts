// OBSTACK Phase E.3 commit fix (2026-08-08) — regression test
// for the WS chunk-envelope translator that was the root
// cause of "Chat tab — no response" on grid-web.
//
// grid-server's ``ws_chunk::map_event`` serializes every
// streamed chunk as a single envelope:
//
//   {"type": "chunk", "session_id": <sid>,
//       "chunk_type": <1-9>, "payload": {<inner>}}
//
// Chunk type enum (per crates/grid-server/src/ws_chunk.rs):
//   1 = text_delta      payload: {text}
//   2 = thinking_delta  payload: {text}
//   3 = tool_start      payload: {tool_name, tool_id, input}
//   4 = tool_result     payload: {tool_id, output, success}
//   5 = done            payload: {text} (rare, flat done also exists)
//   6 = error           payload: {message}
//
// Pre-fix: handler had a flat ``type: "text_delta"`` discriminator
// but the wire sends ``type: "chunk"``. Every streamed frame fell
// through to default-no-op; the chat appeared silent even
// though the WS pipeline was working.
//
// Post-fix: ``mapWireMessageToServerMessage`` translates the
// envelope into the existing flat discriminator. This test
// locks every chunk_type translation path + the legacy
// flat-path back-compat.

import { describe, it, expect } from "vitest";
import { mapWireMessageToServerMessage } from "../ws/types";

describe("WS chunk-envelope translator (Phase E.3 fix)", () => {
  it("translates chunk_type=1 (text_delta) → flat text_delta", () => {
    const wire = {
      type: "chunk",
      session_id: "sess-1",
      chunk_type: 1,
      payload: { text: "hello" },
    };
    expect(mapWireMessageToServerMessage(wire)).toEqual({
      type: "text_delta",
      session_id: "sess-1",
      text: "hello",
    });
  });

  it("translates chunk_type=2 (thinking_delta) → flat thinking_delta", () => {
    expect(
      mapWireMessageToServerMessage({
        type: "chunk",
        session_id: "sess-1",
        chunk_type: 2,
        payload: { text: "thinking..." },
      }),
    ).toEqual({
      type: "thinking_delta",
      session_id: "sess-1",
      text: "thinking...",
    });
  });

  it("translates chunk_type=3 (tool_start) → flat tool_start", () => {
    const out = mapWireMessageToServerMessage({
      type: "chunk",
      session_id: "sess-1",
      chunk_type: 3,
      payload: { tool_name: "Bash", tool_id: "t1", input: { cmd: "ls" } },
    });
    expect(out).toMatchObject({
      type: "tool_start",
      session_id: "sess-1",
      tool_name: "Bash",
      tool_id: "t1",
    });
  });

  it("translates chunk_type=4 (tool_result) → flat tool_result with success default", () => {
    const out = mapWireMessageToServerMessage({
      type: "chunk",
      session_id: "sess-1",
      chunk_type: 4,
      payload: { tool_id: "t1", output: "ok" },
    });
    expect(out).toMatchObject({
      type: "tool_result",
      session_id: "sess-1",
      tool_id: "t1",
      output: "ok",
      success: true,
    });
  });

  it("translates chunk_type=5 (done chunk) → flat done", () => {
    expect(
      mapWireMessageToServerMessage({
        type: "chunk",
        session_id: "sess-1",
        chunk_type: 5,
      }),
    ).toEqual({
      type: "done",
      session_id: "sess-1",
    });
  });

  it("translates chunk_type=6 (error) → flat error (was silently swallowed pre-fix)", () => {
    expect(
      mapWireMessageToServerMessage({
        type: "chunk",
        session_id: "sess-1",
        chunk_type: 6,
        payload: { message: "OpenAI API error 400" },
      }),
    ).toEqual({
      type: "error",
      session_id: "sess-1",
      message: "OpenAI API error 400",
    });
  });

  it("preserves legacy flat ServerMessage shapes (back-compat)", () => {
    // The translator must NOT regress the existing flat
    // discriminator when a server (current or older) drops
    // the chunk envelope and just sends ``{type:"text_delta"}``
    // directly. This protects against silent breakage if
    // grid-server ever flips back to flat envelopes.
    expect(
      mapWireMessageToServerMessage({
        type: "text_delta",
        session_id: "sess-1",
        text: "hello",
      }),
    ).toEqual({
      type: "text_delta",
      session_id: "sess-1",
      text: "hello",
    });
  });

  it("returns null on unknown chunk_type (drops, doesn't crash)", () => {
    // Future chunk types (the wire enum is 1-9 today; 10+
    // could appear). Pass-through as null means the handler
    // won't try to update atom state with garbage.
    expect(
      mapWireMessageToServerMessage({
        type: "chunk",
        session_id: "sess-1",
        chunk_type: 99,
        payload: { future_field: "..." },
      }),
    ).toBeNull();
  });

  it("returns null on malformed input (defensive)", () => {
    expect(mapWireMessageToServerMessage(null)).toBeNull();
    expect(mapWireMessageToServerMessage(undefined)).toBeNull();
    expect(mapWireMessageToServerMessage("string")).toBeNull();
    expect(mapWireMessageToServerMessage(42)).toBeNull();
    // Object with no ``type`` field — also malformed.
    expect(mapWireMessageToServerMessage({ foo: "bar" })).toBeNull();
  });

  it("drops chunk envelope with missing session_id (no fallback ID)", () => {
    // Defensive: if L4 ever sends a chunk without a
    // session_id, we shouldn't fabricate one. Drop it.
    expect(
      mapWireMessageToServerMessage({
        type: "chunk",
        chunk_type: 1,
        payload: { text: "orphan chunk" },
      }),
    ).toBeNull();
  });
});
