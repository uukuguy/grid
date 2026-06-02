"""HNSW tombstone-rebuild trigger tests (D91 / L2-03 / Phase 7.2 Plan 02 T02).

Coverage:
  1. Under-threshold (<30% tombstones): no rebuild on the next add.
  2. At-threshold (>=30% tombstones): the next add triggers a rebuild
     and `_deleted_count` resets to 0.
  3. Recall preservation: pre/post rebuild on a fixed query set, the
     top_k=10 result lists match within +/-0.05 score delta.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from eaasp_l2_memory_engine.vector_index import (
    HNSWVectorIndex,
    TOMBSTONE_REBUILD_THRESHOLD,
)


DIM = 8  # small dim for fast tests
TEST_MAX_ELEMENTS = 200


def _unit_vec(i: int) -> list[float]:
    """Deterministic unit-length vector seeded by ``i``."""
    raw = [math.sin(i + j * 0.37) for j in range(DIM)]
    norm = math.sqrt(sum(v * v for v in raw))
    return [v / norm for v in raw]


@pytest.fixture
def index(tmp_path: Path) -> HNSWVectorIndex:
    return HNSWVectorIndex(
        model_id="test-tombstone",
        octo_root=tmp_path,
        dim=DIM,
        max_elements=TEST_MAX_ELEMENTS,
    )


@pytest.mark.asyncio
async def test_under_threshold_no_rebuild(index: HNSWVectorIndex) -> None:
    """29% tombstones -> next add MUST NOT rebuild (counter persists)."""
    for i in range(100):
        await index.add(f"id-{i}", _unit_vec(i))

    # Delete 29 (29% of 100, strictly under 30%).
    for i in range(29):
        await index.delete(f"id-{i}")

    assert index._deleted_count == 29
    pre_total = index._index.get_current_count()

    # Trigger an add — should NOT rebuild.
    await index.add("id-new-under", _unit_vec(999))
    assert index._deleted_count == 29, (
        "Counter reset -> rebuild fired below threshold (regression)"
    )
    # Sanity: total grew by 1 (no rebuild compaction).
    assert index._index.get_current_count() == pre_total + 1


@pytest.mark.asyncio
async def test_at_threshold_rebuilds(index: HNSWVectorIndex) -> None:
    """>=30% tombstones -> next add triggers rebuild, counter resets."""
    for i in range(100):
        await index.add(f"id-{i}", _unit_vec(i))

    # Delete 30 (exactly at threshold).
    for i in range(30):
        await index.delete(f"id-{i}")

    assert index._deleted_count == 30
    assert (
        index._deleted_count / index._index.get_current_count()
        >= TOMBSTONE_REBUILD_THRESHOLD
    )

    # Trigger an add — MUST rebuild.
    await index.add("id-new-at", _unit_vec(998))

    assert index._deleted_count == 0, (
        f"Rebuild must reset counter; got {index._deleted_count}"
    )
    # Live count = 70 surviving original (id-30..id-99) + 1 new id-new-at.
    assert index.count() == 71


@pytest.mark.asyncio
async def test_recall_preserved_across_rebuild(
    index: HNSWVectorIndex,
) -> None:
    """Top-k=5 recall pre/post rebuild matches within +/-0.05 per hit."""
    for i in range(100):
        await index.add(f"id-{i}", _unit_vec(i))

    # Fixed query set: 5 distinct query vectors.
    queries = [_unit_vec(i + 1000) for i in range(5)]

    # Pre-rebuild hits.
    pre_hits = [await index.search(q, top_k=5) for q in queries]

    # Drive tombstones to threshold + 1 to force rebuild on next add.
    for i in range(30):
        await index.delete(f"id-{i}")
    await index.add("rebuild-trigger", _unit_vec(997))
    assert index._deleted_count == 0  # confirm rebuild fired

    # Post-rebuild hits.
    post_hits = [await index.search(q, top_k=5) for q in queries]

    # Compare per-query: ids that survived AND were in pre's top-5 should
    # still appear in post's top-5; recall delta on overlapping ids
    # should be within +/-0.05 cosine.
    total_surviving = 0
    total_present_post = 0
    for pre, post in zip(pre_hits, post_hits, strict=True):
        surviving_pre_ids = {
            h.id for h in pre if not h.id.startswith("id-")
            or int(h.id.split("-")[1]) >= 30
        }
        post_ids = {h.id for h in post}
        total_surviving += len(surviving_pre_ids)
        total_present_post += len(surviving_pre_ids & post_ids)
        for h_pre in pre:
            if h_pre.id in post_ids and h_pre.id in surviving_pre_ids:
                h_post = next(p for p in post if p.id == h_pre.id)
                assert abs(h_post.score - h_pre.score) <= 0.05, (
                    f"Score drift {h_pre.score} -> {h_post.score} for "
                    f"{h_pre.id} (delta {abs(h_post.score - h_pre.score)})"
                )
    # Recall: at least 80% of surviving pre-hits should still appear post
    # (HNSW is approximate so 100% isn't guaranteed; 0.8 is a comfortable
    # floor for a 70-vector live set + DIM=8).
    assert total_surviving > 0
    recall = total_present_post / total_surviving
    assert recall >= 0.80, (
        f"Recall regression: {recall:.2%} survivors retained "
        f"(pre top-5 ^ post top-5 = {total_present_post}/{total_surviving})"
    )
    # Surface recall for LEDGER capture.
    print(
        f"\n[D91 tombstone rebuild] recall = {recall:.2%} "
        f"({total_present_post}/{total_surviving} survivors retained)"
    )
