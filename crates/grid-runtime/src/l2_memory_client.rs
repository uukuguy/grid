//! L2 Memory Engine HTTP client — moved to grid-engine::l2 (Phase 5.4 D-08).
//! This file remains as a re-export shim for in-tree caller compatibility.
//! See PATTERNS.md §B10.

pub use grid_engine::l2::{
    L2MemoryClient, WriteAnchorRequest, WriteAnchorResponse, WriteFileRequest, WriteFileResponse,
};
