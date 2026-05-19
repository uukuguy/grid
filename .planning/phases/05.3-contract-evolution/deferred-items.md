# Phase 5.3 deferred-items (out-of-scope discoveries during execution)

> Logged per execute-plan workflow scope-boundary rule: only auto-fix
> issues directly caused by current task's changes; everything else
> goes here for orchestrator triage.

## Pre-existing issues observed (NOT caused by 05.3-01)

### grid-cli lib references missing `output` module
- **Discovered:** Task 5.3-01-05 verification (`cargo check --workspace`)
- **Symptom:** `error[E0583]: file not found for module \`output\`` at
  `crates/grid-cli/src/lib.rs:20`
- **Pre-existing:** Confirmed via `git stash` test 2026-05-20 — the
  error reproduces against the worktree base commit
  `c0af57a653cae9713d3d7d3c3b810ab25d3ab0ab` without any 05.3-01
  edits applied.
- **Scope:** Unrelated to CONTRACT-01/02; appears to be a
  feature-flag mismatch (perhaps `output.rs` lives behind `--features
  studio` only and the top-level mod declaration didn't get gated).
- **Action:** Logged for follow-up phase (e.g., 5.4 infra hardening
  cluster), not fixed here.

### L2 HNSW mock index 94GB disk leak (mock-bge-m3:fp16 over-allocation)

- **Discovered:** 2026-05-20 during user-initiated disk audit (out-of-band, not from any 5.3 task)
- **Path:** `data/l2-memory/hnsw-mock-bge-m3-fp16/index.bin`
- **Symptom:** Actual disk usage 94 GB (100,499,169,280 bytes) for an index containing only 1,008 vectors.
  Naive expected size: ~4 MB (1008 × 1024-dim × 4 bytes fp32). **Bloat ratio: ~24,341×**.
- **Created:** 2026-04-15 22:11 (Phase 2.5 era)
- **Last written:** 2026-04-18 01:08 (Phase 3 contract test runs)
- **Not pre-committed:** `data/` is gitignored (`.gitignore:31`) — never in version control.

- **Root cause (code-level):** `tools/eaasp-l2-memory-engine/src/eaasp_l2_memory_engine/vector_index.py:189-192`
  doubles `max_elements` whenever `current_count >= max_elements - 1`:
  ```python
  if current_count >= self._max_elements - 1:
      new_max = self._max_elements * 2
      self._index.resize_index(new_max)
      self._max_elements = new_max
  ```
  Combined with `meta.json` not persisting `max_elements`, every restart loads the on-disk index but
  re-initializes `self._max_elements` from the ctor default (10,000). hnswlib's `load_index()` does NOT
  shrink the underlying allocation; subsequent add()s near the (in-memory) 10k threshold trigger
  another doubling → on-disk capacity ratchets up across restarts. Reverse-engineered from file size:
  the index now holds ~23.7M pre-allocated slots, of which 1,008 (0.004%) are used.

- **hnswlib behavior:** `save_index()` dumps the entire pre-allocated arena (all slots, used or not)
  to disk, not just live vectors. So the 94 GB is real, not sparse.

- **Action plan (P2, mapped to Phase 5.4 SERVER hardening or next-milestone L2 memory cleanup):**
  1. **Persist `max_elements` in `meta.json`** so reloads see the actual capacity, not the ctor default.
  2. **Cap doubling at a sane ceiling** (e.g., 1M) and require explicit operator action beyond that
     — same fail-fast principle as NEW-F3 (no silent unbounded growth).
  3. **Add a `compact()` method** that re-creates the index at `next_label * 1.5` size when the
     used/allocated ratio drops below a threshold (e.g., 5%).
  4. ~~**Operator-side cleanup:** Once Wave 2 of Phase 5.3 completes...~~
     ✅ **DONE 2026-05-20** — user deleted `data/l2-memory/hnsw-mock-bge-m3-fp16/` mid-Wave-2.
     94 GB reclaimed; Wave 2 unaffected (worktree-isolated; no path overlap).
     Phase 5.4+ test fixtures will rebuild as needed.

- **Verification before delete:**
  ```bash
  grep -rn "hnsw-mock-bge-m3-fp16" tools/eaasp-l2-memory-engine/src/ 2>/dev/null | head -5
  ```
  Expect: no hits (path is data-store, not referenced from production code).

- **DEFERRED_LEDGER entry:** To be added as `NEW-L1` (L for "L2-memory") under Phase 5.4 watchlist after
  Phase 5.3 ships. Format mirrors NEW-F1..F4 entries already in LEDGER.
