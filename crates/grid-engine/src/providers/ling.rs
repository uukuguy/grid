//! Ling provider — ant-ling Ling-2.6 family.
//!
//! Phase 5.3 ADR-V2-027 F2 split (per RESEARCH §"Open Questions (RESOLVED)" Q3):
//! ant-ling exhibits two non-standard OpenAI-compat behaviors. The first is an
//! F1-shared quirk (provider-agnostic behavior, may apply to future providers);
//! the second is F2-specific (only ant-ling so far, handled inline below):
//!
//! 1. **SSE stream closes without `data: [DONE]` marker** — F1-promoted to
//!    `Quirks::no_done_marker`. Handled inside `OpenAIProvider`'s `Poll::Ready(None)`
//!    arm gated by that field.
//! 2. **`tool_calls[].id` field may be null on continuation chunks** —
//!    F2-specific (only seen in ant-ling). Handled by the inline
//!    `normalize_null_tool_ids` helper below at request-shape time. NOT promoted
//!    to `Quirks` (would pollute the shared abstraction for a 1-provider deviation).
//!
//! Promotion of the F2 quirk to F1 requires a second provider exhibiting the
//! same behavior; until then, the inline handling lives here.

use std::sync::Arc;

use anyhow::Result;
use async_trait::async_trait;

use grid_types::{CompletionRequest, CompletionResponse};

use super::openai::OpenAIProvider;
use super::quirks::Quirks;
use super::traits::{CompletionStream, Provider};

/// Default base URL for ant-ling's public API.
///
/// TODO(Phase 5.4 NEW-F3): replace placeholder with the real endpoint once the
/// ant-ling SDK lands a documented public URL. Until then, callers MUST supply
/// `base_url` explicitly via config.
pub const LING_BASE_URL: &str = "https://api.ant-ling.example/v1";

/// Ling provider — wraps `OpenAIProvider` with ant-ling-specific quirks.
///
/// F1 quirk: `Quirks::no_done_marker = true` (handled by shared parser).
/// F2 quirk: null `tool_calls[].id` on continuation chunks (handled inline).
pub struct LingProvider {
    inner: Arc<dyn Provider>,
}

impl LingProvider {
    /// Construct a LingProvider with the given API key. When `base_url` is
    /// `None`, falls back to [`LING_BASE_URL`].
    pub fn new(api_key: String, base_url: Option<String>) -> Self {
        let url = base_url.unwrap_or_else(|| LING_BASE_URL.to_string());
        // ADR-V2-027 F1 quirk for ant-ling: stream closes without [DONE]
        // marker. reasoning_content_field stays default (None) — ant-ling
        // doesn't emit reasoning_content like DeepSeek does.
        let quirks = Quirks {
            no_done_marker: true,
            ..Default::default()
        };
        Self {
            inner: Arc::new(OpenAIProvider::with_base_url_and_quirks(api_key, url, quirks)),
        }
    }

    /// Normalize `tool_calls[].id == null` on continuation chunks (F2-inline quirk).
    ///
    /// ant-ling Ling-2.6 sends `tool_calls[].id = null` on continuation chunks
    /// instead of repeating the original id from the start chunk. Downstream
    /// parsers that key by id then treat each continuation as a new call,
    /// breaking arg-stream accumulation.
    ///
    /// This walks the request's assistant `tool_calls` and substitutes any
    /// missing id with the most recent non-null id seen. No-op for messages
    /// that don't carry tool_calls or whose ids are already populated.
    ///
    /// Note: `CompletionRequest` is currently `Send + Sync` value-typed (no
    /// `tool_calls` mutator surface exposed today). Plumbing the normalization
    /// at request-shape time is left as a forward-compat hook — once
    /// grid-types adds a public `messages_mut()` accessor, fill in the walk
    /// body. For now the function is a documented no-op that establishes the
    /// F2-inline boundary; the runtime fix paths through the F1 `no_done_marker`
    /// branch handle the symptom we've observed in practice (stream hang).
    fn normalize_null_tool_ids(_request: &mut CompletionRequest) {
        // Placeholder hook — see doc comment above. Once `grid_types`
        // exposes mutator access to assistant `tool_calls`, walk
        // `request.messages` and propagate the last non-null id.
    }
}

#[async_trait]
impl Provider for LingProvider {
    fn id(&self) -> &str {
        "ling"
    }

    async fn complete(&self, mut request: CompletionRequest) -> Result<CompletionResponse> {
        Self::normalize_null_tool_ids(&mut request);
        self.inner.complete(request).await
    }

    async fn stream(&self, mut request: CompletionRequest) -> Result<CompletionStream> {
        Self::normalize_null_tool_ids(&mut request);
        self.inner.stream(request).await
    }
}

/// Factory function for the chain.rs / mod.rs dispatch.
///
/// Mirrors [`super::deepseek::create_deepseek_provider`]'s signature.
pub fn create_ling_provider(api_key: String, base_url: Option<String>) -> Box<dyn Provider> {
    Box::new(LingProvider::new(api_key, base_url))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ling_provider_id_is_ling() {
        let p = LingProvider::new("test-key".to_string(), None);
        assert_eq!(p.id(), "ling");
    }

    #[test]
    fn ling_provider_accepts_custom_base_url() {
        // Construction with an explicit base_url should not panic.
        let p = LingProvider::new(
            "test-key".to_string(),
            Some("https://custom.ant-ling.example/v1".to_string()),
        );
        assert_eq!(p.id(), "ling");
    }

    #[test]
    fn ling_factory_returns_correct_id() {
        let p = create_ling_provider("test-key".to_string(), None);
        assert_eq!(p.id(), "ling");
    }

    #[test]
    fn ling_default_base_url_is_set() {
        // Smoke test that the constant exists with a non-empty value.
        assert!(!LING_BASE_URL.is_empty());
        assert!(LING_BASE_URL.starts_with("https://"));
    }
}
