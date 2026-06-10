"""Embedding provider abstractions for L2 Memory Engine.

Supports:
- MockEmbedding: deterministic hash-based, for tests (default).
- OllamaEmbedding: POSTs to local Ollama (dev), bge-m3:fp16 @ 1024 dims.

Configuration via environment variables:
- EAASP_EMBEDDING_PROVIDER: "mock" (default) | "ollama"
- EAASP_EMBEDDING_MODEL: model name (defaults vary by provider)
- EAASP_OLLAMA_URL: Ollama base URL (default "http://localhost:11434")

Note on Ollama/macOS proxy: httpx.AsyncClient uses `trust_env=False` to bypass
system proxies (e.g. Clash) which otherwise turn 127.0.0.1 calls into 502. See
MEMORY.md "Ollama 已知问题" for precedent in reqwest / grid-engine OpenAIProvider.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import os
import random
from typing import Protocol

import httpx


# D93 / L2-04 (Phase 7.2 Plan 02 T03) — per-provider concurrency caps
# for embed_batch. Mock has no real I/O so 100 is effectively no limit;
# Ollama-local typically saturates at 5 concurrent embed requests
# (see CONTEXT.md D-03). The L2_EMBED_BATCH_CONCURRENCY env var, if set,
# overrides BOTH per-provider defaults globally for tuning / tests.
#
# Strict-by-default per ADR-V2-028: malformed env value raises
# ValueError, no silent fallback.
EMBED_BATCH_CONCURRENCY_MOCK_DEFAULT = 100
EMBED_BATCH_CONCURRENCY_OLLAMA_DEFAULT = 5


def _load_embed_batch_concurrency_override() -> int | None:
    raw = os.environ.get("L2_EMBED_BATCH_CONCURRENCY")
    if raw is None:
        return None
    try:
        parsed = int(raw)
    except ValueError as e:
        raise ValueError(
            f"L2_EMBED_BATCH_CONCURRENCY={raw!r} is not an integer "
            f"(strict-by-default per ADR-V2-028)"
        ) from e
    if parsed < 1:
        raise ValueError(f"L2_EMBED_BATCH_CONCURRENCY={parsed} must be >= 1")
    return parsed


_EMBED_BATCH_CONCURRENCY_OVERRIDE = _load_embed_batch_concurrency_override()

# bge-m3 family embedding dimension (fixed).
BGE_M3_DIMENSION = 1024


class EmbeddingProvider(Protocol):
    """Interface for embedding providers (dev/test/prod)."""

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch (may be sequential for simple providers)."""
        ...

    @property
    def dimension(self) -> int:
        """Embedding dimension (e.g., 1024 for bge-m3:fp16)."""
        ...

    @property
    def model_id(self) -> str:
        """Model identifier (e.g., 'bge-m3:fp16@ollama')."""
        ...


class OllamaEmbedding:
    """Ollama embedding provider (dev environment).

    POSTs to {ollama_url}/api/embeddings with body {"model": ..., "prompt": text},
    reads response["embedding"] as list[float].
    """

    def __init__(
        self,
        model: str = "bge-m3:fp16",
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        # Fixed for bge-m3 family. Extend if adding other models.
        self._dim = BGE_M3_DIMENSION
        # D93 / L2-04 — per-provider concurrency cap, overridable via env.
        self._concurrency_limit = (
            _EMBED_BATCH_CONCURRENCY_OVERRIDE
            if _EMBED_BATCH_CONCURRENCY_OVERRIDE is not None
            else EMBED_BATCH_CONCURRENCY_OLLAMA_DEFAULT
        )

    async def embed(self, text: str) -> list[float]:
        # trust_env=False: bypass macOS proxy (Clash/etc) which breaks localhost.
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            resp = await client.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # D93 / L2-04 — asyncio.gather + per-provider semaphore.
        sem = asyncio.Semaphore(self._concurrency_limit)

        async def _one(t: str) -> list[float]:
            async with sem:
                return await self.embed(t)

        return await asyncio.gather(*(_one(t) for t in texts))

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_id(self) -> str:
        return f"{self.model}@ollama"


class MockEmbedding:
    """Deterministic mock embedding for tests.

    Uses SHA-256(text) as the seed for a PRNG that generates `dimension` gaussian
    samples, then L2-normalizes to unit length. Output values are in [-1, 1]
    (signed), suitable for cosine similarity.
    """

    def __init__(self, model: str = "mock-bge-m3:fp16") -> None:
        self.model = model
        self._dim = BGE_M3_DIMENSION
        # D93 / L2-04 — per-provider concurrency cap, overridable via env.
        self._concurrency_limit = (
            _EMBED_BATCH_CONCURRENCY_OVERRIDE
            if _EMBED_BATCH_CONCURRENCY_OVERRIDE is not None
            else EMBED_BATCH_CONCURRENCY_MOCK_DEFAULT
        )

    async def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest, "little", signed=False)
        rng = random.Random(seed)
        samples = [rng.gauss(0.0, 1.0) for _ in range(self._dim)]
        norm = math.sqrt(sum(v * v for v in samples))
        if norm == 0.0:
            # Degenerate; return uniform non-zero vector normalized.
            return [1.0 / math.sqrt(self._dim)] * self._dim
        return [v / norm for v in samples]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # D93 / L2-04 — asyncio.gather + per-provider semaphore.
        # Mock has no real I/O; the semaphore exists only so the
        # rate-limit-respect test can verify the bounding mechanism
        # works (same code path as Ollama).
        sem = asyncio.Semaphore(self._concurrency_limit)

        async def _one(t: str) -> list[float]:
            async with sem:
                return await self.embed(t)

        return await asyncio.gather(*(_one(t) for t in texts))

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def model_id(self) -> str:
        return self.model


# Module-level singleton (reset via reset_embedding_provider() in tests).
_PROVIDER_INSTANCE: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Get or create singleton embedding provider from env config.

    Env:
        EAASP_EMBEDDING_PROVIDER: "mock" (default) | "ollama"
        EAASP_EMBEDDING_MODEL: model name (defaults to provider-specific)
        EAASP_OLLAMA_URL: Ollama base URL (default http://localhost:11434)
    """
    global _PROVIDER_INSTANCE
    if _PROVIDER_INSTANCE is not None:
        return _PROVIDER_INSTANCE

    provider_type = os.getenv("EAASP_EMBEDDING_PROVIDER", "mock").lower()

    if provider_type == "ollama":
        model = os.getenv("EAASP_EMBEDDING_MODEL", "bge-m3:fp16")
        ollama_url = os.getenv("EAASP_OLLAMA_URL", "http://localhost:11434")
        _PROVIDER_INSTANCE = OllamaEmbedding(model=model, ollama_url=ollama_url)
    else:
        model = os.getenv("EAASP_EMBEDDING_MODEL", "mock-bge-m3:fp16")
        _PROVIDER_INSTANCE = MockEmbedding(model=model)

    return _PROVIDER_INSTANCE


def reset_embedding_provider() -> None:
    """For tests: drop the singleton so env changes take effect on next get()."""
    global _PROVIDER_INSTANCE
    _PROVIDER_INSTANCE = None
