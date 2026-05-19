//! 5.3 NEW-F1 ADR-V2-027 prototype regression tests.
//!
//! Exercises the `Quirks` struct in `crates/grid-engine/src/providers/quirks.rs`
//! at its 2-field shape (per Phase 5.3 RESEARCH §"Open Questions (RESOLVED)" Q3
//! = F2: `null_tool_id_continuation` lives in `LingProvider`, NOT in shared
//! `Quirks`).

use grid_engine::providers::quirks::{Quirks, ReasoningContentField};

#[test]
fn quirks_default_is_strict_openai() {
    let q = Quirks::default();
    assert_eq!(q.reasoning_content_field, ReasoningContentField::None);
    assert_eq!(q.no_done_marker, false);
}

#[test]
fn quirks_ling_profile_enables_no_done_marker() {
    let q = Quirks {
        no_done_marker: true,
        ..Default::default()
    };
    assert_eq!(q.no_done_marker, true);
    // Ling profile does NOT touch reasoning_content_field — it stays default.
    assert_eq!(q.reasoning_content_field, ReasoningContentField::None);
}

#[test]
fn quirks_deepseek_profile_enables_multi_field_reasoning() {
    let q = Quirks {
        reasoning_content_field: ReasoningContentField::MultiField,
        ..Default::default()
    };
    assert_eq!(q.reasoning_content_field, ReasoningContentField::MultiField);
    // DeepSeek sends [DONE] markers — strict on stream end.
    assert_eq!(q.no_done_marker, false);
}

#[test]
fn quirks_is_cloneable_and_debug_printable() {
    let q = Quirks::default();
    let q2 = q.clone();
    let s = format!("{:?}", q2);
    assert!(s.contains("Quirks"));
}

#[test]
fn reasoning_content_field_default_is_none() {
    let r = ReasoningContentField::default();
    assert_eq!(r, ReasoningContentField::None);
}
