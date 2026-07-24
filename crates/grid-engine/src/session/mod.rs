pub mod events;
pub mod memory;
pub mod sqlite;
pub mod thread_store;
pub mod transcript;

use async_trait::async_trait;
use grid_types::{ChatMessage, SandboxId, SessionId, TenantId, UserId};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone)]
pub struct SessionData {
    pub session_id: SessionId,
    pub user_id: UserId,
    pub sandbox_id: SandboxId,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SessionSummary {
    pub session_id: String,
    pub created_at: i64,
    pub message_count: usize,
}

/// Result of a tenant-scoped session lookup.
#[derive(Debug, Clone)]
pub enum TenantSessionResult {
    /// Session exists and belongs to the calling tenant + user.
    Ok(SessionData),
    /// Session exists but belongs to a different tenant (or different
    /// user) — a tenant_mismatch response is appropriate at the HTTP layer.
    TenantMismatch,
    /// No session with this id.
    NotFound,
}

#[async_trait]
pub trait SessionStore: Send + Sync {
    async fn create_session(&self) -> SessionData;
    async fn create_session_with_user(&self, user_id: &UserId) -> SessionData;
    async fn get_session(&self, session_id: &SessionId) -> Option<SessionData>;
    async fn get_session_for_user(
        &self,
        session_id: &SessionId,
        user_id: &UserId,
    ) -> Option<SessionData>;
    async fn get_messages(&self, session_id: &SessionId) -> Option<Vec<ChatMessage>>;
    async fn push_message(&self, session_id: &SessionId, message: ChatMessage);
    async fn set_messages(&self, session_id: &SessionId, messages: Vec<ChatMessage>);
    async fn list_sessions(&self, limit: usize, offset: usize) -> Vec<SessionSummary>;
    async fn list_sessions_for_user(
        &self,
        user_id: &UserId,
        limit: usize,
        offset: usize,
    ) -> Vec<SessionSummary>;

    /// Delete a session and all its messages
    async fn delete_session(&self, session_id: &SessionId) -> bool;

    /// Get the most recent session (for --continue functionality)
    async fn most_recent_session(&self) -> Option<SessionData>;

    /// Get the most recent session for a specific user
    async fn most_recent_session_for_user(&self, user_id: &UserId) -> Option<SessionData>;

    /// Count total sessions ever created (all users).
    /// Default implementation falls back to list_sessions with a large limit.
    async fn count_all_sessions(&self) -> usize {
        self.list_sessions(usize::MAX, 0).await.len()
    }

    // ── v3.8.2 multi-user: tenant scoping ──────────────────────────────
    //
    // Default implementations compose on top of `get_session_for_user` /
    // `list_sessions_for_user`, treating user_id as the sole ownership
    // signal. Implementations that store an explicit `tenant_id` per
    // session SHOULD override these to enforce the tenant boundary.

    /// Look up a session by id AND assert that it belongs to the given
    /// `(tenant_id, user_id)` pair. v3.8.2 `SESSION-01` + `TENANT-03`.
    ///
    /// The default impl treats user_id as the sole ownership signal —
    /// sufficient for the current in-memory + sqlite stores which record
    /// only `user_id`. Production deployments with real tenant scoping
    /// should override.
    async fn get_session_for_tenant(
        &self,
        session_id: &SessionId,
        tenant_id: &TenantId,
        user_id: &UserId,
    ) -> TenantSessionResult {
        match self.get_session_for_user(session_id, user_id).await {
            Some(s) => TenantSessionResult::Ok(s),
            None => {
                // Check whether the session exists at all (under any tenant).
                // If it does → tenant_mismatch; otherwise NotFound.
                if self.get_session(session_id).await.is_some() {
                    TenantSessionResult::TenantMismatch
                } else {
                    TenantSessionResult::NotFound
                }
            }
        }
    }

    /// List sessions visible to a `(tenant_id, user_id)`. v3.8.2
    /// `SESSION-02`: direct ID enumeration MUST NOT surface another
    /// tenant's sessions.
    ///
    /// Default impl: filter `list_sessions` by user_id. With the current
    /// stores that record only `user_id`, this is identical to
    /// `list_sessions_for_user`. True multi-tenant storage will need to
    /// override.
    async fn list_sessions_for_tenant(
        &self,
        tenant_id: &TenantId,
        user_id: &UserId,
        limit: usize,
        offset: usize,
    ) -> Vec<SessionSummary> {
        // Use _tenant_id to satisfy dead-code lints; the binding is read
        // by overrides only.
        let _ = tenant_id;
        self.list_sessions_for_user(user_id, limit, offset).await
    }
}

/// A conversation thread within a session.
/// Threads allow branching conversations (forking) from any turn.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Thread {
    pub thread_id: String,
    pub session_id: SessionId,
    pub title: Option<String>,
    pub created_at: i64,
    pub parent_thread_id: Option<String>,
}

/// A single conversation turn (user message + assistant response).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Turn {
    pub turn_id: String,
    pub thread_id: String,
    pub user_message: ChatMessage,
    pub assistant_messages: Vec<ChatMessage>,
    pub created_at: i64,
}

/// Storage trait for thread and turn operations.
/// Separate from SessionStore for backward compatibility.
#[async_trait]
pub trait ThreadStore: Send + Sync {
    // Thread operations
    async fn create_thread(
        &self,
        session_id: &SessionId,
        title: Option<&str>,
    ) -> anyhow::Result<Thread>;
    async fn list_threads(&self, session_id: &SessionId) -> anyhow::Result<Vec<Thread>>;
    async fn get_default_thread(&self, session_id: &SessionId) -> anyhow::Result<Thread>;
    async fn fork_thread(
        &self,
        thread_id: &str,
        from_turn_id: &str,
    ) -> anyhow::Result<Thread>;

    // Turn operations
    async fn push_turn(&self, thread_id: &str, turn: Turn) -> anyhow::Result<()>;
    async fn list_turns(
        &self,
        thread_id: &str,
        limit: usize,
        offset: usize,
    ) -> anyhow::Result<Vec<Turn>>;
    async fn undo_last_turn(&self, thread_id: &str) -> anyhow::Result<Option<Turn>>;
    async fn get_thread_messages(&self, thread_id: &str) -> anyhow::Result<Vec<ChatMessage>>;
}

pub use events::{SessionEvent, SessionEventBus};
pub use memory::InMemorySessionStore;
pub use sqlite::SqliteSessionStore;
pub use thread_store::SqliteThreadStore;
pub use transcript::{TranscriptEntry, TranscriptWriter, make_preview};
