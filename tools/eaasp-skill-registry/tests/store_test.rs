use eaasp_skill_registry::models::{SkillStatus, SubmitDraftRequest};
use eaasp_skill_registry::store::SkillStore;

fn make_draft(id: &str, name: &str, version: &str, tags: Vec<&str>) -> SubmitDraftRequest {
    SubmitDraftRequest {
        id: id.to_string(),
        name: name.to_string(),
        description: format!("{name} description"),
        version: version.to_string(),
        author: Some("tester".to_string()),
        tags: Some(tags.into_iter().map(String::from).collect()),
        frontmatter_yaml: format!("name: {name}\nversion: {version}\n"),
        prose: format!("# {name}\n\nThis is the prose for {name}."),
        source_dir: None,
    }
}

#[tokio::test]
async fn store_submit_and_read() {
    let tmp = tempfile::tempdir().unwrap();
    let store = SkillStore::open(tmp.path()).await.unwrap();

    let req = make_draft(
        "hello-skill",
        "Hello Skill",
        "0.1.0",
        vec!["greeting", "demo"],
    );
    let meta = store.submit_draft(req).await.unwrap();

    assert_eq!(meta.id, "hello-skill");
    assert_eq!(meta.name, "Hello Skill");
    assert_eq!(meta.status, SkillStatus::Draft);
    assert_eq!(meta.tags, vec!["greeting", "demo"]);

    // Read back
    let content = store
        .read_skill("hello-skill".to_string(), Some("0.1.0".to_string()))
        .await
        .unwrap()
        .expect("skill should exist");

    assert_eq!(content.meta.id, "hello-skill");
    assert_eq!(content.meta.version, "0.1.0");
    assert!(content.prose.contains("This is the prose for Hello Skill"));
    assert!(content.frontmatter_yaml.contains("name: Hello Skill"));
}

#[tokio::test]
async fn store_search_by_tags() {
    let tmp = tempfile::tempdir().unwrap();
    let store = SkillStore::open(tmp.path()).await.unwrap();

    store
        .submit_draft(make_draft("alpha", "Alpha", "1.0.0", vec!["code", "rust"]))
        .await
        .unwrap();
    store
        .submit_draft(make_draft("beta", "Beta", "1.0.0", vec!["code", "python"]))
        .await
        .unwrap();

    // Search by tag "rust"
    let results = store
        .search(Some("rust".to_string()), None, None, None, None)
        .await
        .unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].id, "alpha");

    // Search by tag "code" should return both
    let results = store
        .search(Some("code".to_string()), None, None, None, None)
        .await
        .unwrap();
    assert_eq!(results.len(), 2);
}

#[tokio::test]
async fn store_promote_lifecycle() {
    let tmp = tempfile::tempdir().unwrap();
    let store = SkillStore::open(tmp.path()).await.unwrap();

    store
        .submit_draft(make_draft("lifecycle", "Lifecycle", "1.0.0", vec!["test"]))
        .await
        .unwrap();

    // Draft -> Tested
    store
        .promote(
            "lifecycle".to_string(),
            "1.0.0".to_string(),
            SkillStatus::Tested,
        )
        .await
        .unwrap();
    let content = store
        .read_skill("lifecycle".to_string(), Some("1.0.0".to_string()))
        .await
        .unwrap()
        .unwrap();
    assert_eq!(content.meta.status, SkillStatus::Tested);

    // Tested -> Reviewed
    store
        .promote(
            "lifecycle".to_string(),
            "1.0.0".to_string(),
            SkillStatus::Reviewed,
        )
        .await
        .unwrap();
    let content = store
        .read_skill("lifecycle".to_string(), Some("1.0.0".to_string()))
        .await
        .unwrap()
        .unwrap();
    assert_eq!(content.meta.status, SkillStatus::Reviewed);

    // Reviewed -> Production
    store
        .promote(
            "lifecycle".to_string(),
            "1.0.0".to_string(),
            SkillStatus::Production,
        )
        .await
        .unwrap();
    let content = store
        .read_skill("lifecycle".to_string(), Some("1.0.0".to_string()))
        .await
        .unwrap()
        .unwrap();
    assert_eq!(content.meta.status, SkillStatus::Production);

    // Verify versions list
    let versions = store.list_versions("lifecycle".to_string()).await.unwrap();
    assert_eq!(versions.len(), 1);
    assert_eq!(versions[0].status, SkillStatus::Production);
}

/// 断点 2: frontmatter_yaml WITHOUT trailing newline must not cause the
/// closing `---` to fuse with the last YAML line, breaking parse.
#[tokio::test]
async fn submit_and_read_preserves_v2_frontmatter_no_trailing_newline() {
    let tmp = tempfile::tempdir().unwrap();
    let store = SkillStore::open(tmp.path()).await.unwrap();

    // frontmatter WITHOUT trailing newline — this was the bug case
    let req = SubmitDraftRequest {
        id: "no-newline-skill".into(),
        name: "NoNewline".into(),
        description: "".into(),
        version: "0.1.0".into(),
        author: None,
        tags: None,
        frontmatter_yaml: "name: NoNewline\nversion: 0.1.0\ndependencies:\n  - mcp:mock-scada"
            .into(),
        prose: "# Test\nProse body".into(),
        source_dir: None,
    };
    store.submit_draft(req).await.unwrap();

    let content = store
        .read_skill("no-newline-skill".into(), Some("0.1.0".into()))
        .await
        .unwrap()
        .expect("should read back");

    // CRITICAL: parsed_v2 must not be None (would fail if --- fused with last line)
    assert!(
        content.parsed_v2.is_some(),
        "parsed_v2 must be present after roundtrip with no trailing newline"
    );
    let v2 = content.parsed_v2.unwrap();
    assert_eq!(v2.dependencies, vec!["mcp:mock-scada"]);

    // frontmatter_yaml must not be empty
    assert!(
        !content.frontmatter_yaml.is_empty(),
        "frontmatter_yaml must not be empty"
    );

    // prose must be clean (no frontmatter leaking)
    assert!(
        content.prose.starts_with("# Test"),
        "prose should start with content, not ---; got: {:?}",
        &content.prose[..content.prose.len().min(40)]
    );
}

/// Verify roundtrip when frontmatter_yaml already HAS trailing newline.
#[tokio::test]
async fn submit_and_read_preserves_v2_frontmatter_with_trailing_newline() {
    let tmp = tempfile::tempdir().unwrap();
    let store = SkillStore::open(tmp.path()).await.unwrap();

    let req = SubmitDraftRequest {
        id: "with-newline-skill".into(),
        name: "WithNewline".into(),
        description: "".into(),
        version: "0.1.0".into(),
        author: None,
        tags: None,
        // HAS trailing newline — the normal case
        frontmatter_yaml: "name: WithNewline\nversion: 0.1.0\nruntime_affinity:\n  preferred: grid-runtime\n  compatible:\n    - grid-runtime\n".into(),
        prose: "# Guide\nSome content".into(),
        source_dir: None,
    };
    store.submit_draft(req).await.unwrap();

    let content = store
        .read_skill("with-newline-skill".into(), Some("0.1.0".into()))
        .await
        .unwrap()
        .expect("should read back");

    assert!(content.parsed_v2.is_some());
    let v2 = content.parsed_v2.unwrap();
    assert_eq!(
        v2.runtime_affinity.preferred.as_deref(),
        Some("grid-runtime")
    );
    assert!(content.prose.starts_with("# Guide"));
}

/// Regression test for the v3.14 EAASP verification run.
///
/// Reproduces the failure observed when `make dev-eaasp` is run against
/// a `data/dev-skill-registry/registry.db` that was created by an older
/// version of the binary (pre-D11 / L2-06 migration). The old schema
/// has no `access_scope` column. The previous code embedded
/// `CREATE INDEX IF NOT EXISTS idx_skills_access_scope ON skills(access_scope)`
/// inside the same `execute_batch` block as the `CREATE TABLE IF NOT
/// EXISTS skills(...)` statement. When the table already existed with
/// the old schema, `CREATE TABLE` was a silent no-op and the
/// `CREATE INDEX` then failed with "no such column: access_scope" —
/// aborting `open()` BEFORE `migrate_add_access_scope()` could run.
///
/// The fix moves the index creation out of the CREATE TABLE block; the
/// `migrate_add_access_scope()` migration creates the index
/// idempotently after `ALTER TABLE ... ADD COLUMN access_scope`.
///
/// This test pre-creates a `registry.db` with the legacy schema (no
/// `access_scope` column), then calls `SkillStore::open()` and asserts
/// (a) it succeeds, (b) the column was added, and (c) the index exists.
#[tokio::test]
async fn store_open_migrates_legacy_schema_without_access_scope_column() {
    use tokio_rusqlite::Connection;

    let tmp = tempfile::tempdir().unwrap();
    let base = tmp.path();

    // Pre-create registry.db with the LEGACY schema (no access_scope).
    let legacy_db_path = base.join("registry.db");
    let conn = Connection::open(&legacy_db_path).await.unwrap();
    conn.call(|c: &mut rusqlite::Connection| {
        c.execute_batch(
            "CREATE TABLE skills (
                id            TEXT NOT NULL,
                version       TEXT NOT NULL,
                name          TEXT NOT NULL,
                description   TEXT NOT NULL DEFAULT '',
                status        TEXT NOT NULL DEFAULT 'draft',
                author        TEXT,
                tags          TEXT NOT NULL DEFAULT '[]',
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL,
                git_commit    TEXT,
                PRIMARY KEY (id, version)
            );",
        )?;
        // Also pre-create the skills/ directory so backfill can run.
        Ok(())
    })
    .await
    .unwrap();
    drop(conn);

    // Now open the store. Pre-fix this would fail with
    // "no such column: access_scope in CREATE INDEX ...".
    let store = SkillStore::open(base).await.expect(
        "open() must succeed against a legacy registry.db; the pre-fix \
         code aborted here with 'no such column: access_scope'",
    );

    // Verify access_scope column was added by the migration.
    let has_column: bool = store
        ._test_with_conn(|c: &mut rusqlite::Connection| {
            let mut stmt = c.prepare("PRAGMA table_info(skills)")?;
            let cols: Vec<String> = stmt
                .query_map([], |row| row.get::<_, String>(1))?
                .filter_map(|r| r.ok())
                .collect();
            Ok(cols.iter().any(|c| c == "access_scope"))
        })
        .await
        .unwrap();
    assert!(has_column, "access_scope column must exist after open()");

    // Verify the index was created (idempotent on re-open).
    let has_index: bool = store
        ._test_with_conn(|c: &mut rusqlite::Connection| {
            let mut stmt = c.prepare(
                "SELECT 1 FROM sqlite_master WHERE type='index' \
                 AND name='idx_skills_access_scope'",
            )?;
            Ok(stmt.exists([])?)
        })
        .await
        .unwrap();
    assert!(has_index, "idx_skills_access_scope index must exist");

    // Re-open the store a second time — the migration must remain
    // idempotent (no errors on a DB that already has the column).
    let _store2 = SkillStore::open(base).await.expect("re-open must succeed");
}
