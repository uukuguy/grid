//! PreCompactEmitter — observability hook that captures `PRE_COMPACT`
//! HookEventType firings for contract-test inspection.
//!
//! Phase 7.1 T02 (CONTRACT-01 / D137 part 2). The `HookEventType::PreCompact = 8`
//! lifecycle event is defined at `proto/eaasp/runtime/v2/runtime.proto:246`
//! and travels via the `EventStreamEntry` envelope (runtime.proto:263-269)
//! through the existing `emit_event` RPC at `service.rs:597-613`. The
//! PreCompact HOOK already fires inside
//! `crates/grid-engine/src/context/compaction_pipeline.rs:349` when
//! `CompactionPipelineConfig.proactive_threshold_pct` is breached.
//!
//! What this module adds: a `HookHandler` registered on `HookPoint::PreCompact`
//! that, when fired, appends a JSON line describing the event to
//! `${GRID_CONTRACT_PROBE_OUT}/events.jsonl`. The contract suite reads
//! this file via `tests/contract/harness/event_log.py::fetch_captured_events`.
//!
//! ## Why a file sink instead of in-memory channel
//!
//! The contract tests run in a separate Python process from the runtime
//! Rust subprocess; an in-memory channel would require new RPC plumbing
//! or a new HTTP endpoint inside grid-runtime, both of which are heavier
//! than reusing the existing `GRID_CONTRACT_PROBE_OUT` directory that
//! the scoped-hook bash scripts already write into. File-based capture
//! also stays compatible with multi-process testing (the test reads
//! the same file regardless of how many runtime instances ran).
//!
//! When `GRID_CONTRACT_PROBE_OUT` is unset the hook is a no-op
//! (production runs that don't opt into contract probing pay zero
//! cost).
//!
//! ## Mapping
//!
//! HookContext metadata at the PreCompact fire site (compaction_pipeline.rs:335-348):
//!   - `trigger` (string): "proactive_threshold" | "reactive_413"
//!   - `estimated_tokens` (u64)
//!   - `context_window` (u64)
//!   - `usage_pct` (u32, 0-100)
//!   - `messages_to_compact` (u32)
//!   - `messages_total` (u32)
//!   - `reuses_prior_summary` (bool)
//!   - `prior_summary_count` (u32)
//!
//! Captured line shape (one JSON object per line):
//!   ```json
//!   {
//!     "event_type": "PRE_COMPACT",
//!     "session_id": "...",
//!     "trigger": "proactive_threshold",
//!     "usage_pct": 7,
//!     "timestamp": "2026-06-02T..."
//!   }
//!   ```

use async_trait::async_trait;
use grid_engine::hooks::{HookAction, HookContext, HookFailureMode, HookHandler};
use serde_json::json;
use std::io::Write;
use std::path::PathBuf;
use tracing::{debug, warn};

/// PreCompact observability hook. Append-only file sink.
pub struct PreCompactEmitter {
    /// Resolved file path the hook appends event lines to. `None` means
    /// `GRID_CONTRACT_PROBE_OUT` was unset at construction time and the
    /// hook will be a no-op for every invocation.
    out_file: Option<PathBuf>,
}

impl PreCompactEmitter {
    /// Construct a new emitter reading `GRID_CONTRACT_PROBE_OUT` at
    /// initialization time. The path resolves to
    /// `<probe_out>/events.jsonl`.
    pub fn from_env() -> Self {
        let out_file = std::env::var("GRID_CONTRACT_PROBE_OUT")
            .ok()
            .map(|dir| PathBuf::from(dir).join("events.jsonl"));
        Self { out_file }
    }
}

#[async_trait]
impl HookHandler for PreCompactEmitter {
    fn name(&self) -> &str {
        "pre-compact-emitter"
    }

    fn priority(&self) -> u32 {
        // Run after all critical PreCompact hooks; observability only.
        950
    }

    fn failure_mode(&self) -> HookFailureMode {
        HookFailureMode::FailOpen
    }

    fn is_async(&self) -> bool {
        // Synchronous so the file write completes before the hook
        // returns — tests read the file shortly after the Send turn
        // completes and need the line present.
        false
    }

    async fn execute(&self, ctx: &HookContext) -> anyhow::Result<HookAction> {
        let Some(out_file) = &self.out_file else {
            return Ok(HookAction::Continue);
        };

        let session_id = ctx.session_id.clone().unwrap_or_default();
        let trigger = ctx
            .metadata
            .get("trigger")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string();
        let usage_pct = ctx
            .metadata
            .get("usage_pct")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);

        let line = json!({
            "event_type": "PRE_COMPACT",
            "session_id": session_id,
            "trigger": trigger,
            "usage_pct": usage_pct,
            "timestamp": chrono::Utc::now().to_rfc3339(),
        });

        if let Some(parent) = out_file.parent() {
            if let Err(e) = std::fs::create_dir_all(parent) {
                warn!(error = %e, path = ?parent, "PreCompactEmitter: cannot mkdir parent");
                return Ok(HookAction::Continue);
            }
        }

        let result = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(out_file)
            .and_then(|mut f| writeln!(f, "{}", line));

        match result {
            Ok(()) => {
                debug!(
                    session_id = %session_id,
                    trigger = %trigger,
                    usage_pct = usage_pct,
                    "PreCompactEmitter: captured PRE_COMPACT event"
                );
            }
            Err(e) => {
                warn!(error = %e, path = ?out_file, "PreCompactEmitter: write failed");
            }
        }

        Ok(HookAction::Continue)
    }
}
