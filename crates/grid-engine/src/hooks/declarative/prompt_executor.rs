//! Prompt executor for declarative prompt-type hooks.
//!
//! Calls LLM provider to evaluate a rendered prompt, then parses the JSON
//! decision from the response. Uses a separate short-context call (not the
//! agent's main conversation context).
//!
//! Token budget: single evaluation ≤ 500 output tokens. Default timeout: 10s.

use tracing::{debug, warn};

use crate::hooks::HookContext;
use super::command_executor::HookDecision;
use super::prompt_renderer;
use crate::providers::Provider;

/// Execute a prompt-type hook by rendering the template and calling the LLM.
///
/// Returns a `HookDecision` parsed from the LLM's JSON response.
pub async fn execute_prompt(
    template: &str,
    ctx: &HookContext,
    provider: &dyn Provider,
    model: &str,
    timeout_secs: u32,
) -> anyhow::Result<HookDecision> {
    // 1. Render the prompt template
    let rendered = prompt_renderer::render_prompt(template, ctx);
    debug!(
        rendered_len = rendered.len(),
        "Prompt hook: rendered template"
    );

    // 2. Build a minimal CompletionRequest for evaluation
    let request = grid_types::CompletionRequest {
        model: model.to_string(),
        system: Some(
            "You are a security evaluator. Analyze the request and return a JSON object with \
             \"decision\" (\"allow\" or \"deny\") and \"reason\" fields. Only return valid JSON."
                .to_string(),
        ),
        messages: vec![grid_types::ChatMessage {
            role: grid_types::MessageRole::User,
            content: vec![grid_types::ContentBlock::Text { text: rendered }],
        }],
        max_tokens: 500,
        temperature: Some(0.0),
        tools: vec![],
        stream: false,
        tool_choice: None,
    };

    // 3. Call provider with timeout
    let response = tokio::time::timeout(
        std::time::Duration::from_secs(timeout_secs as u64),
        provider.complete(request),
    )
    .await
    .map_err(|_| anyhow::anyhow!("Prompt hook timed out after {}s", timeout_secs))??;

    // 4. Extract text from response content blocks
    let text: String = response
        .content
        .iter()
        .filter_map(|block| {
            if let grid_types::ContentBlock::Text { text } = block {
                Some(text.as_str())
            } else {
                None
            }
        })
        .collect::<Vec<_>>()
        .join("");
    debug!(response_len = text.len(), "Prompt hook: received LLM response");

    // 5. Parse JSON decision from response
    parse_decision_from_text(&text)
}

/// Parse a HookDecision from LLM text output.
///
/// Tries to find JSON in the text, handling cases where the LLM wraps it
/// in markdown code blocks or adds explanatory text.
fn parse_decision_from_text(text: &str) -> anyhow::Result<HookDecision> {
    let trimmed = text.trim();

    // Try direct parse first
    if let Ok(decision) = serde_json::from_str::<HookDecision>(trimmed) {
        return Ok(decision);
    }

    // Try to extract JSON from fenced code blocks
    if let Some(start) = trimmed.find('{') {
        if let Some(end) = trimmed.rfind('}') {
            let json_str = &trimmed[start..=end];
            if let Ok(decision) = serde_json::from_str::<HookDecision>(json_str) {
                return Ok(decision);
            }
        }
    }

    // Fallback: if text contains "deny" keyword, treat as deny
    if trimmed.to_lowercase().contains("deny") || trimmed.to_lowercase().contains("block") {
        warn!("Prompt hook: could not parse JSON, falling back to keyword detection (deny)");
        return Ok(HookDecision {
            decision: "deny".into(),
            reason: Some(format!("LLM evaluation (unparsed): {}", &trimmed[..trimmed.len().min(200)])),
            updated_input: None,
            system_message: None,
        });
    }

    // Default: allow if no clear deny signal
    warn!("Prompt hook: could not parse decision, defaulting to allow");
    Ok(HookDecision {
        decision: "allow".into(),
        reason: Some("LLM response could not be parsed as decision JSON".into()),
        updated_input: None,
        system_message: None,
    })
}

/// Execute a YES/NO prompt hook for lightweight LLM-based tool gate decisions.
///
/// Renders a fixed "security guard" prompt template, calls the LLM provider
/// with a short token budget, and parses the first word of the response as
/// YES (allow) or NO (deny). Any parse failure defaults to DENY.
///
/// Retry policy: 1 retry on timeout/error (2 attempts total). Both failures → DENY.
pub async fn execute_yesno_prompt(
    tool_name: &str,
    tool_args: &str,
    ctx: &HookContext,
    provider: &dyn Provider,
    model: &str,
    timeout_secs: u32,
) -> anyhow::Result<HookDecision> {
    todo!("execute_yesno_prompt — RED phase")
}

/// Parse a YES/NO decision from LLM text output.
///
/// Takes the first non-empty word, compares case-insensitively:
/// - "YES" → allow
/// - "NO"  → deny
/// - Anything else (including empty) → deny (safe default)
pub fn parse_yesno_from_text(text: &str) -> HookDecision {
    todo!("parse_yesno_from_text — RED phase")
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── YES/NO parsing tests ──

    #[test]
    fn test_yesno_parse_yes_allows() {
        let d = parse_yesno_from_text("YES");
        assert!(d.is_allow(), "expected allow, got '{:?}'", d);
        assert_eq!(d.reason.as_deref(), Some("LLM evaluation: YES"));
    }

    #[test]
    fn test_yesno_parse_no_denies() {
        let d = parse_yesno_from_text("NO");
        assert!(d.is_deny(), "expected deny, got '{:?}'", d);
        assert_eq!(d.reason.as_deref(), Some("LLM evaluation: NO"));
    }

    #[test]
    fn test_yesno_parse_lowercase() {
        let d = parse_yesno_from_text("yes");
        assert!(d.is_allow());
        let d = parse_yesno_from_text("no");
        assert!(d.is_deny());
    }

    #[test]
    fn test_yesno_parse_whitespace_handling() {
        // Surrounding whitespace + first word YES
        let d = parse_yesno_from_text(" maybe YES ");
        assert!(d.is_allow(), "expected allow for ' maybe YES ', got '{:?}'", d);
    }

    #[test]
    fn test_yesno_parse_invalid_word_denies() {
        let d = parse_yesno_from_text("MAYBE");
        assert!(
            d.is_deny(),
            "expected deny for 'MAYBE', got decision='{}'",
            d.decision
        );
        let reason = d.reason.as_deref().unwrap_or("");
        assert!(
            reason.contains("could not be parsed"),
            "reason should mention parse failure, got: {reason:?}"
        );
    }

    #[test]
    fn test_yesno_parse_empty_denies() {
        let d = parse_yesno_from_text("");
        assert!(
            d.is_deny(),
            "expected deny for empty string, got decision='{}'",
            d.decision
        );
    }

    #[test]
    fn test_yesno_parse_newlines_yes() {
        let d = parse_yesno_from_text("\n\n  YES  \n");
        assert!(d.is_allow(), "expected allow for newline+wrapped YES, got '{:?}'", d);
    }

    // ── Integration test: execute_yesno_prompt with mock provider ──

    /// Mock provider that returns a pre-configured response.
    struct MockProvider {
        response: String,
        delay_ms: u64,
    }

    #[async_trait::async_trait]
    impl Provider for MockProvider {
        fn id(&self) -> &str {
            "mock"
        }

        async fn complete(
            &self,
            _request: grid_types::CompletionRequest,
        ) -> anyhow::Result<grid_types::CompletionResponse> {
            if self.delay_ms > 0 {
                tokio::time::sleep(std::time::Duration::from_millis(self.delay_ms)).await;
            }
            Ok(grid_types::CompletionResponse {
                id: "mock-1".into(),
                content: vec![grid_types::ContentBlock::Text {
                    text: self.response.clone(),
                }],
                stop_reason: Some(grid_types::StopReason::EndTurn),
                usage: grid_types::TokenUsage::default(),
            })
        }

        async fn stream(
            &self,
            _request: grid_types::CompletionRequest,
        ) -> anyhow::Result<std::pin::Pin<Box<dyn futures_util::Stream<Item = anyhow::Result<grid_types::StreamEvent>> + Send>>> {
            unimplemented!("stream not used in YES/NO tests")
        }
    }

    #[tokio::test]
    async fn test_yesno_prompt_yes_allows() {
        let provider = MockProvider {
            response: "YES".into(),
            delay_ms: 0,
        };
        let ctx = HookContext::new().with_session("s1").with_tool(
            "bash",
            serde_json::json!({"command": "ls"}),
        );
        let result = execute_yesno_prompt(
            "bash",
            r#"{"command": "ls"}"#,
            &ctx,
            &provider,
            "claude-haiku",
            10,
        )
        .await
        .unwrap();
        assert!(result.is_allow());
    }

    #[tokio::test]
    async fn test_yesno_prompt_no_denies() {
        let provider = MockProvider {
            response: "NO".into(),
            delay_ms: 0,
        };
        let ctx = HookContext::new().with_session("s1").with_tool(
            "rm",
            serde_json::json!({"path": "/etc/hosts"}),
        );
        let result = execute_yesno_prompt(
            "rm",
            r#"{"path": "/etc/hosts"}"#,
            &ctx,
            &provider,
            "claude-haiku",
            10,
        )
        .await
        .unwrap();
        assert!(result.is_deny());
    }

    #[tokio::test]
    async fn test_yesno_prompt_unparseable_denies() {
        let provider = MockProvider {
            response: "MAYBE".into(),
            delay_ms: 0,
        };
        let ctx = HookContext::new().with_session("s1");
        let result = execute_yesno_prompt(
            "curl",
            r#"{"url": "https://example.com"}"#,
            &ctx,
            &provider,
            "claude-haiku",
            10,
        )
        .await
        .unwrap();
        assert!(result.is_deny(), "expected deny for unparseable LLM response");
    }

    #[tokio::test]
    async fn test_yesno_prompt_timeout_retries_then_denies() {
        let provider = MockProvider {
            response: "YES".into(),
            delay_ms: 2000, // 2s delay but timeout is 1s — triggers timeout
        };
        let ctx = HookContext::new().with_session("s1");
        let result = execute_yesno_prompt(
            "bash",
            r#"{"command": "ls"}"#,
            &ctx,
            &provider,
            "claude-haiku",
            1, // 1 second timeout — will trigger for 2s delay
        )
        .await;
        // After 1 retry + 2 attempts both timing out, should return deny
        assert!(
            result.is_ok(),
            "timeout should produce an Ok result (not an error)"
        );
        let decision = result.unwrap();
        assert!(
            decision.is_deny(),
            "double timeout should result in deny, got decision='{}'",
            decision.decision
        );
    }

    // ── Existing JSON parser tests ──

    #[test]
    fn test_parse_clean_json() {
        let text = r#"{"decision": "deny", "reason": "dangerous command"}"#;
        let d = parse_decision_from_text(text).unwrap();
        assert!(d.is_deny());
        assert_eq!(d.reason.as_deref(), Some("dangerous command"));
    }

    #[test]
    fn test_parse_json_in_code_block() {
        let text = r#"Here's my analysis:
```json
{"decision": "allow", "reason": "safe operation"}
```"#;
        let d = parse_decision_from_text(text).unwrap();
        assert!(d.is_allow());
    }

    #[test]
    fn test_parse_json_with_surrounding_text() {
        let text = "After careful analysis, I conclude: {\"decision\": \"deny\", \"reason\": \"path traversal\"} is the result.";
        let d = parse_decision_from_text(text).unwrap();
        assert!(d.is_deny());
    }

    #[test]
    fn test_parse_keyword_fallback_deny() {
        let text = "I would deny this operation because it accesses system files.";
        let d = parse_decision_from_text(text).unwrap();
        assert!(
            d.is_deny(),
            "expected deny, got decision='{}', reason={:?}",
            d.decision,
            d.reason
        );
    }

    #[test]
    fn test_parse_keyword_fallback_block() {
        let text = "I would block this request due to security concerns.";
        let d = parse_decision_from_text(text).unwrap();
        assert!(d.is_deny());
    }

    #[test]
    fn test_parse_unparseable_defaults_allow() {
        let text = "This looks fine to me, proceed with the operation.";
        let d = parse_decision_from_text(text).unwrap();
        assert!(d.is_allow());
    }

    #[test]
    fn test_parse_empty_defaults_allow() {
        let d = parse_decision_from_text("").unwrap();
        assert!(d.is_allow());
    }
}
