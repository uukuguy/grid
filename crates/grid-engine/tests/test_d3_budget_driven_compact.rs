/// D3 (ENGINE-02): budget-driven proactive compaction tests.
///
/// Validates cross-compaction task-budget accounting. Context-pressure
/// compaction is independently covered by the compaction pipeline and L1
/// contract tests, per ADR-V2-018 D4/D5.
use grid_engine::agent::harness;

// ── Budget arithmetic helpers (pure functions, testable without runtime) ──

#[test]
fn apply_budget_decrement_subtracts_input_plus_output() {
    let remaining = harness::apply_budget_decrement(10_000, 500, 200);
    assert_eq!(remaining, 9_300); // 10000 - (500 + 200)
}

#[test]
fn apply_budget_decrement_saturates_at_zero() {
    let remaining = harness::apply_budget_decrement(100, 200, 50);
    assert_eq!(remaining, 0); // saturating_sub prevents underflow
}

#[test]
fn budget_can_continue_true_when_above_min() {
    // 4096 is the MIN_TURN_BUDGET, 4097 should allow continuation
    assert!(
        harness::budget_can_continue(4097),
        "budget above MIN_TURN_BUDGET should allow continuation"
    );
}

#[test]
fn budget_can_continue_false_when_at_exactly_min() {
    assert!(
        !harness::budget_can_continue(harness::MIN_TURN_BUDGET),
        "budget exactly at MIN_TURN_BUDGET should NOT allow continuation"
    );
}

#[test]
fn budget_can_continue_false_when_below_min() {
    assert!(
        !harness::budget_can_continue(100),
        "budget below MIN_TURN_BUDGET should NOT allow continuation"
    );
}

// ── task_budget_multiplier tests ──

#[test]
fn task_budget_multiplier_default_is_50() {
    use grid_engine::agent::AgentLoopConfig;
    assert_eq!(AgentLoopConfig::default().task_budget_multiplier, 50);
}

// ── MIN_TURN_BUDGET constant tests ──

#[test]
fn min_turn_budget_is_4096() {
    assert_eq!(harness::MIN_TURN_BUDGET, 4096);
}
