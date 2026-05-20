//! Phase 5.4 Plan 02 Task 07 — WATCH-04 D142 deployment-mode gate.
//!
//! Per ADR-V2-019 §D2: when `EAASP_DEPLOYMENT_MODE=per_session`, a
//! second `Initialize` call to the same `grid-runtime` process must
//! return `Status::resource_exhausted`. Shared mode allows multi-init.
//!
//! Tests exercise the gate directly on `RuntimeGrpcService::initialize`
//! through tonic's generated trait — no network setup needed.

use std::sync::Arc;
use tonic::Request;

use grid_runtime::contract::DeploymentMode;
use grid_runtime::harness::GridHarness;
use grid_runtime::proto::{self, runtime_service_server::RuntimeService};
use grid_runtime::service::RuntimeGrpcService;

/// Build a minimal in-process service so `initialize` is callable without
/// touching network or a real LLM provider.
async fn make_service(mode: DeploymentMode) -> RuntimeGrpcService<GridHarness> {
    let catalog = Arc::new(grid_engine::AgentCatalog::new());
    let runtime_config = grid_engine::AgentRuntimeConfig::from_parts(
        ":memory:".into(),
        grid_engine::ProviderConfig::default(),
        vec![],
        None,
        None,
        false,
    );
    let tenant_context = grid_engine::TenantContext::for_single_user(
        grid_types::id::TenantId::from_string("test"),
        grid_types::id::UserId::from_string("test-user"),
    );
    let runtime =
        grid_engine::AgentRuntime::new(catalog, runtime_config, Some(tenant_context))
            .await
            .expect("build AgentRuntime");
    let harness = Arc::new(GridHarness::new(Arc::new(runtime)));
    RuntimeGrpcService::with_deployment_mode(harness, mode)
}

fn init_request_for_user(user: &str) -> Request<proto::InitializeRequest> {
    Request::new(proto::InitializeRequest {
        payload: Some(proto::SessionPayload {
            user_id: user.into(),
            runtime_id: "grid-harness".into(),
            user_preferences: Some(proto::UserPreferences {
                user_id: user.into(),
                language: "en".into(),
                ..Default::default()
            }),
            allow_trim_p5: true,
            ..Default::default()
        }),
    })
}

#[tokio::test]
async fn test_shared_mode_allows_multi_session() {
    let service = make_service(DeploymentMode::Shared).await;

    // First Initialize succeeds.
    let resp1 = service
        .initialize(init_request_for_user("user-1"))
        .await
        .expect("first Initialize OK under Shared");
    assert!(!resp1.into_inner().session_id.is_empty());

    // Second Initialize ALSO succeeds — Shared mode multiplexes sessions.
    let resp2 = service
        .initialize(init_request_for_user("user-2"))
        .await
        .expect("second Initialize OK under Shared (multi-session allowed)");
    assert!(!resp2.into_inner().session_id.is_empty());
}

#[tokio::test]
async fn test_per_session_mode_rejects_second() {
    let service = make_service(DeploymentMode::PerSession).await;

    // First Initialize succeeds.
    let resp1 = service
        .initialize(init_request_for_user("only-user"))
        .await
        .expect("first Initialize OK under PerSession");
    assert!(!resp1.into_inner().session_id.is_empty());

    // Second Initialize is rejected with RESOURCE_EXHAUSTED.
    let err = service
        .initialize(init_request_for_user("would-be-second"))
        .await
        .expect_err("second Initialize must fail under PerSession");
    assert_eq!(
        err.code(),
        tonic::Code::ResourceExhausted,
        "expected ResourceExhausted, got {:?} ({})",
        err.code(),
        err.message()
    );
    assert!(
        err.message().contains("per-session"),
        "error message should mention per-session, got: {}",
        err.message()
    );
}

#[test]
fn test_invalid_mode_panics() {
    // Use a child process so the panic doesn't bring down the test runner.
    // Spawn `RuntimeConfig::from_env()` with EAASP_DEPLOYMENT_MODE=foobar
    // via a small binary? Too heavyweight. Instead test the parsing logic
    // through a thread + catch_unwind, which is the documented Rust pattern.

    // Save / restore env vars across the panic test (cargo --test-threads=1
    // ensures we're not racing with other tests in this file).
    let saved_mode = std::env::var("EAASP_DEPLOYMENT_MODE").ok();
    let saved_provider = std::env::var("LLM_PROVIDER").ok();
    let saved_key = std::env::var("OPENAI_API_KEY").ok();
    let saved_model = std::env::var("OPENAI_MODEL_NAME").ok();

    std::env::set_var("EAASP_DEPLOYMENT_MODE", "foobar");
    std::env::set_var("LLM_PROVIDER", "openai");
    std::env::set_var("OPENAI_API_KEY", "test");
    std::env::set_var("OPENAI_MODEL_NAME", "gpt-4o");
    // RuntimeConfig::from_env() also reads GRID_RUNTIME_ADDR; defaults to 50051.
    std::env::remove_var("GRID_RUNTIME_ADDR");

    let result = std::panic::catch_unwind(grid_runtime::config::RuntimeConfig::from_env);
    assert!(
        result.is_err(),
        "from_env() should panic on EAASP_DEPLOYMENT_MODE=foobar"
    );

    // Restore env state.
    match saved_mode {
        Some(v) => std::env::set_var("EAASP_DEPLOYMENT_MODE", v),
        None => std::env::remove_var("EAASP_DEPLOYMENT_MODE"),
    }
    match saved_provider {
        Some(v) => std::env::set_var("LLM_PROVIDER", v),
        None => std::env::remove_var("LLM_PROVIDER"),
    }
    match saved_key {
        Some(v) => std::env::set_var("OPENAI_API_KEY", v),
        None => std::env::remove_var("OPENAI_API_KEY"),
    }
    match saved_model {
        Some(v) => std::env::set_var("OPENAI_MODEL_NAME", v),
        None => std::env::remove_var("OPENAI_MODEL_NAME"),
    }
}
