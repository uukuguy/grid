//! Internal test modules for grid-runtime (Phase 5.3 CONTRACT-01).
//!
//! Unit tests for crate-private items (e.g., `service::chunk_type_to_proto`)
//! live here because Rust integration tests at `crates/grid-runtime/tests/`
//! can only see `pub` items.

#[cfg(test)]
mod test_chunk_emit;
