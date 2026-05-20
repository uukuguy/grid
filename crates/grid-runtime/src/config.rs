//! grid-runtime configuration.
//!
//! Layered: environment variables > defaults.

use std::net::SocketAddr;

use crate::contract::DeploymentMode;

/// grid-runtime server configuration.
#[derive(Debug, Clone)]
pub struct RuntimeConfig {
    /// gRPC listen address (default: 0.0.0.0:50051).
    pub grpc_addr: SocketAddr,
    /// Runtime instance identifier.
    pub runtime_id: String,
    /// LLM provider API key.
    pub api_key: Option<String>,
    /// LLM provider base URL (e.g. "https://openrouter.ai/api/v1").
    pub base_url: Option<String>,
    /// LLM provider (default: "openai").
    pub provider: String,
    /// LLM model (default: "gpt-4o").
    pub model: String,
    /// Runtime workspace base directory for session isolation.
    /// Each session creates a subdirectory under this path.
    pub runtime_workspace: Option<String>,
    /// Phase 5.4 WATCH-04 D142 — deployment-mode gate per ADR-V2-019.
    ///
    /// `Shared` (default) allows multiple concurrent sessions per process.
    /// `PerSession` enforces max_sessions=1 so EAASP L4 must spawn a fresh
    /// container per session. Read from `EAASP_DEPLOYMENT_MODE`.
    pub deployment_mode: DeploymentMode,
}

impl RuntimeConfig {
    /// Load configuration from environment variables.
    pub fn from_env() -> Self {
        let _ = dotenvy::dotenv();

        let grpc_addr: SocketAddr = std::env::var("GRID_RUNTIME_ADDR")
            .unwrap_or_else(|_| "0.0.0.0:50051".into())
            .parse()
            .expect("Invalid GRID_RUNTIME_ADDR");

        let runtime_id =
            std::env::var("GRID_RUNTIME_ID").unwrap_or_else(|_| "grid-harness".into());

        // LLM provider configuration — follows .env conventions.
        // Env vars: LLM_PROVIDER, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL_NAME,
        //           ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL_NAME,
        //           DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL_NAME.
        // Missing required vars → panic with a clear message. No fallback.
        let provider = std::env::var("LLM_PROVIDER")
            .expect("LLM_PROVIDER is required (e.g. \"openai\", \"anthropic\", or \"deepseek\")");

        let (api_key_var, base_url_var, model_var) = match provider.as_str() {
            "anthropic" => ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL_NAME"),
            "deepseek" => ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL_NAME"),
            _ => ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL_NAME"),
        };

        let api_key = std::env::var(api_key_var).ok();
        if api_key.is_none() {
            panic!(
                "{api_key_var} is required for LLM_PROVIDER={provider}. \
                 Set it in .env or shell environment."
            );
        }

        let base_url = std::env::var(base_url_var).ok();

        let model = std::env::var(model_var).unwrap_or_else(|_| {
            panic!(
                "{model_var} is required for LLM_PROVIDER={provider}. \
                 Set it in .env or shell environment."
            )
        });

        // Runtime workspace: EAASP_RUNTIME_WORKSPACE env var.
        // In containers this defaults to "/" (container root IS the workspace).
        // Bare-metal dev: set by dev-eaasp.sh to data/runtime-workspace/.
        let runtime_workspace = std::env::var("EAASP_RUNTIME_WORKSPACE").ok();

        // Phase 5.4 WATCH-04 D142 + ADR-V2-019 §D2 — deployment-mode wire.
        // Default Shared (multi-session per process); explicit per_session
        // gates Initialize() at one session per container.
        let deployment_mode = match std::env::var("EAASP_DEPLOYMENT_MODE")
            .as_deref()
        {
            Ok("per_session") => DeploymentMode::PerSession,
            Ok("shared") | Err(_) => DeploymentMode::Shared,
            Ok(other) => panic!(
                "Invalid EAASP_DEPLOYMENT_MODE: '{}', expected 'shared' or 'per_session'",
                other
            ),
        };

        Self {
            grpc_addr,
            runtime_id,
            api_key,
            base_url,
            provider,
            model,
            runtime_workspace,
            deployment_mode,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn config_with_explicit_vars() {
        std::env::remove_var("GRID_RUNTIME_ADDR");
        std::env::remove_var("GRID_RUNTIME_ID");
        std::env::set_var("LLM_PROVIDER", "openai");
        std::env::set_var("OPENAI_API_KEY", "test-key");
        std::env::set_var("OPENAI_MODEL_NAME", "gpt-4o");
        std::env::remove_var("EAASP_RUNTIME_WORKSPACE");
        std::env::remove_var("EAASP_DEPLOYMENT_MODE");
        let config = RuntimeConfig::from_env();
        assert_eq!(config.grpc_addr.port(), 50051);
        assert_eq!(config.runtime_id, "grid-harness");
        assert_eq!(config.provider, "openai");
        assert_eq!(config.model, "gpt-4o");
        assert_eq!(config.api_key.as_deref(), Some("test-key"));
        // Default deployment mode is Shared when env unset.
        assert_eq!(config.deployment_mode, DeploymentMode::Shared);
        // Cleanup
        std::env::remove_var("LLM_PROVIDER");
        std::env::remove_var("OPENAI_API_KEY");
        std::env::remove_var("OPENAI_MODEL_NAME");
    }
}
