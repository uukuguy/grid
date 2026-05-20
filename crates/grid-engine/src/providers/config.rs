use super::chain::{FailoverPolicy, LlmInstance};
use serde::{Deserialize, Serialize};

/// Error returned by [`ProviderConfig::try_from_env`].
///
/// Phase 5.4 NEW-F3 + ADR-V2-028 (Strict-by-default Configuration
/// Validation) — production callers must use the Result-returning API
/// and surface missing-env / unknown-provider explicitly. The legacy
/// silent `Default` impl is preserved ONLY for serde + test fixtures
/// per RESEARCH §4 Q7.
#[derive(Debug, thiserror::Error)]
pub enum ConfigError {
    #[error("required env var {0} is not set")]
    MissingEnv(&'static str),
    #[error("unknown LLM_PROVIDER value: {0}")]
    UnknownProvider(String),
}

/// LLM Provider configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderConfig {
    /// Provider name (e.g., "anthropic", "openai")
    pub name: String,
    /// API key (supports ${ENV_VAR} format)
    pub api_key: Option<String>,
    /// Base URL for API (optional, provider-specific default used if not set)
    pub base_url: Option<String>,
    /// Model name (optional, provider-specific default used if not set)
    pub model: Option<String>,
}

impl Default for ProviderConfig {
    fn default() -> Self {
        let name = std::env::var("LLM_PROVIDER").unwrap_or_else(|_| "openai".to_string());
        let (api_key, base_url, model) = match name.as_str() {
            "openai" => (
                std::env::var("OPENAI_API_KEY").ok(),
                std::env::var("OPENAI_BASE_URL").ok(),
                std::env::var("OPENAI_MODEL_NAME").ok(),
            ),
            "deepseek" => (
                std::env::var("DEEPSEEK_API_KEY").ok(),
                std::env::var("DEEPSEEK_BASE_URL").ok(),
                std::env::var("DEEPSEEK_MODEL_NAME").ok(),
            ),
            _ => (
                std::env::var("ANTHROPIC_API_KEY").ok(),
                std::env::var("ANTHROPIC_BASE_URL").ok(),
                std::env::var("ANTHROPIC_MODEL_NAME").ok(),
            ),
        };
        Self {
            name,
            api_key,
            base_url,
            model,
        }
    }
}

impl ProviderConfig {
    /// Strict env loader per ADR-V2-028 + Phase 5.4 NEW-F3.
    ///
    /// Returns `Err(ConfigError::MissingEnv)` if any required env var is
    /// unset, or `Err(ConfigError::UnknownProvider)` for unrecognised
    /// `LLM_PROVIDER`. Production entrypoints (grid-server, grid-runtime)
    /// MUST call this — NOT the silent-fallback `Default` impl, which is
    /// reserved for serde/test paths per RESEARCH §4 Q7.
    ///
    /// Required env vars by provider:
    /// - `openai`:    `OPENAI_API_KEY`, `OPENAI_MODEL_NAME`
    /// - `deepseek`:  `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL_NAME`
    /// - `anthropic`: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL_NAME`
    ///
    /// `<PROVIDER>_BASE_URL` remains optional in all cases (provider
    /// defaults apply when absent).
    pub fn try_from_env() -> Result<Self, ConfigError> {
        let name = std::env::var("LLM_PROVIDER")
            .map_err(|_| ConfigError::MissingEnv("LLM_PROVIDER"))?;
        let (api_key_var, model_var) = match name.as_str() {
            "openai" => ("OPENAI_API_KEY", "OPENAI_MODEL_NAME"),
            "deepseek" => ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL_NAME"),
            "anthropic" => ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL_NAME"),
            other => return Err(ConfigError::UnknownProvider(other.into())),
        };
        let api_key = std::env::var(api_key_var)
            .map_err(|_| ConfigError::MissingEnv(api_key_var))?;
        let model = std::env::var(model_var)
            .map_err(|_| ConfigError::MissingEnv(model_var))?;
        let base_url_var = format!("{}_BASE_URL", name.to_uppercase());
        let base_url = std::env::var(&base_url_var).ok();
        Ok(Self {
            name,
            api_key: Some(api_key),
            base_url,
            model: Some(model),
        })
    }
}

/// Provider Chain 配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderChainConfig {
    #[serde(default = "default_policy")]
    pub failover_policy: FailoverPolicy,
    #[serde(default = "default_interval")]
    pub health_check_interval_sec: u64,
    pub instances: Vec<LlmInstanceConfig>,
}

fn default_policy() -> FailoverPolicy {
    FailoverPolicy::Automatic
}

fn default_interval() -> u64 {
    30
}

/// 单个实例的配置（从 env 读取 api_key）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LlmInstanceConfig {
    pub id: String,
    pub provider: String,
    pub api_key: String, // 支持 ${ENV_VAR} 格式
    pub base_url: Option<String>,
    pub model: String,
    pub priority: u8,
    pub max_rpm: Option<u32>,
    #[serde(default = "default_enabled")]
    pub enabled: bool,
}

fn default_enabled() -> bool {
    true
}

impl LlmInstanceConfig {
    /// 转换为运行时 LlmInstance
    pub fn to_instance(&self) -> LlmInstance {
        LlmInstance {
            id: self.id.clone(),
            provider: self.provider.clone(),
            api_key: self.api_key.clone(),
            base_url: self.base_url.clone(),
            model: self.model.clone(),
            priority: self.priority,
            max_rpm: self.max_rpm,
            enabled: self.enabled,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Mutex, OnceLock};

    /// Process-wide env lock — env mutation is process-global, so even with
    /// --test-threads=1 cargo may interleave tests from different binaries.
    /// Using a Mutex here is belt-and-suspenders alongside the per-task
    /// `--test-threads=1` recipe from CLAUDE.md "No auto full tests" rule.
    fn env_lock() -> &'static Mutex<()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
    }

    /// RAII guard that snapshots + clears a set of env vars on entry and
    /// restores them on drop. Lets each test mutate freely without leaking
    /// state to sibling tests.
    struct EnvGuard {
        snapshots: Vec<(&'static str, Option<String>)>,
        _lock: std::sync::MutexGuard<'static, ()>,
    }

    impl EnvGuard {
        fn new(keys: &[&'static str]) -> Self {
            let lock = env_lock().lock().unwrap_or_else(|p| p.into_inner());
            let snapshots: Vec<_> = keys
                .iter()
                .map(|&k| (k, std::env::var(k).ok()))
                .collect();
            for &k in keys {
                std::env::remove_var(k);
            }
            Self {
                snapshots,
                _lock: lock,
            }
        }
    }

    impl Drop for EnvGuard {
        fn drop(&mut self) {
            for (k, v) in &self.snapshots {
                match v {
                    Some(value) => std::env::set_var(k, value),
                    None => std::env::remove_var(k),
                }
            }
        }
    }

    // Keys the strict loader inspects across all three providers.
    const PROVIDER_KEYS: &[&str] = &[
        "LLM_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_MODEL_NAME",
        "OPENAI_BASE_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_MODEL_NAME",
        "DEEPSEEK_BASE_URL",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL_NAME",
        "ANTHROPIC_BASE_URL",
    ];

    #[test]
    fn test_try_from_env_missing_llm_provider_err() {
        let _g = EnvGuard::new(PROVIDER_KEYS);
        let err = ProviderConfig::try_from_env()
            .expect_err("missing LLM_PROVIDER should Err");
        assert!(matches!(err, ConfigError::MissingEnv("LLM_PROVIDER")));
    }

    #[test]
    fn test_try_from_env_missing_api_key_err() {
        let _g = EnvGuard::new(PROVIDER_KEYS);
        std::env::set_var("LLM_PROVIDER", "openai");
        let err = ProviderConfig::try_from_env()
            .expect_err("missing OPENAI_API_KEY should Err");
        assert!(matches!(err, ConfigError::MissingEnv("OPENAI_API_KEY")));
    }

    #[test]
    fn test_try_from_env_missing_model_err() {
        let _g = EnvGuard::new(PROVIDER_KEYS);
        std::env::set_var("LLM_PROVIDER", "openai");
        std::env::set_var("OPENAI_API_KEY", "sk-xxx");
        let err = ProviderConfig::try_from_env()
            .expect_err("missing OPENAI_MODEL_NAME should Err");
        assert!(matches!(err, ConfigError::MissingEnv("OPENAI_MODEL_NAME")));
    }

    #[test]
    fn test_try_from_env_unknown_provider_err() {
        let _g = EnvGuard::new(PROVIDER_KEYS);
        std::env::set_var("LLM_PROVIDER", "foobar");
        let err = ProviderConfig::try_from_env()
            .expect_err("unknown provider should Err");
        match err {
            ConfigError::UnknownProvider(name) => assert_eq!(name, "foobar"),
            other => panic!("expected UnknownProvider, got {:?}", other),
        }
    }

    #[test]
    fn test_try_from_env_all_set_ok() {
        let _g = EnvGuard::new(PROVIDER_KEYS);
        std::env::set_var("LLM_PROVIDER", "openai");
        std::env::set_var("OPENAI_API_KEY", "sk-test");
        std::env::set_var("OPENAI_MODEL_NAME", "gpt-4o");
        std::env::set_var("OPENAI_BASE_URL", "https://example.invalid");
        let cfg = ProviderConfig::try_from_env().expect("all required env set");
        assert_eq!(cfg.name, "openai");
        assert_eq!(cfg.api_key.as_deref(), Some("sk-test"));
        assert_eq!(cfg.model.as_deref(), Some("gpt-4o"));
        assert_eq!(cfg.base_url.as_deref(), Some("https://example.invalid"));
    }

    #[test]
    fn test_try_from_env_deepseek_ok() {
        let _g = EnvGuard::new(PROVIDER_KEYS);
        std::env::set_var("LLM_PROVIDER", "deepseek");
        std::env::set_var("DEEPSEEK_API_KEY", "ds-test");
        std::env::set_var("DEEPSEEK_MODEL_NAME", "deepseek-chat");
        let cfg = ProviderConfig::try_from_env().expect("deepseek required env set");
        assert_eq!(cfg.name, "deepseek");
        assert_eq!(cfg.api_key.as_deref(), Some("ds-test"));
        assert!(cfg.base_url.is_none(), "DEEPSEEK_BASE_URL unset → None");
    }
}
