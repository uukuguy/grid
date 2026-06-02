# AUDIT-T01: L2 connection-pool consumption audit

**Phase:** 07.2 Plan 01 Task T01
**Date:** 2026-06-02
**Purpose:** Verify D12 + D94 connection-pool work (Phase 2.5 S2.T1/T6) is correctly consumed by all hot-path callers. No source change in T01; this matrix is the close-out evidence for L115 (D12) + L224 (D94).

## Step 1 — `aiosqlite.connect(` call-site enumeration

```
$ rg -n "aiosqlite\.connect\(" tools/eaasp-l2-memory-engine/src/
tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/db.py:38:                db = await aiosqlite.connect(path)
tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/db.py:159:    async with aiosqlite.connect(path) as db:
tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/db.py:171:    db = await aiosqlite.connect(path)
```

Result: **3 sites, all inside `db.py`** (singleton inner, init_db bootstrap, legacy `connect()`). Matches planning-time expectation; zero residual leaks in store hot paths.

## Step 2 — Store hot-path verdict matrix

| Call site | Hot path? | Uses singleton? | Verdict |
|-----------|-----------|-----------------|---------|
| `db.py:38` — inside `get_shared_connection()` | NO (one-time per-path init) | N/A (this IS the pool) | clean |
| `db.py:159` — inside `init_db()` | NO (one-shot schema bootstrap at startup) | N/A | clean |
| `db.py:171` — inside legacy `connect()` helper | NO (no prod callers — see Step 3) | N/A | document, no action |
| `anchors.py:50` — `AnchorStore.write` | YES | YES (`get_shared_connection`) | clean |
| `anchors.py:91` — `AnchorStore.get` | YES | YES | clean |
| `anchors.py:99` — `AnchorStore.list_by_event` | YES | YES | clean |
| `anchors.py:108` — `AnchorStore.list_by_session` | YES | YES | clean |
| `files.py:112` — `MemoryFileStore.write` | YES | YES + `get_write_lock` (BEGIN IMMEDIATE) | clean |
| `files.py:215` — `MemoryFileStore.read_latest` | YES | YES | clean |
| `files.py:279` — `MemoryFileStore.list` | YES | YES | clean |
| `index.py:295` — `HybridIndex.search` FTS5 path | YES | YES | clean |
| `index.py:384` — `HybridIndex.search` HNSW union fetch | YES | YES | clean |

Every "Hot path? = YES" row uses the singleton.

## Step 3 — Legacy `connect()` helper callers

```
$ rg -n "from \.db import connect\b|from eaasp_l2_memory_engine\.db import connect\b|db\.connect\(" \
    tools/eaasp-l2-memory-engine/src/ tools/eaasp-l2-memory-engine/tests/
(no output)
```

Result: **zero callers** of the legacy `connect()` at `db.py:169-173`. Marked "document, no action" — kept for backward compat at module level; safe to delete in a future cleanup phase (not this phase, per Plan 01 deferred-bucket).

## Step 4 — Sanity counters

```
$ rg -c "aiosqlite\.connect\(" tools/eaasp-l2-memory-engine/src/
  → 3 (db.py only)

$ rg -c "from \.db import get_shared_connection" tools/eaasp-l2-memory-engine/src/
  → anchors.py: 1
    files.py: 1
    index.py: 1
  (3 total, ≥3 required by acceptance gate)
```

## Conclusion

D12 + D94 substantively shipped in Phase 2.5 S2.T1/T6 and remains correctly consumed. No residual `aiosqlite.connect(path)` leak in any AnchorStore / MemoryFileStore / HybridIndex hot path. Plan 01 T02 will add the explicit high-concurrency throughput test; T01 is verify-only.

---

(D98 cache verdict will be appended by T03.)
