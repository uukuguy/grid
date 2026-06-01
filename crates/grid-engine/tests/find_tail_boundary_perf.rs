//! ENGINE-05 (D103) — measured baseline for `find_tail_boundary` at the
//! long-conversation worst case identified in DEFERRED_LEDGER L233. The
//! function is internal (`fn` in `compaction_pipeline.rs`) — this test
//! reaches it via the `#[doc(hidden)] pub fn find_tail_boundary_for_tests`
//! shim re-exported from `grid_engine::context`.
//!
//! Regression threshold: <50ms for a 200-turn synthetic conversation at
//! 200k tail_protect_tokens. This is GENEROUS (~10x typical observed)
//! and exists to catch true O(N^2) regressions, not micro-optimization
//! deltas. Tighten when a faster baseline is established.

use std::time::Instant;

use grid_types::{ChatMessage, ContentBlock, MessageRole};

/// Build a synthetic 200-turn conversation with roughly uniform message
/// sizes. Each message is ~500 chars (~125 tokens estimated), giving
/// the function ~25k tokens of total content to walk against a 200k
/// tail budget — i.e. the entire conversation fits in tail, exercising
/// the worst-case scan length.
fn synth_messages(turn_count: usize) -> Vec<ChatMessage> {
    let body: String = "x".repeat(500);
    (0..turn_count)
        .map(|i| {
            let role = if i % 2 == 0 {
                MessageRole::User
            } else {
                MessageRole::Assistant
            };
            ChatMessage {
                role,
                content: vec![ContentBlock::Text {
                    text: format!("turn-{}: {}", i, body),
                }],
            }
        })
        .collect()
}

#[test]
fn find_tail_boundary_perf_baseline() {
    let messages = synth_messages(200);
    let tail_budget: u64 = 200_000;
    let start = Instant::now();
    let _boundary =
        grid_engine::context::find_tail_boundary_for_tests(&messages, tail_budget);
    let elapsed = start.elapsed();
    assert!(
        elapsed.as_millis() < 50,
        "find_tail_boundary at 200 turns × 200k tail must complete <50ms, \
         got {:?}. This is a regression canary; if the function was \
         recently refactored, investigate before relaxing the bound.",
        elapsed
    );
    println!(
        "ENGINE-05 (D103) baseline: find_tail_boundary 200x200k = {:?}",
        elapsed
    );
}
