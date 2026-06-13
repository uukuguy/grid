"""Semantic score backfill tests — FTS-only hits get cosine from DB (D95 / L2-18).

Tests that when a memory appears in FTS results but NOT in HNSW (e.g. HNSW
add previously failed, or index was rebuilt), the semantic_score is backfilled
from the ``embedding_vec`` BLOB in the DB instead of being left at 0.0.
"""

from __future__ import annotations

import os
import shutil

import pytest

from eaasp_l2_memory_engine.files import MemoryFileIn, MemoryFileStore
from eaasp_l2_memory_engine.index import HybridIndex

pytestmark = pytest.mark.asyncio


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _remove_hnsw_dir(octo_root: str) -> None:
    """Remove the l2-memory HNSW directory so HNSW loads as empty."""
    hnsw_root = os.path.join(octo_root, "l2-memory")
    if os.path.isdir(hnsw_root):
        shutil.rmtree(hnsw_root)


# ────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────


async def test_fts_only_hit_gets_semantic_backfill(db_path: str, tmp_path) -> None:
    """FTS-only hit with embedding_vec in DB gets real semantic_score > 0.

    We write a memory (which stores both DB row + HNSW vector), then
    delete the HNSW directory so the next search has an empty HNSW.
    The memory appears in FTS but not HNSW — the backfill should compute
    cosine similarity from the DB ``embedding_vec`` blob.
    """
    # Use the same content for write and search so the query embedding
    # and stored embedding are from the same text → cosine near 1.0.
    content = "unique semantic backfill test phrase"
    store = MemoryFileStore(db_path)
    mem = await store.write(
        MemoryFileIn(
            memory_id="backfill-test-mem",
            scope="test",
            category="backfill",
            content=content,
        )
    )
    # Verify the write worked (embedding stored in DB even if not surfaced in output).
    assert mem.memory_id == "backfill-test-mem"

    # Delete HNSW so the next search has empty semantic index.
    octo_root = os.path.dirname(os.path.abspath(db_path))
    _remove_hnsw_dir(octo_root)

    # Now search with the SAME text — FTS will find it, HNSW is empty.
    # Since the query text matches the stored text, MockEmbedding produces
    # identical vectors → cosine similarity ≈ 1.0.
    index = HybridIndex(db_path, octo_root=octo_root)
    hits = await index.search(content)

    assert len(hits) == 1, f"Expected 1 FTS hit, got {len(hits)}"
    hit = hits[0]
    assert hit.memory.memory_id == mem.memory_id

    # D95: the FTS-only hit should have a non-zero semantic_score
    # computed from the DB embedding_vec via cosine similarity.
    assert hit.semantic_score > 0.0, (
        f"Expected semantic_score > 0.0 for FTS-only hit with DB embedding_vec, "
        f"got {hit.semantic_score}. D95 backfill may not be working."
    )

    # Cosine similarity of a vector with itself is ~1.0 (semantic).
    # Since the query embedding and the stored embedding are both from
    # MockEmbedding with the same text, the cosine should be close to 1.0.
    assert hit.semantic_score > 0.9, (
        f"Expected near-1.0 cosine for identical text, got {hit.semantic_score}"
    )


async def test_fts_only_hit_null_embedding_vec_graceful(db_path: str, tmp_path) -> None:
    """FTS-only hit with NULL embedding_vec → semantic_score = 0.0.

    Legacy rows without embedding vectors should not crash the backfill.
    """
    # Insert a row directly without embedding columns (simulating pre-migration).
    from eaasp_l2_memory_engine.db import get_shared_connection

    db = await get_shared_connection(db_path)
    import json
    import time

    now = int(time.time() * 1000)
    await db.execute(
        """
        INSERT INTO memory_files (
            memory_id, version, scope, category, content, evidence_refs,
            status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "legacy-mem",
            1,
            "legacy",
            "c",
            "legacy content without embedding",
            json.dumps([]),
            "agent_suggested",
            now,
            now,
        ),
    )
    await db.execute(
        """INSERT INTO memory_fts (memory_id, version, content_text, category, scope)
           VALUES (?, ?, ?, ?, ?)""",
        ("legacy-mem", 1, "legacy content without embedding", "c", "legacy"),
    )
    await db.commit()

    # Search should find the legacy row via FTS.
    octo_root = os.path.dirname(os.path.abspath(db_path))
    _remove_hnsw_dir(octo_root)

    index = HybridIndex(db_path, octo_root=octo_root)
    hits = await index.search("legacy content")

    assert len(hits) >= 1
    for hit in hits:
        if hit.memory.memory_id == "legacy-mem":
            assert hit.semantic_score == 0.0, "NULL embedding_vec should yield semantic_score=0.0"


async def test_hnsw_hits_preserved_over_backfill(db_path: str, tmp_path) -> None:
    """HNSW semantic scores take precedence — backfill does not override them.

    When a memory appears in BOTH FTS and HNSW, the HNSW cosine score
    is used, not the DB backfill value.
    """
    store = MemoryFileStore(db_path)

    # Write two memories to populate both DB and HNSW.
    mem1 = await store.write(
        MemoryFileIn(
            memory_id="hnsw-preserved-1",
            scope="test",
            category="hnsw",
            content="apple banana cherry",
        )
    )
    mem2 = await store.write(
        MemoryFileIn(
            memory_id="hnsw-preserved-2",
            scope="test",
            category="hnsw",
            content="delta epsilon zeta",
        )
    )

    # Keep the HNSW directory intact — both FTS and HNSW should work.
    index = HybridIndex(db_path)
    hits = await index.search("apple banana")

    assert len(hits) >= 1
    for hit in hits:
        if hit.memory.memory_id == mem1.memory_id:
            # The HNSW hit should have a semantic_score from HNSW,
            # not 0.0 and not a separately-computed backfill value.
            assert hit.semantic_score > 0.0, (
                f"HNSW hit should have semantic_score > 0, got {hit.semantic_score}"
            )
            break
    else:
        pytest.fail(f"Expected to find {mem1.memory_id} in search results")


async def test_keyword_only_mode_no_crash(db_path: str, tmp_path) -> None:
    """Keyword-only mode (no query_embedding) — no crash, semantic_score = 0.0.

    When embedding fails, search degrades to keyword-only. The backfill
    path should not execute (no query_embedding to compare against).
    """
    # Force embedding to fail by using an invalid provider.
    import os as _os

    old_provider = _os.environ.get("EAASP_EMBEDDING_PROVIDER")
    _os.environ["EAASP_EMBEDDING_PROVIDER"] = "ollama"
    old_url = _os.environ.get("EAASP_OLLAMA_URL")
    _os.environ["EAASP_OLLAMA_URL"] = "http://127.0.0.1:19999"  # invalid port

    try:
        # Reset the provider singleton to pick up new env.
        from eaasp_l2_memory_engine.embedding.provider import (
            reset_embedding_provider,
            set_embedding_client,
        )

        reset_embedding_provider()
        set_embedding_client(None)  # no shared client either

        store = MemoryFileStore(db_path)
        await store.write(
            MemoryFileIn(
                memory_id="kw-only-mem",
                scope="test",
                category="kw",
                content="keyword only search test",
            )
        )

        octo_root = os.path.dirname(os.path.abspath(db_path))
        _remove_hnsw_dir(octo_root)
        index = HybridIndex(db_path, octo_root=octo_root)
        hits = await index.search("keyword only")

        # The embedding provider will fail (connection refused to invalid host),
        # so keyword_only=True. The backfill path is skipped — no crash.
        assert len(hits) >= 1
        for hit in hits:
            if hit.memory.memory_id == "kw-only-mem":
                assert hit.semantic_score == 0.0, "keyword-only mode should have semantic_score=0.0"
    finally:
        if old_provider is None:
            _os.environ.pop("EAASP_EMBEDDING_PROVIDER", None)
        else:
            _os.environ["EAASP_EMBEDDING_PROVIDER"] = old_provider
        if old_url is None:
            _os.environ.pop("EAASP_OLLAMA_URL", None)
        else:
            _os.environ["EAASP_OLLAMA_URL"] = old_url
        from eaasp_l2_memory_engine.embedding.provider import reset_embedding_provider

        reset_embedding_provider()
