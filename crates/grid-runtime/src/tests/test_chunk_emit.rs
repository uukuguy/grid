//! Wire-emission unit tests for `chunk_type_to_proto` (Phase 5.3 CONTRACT-01,
//! ADR-V2-021 contract-v1.2.0).
//!
//! Asserts that the private mapper at `crates/grid-runtime/src/service.rs:29`
//! produces the correct wire ints for the two new wire values added in 5.3:
//!
//! - `CHUNK_TYPE_THINKING_TRACE = 8` (D-02 end-of-turn structured reasoning)
//! - `CHUNK_TYPE_ATTACHMENT_REF = 9` (D-03 opaque blob URI envelope)
//!
//! Also includes a pin-down test for existing wires so an accidental
//! renumber (Pitfall 2 — closed-enum invariant) trips this suite.

use crate::proto::ChunkType;
use crate::service::chunk_type_to_proto;

#[test]
fn chunk_emit_thinking_trace_maps_to_wire_8() {
    assert_eq!(
        chunk_type_to_proto("thinking_trace"),
        ChunkType::ThinkingTrace as i32
    );
    assert_eq!(chunk_type_to_proto("thinking_trace"), 8);
}

#[test]
fn chunk_emit_attachment_ref_maps_to_wire_9() {
    assert_eq!(
        chunk_type_to_proto("attachment_ref"),
        ChunkType::AttachmentRef as i32
    );
    assert_eq!(chunk_type_to_proto("attachment_ref"), 9);
}

#[test]
fn chunk_emit_unknown_chunk_falls_to_unspecified() {
    // Anti-silent-fallback contract (ADR-V2-021): unknown emits UNSPECIFIED
    // AND logs at tracing::error level so the violation is loud at the
    // gRPC boundary, not silent.
    assert_eq!(
        chunk_type_to_proto("not_a_real_wire"),
        ChunkType::Unspecified as i32
    );
    assert_eq!(chunk_type_to_proto("not_a_real_wire"), 0);
}

#[test]
fn chunk_emit_existing_wires_unchanged() {
    // Pitfall 2 (no-renumber) regression — verify existing wires didn't
    // shift when wires 8/9 were appended in contract-v1.2.0.
    assert_eq!(chunk_type_to_proto("text_delta"), 1);
    assert_eq!(chunk_type_to_proto("thinking"), 2);
    assert_eq!(chunk_type_to_proto("tool_start"), 3);
    assert_eq!(chunk_type_to_proto("tool_result"), 4);
    assert_eq!(chunk_type_to_proto("done"), 5);
    assert_eq!(chunk_type_to_proto("error"), 6);
    assert_eq!(chunk_type_to_proto("workflow_continuation"), 7);
}
