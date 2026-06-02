"""High-concurrency throughput test for L2 memory-engine singleton connection.

D12 + D94 evidence test (Phase 7.2 Plan 01 T02). Proves the per-path
shared aiosqlite.Connection + asyncio.Lock infrastructure at
src/eaasp_l2_memory_engine/db.py:15-86 actually delivers concurrent
throughput WITHOUT producing 'database is locked' errors.

Test shape (CONTEXT.md D-01 / specifics):
  - 10 coroutines, each doing 10 operations (5 writes + 5 reads, mixed).
  - Total 100 ops against a single MemoryFileStore + HybridIndex.
  - PASS = wall-clock < 5s AND zero OperationalError('database is locked').

Soft-degrade hits in HNSW (Ollama unreachable etc.) are tolerated; only
the SQLite-level lock-error pattern fails the test.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time

import pytest

from eaasp_l2_memory_engine.files import MemoryFileIn, MemoryFileStore
from eaasp_l2_memory_engine.index import HybridIndex


N_COROUTINES = 10
OPS_PER_COROUTINE = 10  # 5 writes + 5 reads (alternating)
WALLCLOCK_BUDGET_SECONDS = 5.0


@pytest.mark.asyncio
async def test_concurrent_read_write_no_lock_errors(
    db_path: str,
) -> None:
    """10 coroutines x 10 ops, 0 lock errors, < 5s wall clock."""
    store = MemoryFileStore(db_path)
    index = HybridIndex(db_path)
    lock_errors: list[str] = []

    async def worker(worker_id: int) -> None:
        for op in range(OPS_PER_COROUTINE):
            memory_id = f"throughput-{worker_id}-{op}"
            if op % 2 == 0:
                # write
                try:
                    await store.write(
                        MemoryFileIn(
                            memory_id=memory_id,
                            scope="test",
                            category="throughput",
                            content=f"hello from worker {worker_id} op {op}",
                            evidence_refs=[],
                            status="agent_suggested",
                        )
                    )
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        lock_errors.append(
                            f"worker {worker_id} op {op}: {e}"
                        )
                        raise
            else:
                # read — list latest entries in scope
                try:
                    await store.list(scope="test", limit=20)
                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e):
                        lock_errors.append(
                            f"worker {worker_id} op {op}: {e}"
                        )
                        raise

    start = time.perf_counter()
    await asyncio.gather(
        *(worker(w) for w in range(N_COROUTINES)),
    )
    elapsed = time.perf_counter() - start

    assert not lock_errors, (
        f"Expected 0 lock errors, got {len(lock_errors)}: "
        f"{lock_errors[:3]}..."
    )
    assert elapsed < WALLCLOCK_BUDGET_SECONDS, (
        f"Wall-clock budget exceeded: {elapsed:.2f}s "
        f"> {WALLCLOCK_BUDGET_SECONDS}s for "
        f"{N_COROUTINES * OPS_PER_COROUTINE} ops"
    )
    # Sanity: at least 5 writes per worker, all latest-versioned by
    # singleton write-lock; list should reflect all writes.
    final_list = await store.list(scope="test", limit=200)
    assert len(final_list) == N_COROUTINES * (OPS_PER_COROUTINE // 2), (
        f"Expected {N_COROUTINES * (OPS_PER_COROUTINE // 2)} unique "
        f"memory_ids in scope=test, got {len(final_list)}"
    )

    # Defensive: the HybridIndex should also be queryable without lock errors.
    try:
        hits = await index.search("hello", top_k=5)
    except sqlite3.OperationalError as e:
        pytest.fail(f"index.search raised lock error: {e}")
    # No assertion on hits count — embedding provider may be unavailable in
    # CI; we only assert no SQLite-level lock errors propagate.
    _ = hits

    # Surface wall-clock to stdout for LEDGER close-out evidence capture.
    print(
        f"\n[D12+D94 throughput] {N_COROUTINES * OPS_PER_COROUTINE} ops "
        f"in {elapsed * 1000:.0f}ms, 0 lock errors"
    )
