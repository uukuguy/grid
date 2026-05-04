//! Keyboard event handler for the conversation-centric TUI.
//!
//! This module has been split into mode-specific handlers.
//! See the `key_handlers` subdirectory for the implementation.

pub use key_handlers::{handle_key, handle_key_for_test};

#[cfg(test)]
mod integration_tests {
    use super::key_handlers::tests::*;
}
