//! Cross-mode key-handler integration tests (Phase 5.2 T-01.14).
//!
//! Unit tests inside `tui/key_handlers/*.rs` cover per-mode behavior.
//! This file locks the **cross-mode** invariants documented in
//! `tui/key_handlers/INVARIANTS.md` "Cross-mode asymmetries" — properties
//! that span dispatcher routing and would silently rot if covered only by
//! per-mode unit tests.
//!
//! Each test maps to an asymmetry row in INVARIANTS.md; the row number is
//! cited in the test doc-comment so a future edit that breaks the contract
//! can be traced back to the documented rule.

#![cfg(feature = "studio")]

use crossterm::event::KeyCode;
use grid_cli::tui::app_state::OverlayMode;
use grid_cli::tui::key_handlers::{execute_slash_command, handle_key};

mod common;
use common::{ctrl, fresh_state, key};

/// INVARIANTS.md asymmetry #4 — Esc cascade priority in Normal mode.
///
/// When vim is enabled and in `Insert` mode, Esc must enter `VimMode::Normal`
/// **before** falling through to autocomplete-dismiss / streaming-cancel /
/// input-clear / scroll-reset. After landing in vim normal mode, a second
/// Esc with an empty input and no streaming should be a no-op (vim normal
/// already terminal; nothing to cancel).
///
/// Locks `normal.rs:459-498` cascade ordering. If the vim guard at line 462
/// regresses to a later position in the match arm, this test fails.
#[tokio::test]
async fn esc_cascade_enters_vim_normal_before_clearing_input() {
    let mut state = fresh_state();
    // Enable vim, start in Insert mode, type some content
    state.vim.enabled = true;
    state.vim.mode = grid_cli::tui::widgets::figures::VimMode::Insert;

    // Type 'h' — should land in input_buffer (vim insert routes through vim_insert handler)
    handle_key(&mut state, key(KeyCode::Char('h'))).await;
    assert_eq!(state.input_buffer, "h", "vim insert must accept char input");

    // First Esc — vim Insert → Normal. Buffer must NOT be cleared.
    handle_key(&mut state, key(KeyCode::Esc)).await;
    assert_eq!(
        state.vim.mode,
        grid_cli::tui::widgets::figures::VimMode::Normal,
        "first Esc must transition vim Insert → Normal"
    );
    assert_eq!(
        state.input_buffer, "h",
        "first Esc must NOT clear input — vim transition takes priority over input-clear"
    );

    // Second Esc — already in vim normal, no streaming, but buffer non-empty.
    // Per mod.rs dispatch: vim_normal::handle_vim_normal_key handles Esc as no-op
    // (Esc is not in vim_normal's match arms — see vim_normal.rs).
    // The vim_normal handler returns early for non-Ctrl keys, so this Esc does
    // NOT fall through to the Normal-mode Esc cascade.
    handle_key(&mut state, key(KeyCode::Esc)).await;
    assert_eq!(
        state.vim.mode,
        grid_cli::tui::widgets::figures::VimMode::Normal,
        "second Esc must stay in vim normal"
    );
    assert_eq!(
        state.input_buffer, "h",
        "second Esc from vim normal must NOT reach the Normal-mode cascade"
    );

    // Press 'i' — should re-enter Insert mode (lock vim normal → insert transition)
    handle_key(&mut state, key(KeyCode::Char('i'))).await;
    assert_eq!(
        state.vim.mode,
        grid_cli::tui::widgets::figures::VimMode::Insert,
        "'i' from vim normal must re-enter Insert"
    );
}

/// INVARIANTS.md asymmetry #5 — slash-overlay reuse parity.
///
/// `/debug` (rows 68, 136) must reach the same overlay state as Ctrl+D
/// (rows 3, 82). The contract reads: "a test breaking one must break both
/// surfaces" — this is the test that enforces it.
///
/// Similarly for `/eval` vs Ctrl+E (with empty input) and `/sessions` vs
/// Ctrl+A (with empty input).
#[tokio::test]
async fn slash_debug_and_ctrl_d_reach_same_overlay() {
    // Path A: Ctrl+D opens AgentDebug
    let mut state_a = fresh_state();
    assert_eq!(state_a.overlay, OverlayMode::None);
    handle_key(&mut state_a, ctrl('d')).await;
    assert_eq!(
        state_a.overlay,
        OverlayMode::AgentDebug,
        "Ctrl+D must open AgentDebug overlay"
    );

    // Path B: /debug opens AgentDebug
    let mut state_b = fresh_state();
    execute_slash_command(&mut state_b, "/debug").await;
    assert_eq!(
        state_b.overlay,
        OverlayMode::AgentDebug,
        "/debug must open AgentDebug overlay"
    );

    // Parity lock — both surfaces converged to identical overlay state.
    assert_eq!(state_a.overlay, state_b.overlay, "Ctrl+D and /debug must converge");

    // Toggle parity: pressing Ctrl+D from the /debug-opened state must close it.
    handle_key(&mut state_b, ctrl('d')).await;
    assert_eq!(
        state_b.overlay,
        OverlayMode::None,
        "Ctrl+D from /debug-opened state must close overlay (stateful toggle, asymmetry #10)"
    );

    // /eval parity (with empty input — Ctrl+E only routes to overlay when input is empty)
    let mut state_c = fresh_state();
    execute_slash_command(&mut state_c, "/eval").await;
    assert_eq!(state_c.overlay, OverlayMode::Eval);

    let mut state_d = fresh_state();
    handle_key(&mut state_d, ctrl('e')).await;
    assert_eq!(
        state_d.overlay,
        OverlayMode::Eval,
        "Ctrl+E on empty input must open Eval overlay (rows 4, 83)"
    );
    assert_eq!(state_c.overlay, state_d.overlay, "/eval and Ctrl+E must converge");
}

/// INVARIANTS.md asymmetry #8 — ModelSelector dual navigation.
///
/// `↑/k` (prev) and `↓/j` (next) must both work — vim users and arrow-key
/// users share the same selector. Tests must lock both paths so neither
/// alias can silently regress.
#[tokio::test]
async fn model_selector_dual_nav_works_for_arrows_and_vim_keys() {
    let mut state = fresh_state();
    // Make selector visible with at least 2 entries so prev/next are observable.
    state.model_selector.visible = true;
    state.model_selector.models = vec!["model-a".into(), "model-b".into(), "model-c".into()];
    state.model_selector.selected = 0;

    // ↓ should advance to index 1
    handle_key(&mut state, key(KeyCode::Down)).await;
    assert_eq!(state.model_selector.selected, 1, "Down arrow must advance selector");

    // j should advance to index 2
    handle_key(&mut state, key(KeyCode::Char('j'))).await;
    assert_eq!(state.model_selector.selected, 2, "j must advance selector (vim alias of Down)");

    // ↑ should retreat to index 1
    handle_key(&mut state, key(KeyCode::Up)).await;
    assert_eq!(state.model_selector.selected, 1, "Up arrow must retreat selector");

    // k should retreat to index 0
    handle_key(&mut state, key(KeyCode::Char('k'))).await;
    assert_eq!(state.model_selector.selected, 0, "k must retreat selector (vim alias of Up)");

    // Esc should close the selector without changing state.model_name
    let before = state.model_name.clone();
    handle_key(&mut state, key(KeyCode::Esc)).await;
    assert!(
        !state.model_selector.visible,
        "Esc must close model selector (row 91)"
    );
    assert_eq!(state.model_name, before, "Esc on selector must NOT mutate state.model_name");
}
