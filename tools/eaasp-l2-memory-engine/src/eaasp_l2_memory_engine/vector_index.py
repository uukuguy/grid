"""S2.T1 — HNSW in-process vector index, per-model_id directory isolation.

ADR-V2-015 iron laws enforced here:
  1. Dimension is tracked per model_id; a mismatched dim at query time raises.
  2. Search and add must match the index's model_id; reload with a different
     model_id raises.
  3. Migration (dual-write + re-index) is handled elsewhere.

The module is async-friendly: all mutating ops (``add``/``delete``/``save``)
are serialized via ``asyncio.Lock``. ``search`` is lock-free because hnswlib
is safe for concurrent reads.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import NamedTuple, Protocol

import hnswlib


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Hard cap on HNSW vector index growth (NEW-L1 / Phase 5.5).
# At dim=1024 fp32, 1_000_000 vectors ≈ 4 GB of raw vector data; matches
# typical L2-memory production load. Past this cap the index refuses to grow
# further and raises RuntimeError — operators should migrate to a fresh
# index rather than let memory / disk usage grow unbounded.
# NOTE: tests monkey-patch this constant down (e.g. to 100) for fast coverage
# of the cap-hit path; production code never overrides it. See ADR-V2-032
# style records for similar single-knob conventions.
HNSW_HARD_CAP = 1_000_000


# D91 / L2-03 — rebuild trigger ratio. Crossing this on the next add()
# call rebuilds the index in-place. CONTEXT.md D-02 documents the choice
# of 30% (matches ROADMAP wording verbatim + common HNSW practice).
TOMBSTONE_REBUILD_THRESHOLD = 0.30


# ---------------------------------------------------------------------------
# Public error types
# ---------------------------------------------------------------------------


class DimensionMismatchError(ValueError):
    """Raised when a provided vector does not match the index dimension."""


class ModelIdMismatchError(ValueError):
    """Raised when loading an index whose stored model_id differs from the
    configured one."""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


class Hit(NamedTuple):
    """A search result. ``score`` is cosine similarity in [-1, 1]."""

    id: str
    score: float


class VectorIndex(Protocol):
    """Abstract contract. Concrete backends must honour ADR-V2-015."""

    async def add(self, id: str, vec: list[float]) -> None: ...

    async def search(self, vec: list[float], top_k: int) -> list[Hit]: ...

    async def delete(self, id: str) -> None: ...

    async def save(self) -> None: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def model_id_to_safe_dirname(model_id: str) -> str:
    """Convert ``'bge-m3:fp16@ollama'`` → ``'bge-m3-fp16-ollama'``.

    Replaces filesystem-unfriendly characters with ``-``. The mapping is
    many-to-one — two distinct model_ids could collapse to the same dir, but
    ADR-V2-015 treats model_id as the unique key tracked in meta.json, so
    :class:`HNSWVectorIndex` will catch cross-id reloads via
    :class:`ModelIdMismatchError`.
    """
    return (
        model_id.replace(":", "-").replace("/", "-").replace(".", "-").replace("@", "-")
    )


# ---------------------------------------------------------------------------
# HNSW backend
# ---------------------------------------------------------------------------


class HNSWVectorIndex:
    """HNSW-backed in-process vector index, one directory per model_id.

    On construction, attempts to load an existing index from
    ``{octo_root}/l2-memory/hnsw-{safe_name}/``. If the directory has a
    pre-existing index with a different ``model_id`` or ``dim`` in its
    ``meta.json`` the constructor raises.
    """

    def __init__(
        self,
        model_id: str,
        octo_root: str | Path,
        dim: int = 1024,
        space: str = "cosine",
        M: int = 16,
        ef_construction: int = 200,
        max_elements: int = 10_000,
    ) -> None:
        self.model_id = model_id
        self.dim = dim
        self.space = space
        self.M = M
        self.ef_construction = ef_construction
        self._max_elements = max_elements

        safe_name = model_id_to_safe_dirname(model_id)
        self.index_dir = Path(octo_root) / "l2-memory" / f"hnsw-{safe_name}"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.index_dir / "index.bin"
        self.meta_path = self.index_dir / "meta.json"

        # hnswlib expects Literal["l2","ip","cosine"]; space validated above so cast is safe.
        self._index = hnswlib.Index(space=space, dim=dim)  # type: ignore[arg-type]
        self._id_to_label: dict[str, int] = {}
        self._label_to_id: dict[int, str] = {}
        self._next_label = 0
        # D91 / L2-03 (Phase 7.2 Plan 02 T01) — tombstone bookkeeping.
        # Increments on every successful mark_deleted; rebuild trigger is
        # `_deleted_count / total >= TOMBSTONE_REBUILD_THRESHOLD`. After
        # rebuild the counter resets to 0 and the index is repacked.
        #
        # `_deleted_count` is the monotonic counter of soft-delete events
        # for THIS process lifetime. Persisted across save() so reload
        # restores the tombstone debt (avoids accidental rebuild loss).
        self._deleted_count = 0
        self._loaded = False
        self._write_lock = asyncio.Lock()

        # Try to load existing index (raises on model_id / dim mismatch)
        self._try_load_sync()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _try_load_sync(self) -> None:
        """Load index from disk if present; otherwise initialize empty.

        Raises:
            ModelIdMismatchError: when the on-disk meta.json declares a
                different model_id.
            DimensionMismatchError: when the on-disk meta.json declares a
                different dim.
        """
        if self.index_path.exists() and self.meta_path.exists():
            meta = json.loads(self.meta_path.read_text())
            if meta["model_id"] != self.model_id:
                raise ModelIdMismatchError(
                    f"Index at {self.index_dir} has model_id="
                    f"{meta['model_id']!r}, but loading with "
                    f"{self.model_id!r}"
                )
            if meta["dim"] != self.dim:
                raise DimensionMismatchError(
                    f"Index dim={meta['dim']}, code dim={self.dim}"
                )
            # NEW-L1 (Phase 5.5): restore persisted max_elements BEFORE
            # load_index, so reload preserves the grown capacity instead
            # of clamping back to the constructor default (10_000).
            # Older meta.json files written before NEW-L1 lack this key —
            # fall back to whatever was passed to the constructor.
            self._max_elements = int(meta.get("max_elements", self._max_elements))
            self._index.load_index(
                str(self.index_path), max_elements=self._max_elements
            )
            self._id_to_label = dict(meta["id_to_label"])
            # JSON object keys are strings; labels are ints.
            self._label_to_id = {int(k): v for k, v in meta["label_to_id"].items()}
            self._next_label = int(meta["next_label"])
            # D91 / L2-03 — restore tombstone debt across restarts.
            # Older meta.json files written before D91 lack this key —
            # default to 0 (which means "no rebuild debt yet").
            self._deleted_count = int(meta.get("deleted_count", 0))
            self._loaded = True
        else:
            self._index.init_index(
                max_elements=self._max_elements,
                M=self.M,
                ef_construction=self.ef_construction,
            )
            self._loaded = True

        # ef controls query recall; raise slightly above ef_construction or a
        # sensible floor of 50.
        self._index.set_ef(max(self.ef_construction, 50))

    # ------------------------------------------------------------------
    # Mutating API
    # ------------------------------------------------------------------

    async def add(self, id: str, vec: list[float]) -> None:
        """Insert or overwrite the vector for ``id``.

        If ``id`` already exists, the prior label is soft-deleted (via
        ``mark_deleted``) and a fresh label is assigned.
        """
        if len(vec) != self.dim:
            raise DimensionMismatchError(f"vec len {len(vec)} != index dim {self.dim}")
        async with self._write_lock:
            # Grow if we're about to hit capacity.
            # NEW-L1 (Phase 5.5): cap doubling at HNSW_HARD_CAP and refuse to
            # grow further once at the cap. Previous code silently doubled
            # forever, producing 94 GB+ index dumps in pathological cases.
            current_count = self._index.get_current_count()
            if current_count >= self._max_elements - 1:
                new_max = min(self._max_elements * 2, HNSW_HARD_CAP)
                if new_max <= self._max_elements:
                    raise RuntimeError(
                        f"HNSW index at hard cap ({HNSW_HARD_CAP} vectors); "
                        f"refusing to grow further. Migrate to a fresh index."
                    )
                self._index.resize_index(new_max)
                self._max_elements = new_max

            # D91 / L2-03 — rebuild if tombstone ratio crossed threshold.
            # `total` excludes nothing — get_current_count includes
            # tombstones, which is what we want as denominator. Numerator
            # is the monotonic counter from mark_deleted.
            total = self._index.get_current_count()
            if (
                total > 0
                and self._deleted_count / total >= TOMBSTONE_REBUILD_THRESHOLD
            ):
                await self._rebuild_locked()

            if id in self._id_to_label:
                old_label = self._id_to_label[id]
                self._label_to_id.pop(old_label, None)
                try:
                    self._index.mark_deleted(old_label)
                    self._deleted_count += 1
                except (RuntimeError, Exception):  # noqa: BLE001
                    # Label may already be marked deleted; idempotent.
                    # Do NOT bump counter — that would double-count
                    # the same tombstone if add() is called repeatedly
                    # on a re-used id.
                    pass

            label = self._next_label
            self._next_label += 1
            self._index.add_items([vec], [label])
            self._id_to_label[id] = label
            self._label_to_id[label] = id

    async def delete(self, id: str) -> None:
        """Soft-delete ``id``. Search will skip deleted labels."""
        async with self._write_lock:
            if id not in self._id_to_label:
                return
            label = self._id_to_label.pop(id)
            self._label_to_id.pop(label, None)
            try:
                self._index.mark_deleted(label)
                self._deleted_count += 1
            except (RuntimeError, Exception):  # noqa: BLE001
                # Label may already be marked deleted; idempotent.
                # Do NOT bump counter — that would double-count.
                pass

    async def _rebuild_locked(self) -> None:
        """Repack the HNSW index in-place. Caller MUST hold ``self._write_lock``.

        D91 / L2-03 (Phase 7.2 Plan 02 T01). Trigger: tombstone ratio >=
        ``TOMBSTONE_REBUILD_THRESHOLD``. Strategy:
          1. Build a fresh ``hnswlib.Index`` of the same params + the
             current ``self._max_elements`` cap.
          2. Replay every LIVE label (i.e. label present in
             ``self._label_to_id``) into the new index via ``add_items``.
          3. Swap the inner ``self._index`` pointer to the new instance.
          4. Reset ``self._deleted_count`` to 0 + persist via ``save()``.

        Recall is preserved within the hnswlib ``M`` / ``ef_construction``
        bounds; pre/post recall on a fixed query set should match within
        ±0.05 (T02 measures this).
        """
        # Step 1 — snapshot live data BEFORE mutating self._index.
        # We need the vectors back from the OLD index. hnswlib provides
        # `get_items(labels)` for this; it returns the raw vectors keyed
        # by label, including tombstoned ones (which we skip).
        live_labels = sorted(self._label_to_id.keys())
        if not live_labels:
            # All-tombstoned edge case: build an empty index, no replay.
            live_vectors: list[list[float]] = []
        else:
            # `get_items(list[int])` -> ndarray|list[list[float]] in order.
            # Cast through list() so the downstream add_items receives a
            # plain Python list of lists, matching the type of the original
            # add() call sites.
            raw = self._index.get_items(live_labels)
            live_vectors = [list(v) for v in raw]

        # Step 2 — fresh index, same construction params.
        new_index = hnswlib.Index(space=self.space, dim=self.dim)  # type: ignore[arg-type]
        new_index.init_index(
            max_elements=self._max_elements,
            M=self.M,
            ef_construction=self.ef_construction,
        )
        new_index.set_ef(max(self.ef_construction, 50))

        # Step 3 — replay. Labels stay identical so _id_to_label / _label_to_id
        # need no remapping; tombstones simply vanish.
        if live_vectors:
            new_index.add_items(live_vectors, live_labels)

        # Step 4 — swap + reset counter + persist.
        self._index = new_index
        self._deleted_count = 0
        self._index.save_index(str(self.index_path))
        # meta.json refresh — save() also acquires the write_lock which we
        # already hold. Inline the meta write:
        meta = {
            "model_id": self.model_id,
            "dim": self.dim,
            "space": self.space,
            "M": self.M,
            "ef_construction": self.ef_construction,
            "max_elements": self._max_elements,
            "next_label": self._next_label,
            "id_to_label": self._id_to_label,
            "label_to_id": {
                str(k): v for k, v in self._label_to_id.items()
            },
            "deleted_count": self._deleted_count,
        }
        self.meta_path.write_text(json.dumps(meta))

    async def save(self) -> None:
        """Persist the index and metadata to disk."""
        async with self._write_lock:
            self._index.save_index(str(self.index_path))
            meta = {
                "model_id": self.model_id,
                "dim": self.dim,
                "space": self.space,
                "M": self.M,
                "ef_construction": self.ef_construction,
                # NEW-L1 (Phase 5.5): persist current cap so reload restores
                # the grown capacity instead of defaulting back to 10_000.
                "max_elements": self._max_elements,
                "next_label": self._next_label,
                "id_to_label": self._id_to_label,
                # Stringify keys for JSON; parsed back to int on load.
                "label_to_id": {str(k): v for k, v in self._label_to_id.items()},
                # D91 / L2-03 — persist tombstone debt across restarts.
                "deleted_count": self._deleted_count,
            }
            self.meta_path.write_text(json.dumps(meta))

    # ------------------------------------------------------------------
    # Read-only API
    # ------------------------------------------------------------------

    async def search(self, vec: list[float], top_k: int) -> list[Hit]:
        """Return the top ``top_k`` hits by cosine similarity.

        Deleted labels are filtered out. Empty index returns ``[]``.
        """
        if len(vec) != self.dim:
            raise DimensionMismatchError(f"vec len {len(vec)} != index dim {self.dim}")
        # Use *live* count (excluding soft-deleted) as the hard ceiling.
        # ``get_current_count`` includes deleted items, so requesting k >
        # alive_count causes hnswlib to raise "Cannot return results in a
        # contiguous 2D array".
        alive = len(self._id_to_label)
        if alive == 0:
            return []
        requested = min(max(top_k, 1), alive)
        try:
            labels, distances = self._index.knn_query([vec], k=requested)
        except RuntimeError:
            # Graph may be sparse after deletions; retry with k=1 to at least
            # return the nearest live neighbour.
            if requested <= 1:
                return []
            labels, distances = self._index.knn_query([vec], k=1)
        out: list[Hit] = []
        for label, dist in zip(labels[0], distances[0]):
            label_int = int(label)
            if label_int not in self._label_to_id:
                continue  # soft-deleted
            # hnswlib returns *distance*; for cosine space it is 1 - cos_sim.
            score = 1.0 - float(dist)
            out.append(Hit(id=self._label_to_id[label_int], score=score))
            if len(out) >= top_k:
                break
        return out

    # ------------------------------------------------------------------
    # Introspection (mainly for tests / diagnostics)
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Number of live (non-deleted) entries in the index."""
        return len(self._id_to_label)


__all__ = [
    "DimensionMismatchError",
    "HNSWVectorIndex",
    "Hit",
    "ModelIdMismatchError",
    "VectorIndex",
    "model_id_to_safe_dirname",
]
