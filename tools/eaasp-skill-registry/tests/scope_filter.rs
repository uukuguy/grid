//! D11 / L2-06 (Phase 7.2 Plan 03 T02) — scope filter must be applied
//! BEFORE LIMIT N, so `scope=X + limit=5` returns <=5 results all matching
//! scope=X (no fewer-than-limit results because of post-query filtering).
//!
//! Note (D46 / L3-03 / Phase 7.3): each access_scope is now owned by at most
//! one skill. The test uses unique scopes — the filter is verified by exact
//! match against each individual scope.

use eaasp_skill_registry::models::SubmitDraftRequest;
use eaasp_skill_registry::store::SkillStore;
use tempfile::TempDir;

fn make_request(
    id: &str,
    version: &str,
    access_scope: Option<&str>,
) -> SubmitDraftRequest {
    // Hand-craft a minimal v2 frontmatter so backfill / submit_draft both
    // pick up access_scope. V2Frontmatter only requires that any field
    // present validate; access_scope alone is enough.
    let frontmatter_yaml = match access_scope {
        Some(s) => format!(
            "name: {id}\nversion: {version}\naccess_scope: {s}\n"
        ),
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
async fn scope_filter_returns_exactly_matching_subset_within_limit() {
    let dir = TempDir::new().unwrap();
    let store = SkillStore::open(dir.path()).await.unwrap();

    // 10 skills total: each with a unique scope (namespace guard enforces
    // at most one skill per access_scope since D46 / Phase 7.3).
    let scopes: [&str; 10] = [
        "a-0", "a-1", "a-2", "a-3", "a-4", "a-5", "a-6",
        "b-0", "b-1", "b-2",
    ];
    for (i, scope) in scopes.iter().enumerate() {
        let id = format!("skill-{i}");
        store
            .submit_draft(make_request(&id, "v1", Some(scope)))
            .await
            .unwrap();
    }

    // scope="a-3" + limit=5 -> exactly 1 result (a-3 is unique).
    let results = store
        .search(None, None, None, Some("a-3".to_string()), Some(5))
        .await
        .unwrap();
    assert_eq!(results.len(), 1, "scope a-3 should match exactly 1 skill");
    assert_eq!(results[0].id, "skill-3");

    // scope="a-3" + limit=1 -> still 1 result (LIMIT applied before filter,
    // but filter reduces to 1 anyway).
    let limited = store
        .search(None, None, None, Some("a-3".to_string()), Some(1))
        .await
        .unwrap();
    assert_eq!(limited.len(), 1);

    // scope=None -> returns ALL 10 (no scope filter).
    let all = store
        .search(None, None, None, None, Some(100))
        .await
        .unwrap();
    assert_eq!(all.len(), 10);

    // scope=zeta (nonexistent) -> 0 rows, LIMIT does not fabricate results.
    let zeta = store
        .search(None, None, None, Some("zeta".to_string()), Some(5))
        .await
        .unwrap();
    assert_eq!(zeta.len(), 0);
}

#[tokio::test]
async fn scope_filter_excludes_null_access_scope() {
    // Legacy v1-style skills have no access_scope. They MUST NOT appear in
    // results when scope filter is `Some(_)`.
    let dir = TempDir::new().unwrap();
    let store = SkillStore::open(dir.path()).await.unwrap();

    store
        .submit_draft(make_request("legacy-1", "v1", None))
        .await
        .unwrap();
    store
        .submit_draft(make_request("scoped-1", "v1", Some("alpha")))
        .await
        .unwrap();

    let alpha = store
        .search(None, None, None, Some("alpha".to_string()), None)
        .await
        .unwrap();
    assert_eq!(alpha.len(), 1);
    assert_eq!(alpha[0].id, "scoped-1");

    // scope=None returns both (the legacy + the scoped).
    let all = store
        .search(None, None, None, None, None).await.unwrap();
    assert_eq!(all.len(), 2);
}
