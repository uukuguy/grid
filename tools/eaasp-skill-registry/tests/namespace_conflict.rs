//! D46 / L3-03 (Phase 7.3 Plan 01 T03) — namespace conflict guard tests.
//!
//! The guard in `submit_draft()` rejects submissions where a different skill
//! already owns the requested `access_scope`. Same-skill re-registrations,
//! wildcard scope (`*`), and `None` scope are all allowed.

use eaasp_skill_registry::models::SubmitDraftRequest;
use eaasp_skill_registry::store::SkillStore;
use tempfile::TempDir;

fn make_request(id: &str, version: &str, access_scope: Option<&str>) -> SubmitDraftRequest {
    let frontmatter_yaml = match access_scope {
        Some(s) => format!("name: {id}\nversion: {version}\naccess_scope: {s}\n"),
        None => format!("name: {id}\nversion: {version}\n"),
    };
    SubmitDraftRequest {
        id: id.to_string(),
        version: version.to_string(),
        name: id.to_string(),
        description: format!("test skill {id}"),
        author: Some("test".to_string()),
        tags: None,
        frontmatter_yaml,
        prose: "test body".to_string(),
        source_dir: None,
    }
}

#[tokio::test]
async fn test_register_same_scope_conflicts() {
    let dir = TempDir::new().unwrap();
    let store = SkillStore::open(dir.path()).await.unwrap();

    // Skill A registers scope=X — allowed.
    store
        .submit_draft(make_request("skill_a", "v1", Some("ecommerce")))
        .await
        .unwrap();

    // Skill B tries scope=X — REJECTED (conflict with skill_a).
    let err = store
        .submit_draft(make_request("skill_b", "v1", Some("ecommerce")))
        .await
        .unwrap_err();
    let msg = format!("{err:#}");
    assert!(
        msg.contains("namespace_conflict"),
        "expected namespace_conflict, got: {msg}"
    );
    assert!(
        msg.contains("ecommerce"),
        "error should mention the scope, got: {msg}"
    );
    assert!(
        msg.contains("skill_a"),
        "error should mention the existing skill ID, got: {msg}"
    );
}

#[tokio::test]
async fn test_register_different_scope_allowed() {
    let dir = TempDir::new().unwrap();
    let store = SkillStore::open(dir.path()).await.unwrap();

    store
        .submit_draft(make_request("skill_a", "v1", Some("ecommerce")))
        .await
        .unwrap();
    store
        .submit_draft(make_request("skill_b", "v1", Some("finance")))
        .await
        .unwrap();

    // Both should be searchable by their respective scopes.
    let ecom = store
        .search(None, None, None, Some("ecommerce".to_string()), None)
        .await
        .unwrap();
    assert_eq!(ecom.len(), 1);
    assert_eq!(ecom[0].id, "skill_a");

    let fin = store
        .search(None, None, None, Some("finance".to_string()), None)
        .await
        .unwrap();
    assert_eq!(fin.len(), 1);
    assert_eq!(fin[0].id, "skill_b");
}

#[tokio::test]
async fn test_register_same_id_same_scope_allowed() {
    let dir = TempDir::new().unwrap();
    let store = SkillStore::open(dir.path()).await.unwrap();

    // First registration of skill_a with scope=X.
    store
        .submit_draft(make_request("skill_a", "v1", Some("ecommerce")))
        .await
        .unwrap();

    // Re-registration (same id, same scope) — allowed (update/redeploy).
    store
        .submit_draft(make_request("skill_a", "v2", Some("ecommerce")))
        .await
        .unwrap();

    // Verify both versions exist.
    let versions = store.list_versions("skill_a".to_string()).await.unwrap();
    assert_eq!(versions.len(), 2);
}

#[tokio::test]
async fn test_register_null_scope_allowed() {
    let dir = TempDir::new().unwrap();
    let store = SkillStore::open(dir.path()).await.unwrap();

    // Multiple skills with scope=None — no conflict.
    store
        .submit_draft(make_request("skill_a", "v1", None))
        .await
        .unwrap();
    store
        .submit_draft(make_request("skill_b", "v1", None))
        .await
        .unwrap();

    // Both should be returned when scope=None.
    let all = store.search(None, None, None, None, None).await.unwrap();
    assert_eq!(all.len(), 2);
}

#[tokio::test]
async fn test_register_wildcard_scope_allowed_multiple() {
    let dir = TempDir::new().unwrap();
    let store = SkillStore::open(dir.path()).await.unwrap();

    // Multiple skills with wildcard scope "*" — allowed (wildcard = open).
    store
        .submit_draft(make_request("skill_a", "v1", Some("*")))
        .await
        .unwrap();
    store
        .submit_draft(make_request("skill_b", "v1", Some("*")))
        .await
        .unwrap();

    // Both should be searchable.
    let all = store.search(None, None, None, None, None).await.unwrap();
    assert_eq!(all.len(), 2);
}

#[tokio::test]
async fn test_register_same_scope_as_wildcard() {
    let dir = TempDir::new().unwrap();
    let store = SkillStore::open(dir.path()).await.unwrap();

    // Skill A with scope=* (wildcard) — allowed.
    store
        .submit_draft(make_request("skill_a", "v1", Some("*")))
        .await
        .unwrap();

    // Skill B with scope=* — also allowed (wildcard not exclusive).
    store
        .submit_draft(make_request("skill_b", "v1", Some("*")))
        .await
        .unwrap();

    // Both exist.
    let all = store.search(None, None, None, None, None).await.unwrap();
    assert_eq!(all.len(), 2);
}
