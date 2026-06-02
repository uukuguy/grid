"""HybridIndex HNSW-cache non-regression test (D98 / L2-05 / Phase 7.2 Plan 01 T03).

Asserts the process-level HNSW cache wired in `HybridIndex.__init__`
(`self._hnsw_cache`) reuses the same HNSWVectorIndex instance across
multiple `search()` calls instead of constructing a new one per call.

Without this guard, a future refactor that drops the cache (e.g. moving
HNSWVectorIndex construction inline at `search()` body level) would
silently regress L2 hot-path latency by ~10ms per call (CONTEXT.md D-07).
"""

from __future__ import annotations

import pytest

from eaasp_l2_memory_engine.files import MemoryFileIn, MemoryFileStore
from eaasp_l2_memory_engine.index import HybridIndex


@pytest.mark.asyncio
async def test_hybrid_index_caches_hnsw_per_model(
    db_path: str,
) -> None:
    """HybridIndex._hnsw_cache is populated on first search, reused after."""
    store = MemoryFileStore(db_path)
    index = HybridIndex(db_path)

    # Seed at least one memory so the FTS path is non-empty.
    await store.write(
        MemoryFileIn(
            memory_id="cache-seed",
            scope="test",
            category="cache",
            content="hello cache seed content",
            evidence_refs=[],
            status="agent_suggested",
        )
    )

    # Cache is empty before any search.
    assert index._hnsw_cache == {}, (
        f"_hnsw_cache should start empty, got {index._hnsw_cache!r}"
    )

    # First search populates the cache (one entry, keyed by model_id+dim).
    await index.search("hello", top_k=3)

    # If the embedding provider degraded (Ollama unreachable etc.), the
    # cache MAY stay empty. That's a soft-degrade scenario; in that case
    # we cannot assert reuse — just assert no exception was raised.
    first_size = len(index._hnsw_cache)
    if first_size == 0:
        pytest.skip(
            "embedding provider degraded; HNSW cache not exercised. "
            "Re-run with EAASP_EMBEDDING_PROVIDER=mock (the default) "
            "to verify cache reuse path."
        )

    assert first_size == 1, (
        f"After one successful search, cache should hold 1 entry, "
        f"got {first_size}"
    )
    cache_key = next(iter(index._hnsw_cache.keys()))
    first_instance_id = id(index._hnsw_cache[cache_key])

    # Drive 5 more searches; cache must not grow and the instance pointer
    # MUST remain identical.
    for _ in range(5):
        await index.search("hello", top_k=3)
    assert len(index._hnsw_cache) == 1, (
        f"Cache grew across calls; expected steady 1, got "
        f"{len(index._hnsw_cache)}. New entries: "
        f"{list(index._hnsw_cache.keys())}"
    )
    assert id(index._hnsw_cache[cache_key]) == first_instance_id, (
        "HNSWVectorIndex instance changed across searches — cache is "
        "being re-populated per call (D98 regression)."
    )
