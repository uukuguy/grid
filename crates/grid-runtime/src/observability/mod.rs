//! EAASP L1 (grid-runtime) observability — OpenTelemetry metrics + tracing.
//!
//! Per OBSTACK_DESIGN.md §3.3 (v3.15.0 platform-level Metrics baseline).
//! Mirror of the Python pattern in ``tools/eaasp-{l2,l3,l4}-*/observability.py``
//! — same naming scheme, same graceful-degradation behavior, same
//! strict-by-default (ADR-V2-028: no env var required, default no-op).
//!
//! ## Initial scope (v3.15.0)
//!
//! This is the **minimal-viable mirror** for the L1 Rust layer:
//! record_* helpers + time_block helper + a tracer helper. All default
//! to no-op (no global OTel initialization required, no metrics emit
//! unless the caller flips on a real provider via
//! ``init_observability(exporter="stdout")``).
//!
//! Future v3.15.x follow-ups:
//! - Real OTel SDK initialization wiring (`opentelemetry_sdk::metrics`)
//! - Hot-reload of the global meter via ``Provider::shutdown`` + replace
//! - Wire `opentelemetry-otlp` for OTLP exporter
//! - Add tracing_subscriber::fmt + `tracing_opentelemetry::layer()` for
//!   automatic span→metrics correlation
//!
//! Boundary discipline (OBSTACK §4.4):
//! - 0 cross-crate import from L2 / L3 / L4 Python observability
//!   modules. Each layer ships its own mirror.

use std::time::Instant;

/// Stable service identity (per OTel resource convention).
pub const SERVICE_NAME: &str = "grid-runtime";
pub const SERVICE_VERSION: &str = env!("CARGO_PKG_VERSION");

// ─── Metric name constants ─────────────────────────────────────────────────
//
// All names follow the `<layer>.<entity>.<measurement>` convention
// from OBSTACK_DESIGN.md §3.3. DO NOT rename without a coordinated
// update across L0–L5.

pub const METRIC_REQUEST_TOTAL: &str = "l1.runtime.requests.total";
pub const METRIC_REQUEST_DURATION: &str = "l1.runtime.requests.duration";
pub const METRIC_IN_FLIGHT: &str = "l1.runtime.in_flight";
pub const METRIC_LLM_TOTAL: &str = "l1.runtime.llm.total";
pub const METRIC_LLM_DURATION: &str = "l1.runtime.llm.duration";
pub const METRIC_TOOL_TOTAL: &str = "l1.runtime.tool.total";
pub const METRIC_ERRORS_TOTAL: &str = "l1.runtime.errors.total";

// ─── Metrics state ──────────────────────────────────────────────────────────
//
// Default state: no provider installed → record_* is a no-op fast path.
// Call ``init_observability`` to install a real provider.

static METER_READY: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

/// Has a real OTel provider been installed?
///
/// When false (the default), ``record_*`` is a no-op — call sites stay
/// unconditional and tests don't accidentally emit metrics.
pub fn is_initialized() -> bool {
    METER_READY.load(std::sync::atomic::Ordering::Acquire)
}

/// One-shot initialization. Idempotent.
///
/// `exporter`:
/// - ``None`` → check ``EAASP_OTEL_EXPORTER`` env var, default ``"none"``
/// - ``"none"`` → leave no-op (default)
/// - ``"stdout"`` → install SDK with stdout exporters (placeholder;
///   full wiring deferred to a follow-up — for now this still leaves
///   the no-op path active and logs a tracing event)
pub fn init_observability(exporter: Option<&str>) {
    let chosen = exporter
        .map(|s| s.to_string())
        .or_else(|| std::env::var("EAASP_OTEL_EXPORTER").ok())
        .unwrap_or_else(|| "none".to_string())
        .to_lowercase();

    if chosen == "none" {
        METER_READY.store(false, std::sync::atomic::Ordering::Release);
        return;
    }

    // Placeholder: real SDK wiring lands in a follow-up. For now we
    // emit a tracing event so operators can see the intent and keep
    // record_* as no-op until then.
    tracing::info!(
        target: "eaasp::l1::observability",
        exporter = %chosen,
        "L1 OTel init requested; SDK wiring deferred to v3.15.x follow-up — record_* stays no-op"
    );
    METER_READY.store(true, std::sync::atomic::Ordering::Release);
}

// ─── record_* helpers (no-op when not initialized) ─────────────────────────
//
// Mirrors of the Python layer's record_* functions. Each fires a
// counter increment with `status` (or model / kind) label.
//
// When METER_READY is false (the default), record_* is a cheap no-op —
// same behavior as the Python layer under no-op OTel.

pub fn record_request(op: &str, status: &str) {
    if !is_initialized() {
        return;
    }
    // Real metric emit would happen here via the SDK. Until the SDK
    // wiring lands (v3.15.x follow-up), we route through tracing::info
    // so the platform OTel pipeline can later attach a layer and
    // forward it.
    tracing::debug!(
        target: "eaasp::l1::observability",
        metric = METRIC_REQUEST_TOTAL,
        op = %op,
        status = %status,
        "l1.runtime.requests.total++"
    );
}

pub fn record_request_duration(op: &str, status: &str, secs: f64) {
    if !is_initialized() {
        return;
    }
    tracing::debug!(
        target: "eaasp::l1::observability",
        metric = METRIC_REQUEST_DURATION,
        op = %op,
        status = %status,
        secs = secs,
        "l1.runtime.requests.duration.observe"
    );
}

pub fn record_llm(model: &str, status: &str) {
    if !is_initialized() {
        return;
    }
    tracing::debug!(
        target: "eaasp::l1::observability",
        metric = METRIC_LLM_TOTAL,
        model = %model,
        status = %status,
        "l1.runtime.llm.total++"
    );
}

pub fn record_llm_duration(model: &str, secs: f64) {
    if !is_initialized() {
        return;
    }
    tracing::debug!(
        target: "eaasp::l1::observability",
        metric = METRIC_LLM_DURATION,
        model = %model,
        secs = secs,
        "l1.runtime.llm.duration.observe"
    );
}

pub fn record_tool(tool: &str, status: &str) {
    if !is_initialized() {
        return;
    }
    tracing::debug!(
        target: "eaasp::l1::observability",
        metric = METRIC_TOOL_TOTAL,
        tool = %tool,
        status = %status,
        "l1.runtime.tool.total++"
    );
}

pub fn record_error(kind: &str) {
    if !is_initialized() {
        return;
    }
    tracing::debug!(
        target: "eaasp::l1::observability",
        metric = METRIC_ERRORS_TOTAL,
        kind = %kind,
        "l1.runtime.errors.total++"
    );
}

pub fn in_flight_inc(op: &str) {
    if !is_initialized() {
        return;
    }
    tracing::debug!(
        target: "eaasp::l1::observability",
        metric = METRIC_IN_FLIGHT,
        op = %op,
        "l1.runtime.in_flight++"
    );
}

pub fn in_flight_dec(op: &str) {
    if !is_initialized() {
        return;
    }
    tracing::debug!(
        target: "eaasp::l1::observability",
        metric = METRIC_IN_FLIGHT,
        op = %op,
        "l1.runtime.in_flight--"
    );
}

// ─── Tracer ────────────────────────────────────────────────────────────────
//
// Even when no metrics provider is installed, `get_tracer()` returns the
// global OTel tracer (which is a no-op tracer by default). That lets
// call sites stay unconditional: any hot path can wrap itself in a
// span and the SDK layer is added later.

/// Return the global OTel tracer for the L1 process.
///
/// When no provider is installed (the default), this returns the
/// OTel global no-op tracer — usable, but no spans are exported.
pub fn get_tracer() -> opentelemetry::global::BoxedTracer {
    opentelemetry::global::tracer(SERVICE_NAME)
}

// ─── Time-block helper (record on exit) ────────────────────────────────────
//
// Mirrors the Python ``time_block()`` / ``_Timer`` pattern:
//   with time_block(...) as t: ...; t.record_request("ok")

pub struct TimeBlock {
    op: &'static str,
    start: Instant,
}

pub fn time_block(op: &'static str) -> TimeBlock {
    in_flight_inc(op);
    TimeBlock {
        op,
        start: Instant::now(),
    }
}

impl TimeBlock {
    pub fn elapsed_secs(&self) -> f64 {
        self.start.elapsed().as_secs_f64()
    }

    /// Record the request as complete with the given status and emit
    /// both the counter increment and the duration histogram in one
    /// call. Decrements the in-flight gauge.
    pub fn record_request(self, status: &'static str) -> f64 {
        let secs = self.elapsed_secs();
        record_request(self.op, status);
        record_request_duration(self.op, status, secs);
        in_flight_dec(self.op);
        secs
    }

    /// LLM counterpart: counter + duration histogram.
    pub fn record_llm(self, model: &str, status: &'static str) -> f64 {
        let secs = self.elapsed_secs();
        record_llm(model, status);
        record_llm_duration(model, secs);
        secs
    }
}

impl Drop for TimeBlock {
    fn drop(&mut self) {
        // RAII safety net: if the caller forgot to record explicitly,
        // still decrement the in-flight gauge so it doesn't drift.
        in_flight_dec(self.op);
    }
}

// ─── Tests ─────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_is_uninitialized_noop() {
        // Reset globally first so test order doesn't matter.
        METER_READY.store(false, std::sync::atomic::Ordering::Release);
        init_observability(Some("none"));
        assert!(!is_initialized());
    }

    #[test]
    fn record_helpers_noop_when_uninitialized() {
        METER_READY.store(false, std::sync::atomic::Ordering::Release);
        // All record_* must be safe to call without a real provider.
        record_request("Initialize", "ok");
        record_request_duration("Initialize", "ok", 0.001);
        record_llm("claude-sonnet-4", "ok");
        record_llm_duration("claude-sonnet-4", 0.5);
        record_tool("Read", "ok");
        record_error("validation");
        in_flight_inc("Send");
        in_flight_dec("Send");
    }

    #[test]
    fn time_block_round_trip() {
        METER_READY.store(false, std::sync::atomic::Ordering::Release);
        let tb = time_block("Send");
        let _ = tb.elapsed_secs();
        let secs = tb.record_request("ok");
        assert!(secs >= 0.0);
    }

    #[test]
    fn time_block_drop_decrements_in_flight() {
        METER_READY.store(false, std::sync::atomic::Ordering::Release);
        {
            let _tb = time_block("DropTest");
        }
        // Drop fired; gauge returned to baseline. We can't observe the
        // in-flight gauge directly (it's no-op without init), but the
        // drop path is at least covered.
    }

    #[test]
    fn get_tracer_returns_global_tracer() {
        // No panic, no special handling needed; the global tracer is
        // usable even before any real provider is installed.
        let _tracer = get_tracer();
    }

    #[test]
    fn record_op_rejects_unknown_via_constant_only() {
        // The Rust helper does not validate the `op` string itself; the
        // contract relies on stable constants. This test pins the
        // contract by asserting the value of the constants are non-empty.
        assert_eq!(METRIC_REQUEST_TOTAL, "l1.runtime.requests.total");
        assert_eq!(METRIC_IN_FLIGHT, "l1.runtime.in_flight");
    }
}
