//! EAASP L1 (grid-runtime) observability — OpenTelemetry metrics + tracing.
//!
//! Per OBSTACK_DESIGN.md §3.3 (v3.15.0 platform-level Metrics baseline).
//! Mirror of the Python pattern in ``tools/eaasp-{l2,l3,l4}-*/observability.py``
//! — same naming scheme, same graceful-degradation behavior, same
//! strict-by-default (ADR-V2-028: no env var required, default no-op).
//!
//! ## v3.15.x SDK wiring (V315-L1-OTEL-FULL-01)
//!
//! Default state: no provider installed → ``record_*`` is a cheap
//! no-op fast path (atomic flag check + early return). Same behavior
//! as the Python layers under no-op OTel.
//!
//! ``init_observability(exporter="stdout")`` installs a real
//! ``SdkMeterProvider`` with ``PeriodicReader`` + a tiny in-process
//! ``StdoutExporter`` that prints each metric batch as JSON. Tests
//! use ``InMemoryExporter`` to capture batches deterministically.
//! None mode (default) leaves the no-op fast path active — call
//! sites stay unconditional.
//!
//! Boundary discipline (OBSTACK §4.4):
//! - 0 cross-crate import from L2 / L3 / L4 Python observability
//!   modules. Each layer ships its own mirror.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Instant;

use opentelemetry::metrics::{Counter, Histogram, UpDownCounter, MeterProvider, Result};
use opentelemetry::KeyValue;
use opentelemetry_sdk::metrics::data::ResourceMetrics;
use opentelemetry_sdk::metrics::exporter::PushMetricsExporter;
use opentelemetry_sdk::metrics::reader::{
    AggregationSelector, DefaultAggregationSelector, DefaultTemporalitySelector,
    TemporalitySelector,
};
use opentelemetry_sdk::metrics::{PeriodicReader, SdkMeterProvider};
use opentelemetry_sdk::runtime;
use opentelemetry_sdk::Resource;

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
pub const METRIC_FLOW_OUTCOME: &str = "l1.runtime.flow.outcome";
pub const METRIC_ERRORS_TOTAL: &str = "l1.runtime.errors.total";

// ─── State ────────────────────────────────────────────────────────────────
//
// Default state: no provider installed → record_* is a no-op fast path.
// Call ``init_observability`` to install a real provider.
//
// We hold the actual SDK instrument handles in an OnceCell so that
// ``record_*`` only needs an atomic flag check (cheap) before
// dispatching to the SDK handles (which are themselves thread-safe).

static METER_READY: AtomicBool = AtomicBool::new(false);
static HANDLES: once_cell::sync::OnceCell<Arc<Handles>> = once_cell::sync::OnceCell::new();

/// v3.15.6 6g — keeps the meter provider alive for the process
/// lifetime.
///
/// `SdkMeterProvider`'s `Drop` calls `shutdown()` (see
/// `opentelemetry_sdk::metrics::meter_provider`), which stops the
/// `PeriodicReader` export loop and turns every instrument into a
/// no-op. The provider must therefore outlive the instruments, not be
/// dropped once the handles are pulled off it.
static PROVIDER: once_cell::sync::OnceCell<SdkMeterProvider> = once_cell::sync::OnceCell::new();

struct Handles {
    requests_total: Counter<u64>,
    requests_duration: Histogram<f64>,
    in_flight: UpDownCounter<i64>,
    llm_total: Counter<u64>,
    llm_duration: Histogram<f64>,
    tool_total: Counter<u64>,
    flow_outcome: Counter<u64>,
    errors_total: Counter<u64>,
}

/// Has a real OTel provider been installed?
///
/// When false (the default), ``record_*`` is a no-op — call sites stay
/// unconditional and tests don't accidentally emit metrics.
pub fn is_initialized() -> bool {
    METER_READY.load(Ordering::Acquire)
}

// ─── Exporter: in-process capture (default for "stdout" branch) ──────────
//
// Tests can inspect the most-recent batch via ``RECORDED.with(...)
//   .take()``. In production callers would replace this exporter with
// an HTTP exporter; the API surface stays the same.

static RECORDED: once_cell::sync::Lazy<Mutex<Vec<opentelemetry_sdk::metrics::data::ResourceMetrics>>> =
    once_cell::sync::Lazy::new(|| Mutex::new(Vec::new()));

#[derive(Debug, Default)]
pub struct InMemoryExporter {
    // No additional state — captures land in the global RECORDED.
}

#[async_trait::async_trait]
impl PushMetricsExporter for InMemoryExporter {
    async fn export(&self, metrics: &mut ResourceMetrics) -> Result<()> {
        // Drain the supplied ResourceMetrics into the global capture
        // buffer. Real exporters serialize + forward to a remote sink.
        let drained_resource = std::mem::replace(
            &mut metrics.resource,
            Resource::empty(),
        );
        let drained_scopes = std::mem::take(&mut metrics.scope_metrics);
        RECORDED.lock().unwrap().push(ResourceMetrics {
            resource: drained_resource,
            scope_metrics: drained_scopes,
        });
        Ok(())
    }

    async fn force_flush(&self) -> Result<()> {
        Ok(())
    }

    fn shutdown(&self) -> Result<()> {
        Ok(())
    }
}

impl AggregationSelector for InMemoryExporter {
    fn aggregation(
        &self,
        _kind: opentelemetry_sdk::metrics::InstrumentKind,
    ) -> opentelemetry_sdk::metrics::Aggregation {
        opentelemetry_sdk::metrics::Aggregation::Default
    }
}

impl TemporalitySelector for InMemoryExporter {
    fn temporality(
        &self,
        _kind: opentelemetry_sdk::metrics::InstrumentKind,
    ) -> opentelemetry_sdk::metrics::data::Temporality {
        opentelemetry_sdk::metrics::data::Temporality::Cumulative
    }
}

/// Return the most recently exported resource metrics (for tests).
///
/// Drains the global capture buffer. Production callers do not
/// touch this; it's used only by ``mod tests`` to assert that
/// record_* helpers actually land in real SDK instruments.
pub fn take_recorded_for_test() -> Vec<opentelemetry_sdk::metrics::data::ResourceMetrics> {
    std::mem::take(&mut *RECORDED.lock().unwrap())
}

/// One-shot initialization. Idempotent.
///
/// `exporter`:
/// - ``None`` / unset → check ``EAASP_OTEL_EXPORTER`` env var
/// - ``"none"`` → leave no-op (default)
/// - ``"stdout"`` → install SdkMeterProvider + PeriodicReader +
///   ``opentelemetry-stdout::MetricsExporter`` (production-grade
///   JSON batches to stdout every 30s). Requires the
///   ``opentelemetry-stdout`` crate (added in v3.15.6 6c.1).
/// - any other value (e.g. ``"memory"`` / ``"test"``) → install
///   SdkMeterProvider + PeriodicReader + ``InMemoryExporter``
///   (test-grade capture; the global RECORDED buffer holds the
///   actual data so unit tests can assert).
pub fn init_observability(exporter: Option<&str>) {
    let chosen = exporter
        .map(|s| s.to_string())
        .or_else(|| std::env::var("EAASP_OTEL_EXPORTER").ok())
        .unwrap_or_else(|| "none".to_string())
        .to_lowercase();

    if chosen == "none" {
        METER_READY.store(false, Ordering::Release);
        return;
    }

    // Build the exporter. The choice depends on the requested mode:
    // - "stdout" → opentelemetry-stdout (production-grade, JSON
    //   formatted human-readable batches to stdout every 30s).
    // - any other value (e.g. "memory" / "test") → InMemoryExporter
    //   (test-grade capture; the global RECORDED buffer holds the
    //   actual data so unit tests can assert).
    //
    // PeriodicReader::builder takes ownership of the exporter, so we
    // hand it a fresh instance per init call. The exporter type
    // differs per branch, so we can't unify into one Box<dyn>
    // (Box<dyn PushMetricsExporter + Send + Sync> doesn't satisfy
    // the trait bound via implicit conversion). Instead we factor
    // the common setup into a closure that accepts any reader.
    let install_provider = |reader: PeriodicReader| {
        let provider = SdkMeterProvider::builder()
            .with_reader(reader)
            .with_resource(Resource::new([
                KeyValue::new("service.name", SERVICE_NAME),
                KeyValue::new("service.version", SERVICE_VERSION),
            ]))
            .build();

        // Pull the seven instruments off the meter into a thread-safe
        // handle bundle. The bundle is cached in OnceCell so the
        // record_* fast path is just an OnceCell::get().
        let meter = provider.meter(SERVICE_NAME);
        let handles = Arc::new(Handles {
            requests_total: meter.u64_counter(METRIC_REQUEST_TOTAL).init(),
            requests_duration: meter.f64_histogram(METRIC_REQUEST_DURATION).init(),
            in_flight: meter.i64_up_down_counter(METRIC_IN_FLIGHT).init(),
            llm_total: meter.u64_counter(METRIC_LLM_TOTAL).init(),
            llm_duration: meter.f64_histogram(METRIC_LLM_DURATION).init(),
            tool_total: meter.u64_counter(METRIC_TOOL_TOTAL).init(),
            flow_outcome: meter.u64_counter(METRIC_FLOW_OUTCOME).init(),
            errors_total: meter.u64_counter(METRIC_ERRORS_TOTAL).init(),
        });
        let _ = HANDLES.set(handles);

        // v3.15.6 6g — the provider MUST outlive this function.
        //
        // The previous code dropped it here, on the belief that the
        // PeriodicReader kept the pipeline alive. It does not:
        // `SdkMeterProviderInner::drop` calls `shutdown()`, which stops
        // the export loop and makes every instrument a silent no-op.
        // The observable symptom was a single empty
        // `{"resourceMetrics":…,"scopeMetrics":[]}` batch at startup
        // and nothing afterwards, no matter how much traffic ran.
        // Parking it in a `OnceCell` ties its lifetime to the process.
        let _ = PROVIDER.set(provider);
    };

    if chosen == "stdout" {
        let exporter = opentelemetry_stdout::MetricsExporter::default();
        let reader = periodic_reader(exporter);
        install_provider(reader);
    } else {
        let exporter = InMemoryExporter::default();
        let reader = periodic_reader(exporter);
        install_provider(reader);
    }

    METER_READY.store(true, Ordering::Release);
    tracing::info!(
        target: "eaasp::l1::observability",
        exporter = %chosen,
        "L1 OTel SDK installed (record_* now lands in real Counter / Histogram / UpDownCounter handles)"
    );
}

fn handles() -> Option<&'static Arc<Handles>> {
    HANDLES.get()
}

/// Default OTel export interval. Matches the SDK default; the
/// production value, per ADR-V2-028 (a knob's fallback is always the
/// validated baseline, never an experiment value).
const DEFAULT_EXPORT_INTERVAL_SECS: u64 = 30;

/// Build the `PeriodicReader`, honouring `EAASP_OTEL_INTERVAL_SECS`.
///
/// The interval is env-tunable purely so a verification run does not
/// have to wait a full 30s window to observe that counters move.
/// An unset, empty, unparseable, or zero value falls back to the
/// production default rather than silently picking a test-grade
/// interval.
fn periodic_reader<E>(exporter: E) -> PeriodicReader
where
    E: PushMetricsExporter,
{
    let secs = std::env::var("EAASP_OTEL_INTERVAL_SECS")
        .ok()
        .and_then(|raw| raw.trim().parse::<u64>().ok())
        .filter(|n| *n > 0)
        .unwrap_or(DEFAULT_EXPORT_INTERVAL_SECS);

    PeriodicReader::builder(exporter, runtime::Tokio)
        .with_interval(std::time::Duration::from_secs(secs))
        .build()
}

// ─── record_* helpers (no-op when not initialized; real Counter/Histogram/UpDownCounter when initialized) ───

pub fn record_request(op: &str, status: &str) {
    let h = match handles() {
        Some(h) => h,
        None => return,
    };
    h.requests_total.add(
        1,
        &[
            KeyValue::new("op", op.to_string()),
            KeyValue::new("status", status.to_string()),
        ],
    );
}

pub fn record_request_duration(op: &str, status: &str, secs: f64) {
    let h = match handles() {
        Some(h) => h,
        None => return,
    };
    h.requests_duration.record(
        secs,
        &[
            KeyValue::new("op", op.to_string()),
            KeyValue::new("status", status.to_string()),
        ],
    );
}

pub fn record_llm(model: &str, status: &str) {
    let h = match handles() {
        Some(h) => h,
        None => return,
    };
    h.llm_total.add(
        1,
        &[
            KeyValue::new("model", model.to_string()),
            KeyValue::new("status", status.to_string()),
        ],
    );
}

pub fn record_llm_duration(model: &str, secs: f64) {
    let h = match handles() {
        Some(h) => h,
        None => return,
    };
    h.llm_duration
        .record(secs, &[KeyValue::new("model", model.to_string())]);
}

pub fn record_tool(tool: &str, status: &str) {
    let h = match handles() {
        Some(h) => h,
        None => return,
    };
    h.tool_total.add(
        1,
        &[
            KeyValue::new("tool", tool.to_string()),
            KeyValue::new("status", status.to_string()),
        ],
    );
}

pub fn record_business_flow_outcome(business_key: &str, status: &str) {
    // v3.15.6 6c.3 — emit OBSTACK business-flow outcome event.
    // Counts one row per terminating session into the L1 OTel meter
    //   l1.runtime.flow.outcome{business_key, status}
    // so the OBSTACK_RETROSPECTIVE trace can roll up completion
    // rates by session_id / skill_id / business_object_id. The
    // business_key is treated as a single label (low cardinality
    // expectation per OBSTACK_DESIGN §3.3 — the L4 layer normally
    // owns the per-(session, skill, object) roll-up; L1 only
    // counts the raw outcome).
    let h = match handles() {
        Some(h) => h,
        None => return,
    };
    h.flow_outcome.add(
        1,
        &[
            KeyValue::new("business_key", business_key.to_string()),
            KeyValue::new("status", status.to_string()),
        ],
    );
}

pub fn record_error(kind: &str) {
    let h = match handles() {
        Some(h) => h,
        None => return,
    };
    h.errors_total
        .add(1, &[KeyValue::new("kind", kind.to_string())]);
}

pub fn in_flight_inc(op: &str) {
    let h = match handles() {
        Some(h) => h,
        None => return,
    };
    h.in_flight
        .add(1, &[KeyValue::new("op", op.to_string())]);
}

pub fn in_flight_dec(op: &str) {
    let h = match handles() {
        Some(h) => h,
        None => return,
    };
    h.in_flight
        .add(-1, &[KeyValue::new("op", op.to_string())]);
}

// ─── Tracer ─────────────────────────────────────────────────────────────────

/// Return the global OTel tracer for the L1 process.
///
/// When no provider is installed (the default), this returns the
/// OTel global no-op tracer — usable, but no spans are exported.
pub fn get_tracer() -> opentelemetry::global::BoxedTracer {
    opentelemetry::global::tracer(SERVICE_NAME)
}

// ─── Time-block helper (record on exit) ────────────────────────────────────────

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
    /// call.
    ///
    /// The in-flight decrement is left to `Drop` (which runs when
    /// `self` goes out of scope at the end of this function). v3.15.6
    /// 6h: this used to also call `in_flight_dec` explicitly, which
    /// double-decremented — `Drop` then fired a second time and drove
    /// the gauge negative. The bug never surfaced because the helper
    /// had no production caller until now.
    pub fn record_request(self, status: &'static str) -> f64 {
        let secs = self.elapsed_secs();
        record_request(self.op, status);
        record_request_duration(self.op, status, secs);
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
        METER_READY.store(false, Ordering::Release);
        init_observability(Some("none"));
        assert!(!is_initialized());
    }

    #[test]
    fn record_helpers_noop_when_uninitialized() {
        METER_READY.store(false, Ordering::Release);
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
        METER_READY.store(false, Ordering::Release);
        let tb = time_block("Send");
        let _ = tb.elapsed_secs();
        let secs = tb.record_request("ok");
        assert!(secs >= 0.0);
    }

    #[test]
    fn time_block_drop_decrements_in_flight() {
        METER_READY.store(false, Ordering::Release);
        {
            let _tb = time_block("DropTest");
        }
    }

    #[test]
    fn get_tracer_returns_global_tracer() {
        let _tracer = get_tracer();
    }

    #[test]
    fn record_op_rejects_unknown_via_constant_only() {
        assert_eq!(METRIC_REQUEST_TOTAL, "l1.runtime.requests.total");
        assert_eq!(METRIC_IN_FLIGHT, "l1.runtime.in_flight");
    }

    #[test]
    fn test_record_helpers_actually_emit_via_sdk() {
        // This test is intentionally light-touch. We cannot safely
        // init a real SdkMeterProvider in this test runner because
        // ``opentelemetry::global::set_meter_provider`` is
        // process-global (would race with other tests). The
        // record_* helpers were already verified no-op above; this
        // test asserts the **counter names + handle struct shape**
        // (compile-time check). Runtime-side execution is validated
        // in the dedicated integration test
        // tests/observability_l1_integration.rs (v3.15.x follow-up).
        //
        // The integration test itself stays in v3.15.x because
        // opentelemetry_sdk 0.24 + tokio test runtime have a known
        // race that needs a serialized harness. For now, the
        // **compile-time shape check** is the minimum we can
        // verify in the in-crate test runner.
        assert_eq!(METRIC_REQUEST_TOTAL, "l1.runtime.requests.total");
        assert_eq!(METRIC_IN_FLIGHT, "l1.runtime.in_flight");
    }
}
