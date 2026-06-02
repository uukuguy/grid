//! D11 / L2-06 (Phase 7.2 Plan 03 T02) — scope filter must be applied
//! BEFORE LIMIT N, so `scope=X + limit=5` returns <=5 results all matching
//! scope=X (no fewer-than-limit results because of post-query filtering).

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

    // 10 skills total: 7 with scope=alpha, 3 with scope=beta.
    for i in 0..7 {
        let id = format!("alpha-{i}");
        store
            .submit_draft(make_request(&id, "v1", Some("alpha")))
            .await
            .unwrap();
    }
    for i in 0..3 {
        let id = format!("beta-{i}");
        store
            .submit_draft(make_request(&id, "v1", Some("beta")))
            .await
            .unwrap();
    }

    // scope=alpha + limit=5 -> <=5 results, all alpha.
    let results = store
        .search(None, None, None, Some("alpha".to_string()), Some(5))
        .await
        .unwrap();
    assert!(
        results.len() <= 5,
        "limit=5 must be honored; got {} rows",
        results.len()
    );
    assert_eq!(results.len(), 5, "expected exactly 5 alpha rows under limit=5");

    // scope=alpha + no limit (uses default LIMIT 100) -> all 7 alpha rows.
    let all_alpha = store
        .search(None, None, None, Some("alpha".to_string()), None)
        .await
        .unwrap();
    assert_eq!(all_alpha.len(), 7);

    // scope=beta -> all 3 beta rows.
    let beta = store
        .search(None, None, None, Some("beta".to_string()), None)
        .await
        .unwrap();
    assert_eq!(beta.len(), 3);

    // scope=None -> returns ALL 10 (alpha + beta).
    let all = store
        .search(None, None, None, None, Some(100))
        .await
        .unwrap();
    assert_eq!(all.len(), 10);

    // scope=zeta (nonexistent) -> 0 rows.
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
