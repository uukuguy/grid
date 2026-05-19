//! DeepSeek provider.
//!
//! DeepSeek's API is OpenAI-compatible *for `deepseek-chat`*. The
//! `deepseek-reasoner` model adds a `reasoning_content` field on assistant
//! responses that **must** be echoed back on subsequent turns, or the
//! API returns HTTP 400 (`The reasoning_content in the thinking mode
//! must be passed back to the API`). Supporting that round-trip requires
//! a schema change on `grid_types::ChatMessage` to carry the thinking
//! payload across turns, which is intentionally deferred to Phase 5.3
//! (see [`D-deepseek-reasoner`] in the deferred ledger).
//!
//! For now this provider:
//!   * accepts any `deepseek-chat*` request and delegates to the OpenAI
//!     implementation with DeepSeek's base URL (cleanly OAI-compatible),
//!   * rejects `deepseek-reasoner*` requests with a clear error so users
//!     don't silently hit the 400 mid-conversation.

use std::sync::Arc;

use anyhow::{anyhow, Result};
use async_trait::async_trait;

use grid_types::{CompletionRequest, CompletionResponse};

use super::openai::OpenAIProvider;
use super::quirks::{Quirks, ReasoningContentField};
use super::traits::{CompletionStream, Provider};

/// Default base URL for DeepSeek's public API.
pub const DEEPSEEK_BASE_URL: &str = "https://api.deepseek.com/v1";

pub struct DeepSeekProvider {
    inner: Arc<dyn Provider>,
}

impl DeepSeekProvider {
    pub fn new(api_key: String, base_url: Option<String>) -> Self {
        let url = base_url.unwrap_or_else(|| DEEPSEEK_BASE_URL.to_string());
        // ADR-V2-027 F1 quirk: DeepSeek emits reasoning_content as a top-level
        // delta field (shared with qwen / minimax / siliconflow). Without this
        // quirk the strict-OpenAI default would silently drop the thinking
        // deltas. DeepSeek DOES emit [DONE] markers — no_done_marker stays false.
        let quirks = Quirks {
            reasoning_content_field: ReasoningContentField::MultiField,
            ..Default::default()
        };
        Self {
            inner: Arc::new(OpenAIProvider::with_base_url_and_quirks(api_key, url, quirks)),
        }
    }

    fn check_model(model: &str) -> Result<()> {
        if model.starts_with("deepseek-reasoner") {
            return Err(anyhow!(
                "deepseek-reasoner is not supported yet — its multi-turn API \
                 requires echoing `reasoning_content` back on each turn, which \
                 needs a ChatMessage schema extension. Tracked as Phase 5.3 \
                 work. Use deepseek-chat instead."
            ));
        }
        Ok(())
    }
}

#[async_trait]
impl Provider for DeepSeekProvider {
    fn id(&self) -> &str {
        "deepseek"
    }

    async fn complete(&self, request: CompletionRequest) -> Result<CompletionResponse> {
        Self::check_model(&request.model)?;
        self.inner.complete(request).await
    }

    async fn stream(&self, request: CompletionRequest) -> Result<CompletionStream> {
        Self::check_model(&request.model)?;
        self.inner.stream(request).await
    }
}

pub fn create_deepseek_provider(api_key: String, base_url: Option<String>) -> Box<dyn Provider> {
    Box::new(DeepSeekProvider::new(api_key, base_url))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn check_model_accepts_deepseek_chat() {
        assert!(DeepSeekProvider::check_model("deepseek-chat").is_ok());
        assert!(DeepSeekProvider::check_model("deepseek-chat-v3.1").is_ok());
    }

    #[test]
    fn check_model_rejects_deepseek_reasoner() {
        let err = DeepSeekProvider::check_model("deepseek-reasoner").unwrap_err();
        assert!(err.to_string().contains("deepseek-reasoner"));
        assert!(err.to_string().contains("Phase 5.3"));
    }

    #[test]
    fn check_model_rejects_reasoner_variants() {
        assert!(DeepSeekProvider::check_model("deepseek-reasoner-r1").is_err());
    }
}
