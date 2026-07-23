pub mod connection;
pub mod migrations;

pub use connection::Database;

use rusqlite::Connection;
use tracing::info;

pub const CURRENT_VERSION: u32 = 14;

pub fn get_migrations() -> Vec<migrations::Migration> {
    vec![
        migrations::migration_v1(),
        migrations::migration_v2(),
        migrations::migration_v3(),
        migrations::migration_v4(),
        migrations::migration_v5(),
        migrations::migration_v6(),
        migrations::migration_v7(),
        migrations::migration_v8(),
        migrations::migration_v9(),
        migrations::migration_v10(),
        migrations::migration_v11(),
        migrations::migration_v12(),
        migrations::migration_v13(),
        migrations::migration_v14(),
    ]
}

/// Atomically apply pending schema migrations to a SQLite database.
///
/// Multi-process safety (Phase 5.4 NEW-A2, T-02 mitigation per ADR-V2-028):
///
/// 1. `BEGIN EXCLUSIVE` immediately acquires SQLite's writer lock at the
///    file-system level. Concurrent processes calling `migrate()` against the
///    same db file serialize through this lock — only one runs migrations at
///    a time; others wait, then enter the txn after the winner commits.
/// 2. A "double-check" of `user_version` INSIDE the txn lets the losers see
///    that migrations already ran and exit clean (idempotent). Without this,
///    losers would re-run `ALTER TABLE ADD COLUMN` and panic with
///    "duplicate column" (the NEW-A1 forensics 2026-05-16 race trace).
/// 3. `COMMIT` releases the writer lock; subsequent calls see the new
///    `user_version` and skip the migration loop entirely.
pub fn migrate(conn: &Connection) -> rusqlite::Result<()> {
    // Phase 5.4 NEW-A2 fix: BEGIN EXCLUSIVE acquires SQLite writer lock immediately.
    // This serializes multi-process migrate() calls against the same db file.
    conn.execute_batch("BEGIN EXCLUSIVE")?;

    // double-check user_version inside the transaction — if a prior winner
    // already migrated, exit clean (idempotent). T-02 mitigation per ADR-V2-028.
    let version: u32 = conn.pragma_query_value(None, "user_version", |row| row.get(0))?;
    if version >= CURRENT_VERSION {
        conn.execute_batch("COMMIT")?;
        return Ok(());
    }

    info!(
        from = version,
        to = CURRENT_VERSION,
        "Running database migration (exclusive)"
    );

    let migrations = get_migrations();
    for migration in migrations {
        if migration.version > version {
            migration.execute(conn)?;
            info!("Applied migration v{}", migration.version);
        }
    }

    conn.pragma_update(None, "user_version", CURRENT_VERSION)?;
    conn.execute_batch("COMMIT")?;
    info!("Migration to v{CURRENT_VERSION} complete");

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use rusqlite::Connection;

    #[test]
    fn test_fresh_db_reaches_current_version() {
        let conn = Connection::open_in_memory().expect("open in-memory db");
        migrate(&conn).expect("migrate fresh db");
        let version: u32 = conn
            .pragma_query_value(None, "user_version", |row| row.get(0))
            .expect("read user_version");
        assert_eq!(version, CURRENT_VERSION);
    }

    #[test]
    fn test_idempotent() {
        // Calling migrate() twice on the same connection must be a no-op the second
        // time (double-check exits early without re-applying migrations).
        let conn = Connection::open_in_memory().expect("open in-memory db");
        migrate(&conn).expect("first migrate");
        // Second call goes through BEGIN EXCLUSIVE + double-check exit path.
        migrate(&conn).expect("second migrate (idempotent)");
        let version: u32 = conn
            .pragma_query_value(None, "user_version", |row| row.get(0))
            .expect("read user_version");
        assert_eq!(version, CURRENT_VERSION);
    }

    #[test]
    fn test_partial_version_applies_remaining() {
        // Manually pin user_version to 5; migrate() should apply v6..v13 only.
        // Use a file-backed temp DB so we can fully control PRAGMA state.
        let tmp = tempfile::tempdir().expect("tempdir");
        let path = tmp.path().join("partial.db");
        let conn = Connection::open(&path).expect("open file db");

        // Apply migrations up to and including v5 manually
        let migrations = get_migrations();
        for migration in &migrations {
            if migration.version <= 5 {
                migration.execute(&conn).expect("apply v1..v5");
            }
        }
        conn.pragma_update(None, "user_version", 5_u32)
            .expect("set version=5");

        // Now run the full migrate — should pick up only v6..v13
        migrate(&conn).expect("migrate from v5");

        let version: u32 = conn
            .pragma_query_value(None, "user_version", |row| row.get(0))
            .expect("read final user_version");
        assert_eq!(version, CURRENT_VERSION);
    }
}
