//! Phase 5.3 CONTRACT-02 regression — assert `HookPoint::TaskCheckpoint`
//! fires at the two automatic trigger sites in `harness.rs`:
//!
//!   1. `reason="required_tools_satisfied"` — fires inside the D87 Fix 2
//!      satisfied-branch when `next_required.is_none()` after the LLM
//!      called every declared `workflow.required_tools` entry.
//!   2. `reason="max_continuations_reached"` — fires when the harness
//!      would otherwise continue a workflow but `workflow_continuation_count`
//!      has already hit `MAX_WORKFLOW_CONTINUATIONS`.
//!
//! Both tests use the same spy-handler pattern as
//! `subagent_start_hook_test.rs` (Phase 5.3 Task 5.3-01-03) and the same
//! mock-provider scaffolding as `d87_multi_step_workflow_regression.rs`.

use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::{Arc, Mutex};

use anyhow::Result;
use async_trait::async_trait;
use futures_util::stream::{self, StreamExt};
use serde_json::json;

use grid_engine::agent::{
    run_agent_loop, AgentConfig, AgentEvent, AgentLoopConfig, ExecutionMode,
};
use grid_engine::hooks::{HookAction, HookContext, HookHandler, HookPoint, HookRegistry};
use grid_engine::providers::{CompletionStream, Provider};
use grid_engine::tools::{Tool, ToolRegistry};
use grid_types::{
    ChatMessage, CompletionRequest, CompletionResponse, StopReason, StreamEvent, TokenUsage,
    ToolContext, ToolOutput, ToolSource,
};

// ---------------------------------------------------------------------------
// Spy hook handler — capture every fired HookContext clone.
// ---------------------------------------------------------------------------

struct SpyHandler {
    captured: Arc<Mutex<Vec<HookContext>>>,
}

#[async_trait]
impl HookHandler for SpyHandler {
    fn name(&self) -> &str {
        "spy-task-checkpoint"
    }

    async fn execute(&self, ctx: &HookContext) -> Result<HookAction> {
        self.captured.lock().unwrap().push(ctx.clone());
        Ok(HookAction::Continue)
    }
}

// ---------------------------------------------------------------------------
// Required-tools-satisfied provider — one tool call, then EndTurn text.
// `required_tools = ["read_data"]` means the satisfied branch fires after
// call 1.
// ---------------------------------------------------------------------------

struct RequiredToolsSatisfiedProvider {
    call_count: AtomicU32,
}

impl RequiredToolsSatisfiedProvider {
    fn new() -> Self {
        Self {
            call_count: AtomicU32::new(0),
        }
    }
}

#[async_trait]
impl Provider for RequiredToolsSatisfiedProvider {
    fn id(&self) -> &str {
        "required-tools-satisfied-mock"
    }

    async fn complete(&self, _request: CompletionRequest) -> Result<CompletionResponse> {
        anyhow::bail!("streaming only")
    }

    async fn stream(&self, _request: CompletionRequest) -> Result<CompletionStream> {
        let n = self.call_count.fetch_add(1, Ordering::SeqCst);
        match n {
            0 => {
                // Call read_data — satisfies the required_tools set.
                let events: Vec<Result<StreamEvent>> = vec![
                    Ok(StreamEvent::MessageStart {
                        id: "msg_call_read_data".into(),
                    }),
                    Ok(StreamEvent::ToolUseComplete {
                        index: 0,
                        id: "toolu_read_0".into(),
                        name: "read_data".into(),
                        input: json!({}),
                    }),
                    Ok(StreamEvent::MessageStop {
                        stop_reason: StopReason::ToolUse,
                        usage: TokenUsage {
                            input_tokens: 100,
                            output_tokens: 50,
                        },
                    }),
                ];
                Ok(Box::pin(stream::iter(events)))
            }
            _ => {
                // Text-only EndTurn — under D87 Fix 2 the harness would
                // normally re-arm continuation, but `required_tools` are
                // all satisfied, so this turn is accepted as final AND
                // TaskCheckpoint fires with reason=required_tools_satisfied.
                let events: Vec<Result<StreamEvent>> = vec![
                    Ok(StreamEvent::MessageStart {
                        id: "msg_text_final".into(),
                    }),
                    Ok(StreamEvent::TextDelta {
                        text: "All done.".into(),
                    }),
                    Ok(StreamEvent::MessageStop {
                        stop_reason: StopReason::EndTurn,
                        usage: TokenUsage {
                            input_tokens: 150,
                            output_tokens: 30,
                        },
                    }),
                ];
                Ok(Box::pin(stream::iter(events)))
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Max-continuations-reached provider — emits ToolUse on call 0, then keeps
// returning text-only EndTurn forever. With required_tools = None, the D87
// Fix 2 branch increments workflow_continuation_count each pass until MAX
// (=3) is reached; then the harness falls through to the normal exit and
// our new MAX guard fires TaskCheckpoint.
// ---------------------------------------------------------------------------

struct MaxContinuationsReachedProvider {
    call_count: AtomicU32,
}

impl MaxContinuationsReachedProvider {
    fn new() -> Self {
        Self {
            call_count: AtomicU32::new(0),
        }
    }
}

#[async_trait]
impl Provider for MaxContinuationsReachedProvider {
    fn id(&self) -> &str {
        "max-continuations-reached-mock"
    }

    async fn complete(&self, _request: CompletionRequest) -> Result<CompletionResponse> {
        anyhow::bail!("streaming only")
    }

    async fn stream(&self, _request: CompletionRequest) -> Result<CompletionStream> {
        let n = self.call_count.fetch_add(1, Ordering::SeqCst);
        if n == 0 {
            let events: Vec<Result<StreamEvent>> = vec![
                Ok(StreamEvent::MessageStart {
                    id: "msg_tool".into(),
                }),
                Ok(StreamEvent::ToolUseComplete {
                    index: 0,
                    id: "toolu_seed".into(),
                    name: "read_data".into(),
                    input: json!({}),
                }),
                Ok(StreamEvent::MessageStop {
                    stop_reason: StopReason::ToolUse,
                    usage: TokenUsage {
                        input_tokens: 100,
                        output_tokens: 50,
                    },
                }),
            ];
            Ok(Box::pin(stream::iter(events)))
        } else {
            // From call 1 onwards: text-only EndTurn. The harness will arm
            // continuation up to MAX times then fall through, firing
            // TaskCheckpoint(max_continuations_reached) on the post-MAX pass.
            let events: Vec<Result<StreamEvent>> = vec![
                Ok(StreamEvent::MessageStart {
                    id: format!("msg_text_{n}"),
                }),
                Ok(StreamEvent::TextDelta {
                    text: format!("text attempt {n}"),
                }),
                Ok(StreamEvent::MessageStop {
                    stop_reason: StopReason::EndTurn,
                    usage: TokenUsage {
                        input_tokens: 150,
                        output_tokens: 30,
                    },
                }),
            ];
            Ok(Box::pin(stream::iter(events)))
        }
    }
}

// ---------------------------------------------------------------------------
// Stub tool — read_data
// ---------------------------------------------------------------------------

struct ReadDataTool;

#[async_trait]
impl Tool for ReadDataTool {
    fn name(&self) -> &str {
        "read_data"
    }
    fn description(&self) -> &str {
        "Read data"
    }
    fn parameters(&self) -> serde_json::Value {
        json!({"type": "object", "properties": {}})
    }
    async fn execute(
        &self,
        _params: serde_json::Value,
        _ctx: &ToolContext,
    ) -> Result<ToolOutput> {
        Ok(ToolOutput::success("read_data ok".to_string()))
    }
    fn source(&self) -> ToolSource {
        ToolSource::BuiltIn
    }
}

// ---------------------------------------------------------------------------
// Helper — build AgentLoopConfig wired to capture TaskCheckpoint events
// ---------------------------------------------------------------------------

async fn run_with_spy(
    provider: Arc<dyn Provider>,
    required_tools: Option<Vec<String>>,
) -> Vec<HookContext> {
    let captured: Arc<Mutex<Vec<HookContext>>> = Arc::new(Mutex::new(Vec::new()));
    let handler = Arc::new(SpyHandler {
        captured: captured.clone(),
    });
    let registry = HookRegistry::new();
    registry
        .register(HookPoint::TaskCheckpoint, handler)
        .await;
    let registry = Arc::new(registry);

    let mut tool_registry = ToolRegistry::new();
    tool_registry.register(ReadDataTool);
    let tool_registry = Arc::new(tool_registry);

    let mut builder = AgentLoopConfig::builder()
        .provider(provider)
        .tools(tool_registry)
        .model("mock-model".into())
        .max_tokens(1024)
        .max_iterations(15)
        .force_text_at_last(false)
        .tool_choice_supported(true)
        .execution_mode(ExecutionMode::LongWorkflow)
        .hook_registry(registry)
        .agent_config(AgentConfig {
            enable_typing_signal: false,
            enable_parallel: false,
            ..AgentConfig::default()
        });
    if let Some(req) = required_tools {
        builder = builder.required_tools(req);
    }
    let config = builder.build();

    let messages = vec![ChatMessage::user("run the workflow".to_string())];
    let _events: Vec<AgentEvent> = run_agent_loop(config, messages).collect().await;

    let captured = captured.lock().unwrap();
    captured.clone()
}

// ---------------------------------------------------------------------------
// Test 1 — required_tools_satisfied
// ---------------------------------------------------------------------------

#[tokio::test]
async fn task_checkpoint_fires_on_required_tools_satisfied() {
    let provider = Arc::new(RequiredToolsSatisfiedProvider::new()) as Arc<dyn Provider>;
    let captured = run_with_spy(provider, Some(vec!["read_data".to_string()])).await;

    let satisfied: Vec<&HookContext> = captured
        .iter()
        .filter(|c| {
            c.metadata
                .get("reason")
                .and_then(|v| v.as_str())
                == Some("required_tools_satisfied")
        })
        .collect();
    assert_eq!(
        satisfied.len(),
        1,
        "TaskCheckpoint(required_tools_satisfied) MUST fire exactly once; got {} \
         events. Captured: {:?}",
        satisfied.len(),
        captured
            .iter()
            .map(|c| c.metadata.get("reason").cloned())
            .collect::<Vec<_>>()
    );

    let ctx = satisfied[0];
    let json = ctx.to_json();
    assert_eq!(json["event"], "TaskCheckpoint");
    assert_eq!(json["reason"], "required_tools_satisfied");
    assert!(
        json.get("rounds_completed").is_some(),
        "rounds_completed must be top-level"
    );
    assert!(
        json.get("total_tool_calls").is_some(),
        "total_tool_calls must be top-level"
    );
    assert!(
        json.get("completed_tools").is_some(),
        "completed_tools must be top-level"
    );
    assert!(
        json.get("payload").is_none(),
        "must NOT nest under payload.*; envelope = {json}"
    );
}

// ---------------------------------------------------------------------------
// Test 2 — max_continuations_reached
// ---------------------------------------------------------------------------

#[tokio::test]
async fn task_checkpoint_fires_on_max_continuations_reached() {
    let provider = Arc::new(MaxContinuationsReachedProvider::new()) as Arc<dyn Provider>;
    // No required_tools — drives the harness into the open-ended D87 Fix 2
    // continuation path until MAX is reached.
    let captured = run_with_spy(provider, None).await;

    let max_events: Vec<&HookContext> = captured
        .iter()
        .filter(|c| {
            c.metadata
                .get("reason")
                .and_then(|v| v.as_str())
                == Some("max_continuations_reached")
        })
        .collect();
    assert!(
        !max_events.is_empty(),
        "TaskCheckpoint(max_continuations_reached) MUST fire at least once after \
         MAX_WORKFLOW_CONTINUATIONS exhaustion. Captured reasons: {:?}",
        captured
            .iter()
            .map(|c| c.metadata.get("reason").cloned())
            .collect::<Vec<_>>()
    );

    let ctx = max_events[0];
    let json = ctx.to_json();
    assert_eq!(json["event"], "TaskCheckpoint");
    assert_eq!(json["reason"], "max_continuations_reached");
    assert!(
        json.get("rounds_completed").is_some(),
        "rounds_completed must be top-level"
    );
    assert!(
        json.get("total_tool_calls").is_some(),
        "total_tool_calls must be top-level"
    );
    assert!(
        json.get("completed_tools").is_some(),
        "completed_tools must be top-level"
    );
    assert!(
        json.get("payload").is_none(),
        "must NOT nest under payload.*; envelope = {json}"
    );
}
