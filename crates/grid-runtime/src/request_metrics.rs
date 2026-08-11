//! v3.15.6 6h — OBSTACK `l1.runtime.requests.*` wiring.
//!
//! `record_request` / `record_request_duration` / the `time_block`
//! helper have existed since the OTel module landed, but nothing in
//! production ever called them: `requests.total` and
//! `requests.duration` read as zero no matter how much traffic the
//! runtime served. This tower layer is the missing caller.
//!
//! It sits at the HTTP layer that tonic serves gRPC over, so every
//! RPC — current and future — is counted from one place. The
//! alternative (wrapping each of the 19 handler bodies) would have to
//! be repeated for every new method and re-audited at every early
//! return.
//!
//! ## What `op` means
//!
//! The gRPC path is `/eaasp.runtime.v2.RuntimeService/Send`; `op` is
//! the trailing method name (`Send`), **matched against a closed
//! allowlist** of the RPCs declared in `proto/eaasp/runtime/v2/`.
//! Anything else is recorded as the literal `unknown`.
//!
//! The allowlist is a cardinality bound, not decoration. `op` becomes
//! an OTel attribute value and the meter keeps one time series per
//! distinct value for the life of the process. Echoing the raw path
//! segment would let any peer that can reach the gRPC port mint
//! unbounded series (`/x/aaa`, `/x/aab`, …) and grow the metric map
//! without limit — memory exhaustion requiring no authentication.
//! Collapsing to `unknown` also keeps a genuine routing mistake
//! visible as a metric instead of silence.
//!
//! ## Streaming caveat (deliberate)
//!
//! For server-streaming RPCs (`Send`), the HTTP response resolves as
//! soon as headers are sent — the body streams afterwards. So
//! `requests.duration{op="Send"}` measures *time to first response*,
//! not the duration of the whole turn. That is the honest meaning of
//! an RPC-dispatch metric; whole-turn accounting is what
//! `flow.outcome` and `in_flight{op="turn"}` cover (see `harness.rs`).

use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};

use tower::{Layer, Service};

use crate::observability::{record_request, record_request_duration};

/// Every RPC declared in `proto/eaasp/runtime/v2/{runtime,hook}.proto`.
///
/// Keep in sync when the proto gains a method; an unlisted method is
/// still counted, just under [`UNKNOWN_OP`].
const KNOWN_METHODS: &[&str] = &[
    // runtime.proto (17)
    "Initialize",
    "Send",
    "LoadSkill",
    "OnToolCall",
    "OnToolResult",
    "OnStop",
    "GetState",
    "ConnectMCP",
    "EmitTelemetry",
    "GetCapabilities",
    "Terminate",
    "RestoreState",
    "Health",
    "DisconnectMcp",
    "PauseSession",
    "ResumeSession",
    "EmitEvent",
    // hook.proto (4)
    "StreamHooks",
    "EvaluateHook",
    "ReportTelemetry",
    "GetPolicySummary",
];

/// Label for any path that is not a known RPC.
const UNKNOWN_OP: &str = "unknown";

/// Tower layer that records `l1.runtime.requests.*` per gRPC call.
#[derive(Clone, Copy, Debug, Default)]
pub struct RequestMetricsLayer;

impl RequestMetricsLayer {
    pub fn new() -> Self {
        Self
    }
}

impl<S> Layer<S> for RequestMetricsLayer {
    type Service = RequestMetrics<S>;

    fn layer(&self, inner: S) -> Self::Service {
        RequestMetrics { inner }
    }
}

/// Service produced by [`RequestMetricsLayer`].
#[derive(Clone, Debug)]
pub struct RequestMetrics<S> {
    inner: S,
}

/// Resolve a request path to a bounded `op` label.
///
/// Returns a `&'static str` drawn from [`KNOWN_METHODS`], or
/// [`UNKNOWN_OP`]. Never returns caller-controlled text, so the label
/// set cannot exceed `KNOWN_METHODS.len() + 1` regardless of what any
/// peer sends.
fn op_label(path: &str) -> &'static str {
    let name = match path.rsplit('/').next() {
        Some(n) if !n.is_empty() => n,
        _ => return UNKNOWN_OP,
    };
    KNOWN_METHODS
        .iter()
        .find(|known| **known == name)
        .copied()
        .unwrap_or(UNKNOWN_OP)
}

impl<S, ReqBody, ResBody> Service<http::Request<ReqBody>> for RequestMetrics<S>
where
    S: Service<http::Request<ReqBody>, Response = http::Response<ResBody>>,
    S::Future: Send + 'static,
    S::Error: 'static,
{
    type Response = S::Response;
    type Error = S::Error;
    type Future =
        Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send + 'static>>;

    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }

    fn call(&mut self, req: http::Request<ReqBody>) -> Self::Future {
        // Bounded label — see `op_label` and the module note on
        // cardinality. Never the raw path.
        let op: &'static str = op_label(req.uri().path());
        let start = std::time::Instant::now();
        let fut = self.inner.call(req);

        Box::pin(async move {
            let result = fut.await;
            let secs = start.elapsed().as_secs_f64();

            // gRPC reports application errors in the `grpc-status`
            // header (or trailer) rather than the HTTP status, so a
            // failed call still arrives here as HTTP 200. Treat a
            // present, non-zero `grpc-status` as an error; absent
            // means success so far (for streaming calls the final
            // status rides in the trailers, which this layer does not
            // wait for — see the module note on streaming).
            let status = match &result {
                Ok(response) => {
                    let grpc_status = response
                        .headers()
                        .get("grpc-status")
                        .and_then(|v| v.to_str().ok());
                    match grpc_status {
                        Some("0") | None => "ok",
                        Some(_) => "error",
                    }
                }
                Err(_) => "transport_error",
            };

            record_request(op, status);
            record_request_duration(op, status, secs);
            result
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn op_label_extracts_known_methods() {
        assert_eq!(op_label("/eaasp.runtime.v2.RuntimeService/Send"), "Send");
        assert_eq!(
            op_label("/eaasp.runtime.v2.RuntimeService/GetCapabilities"),
            "GetCapabilities"
        );
        assert_eq!(
            op_label("/eaasp.runtime.v2.HookService/EvaluateHook"),
            "EvaluateHook"
        );
    }

    #[test]
    fn op_label_collapses_unknown_paths() {
        // Cardinality bound: an arbitrary path must never become its
        // own metric label, or any peer able to reach the port could
        // grow the meter without limit.
        assert_eq!(op_label("/x/aaa"), UNKNOWN_OP);
        assert_eq!(op_label("/eaasp.runtime.v2.RuntimeService/"), UNKNOWN_OP);
        assert_eq!(op_label("/"), UNKNOWN_OP);
        assert_eq!(op_label(""), UNKNOWN_OP);
        assert_eq!(op_label("/../../etc/passwd"), UNKNOWN_OP);
        assert_eq!(op_label(&format!("/svc/{}", "A".repeat(4096))), UNKNOWN_OP);
    }

    #[test]
    fn op_label_is_case_sensitive_exact_match() {
        // "send" is not "Send" — a near-miss must not slip through as
        // a distinct label.
        assert_eq!(op_label("/svc/send"), UNKNOWN_OP);
        assert_eq!(op_label("/svc/Send "), UNKNOWN_OP);
    }

    #[test]
    fn label_set_is_bounded() {
        // The whole point: labels come from a closed set.
        let paths = [
            "/svc/Send",
            "/svc/attacker-1",
            "/svc/attacker-2",
            "/svc/attacker-3",
        ];
        let labels: std::collections::HashSet<&str> =
            paths.iter().map(|p| op_label(p)).collect();
        assert_eq!(labels.len(), 2, "expected only Send + unknown");
    }

    #[test]
    fn known_methods_cover_the_proto_surface() {
        // 17 runtime.proto + 4 hook.proto = 21 RPCs.
        assert_eq!(KNOWN_METHODS.len(), 21);
    }
}
