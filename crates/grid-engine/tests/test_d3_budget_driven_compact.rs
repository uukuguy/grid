/// D3 (ENGINE-02): budget-driven proactive compaction tests.
///
/// Validates that the harness proactive compaction gate correctly skips
/// compaction when sufficient token budget remains (`task_budget_remaining
/// >= MIN_TURN_BUDGET`) and proceeds when budget is tight
/// (`task_budget_remaining < MIN_TURN_BUDGET`).
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

// ── Budget-tight gate tests ──

#[test]
fn budget_tight_is_true_when_remaining_lt_min_turn_budget() {
    // 100 < 4096 → budget is tight → should compact
    assert!(
        harness::is_budget_tight(100),
        "budget 100 < MIN_TURN_BUDGET should be tight"
    );
}

#[test]
fn budget_tight_is_false_when_remaining_gte_min_turn_budget() {
    // 5000 >= 4096 → budget is not tight → skip compaction
    assert!(
        !harness::is_budget_tight(5000),
        "budget 5000 >= MIN_TURN_BUDGET should NOT be tight"
    );
}

#[test]
fn budget_tight_is_false_at_exact_min_turn_budget() {
    // 4096 >= 4096 → not tight (boundary case)
    assert!(
        !harness::is_budget_tight(harness::MIN_TURN_BUDGET),
        "budget exactly at MIN_TURN_BUDGET should NOT be tight"
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
