//! L2 Memory Engine HTTP client (moved from grid-runtime in Phase 5.4 D-08).
//! See ADR-V2-015 (L2 hybrid retrieval), ADR-V2-024 (双轴 framework).
//!
//! Two consumers share this module:
//! - `grid-runtime` (engine 接入面, gRPC subprocess) — re-exports via
//!   `crates/grid-runtime/src/l2_memory_client.rs` shim
//! - `grid-server` (in-process, per Phase 5.4 D-01) — `AppState::l2_storage()`
pub mod client;
pub use client::{
    L2MemoryClient, WriteAnchorRequest, WriteAnchorResponse, WriteFileRequest, WriteFileResponse,
};
