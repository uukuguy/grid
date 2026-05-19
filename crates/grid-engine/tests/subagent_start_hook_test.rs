//! Phase 5.3 CONTRACT-02 regression — assert `HookPoint::SubagentStart`
//! fires when a SubAgentRuntime is dispatched, with top-level envelope
//! shape per ADR-V2-006 §2.3 (no `payload.*` nesting).
//!
//! Mirror of `crates/grid-engine/tests/harness_envelope_wiring_test.rs`
//! (D151 Phase 4a T1 spy-handler pattern), adapted to the subagent fire
//! site at `crates/grid-engine/src/agent/subagent_runtime.rs:run_async`.
//!
//! Two tests:
//!   1. `subagent_start_fires_with_top_level_envelope` — happy path: hook
//!      fires once, envelope JSON has top-level `subagent_id`/
//!      `subagent_name`/`purpose` keys (no `payload.*` nesting).
//!   2. `subagent_start_block_prevents_spawn` — L3 deny path: hook returns
//!      `HookAction::Block`, the underlying provider is never invoked
//!      (verified via `MarkerProvider`), and the subagent ends up Failed.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use anyhow::Result;
use async_trait::async_trait;

use grid_engine::agent::entry::AgentManifest;
use grid_engine::agent::subagent::{SubAgentManager, SubAgentStatus};
use grid_engine::agent::subagent_runtime::SubAgentRuntime;
use grid_engine::agent::AgentLoopConfig;
use grid_engine::hooks::{HookAction, HookContext, HookHandler, HookPoint, HookRegistry};
use grid_engine::providers::{CompletionStream, Provider};
use grid_types::{CompletionRequest, CompletionResponse};

// ---------------------------------------------------------------------------
// Spy hook handler — captures every fired (HookPoint, ctx-clone) pair.
// HookHandler::execute doesn't see HookPoint, so we always tag with
// SubagentStart since this test only registers for that point.
// ---------------------------------------------------------------------------

struct SpyHandler {
    captured: Arc<Mutex<Vec<HookContext>>>,
    response: HookAction,
}

#[async_trait]
impl HookHandler for SpyHandler {
    fn name(&self) -> &str {
        "spy-subagent-start"
    }

    async fn execute(&self, ctx: &HookContext) -> Result<HookAction> {
        self.captured.lock().unwrap().push(ctx.clone());
        Ok(self.response.clone())
    }
}

// ---------------------------------------------------------------------------
// Marker provider — flips a flag if its methods are called. Used to prove
// that a denied SubagentStart truly stops the agent_loop from running.
// ---------------------------------------------------------------------------

struct MarkerProvider {
    stream_called: Arc<AtomicBool>,
}

#[async_trait]
impl Provider for MarkerProvider {
    fn id(&self) -> &str {
        "marker-test-provider"
    }

    async fn complete(&self, _request: CompletionRequest) -> Result<CompletionResponse> {
        self.stream_called.store(true, Ordering::SeqCst);
        anyhow::bail!("MarkerProvider::complete should never be called in deny test")
    }

    async fn stream(&self, _request: CompletionRequest) -> Result<CompletionStream> {
        self.stream_called.store(true, Ordering::SeqCst);
        anyhow::bail!("MarkerProvider::stream should never be called in deny test")
    }
}

// ---------------------------------------------------------------------------
// NoopProvider — used in the happy-path test where we don't care about
// downstream agent_loop behavior (we just need the loop to fall through).
// ---------------------------------------------------------------------------

struct NoopProvider;

#[async_trait]
impl Provider for NoopProvider {
    fn id(&self) -> &str {
        "noop-test-provider"
    }

    async fn complete(&self, _request: CompletionRequest) -> Result<CompletionResponse> {
        anyhow::bail!("NoopProvider::complete unsupported in this test fixture")
    }

    async fn stream(&self, _request: CompletionRequest) -> Result<CompletionStream> {
        use futures_util::stream;
        // Empty stream — agent_loop will see no events and exit gracefully.
        let events: Vec<Result<grid_types::StreamEvent>> = Vec::new();
        Ok(Box::pin(stream::iter(events)))
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn make_parent_config(
    hooks: Arc<HookRegistry>,
    provider: Arc<dyn Provider>,
) -> AgentLoopConfig {
    let mut cfg = AgentLoopConfig::default();
    cfg.hook_registry = Some(hooks);
    cfg.provider = Some(provider);
    cfg.model = "test-marker".to_string();
    cfg
}

fn make_manifest(name: &str) -> AgentManifest {
    AgentManifest {
        name: name.to_string(),
        ..AgentManifest::default()
    }
}

// ---------------------------------------------------------------------------
// Test 1 — SubagentStart fires once with top-level envelope shape.
// ---------------------------------------------------------------------------

#[tokio::test]
async fn subagent_start_fires_with_top_level_envelope() {
    let captured: Arc<Mutex<Vec<HookContext>>> = Arc::new(Mutex::new(Vec::new()));

    let handler = Arc::new(SpyHandler {
        captured: captured.clone(),
        response: HookAction::Continue,
    });

    let registry = HookRegistry::new();
    registry.register(HookPoint::SubagentStart, handler).await;
    let registry = Arc::new(registry);

    let provider = Arc::new(NoopProvider) as Arc<dyn Provider>;
    let parent_config = make_parent_config(registry.clone(), provider.clone());

    let mgr = Arc::new(SubAgentManager::new(4, 4));
    let manifest = make_manifest("verifier-agent");
    let runtime = SubAgentRuntime::build(
        "verify-top-level-shape".to_string(),
        Some(manifest),
        &parent_config,
        mgr.clone(),
        None,
        None,
    )
    .await
    .expect("subagent build");

    let sa_id = runtime.run_async();

    // The hook fire is the FIRST awaitable in the spawned task body; a few
    // short yields are enough for it to land.
    for _ in 0..50 {
        tokio::time::sleep(std::time::Duration::from_millis(20)).await;
        if !captured.lock().unwrap().is_empty() {
            break;
        }
    }

    let cap = captured.lock().unwrap();
    assert_eq!(
        cap.len(),
        1,
        "SubagentStart MUST fire exactly once pre-spawn; got {}",
        cap.len()
    );

    let ctx = &cap[0];
    assert_eq!(ctx.event.as_deref(), Some("SubagentStart"));

    // ADR-V2-006 §2.3 — top-level flat-struct shape (no payload.* nesting).
    let json = ctx.to_json();
    assert_eq!(json["event"], "SubagentStart");
    assert!(
        json.get("subagent_id").is_some(),
        "subagent_id must be top-level, not nested under payload.*; envelope = {json}"
    );
    assert!(
        json.get("subagent_name").is_some(),
        "subagent_name must be top-level"
    );
    assert!(json.get("purpose").is_some(), "purpose must be top-level");
    assert!(
        json.get("payload").is_none(),
        "must NOT nest under payload.*; envelope = {json}"
    );

    // The subagent_id in the envelope matches the id returned from run_async.
    assert_eq!(json["subagent_id"], serde_json::Value::String(sa_id));
    assert_eq!(json["subagent_name"], "verifier-agent");
    assert!(json["purpose"]
        .as_str()
        .unwrap_or("")
        .starts_with("verify-top-level-shape"));
}

// ---------------------------------------------------------------------------
// Test 2 — SubagentStart Block prevents agent_loop run.
// ---------------------------------------------------------------------------

#[tokio::test]
async fn subagent_start_block_prevents_spawn() {
    let captured: Arc<Mutex<Vec<HookContext>>> = Arc::new(Mutex::new(Vec::new()));

    let handler = Arc::new(SpyHandler {
        captured: captured.clone(),
        response: HookAction::Block("L3 deny — test only".to_string()),
    });

    let registry = HookRegistry::new();
    registry.register(HookPoint::SubagentStart, handler).await;
    let registry = Arc::new(registry);

    let stream_called = Arc::new(AtomicBool::new(false));
    let provider = Arc::new(MarkerProvider {
        stream_called: stream_called.clone(),
    }) as Arc<dyn Provider>;
    let parent_config = make_parent_config(registry.clone(), provider.clone());

    let mgr = Arc::new(SubAgentManager::new(4, 4));
    let manifest = make_manifest("denied-agent");
    let runtime = SubAgentRuntime::build(
        "should-be-denied".to_string(),
        Some(manifest),
        &parent_config,
        mgr.clone(),
        None,
        None,
    )
    .await
    .expect("subagent build");

    let sa_id = runtime.run_async();

    // Wait for the spawned task to fire the hook and call mgr.fail.
    for _ in 0..50 {
        tokio::time::sleep(std::time::Duration::from_millis(20)).await;
        let cap = captured.lock().unwrap();
        if !cap.is_empty() {
            break;
        }
    }
    // Allow mgr.fail to land
    tokio::time::sleep(std::time::Duration::from_millis(60)).await;

    // Hook fired once.
    let cap = captured.lock().unwrap();
    assert_eq!(
        cap.len(),
        1,
        "SubagentStart hook MUST still fire even when denied"
    );
    drop(cap);

    // Provider was never invoked.
    assert!(
        !stream_called.load(Ordering::SeqCst),
        "MarkerProvider.stream/complete MUST NOT be called when SubagentStart denied"
    );

    // Subagent ended up Failed (status accessed via list()).
    let agents = mgr.list().await;
    let denied = agents.iter().find(|h| h.id == sa_id);
    assert!(denied.is_some(), "denied subagent must still be registered");
    assert!(
        matches!(denied.unwrap().status, SubAgentStatus::Failed(_)),
        "denied subagent MUST be marked Failed; got status={:?}",
        denied.unwrap().status
    );
}
