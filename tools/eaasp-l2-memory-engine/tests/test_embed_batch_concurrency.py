"""embed_batch concurrency tests (D93 / L2-04 / Phase 7.2 Plan 02 T04).

Two coverage gates per CONTEXT.md D-03 + ROADMAP success criterion #3:
  1. batch=10 wall-clock <= 30% of sequential (true concurrency evidence).
  2. Concurrent in-flight count never exceeds the semaphore bound.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from eaasp_l2_memory_engine.embedding.provider import (
    EMBED_BATCH_CONCURRENCY_OLLAMA_DEFAULT,
    OllamaEmbedding,
)


class _SleepEmbedding(OllamaEmbedding):
    """Test-only provider: sleeps ``delay_s`` per embed call.

    Inherits embed_batch from OllamaEmbedding so we test the EXACT
    asyncio.gather + semaphore path that ships in prod, not a copy.

    Also instruments concurrent in-flight count for the rate-limit test.
    """

    def __init__(self, delay_s: float = 0.05, concurrency: int | None = None) -> None:
        # Skip OllamaEmbedding's network setup; we only need
        # _concurrency_limit + _dim.
        self.model = "sleep-test"
        self.ollama_url = "http://unused"
        self._dim = 8
        self._concurrency_limit = (
            concurrency
            if concurrency is not None
            else EMBED_BATCH_CONCURRENCY_OLLAMA_DEFAULT
        )
        self._delay_s = delay_s
        self._in_flight = 0
        self._max_in_flight = 0
        self._lock = asyncio.Lock()

    async def embed(self, text: str) -> list[float]:  # type: ignore[override]
        async with self._lock:
            self._in_flight += 1
            if self._in_flight > self._max_in_flight:
                self._max_in_flight = self._in_flight
        try:
            await asyncio.sleep(self._delay_s)
            return [0.0] * self._dim
        finally:
            async with self._lock:
                self._in_flight -= 1


@pytest.mark.asyncio
async def test_batch_ten_under_thirty_percent_of_sequential() -> None:
    """batch=10 via embed_batch is <= 30% of sequential wall-clock."""
    delay = 0.05  # 50ms per embed
    provider = _SleepEmbedding(delay_s=delay, concurrency=10)
    texts = [f"text-{i}" for i in range(10)]

    # Sequential baseline.
    t0 = time.perf_counter()
    for t in texts:
        await provider.embed(t)
    seq_wall = time.perf_counter() - t0

    # Concurrent via embed_batch.
    provider2 = _SleepEmbedding(delay_s=delay, concurrency=10)
    t0 = time.perf_counter()
    await provider2.embed_batch(texts)
    conc_wall = time.perf_counter() - t0

    ratio = conc_wall / seq_wall
    assert ratio <= 0.30, (
        f"Concurrent / sequential = {ratio:.2%} "
        f"(conc {conc_wall:.3f}s vs seq {seq_wall:.3f}s); "
        f"expected <= 30% per CONTEXT.md D-03"
    )
    # Surface ratio for LEDGER capture.
    print(
        f"\n[D93 embed_batch] concurrent/sequential = {ratio:.2%} "
        f"(conc {conc_wall * 1000:.0f}ms vs seq {seq_wall * 1000:.0f}ms; "
        f"batch=10, delay=50ms)"
    )


@pytest.mark.asyncio
async def test_semaphore_bound_honored() -> None:
    """50 concurrent embed_batch entries respect concurrency=5 cap."""
    bound = 5
    provider = _SleepEmbedding(delay_s=0.02, concurrency=bound)
    texts = [f"rl-{i}" for i in range(50)]

    await provider.embed_batch(texts)

    assert provider._max_in_flight <= bound, (
        f"Max in-flight {provider._max_in_flight} exceeded "
        f"semaphore bound {bound}"
    )
    # Sanity: with 50 texts and bound=5, the maximum SHOULD reach 5
    # (otherwise the test isn't actually exercising the semaphore).
    assert provider._max_in_flight == bound, (
        f"Expected max in-flight to saturate at {bound}, got "
        f"{provider._max_in_flight} — semaphore not actually bounded?"
    )
