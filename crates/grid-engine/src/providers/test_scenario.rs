//! Test-scenario header forwarding (Phase 7.1 T05 / CONTRACT-02 / D138).
//!
//! Wire path: `UserMessage.metadata["x-test-scenario"]` →
//! session-scoped value in this module → `X-Test-Scenario` HTTP header
//! on the outbound LLM provider request.
//!
//! Why this lives in `grid-engine/src/providers/`: the LLM provider
//! (`crates/grid-engine/src/providers/openai.rs`) is the one site that
//! emits the outbound HTTP request and needs to read the value. The
//! caller (grid-runtime harness) sets the value via
//! [`set_session_scenario`] before invoking the executor's Send turn.
//!
//! ## Why not env var
//!
//! ADR-V2-028 strict-by-default lineage prohibits env-var shims in
//! production code paths (see CONTEXT.md D-05 step 3 + plan-checker
//! I003). Even gated behind `cfg(debug_assertions)` or a
//! `contract-test` feature, an env-var shim read in the OpenAI
//! provider would be a leaky test-fixture abstraction. The
//! `UserMessage.metadata` map is a documented proto3 field
//! (`proto/eaasp/runtime/v2/runtime.proto:98`) — using it for an
//! in-contract scoped value is strictly cleaner than a sidecar env.
//!
//! ## Threading model
//!
//! Process-global `RwLock<HashMap<session_id, String>>`. The set/clear
//! pair brackets the executor's Send turn. The OpenAI provider reads
//! the value via [`current_session_scenario`] at request-build time;
//! when no session is in scope (the typical "no test" case) the lookup
//! resolves to `None` and no header is emitted.
//!
//! Session is identified by the **current** in-flight session id, set
//! by [`set_session_scenario`]. Since the OpenAI provider does not
//! know the session id at request-build time, we shortcut to a
//! "current scenario" cell that is set/cleared around the Send call.

use std::sync::{OnceLock, RwLock};

#[derive(Default)]
struct ScenarioState {
    /// Current in-flight scenario. `None` when no test scenario is
    /// active for the request being built (which is the
    /// productionprocess-baseline path).
    current: Option<String>,
}

fn state() -> &'static RwLock<ScenarioState> {
    static STATE: OnceLock<RwLock<ScenarioState>> = OnceLock::new();
    STATE.get_or_init(|| RwLock::new(ScenarioState::default()))
}

/// Set the scenario string for the next outbound LLM request.
///
/// The caller (grid-runtime harness) reads
/// `UserMessage.metadata["x-test-scenario"]` and forwards via this
/// function BEFORE invoking the executor's Send. The value persists
/// until cleared via [`clear_session_scenario`].
///
/// Production callers (no metadata key set) do not invoke this
/// function; the state stays at its `None` default.
pub fn set_session_scenario(scenario: impl Into<String>) {
    if let Ok(mut s) = state().write() {
        s.current = Some(scenario.into());
    }
}

/// Clear the scenario value previously set via
/// [`set_session_scenario`].
pub fn clear_session_scenario() {
    if let Ok(mut s) = state().write() {
        s.current = None;
    }
}

/// Read the current scenario value for the in-flight request.
///
/// Returns `None` in the production case where no metadata key was
/// present. Returns `Some(scenario)` when the harness forwarded a
/// `x-test-scenario` metadata key for the active Send turn.
///
/// Read by the OpenAI / Anthropic provider request-build sites to add
/// the `X-Test-Scenario` HTTP header.
pub fn current_session_scenario() -> Option<String> {
    state().read().ok().and_then(|s| s.current.clone())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_none() {
        // Each test starts with cleared state.
        clear_session_scenario();
        assert!(current_session_scenario().is_none());
    }

    #[test]
    fn set_and_read_roundtrip() {
        set_session_scenario("deny-non-required-tool");
        assert_eq!(
            current_session_scenario().as_deref(),
            Some("deny-non-required-tool"),
        );
        clear_session_scenario();
        assert!(current_session_scenario().is_none());
    }
}
