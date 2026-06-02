"""D13 / L2-07: archived memories must not surface in HybridIndex.search.

Phase 7.2 Plan 03 T03 — Option A: MemoryFileStore.archive() deletes all
memory_fts rows for the archived memory_id, plus HybridIndex.search SQL
gains a defense-in-depth `mf.status != 'archived'` filter on both the
FTS path and the HNSW union fetch.

This test exercises both:
  1. Search for archived content returns no hits (FTS deletion held)
  2. Search after process restart returns no hits (persistence held —
     archived memory_fts rows stay gone across HybridIndex re-instantiation)
"""

from __future__ import annotations

import pytest

from eaasp_l2_memory_engine.files import MemoryFileIn, MemoryFileStore
from eaasp_l2_memory_engine.index import HybridIndex


pytestmark = pytest.mark.asyncio


async def test_archived_memory_excluded_from_search(
    file_store: MemoryFileStore, index: HybridIndex, db_path: str
) -> None:
    """Archive a confirmed memory; assert search no longer surfaces it."""
    # Write + confirm so the memory is FTS-searchable.
    suggested = await file_store.write(
        MemoryFileIn(
            scope="user:alice/skill:hr",
            category="policy",
            content="vacation_policy_archive_marker_xyz",
        )
    )
    await file_store.confirm(suggested.memory_id)

    # Sanity: pre-archive search returns the memory.
    pre_hits = await index.search(query="vacation_policy_archive_marker_xyz", top_k=5)
    assert any(h.memory.memory_id == suggested.memory_id for h in pre_hits), (
        "pre-archive sanity: confirmed memory should be FTS-searchable; "
        f"got hits: {[h.memory.memory_id for h in pre_hits]}"
    )

    # Archive — transitions through write() (new version with status=archived)
    # then DELETEs all memory_fts rows for the memory_id.
    archived = await file_store.archive(suggested.memory_id)
    assert archived.status == "archived"

    # Post-archive: search must NOT surface the archived memory.
    post_hits = await index.search(query="vacation_policy_archive_marker_xyz", top_k=5)
    assert not any(h.memory.memory_id == suggested.memory_id for h in post_hits), (
        "post-archive: archived memory leaked into FTS search results; "
        f"got hits: {[h.memory.memory_id for h in post_hits]}"
    )


async def test_archived_memory_excluded_after_restart(
    file_store: MemoryFileStore, db_path: str
) -> None:
    """FTS deletion + status filter survive a fresh HybridIndex instance."""
    suggested = await file_store.write(
        MemoryFileIn(
            scope="user:bob/skill:finance",
            category="threshold",
            content="budget_cap_archive_marker_abc",
        )
    )
    await file_store.confirm(suggested.memory_id)
    await file_store.archive(suggested.memory_id)

    # Fresh HybridIndex instance — simulates process restart.
    fresh_index = HybridIndex(db_path)
    hits = await fresh_index.search(query="budget_cap_archive_marker_abc", top_k=5)
    assert not any(h.memory.memory_id == suggested.memory_id for h in hits), (
        "post-restart: archived memory leaked into FTS search results; "
        f"got hits: {[h.memory.memory_id for h in hits]}"
    )


async def test_non_archived_memories_still_searchable_after_archive_neighbor(
    file_store: MemoryFileStore, index: HybridIndex
) -> None:
    """Archiving memory A must NOT affect search hits for unrelated memory B."""
    a = await file_store.write(
        MemoryFileIn(
            scope="user:alice/skill:hr",
            category="policy",
            content="archive_target_phase72_marker",
        )
    )
    b = await file_store.write(
        MemoryFileIn(
            scope="user:alice/skill:hr",
            category="policy",
            content="keep_alive_phase72_marker",
        )
    )
    await file_store.confirm(a.memory_id)
    await file_store.confirm(b.memory_id)
    await file_store.archive(a.memory_id)

    # Memory B should still be searchable.
    hits = await index.search(query="keep_alive_phase72_marker", top_k=5)
    assert any(h.memory.memory_id == b.memory_id for h in hits), (
        "neighbor isolation: unarchived memory B should still surface; "
        f"got hits: {[h.memory.memory_id for h in hits]}"
    )
    # Memory A should not.
    assert not any(h.memory.memory_id == a.memory_id for h in hits), (
        f"neighbor isolation: archived A leaked; got hits: {[h.memory.memory_id for h in hits]}"
    )
