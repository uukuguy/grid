//! ENGINE-01 (D102) — verify `compaction:` block in config.yaml round-trips
//! through the grid-server config loader and lands on
//! `AgentRuntimeConfig.compaction`. Strict-by-default per ADR-V2-028:
//! unknown keys reject; missing block falls back to default.

use grid_engine::context::CompactionPipelineConfig;
use grid_server::config::Config;

#[test]
fn compaction_block_round_trips_through_yaml() {
    // YAML body with a non-default value on one field. Round-trip:
    // serde_yaml -> Config -> assert.
    let yaml = r#"
compaction:
  proactive_threshold_pct: 60
  tail_protect_tokens: 32000
  reactive_only: true
"#;
    let cfg: Config = serde_yaml::from_str(yaml).expect("config must parse");
    assert_eq!(cfg.compaction.proactive_threshold_pct, 60);
    assert_eq!(cfg.compaction.tail_protect_tokens, 32_000);
    assert!(cfg.compaction.reactive_only);
    // Fields not mentioned in YAML retain the default values.
    let defaults = CompactionPipelineConfig::default();
    assert_eq!(cfg.compaction.summary_max_tokens, defaults.summary_max_tokens);
    assert_eq!(cfg.compaction.keep_recent_messages, defaults.keep_recent_messages);
}

#[test]
fn missing_compaction_block_uses_default() {
    // ENGINE-01: no `compaction:` key at all -> struct gets ::default()
    // via the outer `#[serde(default)]` attribute on Config.compaction.
    let yaml = r#"
server:
  host: 127.0.0.1
  port: 3001
"#;
    let cfg: Config = serde_yaml::from_str(yaml).expect("config must parse");
    let defaults = CompactionPipelineConfig::default();
    assert_eq!(cfg.compaction.proactive_threshold_pct, defaults.proactive_threshold_pct);
    assert_eq!(cfg.compaction.tail_protect_tokens, defaults.tail_protect_tokens);
    assert_eq!(cfg.compaction.reactive_only, defaults.reactive_only);
}

#[test]
fn unknown_compaction_key_rejects_per_adr_v2_028() {
    // ENGINE-01 strict-by-default: a typo'd key under compaction must
    // raise a serde error, not silently fall back to default. This is
    // the ADR-V2-028 lineage canary at the grid-server config loader
    // boundary.
    let yaml = r#"
compaction:
  tail_protect_tokenz: 12345
"#;
    let result: std::result::Result<Config, _> = serde_yaml::from_str(yaml);
    assert!(
        result.is_err(),
        "unknown key `tail_protect_tokenz` must reject; got Ok"
    );
}
