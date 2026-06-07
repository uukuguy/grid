use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use tokio_rusqlite::Connection;

use crate::models::{SkillContent, SkillMeta, SkillStatus, SkillVersion, SubmitDraftRequest};

/// SQLite + filesystem store for skill assets.
pub struct SkillStore {
    db: Connection,
    base_dir: PathBuf,
}

impl SkillStore {
    /// Open (or create) the skill store at `base_dir`.
    /// Creates `registry.db` and `skills/` directory.
    pub async fn open(base_dir: &Path) -> Result<Self> {
        std::fs::create_dir_all(base_dir.join("skills")).context("create skills directory")?;

        let db_path = base_dir.join("registry.db");
        let db = Connection::open(db_path)
            .await
            .context("open SQLite database")?;

        db.call(|conn| {
            conn.execute_batch(
                "CREATE TABLE IF NOT EXISTS skills (
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
                    access_scope  TEXT,
                    PRIMARY KEY (id, version)
                );
                CREATE INDEX IF NOT EXISTS idx_skills_access_scope
                    ON skills(access_scope);",
            )?;
            Ok(())
        })
        .await
        .context("create skills table")?;

        let store = Self {
            db,
            base_dir: base_dir.to_path_buf(),
        };
        store.migrate_add_access_scope().await?;
        store.backfill_access_scope_from_frontmatter().await?;
        Ok(store)
    }

    /// D11 / L2-06 (Phase 7.2 Plan 03 T01) — idempotent migration that
    /// adds the `access_scope` column to pre-existing `skills` tables.
    ///
    /// SQLite's `PRAGMA table_info` is the standard idempotency probe.
    /// If `access_scope` is already a column (either from the fresh
    /// schema in `open()` or from a prior migration run), this is a
    /// no-op. We also (re-)create the `idx_skills_access_scope` index
    /// — `CREATE INDEX IF NOT EXISTS` makes this idempotent.
    async fn migrate_add_access_scope(&self) -> Result<()> {
        self.db
            .call(|conn| {
                let mut stmt = conn.prepare("PRAGMA table_info(skills)")?;
                let cols: Vec<String> = stmt
                    .query_map([], |row| row.get::<_, String>(1))?
                    .filter_map(|r| r.ok())
                    .collect();
                if !cols.iter().any(|c| c == "access_scope") {
                    conn.execute(
                        "ALTER TABLE skills ADD COLUMN access_scope TEXT",
                        [],
                    )?;
                }
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_skills_access_scope \
                     ON skills(access_scope)",
                    [],
                )?;
                Ok(())
            })
            .await
            .context("migrate access_scope column")?;
        Ok(())
    }

    /// D11 / L2-06 (Phase 7.2 Plan 03 T01) — one-pass backfill of the
    /// `access_scope` column for rows that already existed before the
    /// migration. For each row whose access_scope IS NULL, we read the
    /// on-disk SKILL.md, parse v2 frontmatter, and UPDATE the row in
    /// place. Rows without v2 frontmatter (legacy v1, or unparseable)
    /// stay NULL — which scope-filter queries treat as "no scope".
    ///
    /// Idempotent: rows already with a non-NULL value are skipped.
    async fn backfill_access_scope_from_frontmatter(&self) -> Result<()> {
        // List candidates first (cheap; metadata only). For each, read
        // SKILL.md from the filesystem and update.
        let candidates: Vec<(String, String)> = self
            .db
            .call(|conn| {
                let mut stmt = conn.prepare(
                    "SELECT id, version FROM skills WHERE access_scope IS NULL",
                )?;
                let rows = stmt
                    .query_map([], |row| {
                        Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
                    })?
                    .filter_map(|r| r.ok())
                    .collect();
                Ok(rows)
            })
            .await
            .context("list candidates for backfill")?;

        for (id, version) in candidates {
            let skill_path = self
                .base_dir
                .join("skills")
                .join(&id)
                .join(&version)
                .join("SKILL.md");
            if !skill_path.exists() {
                continue;
            }
            let Ok(content) = std::fs::read_to_string(&skill_path) else {
                continue;
            };
            let (frontmatter_yaml, _prose) = parse_skill_md(&content);
            let Ok(parsed_v2) =
                crate::skill_parser::parse_v2_frontmatter(&frontmatter_yaml)
            else {
                continue;
            };
            let Some(scope_value) = parsed_v2.access_scope else {
                continue;
            };
            let id_clone = id.clone();
            let version_clone = version.clone();
            let scope_clone = scope_value.clone();
            self.db
                .call(move |conn| {
                    conn.execute(
                        "UPDATE skills SET access_scope = ?1 \
                         WHERE id = ?2 AND version = ?3",
                        rusqlite::params![scope_clone, id_clone, version_clone],
                    )?;
                    Ok(())
                })
                .await
                .context("backfill access_scope")?;
        }
        Ok(())
    }

    /// Submit a new skill draft. Writes SKILL.md to the filesystem and
    /// inserts/replaces metadata into SQLite.
    pub async fn submit_draft(&self, req: SubmitDraftRequest) -> Result<SkillMeta> {
        let skill_dir = self
            .base_dir
            .join("skills")
            .join(&req.id)
            .join(&req.version);
        std::fs::create_dir_all(&skill_dir).context("create skill version directory")?;

        // Build SKILL.md content with frontmatter.
        // Ensure frontmatter_yaml ends with newline so the closing --- is on its own line.
        let yaml = if req.frontmatter_yaml.ends_with('\n') {
            req.frontmatter_yaml.clone()
        } else {
            format!("{}\n", req.frontmatter_yaml)
        };
        let skill_md = format!("---\n{yaml}---\n\n{}", req.prose);
        std::fs::write(skill_dir.join("SKILL.md"), &skill_md).context("write SKILL.md")?;

        // Copy subdirectories (hooks/, scripts/, etc.) from source_dir if provided.
        if let Some(ref src) = req.source_dir {
            let src_path = std::path::Path::new(src);
            if src_path.is_dir() {
                for entry in std::fs::read_dir(src_path).into_iter().flatten() {
                    if let Ok(entry) = entry {
                        let path = entry.path();
                        if path.is_dir() {
                            let dir_name = path.file_name().unwrap_or_default();
                            let dest = skill_dir.join(dir_name);
                            copy_dir_recursive(&path, &dest).ok();
                        }
                    }
                }
            }
        }

        let now = chrono::Utc::now().to_rfc3339();
        let tags_json = serde_json::to_string(&req.tags.unwrap_or_default())?;

        let meta = SkillMeta {
            id: req.id.clone(),
            name: req.name.clone(),
            description: req.description.clone(),
            version: req.version.clone(),
            status: SkillStatus::Draft,
            author: req.author.clone(),
            tags: serde_json::from_str(&tags_json)?,
            created_at: now.clone(),
            updated_at: now.clone(),
        };

        let m = meta.clone();
        let tags_json_clone = tags_json.clone();
        // D11 / L2-06 (Phase 7.2 Plan 03 T01) — compute access_scope from
        // the v2 frontmatter (if any) BEFORE the move into the closure.
        let access_scope: Option<String> = crate::skill_parser::parse_v2_frontmatter(&req.frontmatter_yaml)
            .ok()
            .and_then(|v2| v2.access_scope);

        // D46 / L3-03 — namespace conflict guard.
        // Reject if another skill already claims this access_scope.
        // Wildcard scope "*" and None scope skip the check.
        if let Some(ref scope) = access_scope {
            if scope != "*" {
                let scope_clone = scope.clone();
                let id_clone = m.id.clone();
                let conflict: Option<String> = self
                    .db
                    .call(move |conn| {
                        let mut stmt = conn.prepare(
                            "SELECT id FROM skills WHERE access_scope = ?1 AND id != ?2 LIMIT 1",
                        )?;
                        let mut rows = stmt.query_map(
                            rusqlite::params![scope_clone, id_clone],
                            |row| row.get::<_, String>(0),
                        )?;
                        Ok(rows.next().transpose()?)
                    })
                    .await
                    .context("check namespace conflict")?;

                if let Some(existing_id) = conflict {
                    return Err(anyhow::anyhow!(
                        "namespace_conflict: access_scope '{}' is already claimed by skill '{}'. \
                         Each access_scope can be owned by at most one skill",
                        scope,
                        existing_id
                    ));
                }
            }
        }

        self.db
            .call(move |conn| {
                conn.execute(
                    "INSERT OR REPLACE INTO skills
                        (id, version, name, description, status, author, tags, created_at, updated_at, access_scope)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
                    rusqlite::params![
                        m.id,
                        m.version,
                        m.name,
                        m.description,
                        m.status.to_string(),
                        m.author,
                        tags_json_clone,
                        m.created_at,
                        m.updated_at,
                        access_scope,
                    ],
                )?;
                Ok(())
            })
            .await
            .context("insert skill into database")?;

        Ok(meta)
    }

    /// Read a skill by ID and optional version. If version is None, returns the latest.
    pub async fn read_skill(
        &self,
        id: String,
        version: Option<String>,
    ) -> Result<Option<SkillContent>> {
        let id_clone = id.clone();
        let version_clone = version.clone();
        let meta = self
            .db
            .call(move |conn| {
                let (sql, params): (String, Vec<Box<dyn rusqlite::types::ToSql>>) =
                    if let Some(ref v) = version_clone {
                        (
                            "SELECT id, version, name, description, status, author, tags, created_at, updated_at
                             FROM skills WHERE id = ?1 AND version = ?2"
                                .to_string(),
                            vec![Box::new(id_clone.clone()), Box::new(v.clone())],
                        )
                    } else {
                        (
                            "SELECT id, version, name, description, status, author, tags, created_at, updated_at
                             FROM skills WHERE id = ?1 ORDER BY created_at DESC LIMIT 1"
                                .to_string(),
                            vec![Box::new(id_clone.clone())],
                        )
                    };

                let params_refs: Vec<&dyn rusqlite::types::ToSql> =
                    params.iter().map(|p| p.as_ref()).collect();

                let mut stmt = conn.prepare(&sql)?;
                let mut rows = stmt.query(params_refs.as_slice())?;

                if let Some(row) = rows.next()? {
                    Ok(Some(row_to_meta(row)?))
                } else {
                    Ok(None)
                }
            })
            .await
            .context("query skill from database")?;

        let Some(meta) = meta else {
            return Ok(None);
        };

        // Read SKILL.md from filesystem
        let skill_path = self
            .base_dir
            .join("skills")
            .join(&meta.id)
            .join(&meta.version)
            .join("SKILL.md");

        if !skill_path.exists() {
            return Ok(None);
        }

        let content = std::fs::read_to_string(&skill_path).context("read SKILL.md")?;

        let (frontmatter_yaml, prose) = parse_skill_md(&content);
        let parsed_v2 = crate::skill_parser::parse_v2_frontmatter(&frontmatter_yaml).ok();

        // skill_dir = parent directory of SKILL.md (absolute path).
        let skill_dir = skill_path
            .parent()
            .and_then(|p| p.canonicalize().ok())
            .map(|p| p.to_string_lossy().into_owned());

        Ok(Some(SkillContent {
            meta,
            frontmatter_yaml,
            prose,
            parsed_v2,
            skill_dir,
        }))
    }

    /// Search skills by optional tag, text query, status, scope, and limit.
    ///
    /// `scope` filters by the `access_scope` column. Filter is applied as
    /// an SQL WHERE clause BEFORE `LIMIT N`, so the result is always
    /// "<=N rows, all matching scope" (D11 / L2-06 / Phase 7.2 Plan 03).
    /// Rows whose `access_scope` is NULL (e.g. legacy v1 skills that have
    /// no v2 frontmatter) are EXCLUDED from a `Some(...)` scope filter and
    /// INCLUDED when `scope` is `None`.
    pub async fn search(
        &self,
        tag: Option<String>,
        query: Option<String>,
        status: Option<String>,
        scope: Option<String>,
        limit: Option<usize>,
    ) -> Result<Vec<SkillMeta>> {
        let base: Vec<SkillMeta> = self.db
            .call(move |conn| {
                let mut sql = "SELECT id, version, name, description, status, author, tags, created_at, updated_at FROM skills WHERE 1=1".to_string();
                let mut params: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();
                let mut idx = 1;

                if let Some(ref t) = tag {
                    sql.push_str(&format!(" AND tags LIKE ?{idx}"));
                    params.push(Box::new(format!("%\"{t}\"%")));
                    idx += 1;
                }

                if let Some(ref q) = query {
                    sql.push_str(&format!(
                        " AND (name LIKE ?{idx} OR description LIKE ?{})",
                        idx + 1
                    ));
                    let pattern = format!("%{q}%");
                    params.push(Box::new(pattern.clone()));
                    params.push(Box::new(pattern));
                    idx += 2;
                }

                if let Some(ref s) = status {
                    sql.push_str(&format!(" AND status = ?{idx}"));
                    params.push(Box::new(s.clone()));
                    idx += 1;
                }

                // D11 / L2-06 (Phase 7.2 Plan 03 T02) — scope filter is
                // now an SQL WHERE clause backed by the `access_scope`
                // column added in T01. Filter is applied BEFORE LIMIT so
                // the result is "<=N rows, all matching scope".
                if let Some(ref s) = scope {
                    sql.push_str(&format!(" AND access_scope = ?{idx}"));
                    params.push(Box::new(s.clone()));
                    #[allow(unused_assignments)]
                    {
                        idx += 1;
                    }
                }

                let lim = limit.unwrap_or(100);
                sql.push_str(&format!(" ORDER BY updated_at DESC LIMIT {lim}"));

                let params_refs: Vec<&dyn rusqlite::types::ToSql> =
                    params.iter().map(|p| p.as_ref()).collect();

                let mut stmt = conn.prepare(&sql)?;
                let mut rows = stmt.query(params_refs.as_slice())?;

                let mut results = Vec::new();
                while let Some(row) = rows.next()? {
                    results.push(row_to_meta(row)?);
                }
                Ok(results)
            })
            .await
            .context("search skills")?;

        // D11 / L2-06 (Phase 7.2 Plan 03 T02) — scope filter is now an
        // SQL WHERE clause backed by the `access_scope` column added in
        // T01. `base` is already the filtered + limited result; return
        // as-is.
        Ok(base)
    }

    /// Promote a skill version to a new status.
    pub async fn promote(
        &self,
        id: String,
        version: String,
        target_status: SkillStatus,
    ) -> Result<()> {
        let now = chrono::Utc::now().to_rfc3339();
        let status_str = target_status.to_string();

        self.db
            .call(move |conn| {
                let changed = conn.execute(
                    "UPDATE skills SET status = ?1, updated_at = ?2 WHERE id = ?3 AND version = ?4",
                    rusqlite::params![status_str, now, id, version],
                )?;
                if changed == 0 {
                    return Err(tokio_rusqlite::Error::Rusqlite(
                        rusqlite::Error::QueryReturnedNoRows,
                    ));
                }
                Ok(())
            })
            .await
            .context("promote skill status")
    }

    /// List all versions of a skill.
    pub async fn list_versions(&self, id: String) -> Result<Vec<SkillVersion>> {
        self.db
            .call(move |conn| {
                let mut stmt = conn.prepare(
                    "SELECT version, status, created_at, git_commit
                     FROM skills WHERE id = ?1 ORDER BY created_at DESC",
                )?;
                let mut rows = stmt.query(rusqlite::params![id])?;
                let mut versions = Vec::new();
                while let Some(row) = rows.next()? {
                    versions.push(SkillVersion {
                        version: row.get(0)?,
                        status: parse_status(&row.get::<_, String>(1)?),
                        created_at: row.get(2)?,
                        git_commit: row.get(3)?,
                    });
                }
                Ok(versions)
            })
            .await
            .context("list skill versions")
    }
}

/// Parse a `SkillMeta` from a SQLite row.
fn row_to_meta(row: &rusqlite::Row<'_>) -> rusqlite::Result<SkillMeta> {
    let tags_str: String = row.get(6)?;
    let tags: Vec<String> = serde_json::from_str(&tags_str).unwrap_or_default();

    Ok(SkillMeta {
        id: row.get(0)?,
        version: row.get(1)?,
        name: row.get(2)?,
        description: row.get(3)?,
        status: parse_status(&row.get::<_, String>(4)?),
        author: row.get(5)?,
        tags,
        created_at: row.get(7)?,
        updated_at: row.get(8)?,
    })
}

/// Parse status string to enum.
fn parse_status(s: &str) -> SkillStatus {
    match s {
        "draft" => SkillStatus::Draft,
        "tested" => SkillStatus::Tested,
        "reviewed" => SkillStatus::Reviewed,
        "production" => SkillStatus::Production,
        _ => SkillStatus::Draft,
    }
}

/// Recursively copy a directory tree.
fn copy_dir_recursive(src: &std::path::Path, dst: &std::path::Path) -> std::io::Result<()> {
    std::fs::create_dir_all(dst)?;
    for entry in std::fs::read_dir(src)? {
        let entry = entry?;
        let dest_path = dst.join(entry.file_name());
        if entry.file_type()?.is_dir() {
            copy_dir_recursive(&entry.path(), &dest_path)?;
        } else {
            std::fs::copy(entry.path(), dest_path)?;
        }
    }
    Ok(())
}

/// Parse a SKILL.md file into (frontmatter_yaml, prose).
/// If content starts with `---\n`, splits at the closing `\n---\n`.
pub fn parse_skill_md(content: &str) -> (String, String) {
    if content.starts_with("---\n") {
        let rest = &content[4..]; // skip opening "---\n"
        if let Some(end_idx) = rest.find("\n---\n") {
            let frontmatter = rest[..end_idx + 1].to_string(); // include trailing newline
            let prose = rest[end_idx + 5..].trim_start().to_string(); // skip "\n---\n"
            return (frontmatter, prose);
        }
    }
    // No frontmatter detected
    (String::new(), content.to_string())
}
