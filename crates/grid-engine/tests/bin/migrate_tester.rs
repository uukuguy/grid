//! Test-only binary spawned by `crates/grid-server/tests/migrate_race.rs`.
//!
//! Each invocation opens the SQLite file at argv[1] and calls
//! `grid_engine::db::migrate()`. Multiple processes running this binary
//! concurrently against the same db file exercise the BEGIN EXCLUSIVE +
//! double-check fix landed in Task 5.4-02-01 (NEW-A2 / T-02 mitigation,
//! Phase 5.4 Plan 02 D-11).
//!
//! Prints `user_version=<N>` to stdout on success; non-zero exit indicates
//! the regression has resurfaced.

fn main() {
    let db_path = std::env::args()
        .nth(1)
        .expect("usage: migrate-tester <db_path>");
    let conn = rusqlite::Connection::open(&db_path).expect("open db");
    grid_engine::db::migrate(&conn).expect("migrate failed");
    let version: u32 = conn
        .pragma_query_value(None, "user_version", |row| row.get(0))
        .expect("read user_version");
    println!("user_version={}", version);
}
