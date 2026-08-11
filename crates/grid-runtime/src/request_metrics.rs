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
//! the trailing method name (`Send`). Unrecognised paths are recorded
//! as `unknown` rather than dropped, so a routing mistake shows up as
//! a metric instead of silence.
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

/// Extract the gRPC method name from a path like
/// `/eaasp.runtime.v2.RuntimeService/Send`.
///
/// Returns `None` for paths that do not look like a gRPC call, so the
/// caller can decide how to label them rather than having a bogus
/// method name invented here.
fn method_name(path: &str) -> Option<&str> {
    let name = path.rsplit('/').next()?;
    if name.is_empty() {
        None
    } else {
        Some(name)
    }
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
        let op = method_name(req.uri().path())
            .unwrap_or("unknown")
            .to_string();
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

            record_request(&op, status);
            record_request_duration(&op, status, secs);
            result
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn method_name_extracts_trailing_segment() {
        assert_eq!(
            method_name("/eaasp.runtime.v2.RuntimeService/Send"),
            Some("Send")
        );
        assert_eq!(
            method_name("/eaasp.runtime.v2.RuntimeService/GetCapabilities"),
            Some("GetCapabilities")
        );
    }

    #[test]
    fn method_name_rejects_trailing_slash_and_root() {
        // Would otherwise be recorded as an empty-string op label.
        assert_eq!(method_name("/eaasp.runtime.v2.RuntimeService/"), None);
        assert_eq!(method_name("/"), None);
    }
}
