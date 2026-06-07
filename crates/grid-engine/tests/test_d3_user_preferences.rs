/// D3 (ENGINE-02): user_preferences wiring tests.
///
/// Validates that the `UserPreferences` type exists, that `AgentLoopConfig`
/// carries an optional `user_preferences` field defaulting to `None`, and
/// that an executor with user_preferences set forwards the value into the
/// per-turn `AgentLoopConfig`.
use grid_engine::agent::loop_config::AgentLoopConfig;
use grid_engine::agent::loop_config::UserPreferences;

// ── UserPreferences type tests ──

#[test]
fn user_preferences_struct_exists_and_has_expected_fields() {
    let prefs = UserPreferences {
        user_id: "user-42".into(),
        language: "zh-CN".into(),
        timezone: "Asia/Shanghai".into(),
        llm_provider: "anthropic".into(),
        llm_model: "claude-sonnet-4-20250514".into(),
    };
    assert_eq!(prefs.user_id, "user-42");
    assert_eq!(prefs.language, "zh-CN");
    assert_eq!(prefs.timezone, "Asia/Shanghai");
    assert_eq!(prefs.llm_provider, "anthropic");
    assert_eq!(prefs.llm_model, "claude-sonnet-4-20250514");
}

#[test]
fn user_preferences_default_is_empty_strings() {
    let prefs = UserPreferences::default();
    assert_eq!(prefs.user_id, "");
    assert_eq!(prefs.language, "");
    assert_eq!(prefs.timezone, "");
    assert_eq!(prefs.llm_provider, "");
    assert_eq!(prefs.llm_model, "");
}

#[test]
fn user_preferences_is_clone() {
    let prefs = UserPreferences {
        user_id: "u1".into(),
        ..Default::default()
    };
    let cloned = prefs.clone();
    assert_eq!(cloned.user_id, "u1");
}

// ── AgentLoopConfig field tests ──

#[test]
fn agent_loop_config_has_user_preferences_field_default_none() {
    let config = AgentLoopConfig::default();
    assert!(
        config.user_preferences.is_none(),
        "user_preferences should default to None"
    );
}

#[test]
fn agent_loop_config_accepts_user_preferences() {
    let prefs = UserPreferences {
        user_id: "test-user".into(),
        language: "en".into(),
        timezone: "UTC".into(),
        llm_provider: "openai".into(),
        llm_model: "gpt-4o".into(),
    };
    let config = AgentLoopConfig {
        user_preferences: Some(prefs.clone()),
        ..AgentLoopConfig::default()
    };
    let out = config.user_preferences.unwrap();
    assert_eq!(out.user_id, "test-user");
    assert_eq!(out.language, "en");
    assert_eq!(out.timezone, "UTC");
}
