//! Non-standard OpenAI-compat behaviors observed in real providers.
//!
//! A quirk lands here when ≥2 providers exhibit the same deviation (F1 rule);
//! single-provider quirks split into a dedicated provider per the deepseek.rs
//! precedent (F2 rule). See ADR-V2-027 for the F1/F2 split rule.
//!
//! ## Current F1-promoted quirks (Phase 5.3)
//! - `reasoning_content_field` — confirmed in deepseek + qwen + minimax + siliconflow
//! - `no_done_marker` — confirmed in ant-ling (single provider for now, but the
//!   *behavior* — synthesize MessageStop on stream end — is a common F1 shape;
//!   we promote it eagerly to avoid duplicating logic in future providers)
//!
//! ## Current F2-split quirks (Phase 5.3)
//! - ant-ling continuation chunks with null tool-call IDs — single-provider;
//!   handled inside `crates/grid-engine/src/providers/ling.rs`, NOT this struct.

/// Aggregated quirks config for an OpenAI-compat provider instance.
///
/// Defaults to a strict OpenAI baseline (`reasoning_content_field: None`,
/// `no_done_marker: false`) — this preserves assertion strength against
/// compliant providers per Phase 5.3 RESEARCH §"Pitfall 5". Vendor-specific
/// providers (e.g. [`crate::providers::ling::LingProvider`]) override the
/// relevant fields at construction time.
#[derive(Debug, Clone, Default)]
pub struct Quirks {
    /// Some providers emit reasoning content under a non-standard field
    /// name (`reasoning_content` / `thinking` / `reasoning`).
    ///
    /// Confirmed providers: deepseek-chat, qwen-reasoning, minimax-reasoning,
    /// siliconflow-reasoning. F1-promoted because ≥2 providers share it.
    pub reasoning_content_field: ReasoningContentField,

    /// Some providers close the SSE stream without emitting the trailing
    /// `data: [DONE]` marker. Currently confirmed: ant-ling Ling-2.6-1T.
    ///
    /// When `true`, synthesize MessageStop from accumulator state on stream
    /// end. When `false` (default), absent `[DONE]` is a contract violation
    /// — preserve assertion strength for compliant providers (Pitfall 5).
    pub no_done_marker: bool,
}

/// Strategy for scanning SSE `delta` chunks for reasoning content.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ReasoningContentField {
    /// Strict OpenAI: no reasoning_content field expected (default).
    #[default]
    None,
    /// Scan multiple field names — equivalent to the historical
    /// `["reasoning_content", "thinking", "reasoning"]` triple at
    /// `crates/grid-engine/src/providers/openai.rs:834` (pre-Phase-5.3).
    MultiField,
}
